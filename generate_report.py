#!/usr/bin/env python3
import os, sys, requests
from datetime import datetime

# ─── CONFIG ──────────────────────────────────────────────────────────────────
PAT      = os.getenv('ASANA_PAT')
WS_GID   = os.getenv('ASANA_WORKSPACE_GID')
WEBHOOK  = os.getenv('SLACK_WEBHOOK_URL')
if not all([PAT, WS_GID, WEBHOOK]):
    sys.stderr.write('Missing one of ASANA_PAT, ASANA_WORKSPACE_GID, or SLACK_WEBHOOK_URL\n')
    sys.exit(1)

HEADERS  = {'Authorization': f'Bearer {PAT}'}
BASE_URL = 'https://app.asana.com/api/1.0'

# ─── HELPERS ─────────────────────────────────────────────────────────────────
def fetch_due(task_gid):
    """Fetch a single task’s due_on date (or return 'TBD')."""
    resp = requests.get(
        f'{BASE_URL}/tasks/{task_gid}',
        headers=HEADERS,
        params={'opt_fields':'due_on'}
    )
    if resp.ok:
        return resp.json().get('data', {}).get('due_on') or 'TBD'
    return 'TBD'

# ─── FETCH PROJECTS ─────────────────────────────────────────────────────────
resp = requests.get(
    f'{BASE_URL}/workspaces/{WS_GID}/projects',
    headers=HEADERS,
    params={'archived': 'false'}
)
if not resp.ok:
    sys.stderr.write(f"Error fetching projects: {resp.status_code} — {resp.text}\n")
    sys.exit(1)

projects = resp.json().get('data', [])
report   = []

for proj in projects:
    name = proj.get('name','')
    pid  = proj.get('gid','')

    # skip drafts
    if 'WORKING DRAFT' in name.upper():
        continue

    # ─── find the Critical Milestones section ────────────────────────────────
    secs = requests.get(
        f'{BASE_URL}/projects/{pid}/sections',
        headers=HEADERS
    ).json().get('data', [])
    cm = next((s for s in secs if s.get('name')=='Critical Milestones'), None)
    if not cm:
        continue

    # ─── pull the compact task list in that section ─────────────────────────
    section_tasks = requests.get(
        f'{BASE_URL}/sections/{cm["gid"]}/tasks',
        headers=HEADERS,
        params={'opt_fields':'gid,name,completed'}
    ).json().get('data', [])

    # ─── Launch milestone ────────────────────────────────────────────────────
    launch = next((t for t in section_tasks if t.get('name')=='Launch'), None)
    if launch and launch.get('completed'):
        # skip any project already launched
        continue
    if launch:
        launch_date = fetch_due(launch['gid'])
        launch_str  = f"Launch – {launch_date}"
    else:
        launch_str  = '–'

    # ─── Next incomplete milestone ───────────────────────────────────────────
    pending = [t for t in section_tasks if not t.get('completed')]
    if pending:
        # fetch due dates for sorting
        for t in pending:
            t['due_on'] = fetch_due(t['gid'])
        # drop those without real due dates
        pending = [t for t in pending if t.get('due_on') not in (None, 'TBD')]
        pending.sort(key=lambda t: datetime.fromisoformat(t['due_on']))
        nxt = pending[0]
        next_str = f"{nxt['name']} – {nxt['due_on']}"
    else:
        next_str = '–'

    # ─── Latest comment across all tasks ─────────────────────────────────────
    # first, list all tasks in the project
    proj_tasks = requests.get(
        f'{BASE_URL}/projects/{pid}/tasks',
        headers=HEADERS,
        params={'opt_fields':'gid'}
    ).json().get('data', [])
    comments = []
    for t in proj_tasks:
        stories = requests.get(
            f'{BASE_URL}/tasks/{t["gid"]}/stories',
            headers=HEADERS,
            params={'opt_fields':'resource_subtype,created_at,text'}
        ).json().get('data', [])
        for s in stories:
            if s.get('resource_subtype')=='comment_added' and s.get('text'):
                comments.append(s)
    if comments:
        comments.sort(key=lambda s: s['created_at'], reverse=True)
        latest_comment = comments[0]['text'].replace('\n',' ')
    else:
        latest_comment = '–'

    # ─── assemble this project’s row ────────────────────────────────────────
    report.append({
        'project': name,
        'next':    next_str,
        'launch':  launch_str,
        'comment
