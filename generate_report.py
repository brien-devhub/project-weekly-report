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

# 2. Fetch all active (non-archived) projects
resp = requests.get(f'{BASE_URL}/workspaces/{WS_GID}/projects',
                    headers=HEADERS,
                    params={'archived': 'false'})
if not resp.ok:
    sys.stderr.write(f"Error fetching projects: {resp.status_code} — {resp.text}\n")
    sys.exit(1)
projects = resp.json().get('data', [])

report_lines = []

for proj in projects:
    name = proj['name']
    # 2a. Exclude working drafts
    if 'WORKING DRAFT' in name.upper():
        continue

    pid = proj['gid']

    # 3. Find “Critical Milestones” section
    secs = requests.get(f'{BASE_URL}/projects/{pid}/sections',
                        headers=HEADERS).json().get('data', [])
    cm   = next((s for s in secs if s['name']=='Critical Milestones'), None)
    if not cm:
        continue

    # 4. List tasks in that section
    tasks = requests.get(
        f'{BASE_URL}/sections/{cm["gid"]}/tasks',
        headers=HEADERS,
        params={'opt_fields':'name,due_on,completed'}
    ).json().get('data', [])

    # 4a. Locate Launch milestone and skip if completed
    launch = next((t for t in tasks if t['name']=='Launch'), None)
    if launch and launch.get('completed'):
        continue
    launch_str = (f"{launch['name']} – {launch['due_on']}"
                  if launch and launch.get('due_on')
                  else '-')

    # 4b. Find next incomplete milestone
    pending = [t for t in tasks if not t['completed'] and t.get('due_on')]
    if pending:
        pending.sort(key=lambda t: datetime.fromisoformat(t['due_on']))
        nt = pending[0]
        next_str = f"{nt['name']} – {nt['due_on']}"
    else:
        next_str = '-'

    # 5. Build one bullet line
    report_lines.append(
        f"• *{name}* – Next: {next_str}; Launch: {launch_str}"
    )

# 6. Assemble Slack message
if not report_lines:
    text = "No active projects with pending milestones."
else:
    header = "*Weekly Critical Milestones Update*\n"
    text   = header + "\n".join(report_lines)

# 7. Post to Slack
post = requests.post(WEBHOOK, json={'text': text})
if not post.ok:
    sys.stderr.write(f"Slack post failed: {post.status_code} — {post.text}\n")
    sys.exit(1)
