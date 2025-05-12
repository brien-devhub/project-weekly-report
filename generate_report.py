#!/usr/bin/env python3
import os
import sys
import requests
from datetime import datetime

# ─── CONFIG ──────────────────────────────────────────────────────────────────
PAT      = os.getenv('ASANA_PAT')
WS_GID   = os.getenv('ASANA_WORKSPACE_GID')
WEBHOOK  = os.getenv('SLACK_WEBHOOK_URL')
if not all([PAT, WS_GID, WEBHOOK]):
    sys.stderr.write('Error: Missing one of ASANA_PAT, ASANA_WORKSPACE_GID, or SLACK_WEBHOOK_URL\n')
    sys.exit(1)

HEADERS  = {'Authorization': f'Bearer {PAT}'}
BASE_URL = 'https://app.asana.com/api/1.0'

# ─── HELPERS ─────────────────────────────────────────────────────────────────
def get_section_gid(project_gid, section_name="Critical Milestones"):
    resp = requests.get(f"{BASE_URL}/projects/{project_gid}/sections", headers=HEADERS)
    if not resp.ok:
        return None
    for sec in resp.json().get('data', []):
        if sec.get('name') == section_name:
            return sec['gid']
    return None

def fetch_tasks_in_section(section_gid):
    resp = requests.get(
        f"{BASE_URL}/workspaces/{WS_GID}/tasks/search",
        headers=HEADERS,
        params={
            "sections.any": section_gid,
            "opt_fields":   "gid,name,due_on,completed"
        }
    )
    return resp.json().get('data', [])

def fetch_latest_comment(project_gid):
    resp = requests.get(
        f"{BASE_URL}/projects/{project_gid}/tasks",
        headers=HEADERS,
        params={"opt_fields": "gid"}
    )
    if not resp.ok:
        return '–'
    comments = []
    for t in resp.json().get('data', []):
        stories = requests.get(
            f"{BASE_URL}/tasks/{t['gid']}/stories",
            headers=HEADERS,
            params={"opt_fields": "resource_subtype,created_at,text"}
        ).json().get('data', [])
        for s in stories:
            if s.get('resource_subtype') == "comment_added" and s.get('text'):
                comments.append(s)
    if not comments:
        return '–'
    comments.sort(key=lambda s: s['created_at'], reverse=True)
    return comments[0]['text'].replace('\n', ' ')

# ─── MAIN ───────────────────────────────────────────────────────────────────
resp = requests.get(
    f"{BASE_URL}/workspaces/{WS_GID}/projects",
    headers=HEADERS,
    params={"archived": "false"}
)
if not resp.ok:
    sys.stderr.write(f"Error fetching projects: {resp.status_code} — {resp.text}\n")
    sys.exit(1)

projects = resp.json().get('data', [])
report   = []

for proj in projects:
    name = proj.get('name', '').strip()
    pid  = proj.get('gid', '')

    if "WORKING DRAFT" in name.upper():
        continue

    sec_gid = get_section_gid(pid)
    if not sec_gid:
        continue

    tasks = fetch_tasks_in_section(sec_gid)

    launch = next((t for t in tasks if t['name'].strip().lower() == "launch"), None)
    if launch and launch.get('completed'):
        continue

    # Now only include the date
    launch_str = launch.get('due_on', 'TBD') if launch else '–'

    pending = [t for t in tasks if not t.get('completed') and t.get('due_on')]
    if pending:
        pending.sort(key=lambda t: datetime.fromisoformat(t['due_on']))
        nxt = pending[0]
        next_str = f"{nxt['name']} – {nxt['due_on']}"
    else:
        next_str = '–'

    latest_comment = fetch_latest_comment(pid)

    report.append({
        "project": name,
        "next":    next_str,
        "launch":  launch_str,
        "comment": latest_comment
    })

# ─── POST TO SLACK ──────────────────────────────────────────────────────────
if not report:
    text = "No active projects with upcoming milestones."
else:
    lines = ["*Weekly Critical Milestones*"]
    for r in report:
        lines.append(
            f"• *{r['project']}*\n"
            f"    – Next:   {r['next']}\n"
            f"    – Launch: {r['launch']}\n"
            f"    – Latest comment: {r['comment']}"
        )
    text = "\n".join(lines)

slack_resp = requests.post(WEBHOOK, json={"text": text})
if not slack_resp.ok:
    sys.stderr.write(f"Slack post failed: {slack_resp.status_code} — {slack_resp.text}\n")
    sys.exit(1)
