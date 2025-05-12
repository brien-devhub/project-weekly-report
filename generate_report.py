#!/usr/bin/env python3
import os, sys, requests
from datetime import datetime

# 1. Load config
PAT      = os.getenv('ASANA_PAT')
WS_GID   = os.getenv('ASANA_WORKSPACE_GID')
WEBHOOK  = os.getenv('SLACK_WEBHOOK_URL')
if not all([PAT, WS_GID, WEBHOOK]):
    sys.stderr.write('Missing ASANA_PAT, ASANA_WORKSPACE_GID or SLACK_WEBHOOK_URL\n')
    sys.exit(1)

HEADERS  = {'Authorization': f'Bearer {PAT}'}
BASE_URL = 'https://app.asana.com/api/1.0'

# 2. Fetch all active projects
resp = requests.get(f'{BASE_URL}/workspaces/{WS_GID}/projects',
                    headers=HEADERS,
                    params={'archived': 'false'})
if not resp.ok:
    sys.stderr.write(f'Error fetching projects: {resp.status_code}\n')
    sys.exit(1)
projects = resp.json().get('data', [])

report = []

for proj in projects:
    pid   = proj['gid']
    name  = proj['name']

    # 3a. Find the Critical Milestones section
    sec_resp = requests.get(f'{BASE_URL}/projects/{pid}/sections',
                            headers=HEADERS)
    secs = sec_resp.json().get('data', [])
    cm = next((s for s in secs if s['name']=='Critical Milestones'), None)
    if not cm:
        continue

    # 3b. Fetch all tasks in that section
    tasks_resp = requests.get(
      f'{BASE_URL}/sections/{cm["gid"]}/tasks',
      headers=HEADERS,
      params={'opt_fields':'name,due_on,completed'}
    )
    tasks = tasks_resp.json().get('data', [])

    # 3c. Next incomplete milestone
    pending = [t for t in tasks if not t['completed'] and t.get('due_on')]
    if pending:
        pending.sort(key=lambda t: datetime.fromisoformat(t['due_on']))
        next_task = pending[0]
        next_str  = f"{next_task['name']} - {next_task['due_on']}"
    else:
        next_str = '-'

    # 3d. Launch milestone (whether complete or not)
    launch_task = next((t for t in tasks if t['name']=='Launch' and t.get('due_on')), None)
    if launch_task:
        launch_str = f"{launch_task['name']} - {launch_task['due_on']}"
    else:
        launch_str = '-'

    report.append({
      'project': name,
      'next':    next_str,
      'launch':  launch_str
    })

# 4. Build Markdown table
if not report:
    table = 'No data to display.'
else:
    table  = '| Project | Next Milestone | Launch |\n'
    table += '| ------- | -------------- | ------ |\n'
    for r in report:
        table += f"| {r['project']} | {r['next']} | {r['launch']} |\n"

# 5. Post to Slack (in a code block so table alignment holds)
payload = {
    'text': f"```{table}```"
}
post = requests.post(WEBHOOK, json=payload)
if not post.ok:
    sys.stderr.write(f'Slack post failed: {post.status_code}\n')
    sys.exit(1)
