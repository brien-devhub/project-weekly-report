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
    sys.stderr.write(f"Error fetching projects: {resp.status_code} — {resp.text}\n")
    sys.exit(1)
projects = resp.json().get('data', [])

rows = []

for proj in projects:
    pid  = proj['gid']
    name = proj['name']

    # 3a. Find the Critical Milestones section
    sec_resp = requests.get(f'{BASE_URL}/projects/{pid}/sections',
                            headers=HEADERS)
    secs = sec_resp.json().get('data', [])
    cm = next((s for s in secs if s['name']=='Critical Milestones'), None)
    if not cm:
        continue

    # 3b. Fetch tasks in that section
    tasks_resp = requests.get(
      f'{BASE_URL}/sections/{cm["gid"]}/tasks',
      headers=HEADERS,
      params={'opt_fields':'name,due_on,completed'}
    )
    tasks = tasks_resp.json().get('data', [])

    # 3c. Locate the Launch milestone (if completed, skip project)
    launch = next((t for t in tasks if t['name']=='Launch'), None)
    if launch and launch.get('completed'):
        continue
    # Format launch string (even if not found or incomplete)
    launch_str = (f"{launch['name']} - {launch['due_on']}"
                  if launch and launch.get('due_on')
                  else '-')

    # 3d. Determine next incomplete milestone
    pending = [t for t in tasks if not t['completed'] and t.get('due_on')]
    if pending:
        pending.sort(key=lambda t: datetime.fromisoformat(t['due_on']))
        nt = pending[0]
        next_str = f"{nt['name']} - {nt['due_on']}"
    else:
        next_str = '-'

    rows.append({
      'project': name,
      'next':    next_str,
      'launch':  launch_str
    })

# 4. Build a padded table
if not rows:
    table = 'No upcoming critical milestones.'
else:
    # calculate column widths
    cols = ['Project', 'Next Milestone', 'Launch']
    widths = {
      'project': max(len(cols[0]), *(len(r['project']) for r in rows)),
      'next':    max(len(cols[1]), *(len(r['next'])    for r in rows)),
      'launch':  max(len(cols[2]), *(len(r['launch'])  for r in rows)),
    }

    # header + separator
    header = (
      cols[0].ljust(widths['project']) + ' | ' +
      cols[1].ljust(widths['next'])    + ' | ' +
      cols[2].ljust(widths['launch'])
    )
    sep = (
      '-' * widths['project'] + '-+-' +
      '-' * widths['next']    + '-+-' +
      '-' * widths['launch']
    )

    # rows
    lines = [header, sep]
    for r in rows:
        lines.append(
          r['project'].ljust(widths['project']) + ' | ' +
          r['next'].ljust(widths['next'])           + ' | ' +
          r['launch'].ljust(widths['launch'])
        )
    table = '\n'.join(lines)

# 5. Post to Slack in a code block
payload = {'text': f"```{table}```"}
post = requests.post(WEBHOOK, json=payload)
if not post.ok:
    sys.stderr.write(f"Slack post failed: {post.status_code} — {post.text}\n")
    sys.exit(1)
