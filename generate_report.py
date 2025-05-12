#!/usr/bin/env python3
import os, sys, requests
from datetime import datetime

# 1. Load config
PAT     = os.getenv('ASANA_PAT')
WS_GID  = os.getenv('ASANA_WORKSPACE_GID')
WEBHOOK = os.getenv('SLACK_WEBHOOK_URL')
if not all([PAT, WS_GID, WEBHOOK]):
    sys.stderr.write('Missing ASANA_PAT, ASANA_WORKSPACE_GID or SLACK_WEBHOOK_URL\n')
    sys.exit(1)

HEADERS  = {'Authorization': f'Bearer {PAT}'}
BASE_URL = 'https://app.asana.com/api/1.0'

# 2. Fetch all active projects
r = requests.get(f'{BASE_URL}/workspaces/{WS_GID}/projects',
                 headers=HEADERS,
                 params={'archived': 'false'})
if not r.ok:
    sys.stderr.write(f"Error fetching projects: {r.status_code} — {r.text}\n")
    sys.exit(1)

projects = r.json().get('data', [])
report   = []

for proj in projects:
    name = proj['name']
    pid  = proj['gid']

    # 2a. Skip working drafts
    if 'WORKING DRAFT' in name.upper():
        continue

    # 3. Find Critical Milestones section
    secs = requests.get(f'{BASE_URL}/projects/{pid}/sections',
                        headers=HEADERS).json().get('data', [])
    cm = next((s for s in secs if s['name']=='Critical Milestones'), None)
    if not cm:
        continue

    # 4. Pull tasks in that section
    tasks = requests.get(
        f'{BASE_URL}/sections/{cm["gid"]}/tasks',
        headers=HEADERS,
        params={'opt_fields':'name,due_on,completed'}
    ).json().get('data', [])

    # 4a. Launch milestone → skip if already completed
    launch = next((t for t in tasks if t['name']=='Launch'), None)
    if launch and launch.get('completed'):
        continue
    launch_str = f"{launch['name']} - {launch['due_on']}" if launch and launch.get('due_on') else '-'

    # 4b. Next incomplete milestone
    pending = [t for t in tasks if not t['completed'] and t.get('due_on')]
    if pending:
        pending.sort(key=lambda t: datetime.fromisoformat(t['due_on']))
        nxt = pending[0]
        next_str = f"{nxt['name']} - {nxt['due_on']}"
    else:
        next_str = '-'

    # 5. Fetch latest comment on the project
    stories = requests.get(
        f'{BASE_URL}/projects/{pid}/stories',
        headers=HEADERS,
        params={'opt_fields':'created_at,text,resource_subtype'}
    ).json().get('data', [])
    # Filter to only user‐added comments
    comments = [s for s in stories if s.get('resource_subtype')=='comment_added' and s.get('text')]
    if comments:
        # sort descending by created_at
        comments.sort(key=lambda s: s['created_at'], reverse=True)
        latest_comment = comments[0]['text']
    else:
        latest_comment = '-'

    report.append({
        'project': name,
        'next':    next_str,
        'launch':  launch_str,
        'comment': latest_comment.replace('\n',' ')  # single‐line
    })

# 6. Build Slack message as bullets
if not report:
    text = "No active projects with upcoming milestones."
else:
    lines = ['*Weekly Critical Milestones*']
    for r in report:
        lines.append(
            f"• *{r['project']}*  \n"
            f"   – Next: {r['next']}  \n"
            f"   – Launch: {r['launch']}  \n"
            f"   – Latest comment: {r['comment']}"
        )
    text = '\n'.join(lines)

# 7. Post to Slack
resp = requests.post(WEBHOOK, json={'text': text})
if not resp.ok:
    sys.stderr.write(f"Slack post failed: {resp.status_code} — {resp.text}\n")
    sys.exit(1)
