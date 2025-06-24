from flask import Flask, request, jsonify
import os
import requests
from datetime import datetime, timedelta

app = Flask(__name__)

ASANA_PAT = os.getenv("ASANA_PAT")

USER_MAP = {
    "brien": "your_asana_user_gid_here"
}

PROJECT_MAP = {
    "SMR": "project_gid_here",
    "DD": "project_gid_here"
}

def create_task(project_gid, name, assignee):
    url = f"https://app.asana.com/api/1.0/tasks"
    headers = {
        "Authorization": f"Bearer {ASANA_PAT}",
        "Content-Type": "application/json"
    }
    due_date = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")
    data = {
        "data": {
            "name": name,
            "assignee": assignee,
            "projects": [project_gid],
            "due_on": due_date,
            "notes": "Auto-created from Slack listener",
            "custom_fields": {
                "your_custom_field_id_for_estimated_time": 60
            }
        }
    }
    requests.post(url, headers=headers, json=data)

@app.route("/", methods=["POST"])
def handle_slack_event():
    payload = request.json

    if payload.get("type") == "url_verification":
        return payload.get("challenge"), 200, {"Content-Type": "text/plain"}

    event = payload.get("event", {})
    if event.get("type") != "message" or "thread_ts" not in event:
        return jsonify({"status": "ignored"}), 200

    user = event.get("user")
    text = event.get("text", "")
    slack_username = event.get("username", "").lower()

    assignee = USER_MAP.get(slack_username)
    if not assignee:
        return jsonify({"error": "Unmapped user"}), 200

    for line in text.strip().split("\n"):
        if " - " not in line:
            continue
        prefix, task_body = line.split(" - ", 1)
        prefix = prefix.strip().upper()
        project_gid = PROJECT_MAP.get(prefix)
        if not project_gid:
            continue
        create_task(project_gid, task_body.strip(), assignee)

    return jsonify({"status": "processed"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
