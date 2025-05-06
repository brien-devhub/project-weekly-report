import os, requests

# pull your PAT and Report GID from environment
PAT = os.environ['2/1207622752023949/1210162423953290:199fcbcb526f1b4e40b76f95aa658dd9']
REPORT_GID = os.environ['1210155607259625']

url = f'https://app.asana.com/api/1.0/reports/{REPORT_GID}/results'
resp = requests.get(url, headers={'Authorization': f'Bearer {PAT}'})
items = resp.json()['data']

# build a Markdown table
md = '| Project | Milestone | Due Date | Completed |\n'
md += '| ------- | --------- | -------- | --------- |\n'
for i in items:
    proj = i['projects'][0]['name']
    name = i['name']
    due  = i.get('due_on','')
    comp = '✅' if i['completed'] else '❌'
    md  += f'| {proj} | {name} | {due} | {comp} |\n'

# print to standard out
print(md)
