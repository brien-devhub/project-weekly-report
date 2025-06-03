#!/usr/bin/env python3
import os
import sys
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# ─── CONFIG ──────────────────────────────────────────────────────────────────
PAT      = os.getenv('ASANA_PAT')
WS_GID   = os.getenv('ASANA_WORKSPACE_GID')
WEBHOOK  = os.getenv('SLACK_WEBHOOK_URL')
if not all([PAT, WS_GID, WEBHOOK]):
    sys.stderr.write('Error: Missing one of ASANA_PAT, ASANA_WORKSPACE_GID, or SLACK_WEBHOOK_URL\n')
    sys.exit(1)

BASE_URL = 'https://app.asana.com/api/1.0'
session  = requests.Session()
session.headers.update({'Authorization': f'Bearer {PAT}'})

# ─── HELPERS ─────────────────────────────────────────────────────────────────

def get_section_gid(project_gid, section_name="Critical Milestones"):
    resp = session.get(f"{BASE_URL}/projects/{project_gid}/sections")
    if not resp.ok:
        return None
    for sec in resp.json().get('data', []):
        if sec.get('name') == section_name:
            return sec['gid']
    return None

def fetch_tasks_in_section(section_gid):
    resp = session.get(
        f"{BASE_URL}/workspaces/{WS_GID}/tasks/search",
        params={
            "sections.any": section_gid,
            "opt_fields":   "gid,name,due_on,completed"
        }
    )
    return resp.json().get('data', [])

def fetch_latest_comments(project_gid, count=3):
    # get all task GIDs in the project
    resp = session.get(
        f"{BASE_URL}/projects/{project_gid}/tasks",
        params={"opt_fields": "gid"}
    )
    if not resp.ok:
        return []
    task_gids = [t['gid'] for t in resp.json().get('data', [])]

    comments = []
    # parallel fetch stories
    with ThreadPoolExecutor(max_workers=10) as exe:
        futures = [exe.submit(session.get,
                              f"{BASE_URL}/tasks/{gid}/stories",
                              params={"opt_fields": "resource_subtype,created_at,text"})
                   for gid in task_gids]
        for fut in as_completed(futures):
            res = fut.result()
            if not res.ok:
                continue
            for s in res.json().get('data', []):
                if s.get('resource_subtype') == "comment_added" and s.get('text'):
                    comments.append(s)
    if not comments:
        return []
    comments.sort(key=lambda s: s['created_at'], reverse=True)
    return [c['text'].replace('\n',' ') for c in comments[:count]]

# ─── MAIN ───────────────────────────────────────────────────────────────────
resp = session.get(
    f"{BASE_URL}/workspaces/{WS_GID}/projects",
    params={"archived": "false"}
)
if not resp.ok:
    sys.stderr.write(f"Error fetching projects: {resp.status_code} — {resp.text}\n")
    sys.exit(1)

report = []
for proj in resp.json().get('data', []):
    name = proj.get('name','').strip()
    pid  = proj.get('gid','')
    if "WORKING DRAFT" in name.upper():
        continue

    sec_gid = get_section_gid(pid)
    if not sec_gid:
        continue

    tasks = fetch_tasks_in_section(sec_gid)

    # skip if Launch is completed
    launch = next((t for t in tasks if t['name'].strip().lower()=="launch"), None)
    if launch and launch.get('completed'):
        continue

    # format Launch date only
    launch_str = (launch.get('due_on') or 'TBD') if launch else '–'

    # find next incomplete milestone with date
    pending = [t for t in tasks if not t.get('completed') and t.get('due_on')]
    if pending:
        pending.sort(key=lambda t: datetime.fromisoformat(t['due_on']))
        nxt = pending[0]
        next_str = f"{nxt['name']} – {nxt['due_on']}"
    else:
        next_str = '–'

    # fetch up to 3 latest comments
    latest_comments = fetch_latest_comments(pid, count=3)

    report.append({
        "project": name,
        "next":    next_str,
        "launch":  launch_str,
        "comments": latest_comments
    })

# ─── POST TO SLACK ──────────────────────────────────────────────────────────
if not report:
    text = "No active projects with upcoming milestones."
else:
    lines = ["*Weekly Critical Milestones*"]
    for idx, r in enumerate(report):
        lines.append(f"• *{r['project']}*")
        lines.append(f"    – Next:   {r['next']}")
        lines.append(f"    – Launch: {r['launch']}")
        if r['comments']:
            lines.append("    – Recent comments:")
            for cidx, cm in enumerate(r['comments'], start=1):
                lines.append(f"       {cidx}. {cm}")
        else:
            lines.append("    – Recent comments: –")
        if idx != len(report) - 1:
            lines.append("────────────────────")
    text = "\n".join(lines)

slack_resp = session.post(WEBHOOK, json={"text": text})
if not slack_resp.ok:
    sys.stderr.write(f"Slack post failed: {slack_resp.status_code} — {slack_resp.text}\n")
    sys.exit(1)
