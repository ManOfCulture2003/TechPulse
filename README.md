# TechPulse — PC Health & Security Monitor

**A private, local-first Windows-friendly system health dashboard.** A practical Python portfolio application for software development, IT support, analytics and junior security roles.

> **MVP status (October 2026):** Core metrics and dashboard were exercised in a Linux test environment; automated tests passed there. The Windows Event Log integration and Windows batch launcher have **not yet been end-to-end tested on a Windows PC**. It is an educational diagnostic tool, not an antivirus or a production SIEM.

**Dashboard preview (Linux development environment, not a Windows verification):**

Preview screenshot is included in the downloadable ZIP; source files live in this GitHub repository.

## What it does

- Monitors live **CPU, RAM, system disk, and network rates** every 15 seconds while running.
- Saves samples in a local SQLite database; displays trends over 30 minutes, 2 hours, 24 hours or 7 days.
- Flags explainable resource thresholds (CPU >= 90%, RAM >= 85%, disk >= 90%) **only for fresh readings**. Old samples are visibly labeled as outdated instead of reported as healthy.
- Lists the top seven running processes by resident memory, without any ability to kill them.
- Optionally shows the **25 most recent Windows Security event 4625 failed-sign-in records from the previous 24 hours**, where permitted. Only event IDs and timestamps are returned.
- Exports collected history as CSV; provides a small documented REST API at `/api/docs`.
- Uses no cloud services, analytics SDKs or paid APIs. All assets and data processing run locally.

## Start on Windows (beginner-friendly)

1. Install **Python 3.11 or newer** from [python.org](https://www.python.org/downloads/) if you do not already have it. On the installer, enable **Add python.exe to PATH**.
2. Unzip this repository to a regular folder, such as `Documents/TechPulse`.
3. Double-click **`run_windows.bat`**. The launcher checks Python 3.11+, creates an isolated `.venv`, and installs dependencies from `requirements.txt` on the first run (internet needed for installation). It also repairs missing packages or changed requirements on later runs.
4. Wait for **`[TechPulse] Dashboard ready`**. Your browser opens only after the local API responds. If it does not open automatically, visit **http://127.0.0.1:8765**.
5. Keep the command window open while monitoring. **Press Ctrl+C** or close the command window to stop.

**Nothing is installed as a background service.** The app does not launch automatically when you turn on your PC.

> **Startup troubleshooting:** If Python is missing or older than 3.11, install/update it and restart the terminal. If port 8765 is busy, close the other app or use the manual command with a different port. If package installation fails, check your internet connection and the error shown in the command window. The launcher never opens the dashboard before the server reports ready, and exits with a nonzero status when startup fails.

## Run manually (Windows / macOS / Linux)

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Windows Command Prompt: .venv\Scripts\activate.bat
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

Open http://127.0.0.1:8765. The web interface is served from the local app; do not use `--host 0.0.0.0` on a machine you want to keep private.

## Testing

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Tests cover API responses, host-header restrictions, alert thresholds, history storage and export, data pruning and downsampling, system sampling, event-log access failures, and launcher startup/recovery behavior using isolated mocks (no browser or package installs during tests). GitHub Actions is configured to run on Ubuntu and Windows when pushed to GitHub.

## Project architecture

```text
Browser (HTML + CSS + JavaScript)
         │ HTTP on 127.0.0.1:8765 only
         ▼
FastAPI REST endpoints
         ├── Monitor (psutil): CPU, memory, disk, network, processes
         ├── HistoryStore: SQLite, seven-day retention, CSV export
         └── Optional Windows Security log reader: event 4625
```

### Important source files

| File | Purpose |
| --- | --- |
| `app/main.py` | Routes and background collector; the application's entry point. |
| `launch.py` | Readiness-aware startup, local Python environment repair and helpful errors. |
| `app/monitor.py` | Reads machine data and translates metric thresholds into useful alerts. |
| `app/storage.py` | Persists metrics and queries trends safely using SQLite. |
| `app/windows_events.py` | Optional read-only Windows event query; returns minimal data. |
| `app/static/` | Dark responsive dashboard, custom chart renderer and live refresh. |
| `tests/` | Automated API, database, monitoring and Windows-event behavior tests. |
| `.github/workflows/tests.yml` | Continuous integration (CI) test workflow. |

## REST endpoints

| Endpoint | Output |
| --- | --- |
| `GET /api/health` | Basic health check. |
| `GET /api/overview` | Latest system metrics, collection freshness (`fresh`, `waiting`, `stale`, `invalid`), and alerts only for fresh readings. |
| `GET /api/history?minutes=120` | Downsampled metric history (10–10,080 minutes). |
| `GET /api/processes` | Top seven processes by RAM. |
| `GET /api/security` | Optional Windows 4625 events or an access explanation. |
| `GET /api/export.csv` | Numeric system metrics as a CSV download. |
| `GET /api/docs` | Generated interactive API docs. |

## Privacy and security model

- Start commands bind to **localhost** (`127.0.0.1`), not a public network interface. Requests with unexpected Host headers are rejected.
- No authentication is supplied because the intended deployment is **one user on their own computer**. Do not expose this prototype to your LAN or the internet.
- No raw usernames, Windows event messages, visited websites, browser histories, passwords, personal files, or IP addresses are collected.
- Process list is only viewed on demand; it is **not written** to SQLite.
- Metrics stay in `data/techpulse.sqlite3`, which is excluded from Git. The default retention is seven days; old records are pruned periodically while the monitor runs.
- The Windows security feature may require additional Windows permissions; failure is shown as unavailable instead of pretending the system is safe.
- A failed Windows sign-in (4625) may have innocent explanations. TechPulse does **not** claim to detect attacks or malware.

## Limits

- Sampling only occurs while the app is open. Monitoring is not continuous after the terminal closes. Previously stored samples are marked outdated after three missed collection intervals (minimum 45 seconds), so historical values are not mistaken for current system health.
- The first CPU reading is intentionally primed before sampling; network readings are rates between two counter samples.
- The Security panel is Windows-specific and may lack permission even on Windows. The MVP does not monitor firewall rules or antivirus status.
- This is not an agent deployed across enterprise machines, not a threat-detection model, and not a production hardening tool.
- Tests passed locally on Linux; validate Windows compatibility with the real PC before claiming that the Windows feature works.

## Next engineering milestones

See [`docs/ROADMAP.md`](docs/ROADMAP.md) for advanced features and [`docs/INTERVIEW_GUIDE.md`](docs/INTERVIEW_GUIDE.md) for demo and interview explanations.

## Credits

Designed and built as a learning portfolio project with AI-assisted implementation. The owner should be able to explain, modify, test and demonstrate its architecture before describing it as their independent software engineering experience.
