# generate_report.py
import os, sys, requests

# 1. Load & validate inputs
PAT               = os.environ.get('ASANA_PAT')
WORKSPACE_GID     = os.environ.get('ASANA_WORKSPACE_GID')
SECTION_GIDS      = os.environ.get('CRITICAL_SECTION_GIDS')
LIMIT             = os.environ.get('LIMIT', '100')

for var, name in [(PAT,'ASANA_PAT'), (WORKSPACE_GID,'ASANA_WORKSPACE_GID'), (SECTION_GIDS,'CRITICAL_SECTION_GIDS')]:
    if not var:
        sys.stderr.write(f"Missing {name}\n")
        sys.exit(1)

# 2. Build the Search URL
base_url = f"https://app.asana.com/api/1.0/workspaces/{WORKSPACE_GID}/tasks/search"
params = {
    'sections.any': SECTION_GIDS,
    'opt_fields': 'projects.name,name,due_on,completed',
    'limit': LIMIT
}

# 3. Fetch
resp = requests.get(base_url, headers={'Authorization': f"Bearer {PAT}"}, params=params)
if not resp.ok:
    sys.stderr.write(f"Asana API error {resp.status_code}: {resp.text}\n")
    sys.exit(1)

payload = resp.json()
data    = payload.get('data')
if data is None:
    sys.stderr.write(f"Unexpected response: {payload}\n")
    sys.exit(1)

# 4. Render Markdown table
md  = '| Project | Milestone | Due Date | Completed |\n'
md += '| ------- | --------- | -------- | --------- |\n'
for item in data:
    proj = item['projects'][0]['name'] if item.get('projects') else ''
    name = item.get('name','')
    due  = item.get('due_on','')
    comp = '✅' if item.get('completed') else '❌'
    md  += f'| {proj} | {name} | {due} | {comp} |\n'

print(md)
