# Weekly Critical Milestones Report

This repository contains a small Python application and a GitHub Actions workflow that, every Monday at 8:30 AM and 1:30 PM Eastern Time, will:

1. Fetch all active Asana projects in your workspace  
2. For each project (except those named “WORKING DRAFT”):
   - Find the “Critical Milestones” section  
   - Skip the project if its **Launch** milestone is already marked complete  
   - Identify the next incomplete milestone (with due date)  
   - Read the three three most recent task-level comments across the project  
3. Post a neatly formatted Slack message listing each project with:
   - **Next** milestone and date  
   - **Launch** date  
   - Up to **3 recent comments**

---

## Repository Structure

```
.
├── .github
│   └── workflows
│       └── weekly-milestones.yml   # GitHub Actions workflow
├── weekly_milestones.py            # Main Python script
└── README.md                       # This file
```

---

## Prerequisites

- **Python 3.7+**  
- **pip**  
- An Asana Personal Access Token with access to your workspace  
- A Slack Incoming Webhook URL for your target channel  

---

## Setup

1. **Clone the repository**  
   ```bash
   git clone https://github.com/<your-org>/project-weekly-report.git
   cd project-weekly-report
   ```

2. **Install dependencies**  
   ```bash
   pip install requests
   ```

3. **Configure environment variables**  
   Store these as GitHub **Actions Secrets** (in Settings → Secrets → Actions), and export for local testing:

   | Name                   | Description                                            |
   |------------------------|--------------------------------------------------------|
   | `ASANA_PAT`            | Your Asana Personal Access Token                       |
   | `ASANA_WORKSPACE_GID`  | GID of your Asana workspace (from the Asana web UI)    |
   | `SLACK_WEBHOOK_URL`    | Your Slack Incoming Webhook URL                        |

   ```bash
   export ASANA_PAT="…"
   export ASANA_WORKSPACE_GID="…"
   export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/…"
   ```

---

## Running Locally

You can test the script on demand:

```bash
python weekly_milestones.py
```

It will immediately post the report to Slack (make sure your env vars are set).

---

## GitHub Actions Workflow

The file `.github/workflows/weekly-milestones.yml` schedules two runs every Monday:

- **08:30 AM Eastern** → `cron: '30 12 * * 1'`  
- **01:30 PM Eastern** → `cron: '30 17 * * 1'`  

It also supports manual dispatch via the **Run workflow** button.

### How it works

1. Checks out this repo.  
2. Sets up Python and installs `requests`.  
3. Exports your three secrets into the environment.  
4. Runs `python weekly_milestones.py`.  

---

## Customization

- **Schedule**: Edit the `cron:` lines in the workflow to run at other times or days.  
- **Comment count**: In `weekly_milestones.py`, change the `count=3` in `fetch_latest_comments(pid, count=3)` to fetch more or fewer comments.  
- **Section name**: If your milestone section is named differently, adjust the default in `get_section_gid(..., section_name="Critical Milestones")`.  
- **Filtering**: To include or exclude additional projects, modify the project-name checks in the main loop.

---

## Troubleshooting

- **Missing dates**: Ensure your Critical Milestones tasks in Asana have a valid **Due Date** field set.  
- **Authentication errors**: Double-check that your `ASANA_PAT` and `ASANA_WORKSPACE_GID` are correct.  
- **Slack failures**: Confirm that your `SLACK_WEBHOOK_URL` is valid and that the target channel still exists.

---

> _Maintained by Brien Hall <brien@devhub.com>. Feel free to open a PR for improvements or adjustments._
