# How to explain TechPulse in an interview

## Your 60-second introduction

> I built TechPulse as a local PC-health monitoring application because most users cannot easily connect CPU, RAM, disk, network activity and basic security events in one simple view. It uses Python and FastAPI for the backend, psutil for system measurements, SQLite for storing history, and a responsive JavaScript dashboard. It collects samples every 15 seconds, calculates resource alerts, supports historical charts, and lets the user export the data as CSV. I also added automated tests and a GitHub Actions workflow, and designed the app to stay on localhost rather than collecting information in a cloud service. The first version is a personal diagnostic tool, not a full enterprise security product.

Adapt this to reflect the work **you personally understand and can demonstrate**. If AI built much of it, be truthful: "I built this with AI assistance, then tested, modified and learned the components." Do not claim experience you cannot discuss.

## Show an interviewer in three minutes

1. Launch `run_windows.bat`, open `http://127.0.0.1:8765`, and explain the live metrics.
2. Open Task Manager and compare its CPU/RAM totals with TechPulse (small timing differences are normal).
3. Explain the two colored history lines and switch the history window.
4. Open `app/monitor.py`, show `psutil` and the threshold rules.
5. Open `app/storage.py`, explain how each sample is saved in SQLite and fetched through the API.
6. Click **Export data**, open the CSV, and explain its columns.
7. If Windows Event Log access works, show one failed-login event ID/timestamp; otherwise explain why access can be restricted. Never create failed login attempts for a demo.
8. Run `python -m pytest -q` and explain what is tested.

## Concepts to understand in simple words

**API:** A messenger between the browser and Python. The browser requests `/api/overview`; Python returns the current numbers as JSON.

**JSON:** A structured way to package values so the interface can display them.

**SQLite:** A database kept inside one local file. This stores measurements so the chart can show earlier activity.

**Backend:** Python handles monitoring, data storage, security-event queries and API responses.

**Frontend:** HTML is the structure, CSS controls the look, and JavaScript requests data and updates charts.

**Threshold alert:** A rule such as `RAM >= 85%` causes a warning; it doesn't diagnose the root cause by itself.

**Unit test:** A small automated check that proves a piece of code behaves as expected in defined circumstances.

**CI (GitHub Actions):** A service that runs tests each time code is pushed, helping catch breaks before merging changes.

**Localhost:** A network address (`127.0.0.1`) that points to your own computer. It is not a public web deployment.

## Interview questions you should expect

**Q: Why did you choose FastAPI?** It makes it straightforward to define Python API routes, validate user input, and generate interactive API documentation.

**Q: Why not use PostgreSQL?** SQLite is enough for a single-user, single-device MVP. PostgreSQL would make more sense if many users or machines were writing concurrently.

**Q: How do you calculate network speed?** Compare the cumulative bytes sent/received between two samples and divide the difference by elapsed seconds. The first sample has no prior interval, so it reports zero.

**Q: How is sensitive information protected?** The app is configured to listen on localhost, stores only numerical system metrics in SQLite, does not persist the process list, and reduces failed-sign-in events to IDs and timestamps. This is a sensible local-only default, not a substitute for security controls if deployed over a network.

**Q: What is a false positive?** A warning that looks suspicious but has a harmless explanation. A Windows Event 4625 means a login failed, not that an attacker succeeded.

**Q: What is one technical trade-off?** A 15-second polling interval gives a useful experience with modest local overhead. Faster polling would increase detail but could use more CPU and disk.

**Q: What would you improve next?** First test Windows installation and Event Log permissions, then add a properly tested event log dashboard, longer-term metrics aggregation, and a signed desktop installer.

**Q: Did you write every line of code yourself?** Never say yes if you didn't. Explain honestly what you used AI to generate, which tests you ran, what defects you found, and which improvements you personally made.

## Honest future resume bullet (only once you have successfully run and demonstrated it)

**TechPulse — Local PC Health & Security Monitor | Python, FastAPI, SQLite, psutil, JavaScript**
- Built and tested a local PC monitoring application that records 15-second CPU, memory, disk and network metrics, persists history in SQLite and visualizes trends with a responsive web dashboard.
- Implemented explainable resource alerts, CSV export, top-process reporting and optional Windows failed-sign-in event summaries; added API/database unit tests and cross-platform CI configuration.

Do not advertise the Windows event feature as tested on Windows until you have verified it on your computer.
