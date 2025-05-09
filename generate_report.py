import os
import sys
import requests

# Load secrets
PAT         = os.environ.get('ASANA_PAT')
REPORT_GID  = os.environ.get('ASANA_REPORT_GID')

# Validate
if not PAT:
    sys.stderr.write("Missing ASANA_PAT\n")
    sys.exit(1)
if not REPORT_GID:
    sys.stderr.write("Missing ASANA_REPORT_GID\n")
    sys.exit(1)

# Call the Asana Reports API
url  = f'https://app.asana.com/api/1.0/reports/{REPORT_GID}/results'
resp = requests.get(url, headers={'Authorization': f'Bearer {PAT}'})

# Surface HTTP errors
if not resp.ok:
    sys.stderr.write(f"Asana API error {resp.status_code}: {resp.text}\n")
    sys.exit(1)

payload = resp.json()

# Check payload structure
data = payload.get('data')
if data is None:
    sys.stderr.write(f"Unexpected response format: {payload}\n")
    sys.exit(1)

# Build Markdown table
md  = '| Project | Milestone | Due Date | Completed |\n'
md += '| ------- | --------- | -------- | --------- |\n'
for item in data:
    proj = item['projects'][0]['name'] if item.get('projects') else ''
    name = item.get('name','')
    due  = item.get('due_on','')
    comp = '✅' if item.get('completed') else '❌'
    md  += f'| {proj} | {name} | {due} | {comp} |\n'

# Output the table
print(md)
