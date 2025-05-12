#!/usr/bin/env python3
import os, sys, requests
from datetime import datetime

# ─── CONFIG ──────────────────────────────────────────────────────────────────
PAT      = os.getenv('ASANA_PAT')
WS_GID   = os.getenv('ASANA_WORKSPACE_GID')
WEBHOOK  = os.getenv('SLACK_WEBHOOK_URL')
if not all([PAT, WS_GID, WEBHOOK]):
    sys.stderr.write('Missing ASANA_PAT, ASANA_WORKSPACE_GID or SLACK_WEBHOOK_URL\n')
    sys.exit(1)

HEADERS  = {'Authorization': f'Bearer {PAT}'}
BASE_URL = 'https://app.asana.com/api/1.0'

# ─── FETCH PROJECTS ─────────────────────────────────────────────────────────
res = requests.get(
    f'{BASE_URL}/workspaces/{WS_GID}/projects',
    headers=HEADERS,
    params={'archived': 'false'}
)
if not res.ok:
    sys.stderr.write(f"Error fetching projects: {res.status_code} — {res.text}\n")
    sys.exit(1)

projects = res.json().get('data', [])
report   = []

for proj in projects:
    name = proj['name']
    pid  = proj['gid']

    # skip drafts
    if 'WORKING DRAFT' in name.upper():
        continue

    # ─── Milestones ────────────────────────────────────────────────────────
    # find Critical Milestones section
    secs = requests.get(f'{BASE_URL}/projects/{pid}/sections',
                        headers=HEADERS).json().get('data', [])
    cm = next((s for s in secs if s['name']=='Critical Milestones'), None)
    if not cm:
        continue

    # get tasks in Critical Milestones
    section_tasks = requests.get(
        f'{BASE_URL}/sections/{cm["gid"]}/tasks',
        headers=HEADERS,
        params={'opt_fields':'gid,name,due_on,completed'}
    ).json().get('data', [])

    # Launch milestone (skip if completed)
    launch = next((t for t in section_tasks if t['name']=='Launch'), None)
    if launch and launch.get('completed'):
        continue
    launch_date = launch.get('due_on') or 'TBD' if launch else '–'
    launch_str  = f"{launch['name']} – {launch_date}" if launch else '–'

    # next incomplete
    pending = [t for t in section_tasks if not t['completed'] and t.get('due_on')]
    if pending:
        pending.sort(key=lambda t: datetime.fromisoformat(t['due_on']))
        nxt = pending[0]
        next_str = f"{nxt['name']} – {nxt['due_on']}"
    else:
        next_str = '–'

    # ─── Comments ────────────────────────────────────────────────────────────
    # fetch all tasks in the project
    proj_tasks = requests.get(
        f'{BASE_URL}/projects/{pid}/tasks',
        headers=HEADERS,
        params={'opt_fields':'gid'}
    ).json().get('data', [])

    latest_comment = '–'
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
        # single-line
        latest_comment = comments[0]['text'].replace('\n',' ')

    report.append({
        'project': name,
        'next':    next_str,
        'launch':  launch_str,
        'comment': latest_comment
    })

# ─── BUILD SLACK MESSAGE ────────────────────────────────────────────────────
if not report:
    text = "No active projects with upcoming milestones."
else:
    lines = ['*Weekly Critical Milestones*']
    for r in report:
        lines.append(
            f"• *{r['project']}*\n"
            f"    – Next:   {r['next']}\n"
            f"    – Launch: {r['launch']}\n"
            f"    – Latest comment: {r['comment']}"
        )
    text = '\n'.join(lines)

# ─── POST TO SLACK ──────────────────────────────────────────────────────────
resp = requests.post(WEBHOOK, json={'text': text})
if not resp.ok:
    sys.stderr.write(f"Slack post failed: {resp.status_code} — {resp.text}\n")
    sys.exit(1)
