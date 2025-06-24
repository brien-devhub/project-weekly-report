import os
import requests
from datetime import datetime

ASANA_PAT = os.getenv("ASANA_PAT")
REPORT_GID = os.getenv("ASANA_REPORT_GID")
SLACK_WEBHOOK = os.getenv("SLACK_WEBHOOK")

BASE_URL = "https://app.asana.com/api/1.0"
HEADERS = {"Authorization": f"Bearer {ASANA_PAT}"}


def get_projects():
    res = requests.get(f"{BASE_URL}/portfolios/{REPORT_GID}/items", headers=HEADERS)
    return res.json().get("data", [])


def get_sections(project_gid):
    res = requests.get(f"{BASE_URL}/projects/{project_gid}/sections", headers=HEADERS)
    return res.json().get("data", [])


def get_tasks(section_gid):
    res = requests.get(f"{BASE_URL}/sections/{section_gid}/tasks", headers=HEADERS)
    return res.json().get("data", [])


def get_task_details(task_gid):
    res = requests.get(f"{BASE_URL}/tasks/{task_gid}", headers=HEADERS)
    return res.json().get("data", {})


def get_task_comments(task_gid):
    res = requests.get(f"{BASE_URL}/tasks/{task_gid}/stories", headers=HEADERS)
    comments = res.json().get("data", [])
    return [c for c in comments if c["type"] == "comment"]


def is_incomplete(task):
    return task.get("completed") is False and task.get("resource_subtype") == "default_task"


def format_project(project):
    sections = get_sections(project["gid"])
    cm_section = next((s for s in sections if "critical milestone" in s["name"].lower()), None)
    if not cm_section:
        return None

    tasks = get_tasks(cm_section["gid"])
    incomplete = [get_task_details(t["gid"]) for t in tasks if is_incomplete(t)]
    if not incomplete:
        return None

    incomplete.sort(key=lambda t: t.get("due_on") or "9999-12-31")
    next_milestone = incomplete[0]

    launch_milestone = next((t for t in tasks if "launch" in t["name"].lower()), None)
    launch_date = None
    if launch_milestone:
        launch_detail = get_task_details(launch_milestone["gid"])
        if not launch_detail.get("completed"):
            launch_date = launch_detail.get("due_on")

    all_comments = []
    for section in sections:
        tasks = get_tasks(section["gid"])
        for t in tasks:
            detail = get_task_details(t["gid"])
            if detail.get("completed"):
                continue
            comments = get_task_comments(t["gid"])
            all_comments.extend([(c["created_at"], c["text"]) for c in comments])

    all_comments.sort(reverse=True)
    comments = [f"- {c[1]}" for c in all_comments[:6]]

    return {
        "name": project["name"],
        "next": f'{next_milestone["name"]} – {next_milestone.get("due_on", "No date")}',
        "launch": f'{launch_date}' if launch_date else "None",
        "comments": comments
    }


def post_to_slack(message):
    requests.post(SLACK_WEBHOOK, json={"text": message})


def main():
    projects = get_projects()
    rows = []
    for p in projects:
        if "WORKING DRAFT" in p["name"].upper():
            continue
        entry = format_project(p)
        if entry and entry["launch"] != "None":
            rows.append(entry)

    lines = ["*Weekly Project Report*"]
    for r in rows:
        lines.append("")
        lines.append(f"*{r['name']}*")
        lines.append(f"> *Next Open Milestone:* {r['next']}")
        lines.append(f"> *Projected Launch Date:* {r['launch']}")
        lines.append("> *Most recent task comments:*")
        if r["comments"]:
            for comment in r["comments"]:
                lines.append(comment)
        else:
            lines.append("- No comments found")

    post_to_slack("\n".join(lines))


if __name__ == "__main__":
    main()
