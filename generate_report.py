import os
import requests
from datetime import datetime

ASANA_PAT      = os.getenv("ASANA_PAT")
REPORT_GID     = os.getenv("ASANA_REPORT_GID")
SLACK_WEBHOOK  = os.getenv("SLACK_WEBHOOK")

BASE_URL = "https://app.asana.com/api/1.0"
HEADERS  = {"Authorization": f"Bearer {ASANA_PAT}"}

def get_projects():
    resp = requests.get(f"{BASE_URL}/portfolios/{REPORT_GID}/items", headers=HEADERS)
    return resp.json().get("data", [])

def get_sections(project_gid):
    resp = requests.get(f"{BASE_URL}/projects/{project_gid}/sections", headers=HEADERS)
    return resp.json().get("data", [])

def get_tasks(section_gid):
    resp = requests.get(f"{BASE_URL}/sections/{section_gid}/tasks", headers=HEADERS)
    return resp.json().get("data", [])

def get_task_details(task_gid):
    resp = requests.get(f"{BASE_URL}/tasks/{task_gid}", headers=HEADERS)
    return resp.json().get("data", {})

def get_task_comments(task_gid):
    resp = requests.get(f"{BASE_URL}/tasks/{task_gid}/stories", headers=HEADERS)
    return [s for s in resp.json().get("data", [])
            if s.get("type") == "comment"]

def is_incomplete(task):
    return not task.get("completed") and task.get("resource_subtype") == "default_task"

def format_project(project):
    # 1. Find Critical Milestones section
    sections = get_sections(project["gid"])
    cm = next((s for s in sections if "critical milestone" in s["name"].lower()), None)
    if not cm:
        return None

    # 2. Next open milestone
    cm_tasks   = get_tasks(cm["gid"])
    details    = [get_task_details(t["gid"]) for t in cm_tasks]
    open_tasks = [t for t in details if is_incomplete(t)]
    if not open_tasks:
        return None
    open_tasks.sort(key=lambda t: t.get("due_on") or "9999-12-31")
    next_task = open_tasks[0]

    # 3. Launch date (if not complete)
    launch = next((t for t in details if "launch" in t["name"].lower()), None)
    launch_date = None
    if launch and not launch.get("completed"):
        launch_date = launch.get("due_on")

    # 4. Gather up to 6 comments from all non-closed, non-completed tasks
    all_comments = []
    for s in sections:
        name_lower = s["name"].strip().lower()
        if name_lower in ("closed", "done", "complete"):
            continue
        for t in get_tasks(s["gid"]):
            td = get_task_details(t["gid"])
            if td.get("completed"):
                continue
            for c in get_task_comments(td["gid"]):
                all_comments.append((c["created_at"], c["text"]))

    # sort descending by date and take top 6
    all_comments.sort(key=lambda x: x[0], reverse=True)
    comments = [f"- {c[1]}" for c in all_comments[:6]]

    return {
        "name":    project["name"],
        "next":    f"{next_task['name']} – {next_task.get('due_on','No date')}",
        "launch":  launch_date or "None",
        "comments": comments
    }

def post_to_slack(text):
    requests.post(SLACK_WEBHOOK, json={"text": text})

def main():
    rows = []
    for p in get_projects():
        # skip draft and template
        if p["name"].upper().startswith("WORKING DRAFT"):
            continue
        if p["name"] == "2025 Project Template":
            continue

        entry = format_project(p)
        if entry and entry["launch"] != "None":
            rows.append(entry)

    # build Slack message
    lines = ["*Weekly Project Report*"]
    for idx, r in enumerate(rows):
        lines.append("")  # blank line
        lines.append(f"*{r['name']}*")
        lines.append(f"> *Next Open Milestone:* {r['next']}")
        lines.append(f"> *Projected Launch Date:* {r['launch']}")
        lines.append("> *Most recent task comments:*")
        if r["comments"]:
            for c in r["comments"]:
                lines.append(c)
        else:
            lines.append("- No comments found")

        # divider except after the last project
        if idx < len(rows) - 1:
            lines.append("— — — — — — — — — — —")

    post_to_slack("\n".join(lines))

if __name__ == "__main__":
    main()
