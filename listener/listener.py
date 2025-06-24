from flask import Flask, request, jsonify
import os
import requests
from datetime import datetime, timedelta

app = Flask(__name__)

ASANA_PAT = os.getenv("ASANA_PAT")
PROJECT_MAP = {
    "SMR": "1201234567890",
    "MSE": "1200987654321"
    # Add more project codes and their Asana GIDs here
}

USER_MAP = {
    "jess": "asana_user_gid_1",
    "dan": "asana_user_gid_2"
    # Add more Slack usernames to Asana user GIDs here
}

HEADERS = {
    "Authorization": f"Bearer {ASANA_PAT}",
    "Content-Type": "application/json"
}

def create_task(project_gid, name, assignee):
    url = "https://app.asana.com/api/1.0/tasks"
    tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime('%Y-%m-%d')
    data = {
        "name": name,
        "projects": [project_gid],
        "assignee": assignee,
        "due_on": tomorrow,
        "notes": "Created from Slack reply"
    }
    response = requests.post(url, json={"data": data}, headers=HEADERS)
    return response.status_code, response.json()

@app.route("/", methods=["POST"])
def handle_slack_event():
    payload = request.json

    # Slack URL verification challenge
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

    for line in text.strip().split("\\n"):
        if " - " not in line:
            continue
        prefix, task_body = line.split(" - ", 1)
        prefix = prefix.strip().upper()
        project_gid = PROJECT_MAP.get(prefix)
        if not project_gid:
            continue
        create_task(project_gid, task_body.strip(), assignee)

    return jsonify({"status": "processed"}), 200
