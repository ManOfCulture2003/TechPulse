# TechPulse development roadmap

## MVP — implemented in source
- [x] Read-only local CPU/RAM/disk/network monitor
- [x] Persistent history with seven-day retention
- [x] Responsive browser dashboard with custom chart
- [x] Threshold alerts with understandable advice
- [x] API and UI sample freshness states, preventing stale saved readings from looking healthy
- [x] Collector lifecycle/failure diagnostics and live-alert gating; failed collection and lost dashboard connections no longer look healthy
- [x] Readiness-aware Windows launcher, dependency repair and clear startup failure handling (automated tests; real Windows-PC verification still pending)
- [x] Top memory-consuming processes
- [x] CSV export and REST endpoints
- [x] Privacy-minimized downloadable diagnostic JSON report with SQL aggregate summaries and historical sampling-gap estimates
- [x] Optional minimal Windows 4625 event view with access errors handled
- [x] Automated tests and GitHub Actions configuration
- [ ] **Validate installation and Windows event query on the owner's actual PC**
- [x] **Confirm GitHub Actions passes on the published repository** (October 28, 2026; recheck on each new PR)

## Next — after Windows smoke testing
1. Improve data quality: timestamps, missing samples, performance benchmarks and time-zone support.
2. Add a safe, opt-in system tray app and explicit startup control (no hidden service).
3. Add nontechnical health explanations and exportable diagnostic reports.
4. Add richer event log summaries with filters and configurable time windows (no raw usernames stored).
5. Add unit tests for threshold transitions and end-to-end Windows tests.
6. Add a signed installer and automatic release packaging.

## Advanced — optional portfolio expansion
- **Data engineering:** rollups, trend analysis, daily/weekly reports and retention settings.
- **Security:** Windows Defender status via documented local APIs, read-only firewall posture and audit event triage. Label all indicators carefully and avoid overclaiming malware detection.
- **Deployment:** Docker demo using mocked telemetry, GitHub Actions release artifacts, dependency vulnerability scanning and versioned API contracts.
- **Product:** accessible onboarding, consent-based notifications, dark/light mode, process search, user-feedback loop.

A useful engineering project is not measured by how many frameworks it lists. Keep each new feature small, tested and explainable.
