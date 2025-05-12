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
def fetch_due(task_gid):
    """Fetch a single task’s due_on date (or return 'TBD')."""
    resp = requests.get(
        f'{BASE_URL}/tasks/{task_gid}',
        headers=HEADERS,
        params={'opt_fields': 'due_on'}
    )
    if resp.ok:
        return resp.json().get('data', {}).get('due_on') or 'TBD'
    return 'TBD'

def get_section_gid(project_gid, section_name="Critical Milestones"):
    """Return the GID of the named section, or None."""
    resp = requests.get(
        f"{BASE_URL}/projects/{project_gid}/sections",
        headers=HEADERS
    )
    if not resp.ok:
        return None
    for sec in resp.json().get('data', []):
        if sec.get('name') == section_name:
            return sec['gid']
    return None

def fetch_latest_comment(project_gid):
    """Grab the most recent comment_added across all tasks in the project."""
    resp = requests.get(
        f"{BASE_URL}/projects/{project_gid}/tasks",
        headers=HEADERS,
        params={"opt_fields": "gid"}
    )
    if not resp.ok:
        return '–'
    comments = []
    for t in resp.json().get('data', []):
        gid = t['gid']
        stories = requests.get(
            f"{BASE_URL}/tasks/{gid}/stories",
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
    name = proj.get('name', '')
    pid  = proj.get('gid', '')

    # skip drafts
    if "WORKING DRAFT" in name.upper():
        continue

    # find Critical Milestones section
    sec_gid = get_section_gid(pid)
    if not sec_gid:
        continue

    # pull tasks (compact) in that section
    sec_tasks_resp = requests.get(
        f"{BASE_URL}/sections/{sec_gid}/tasks",
        headers=HEADERS,
        params={"opt_fields": "gid,name,completed"}
    )
    if not sec_tasks_resp.ok:
        continue
    section_tasks = sec_tasks_resp.json().get('data', [])

    # skip if Launch milestone exists and is completed
    launch = next((t for t in section_tasks if t['name'] == "Launch"), None)
    if launch and launch.get('completed'):
        continue

    # format Launch with its real due date
    if launch:
        launch_date = fetch_due(launch['gid'])
        launch_str  = f"Launch – {launch_date}"
    else:
        launch_str  = '–'

    # find next incomplete milestone with a real date
    pending = [t for t in section_tasks if not t['completed']]
    dated = []
    for t in pending:
        due = fetch_due(t['gid'])
        if due not in (None, '', 'TBD'):
            dated.append({'name': t['name'], 'due_on': due})
    if dated:
        dated.sort(key=lambda x: datetime.fromisoformat(x['due_on']))
        nxt = dated[0]
        next_str = f"{nxt['name']} – {nxt['due_on']}"
    else:
        next_str = '–'

    # fetch most recent project‐level comment
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
