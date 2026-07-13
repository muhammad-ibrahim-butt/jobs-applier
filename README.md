# Jobs Applier

[![CI](https://github.com/muhammad-ibrahim-butt/jobs-applier/actions/workflows/ci.yml/badge.svg)](https://github.com/muhammad-ibrahim-butt/jobs-applier/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Local-first job scraper and auto-applier. Discovers jobs via **Apify**, local **JobSpy**, and free APIs (**Remotive**, **RemoteOK**) — if one source fails, the next runs. Filters for remote matches, auto-applies where reliable (LinkedIn Easy Apply, Greenhouse, Lever, Ashby), and **emails you** one clear summary with job cards when you must apply yourself.

Your credentials, resume, and browser session stay on your machine.

## Features

- Multi-source scraping with fallback (Apify → JobSpy → Remotive → RemoteOK)
- Config-driven filters (remote-only, keywords, blocklists, relevance, recency)
- Auto-apply adapters: LinkedIn Easy Apply, Greenhouse, Lever, Ashby
- One practical email per run (what applied + links you still need to open)
- Daily apply cap, dry-run mode, SQLite history
- SMTP notifications (Gmail, Namecheap/cPanel, etc.)
- Daemon / scheduled runs while your PC is on

## Architecture

```
Scrape sources (fallback / merge)
  ├── Apify actor
  ├── Local JobSpy (LinkedIn / Indeed)
  ├── Remotive API
  └── RemoteOK API
          ↓
Filter → Apply Router
            ├── LinkedIn Easy Apply
            ├── Greenhouse / Lever / Ashby
            └── Email summary (manual apply)
                      ↓
               SQLite + SMTP
```

## Quick start

**Prerequisites:** Python 3.11+, [uv](https://docs.astral.sh/uv/), [Apify](https://apify.com) token, Chromium via Playwright.

### Install

```bash
git clone https://github.com/muhammad-ibrahim-butt/jobs-applier.git
cd jobs-applier
uv sync
uv run playwright install chromium
```

Windows (PowerShell) is the same once `uv` is installed.

Run all commands from the **repository root** (config paths are relative to the current working directory).

### Configure

```bash
uv run jobs-applier init
```

| File | Purpose |
|------|---------|
| `.env` | Apify token, SMTP (optional), caps, paths |
| `profile.yaml` | Your applicant details and default answers |
| `config.yaml` | Search queries, platforms, filters |
| `resume.pdf` | Resume path from `RESUME_PATH` |

Minimal `.env`:

```env
APIFY_API_TOKEN=your_apify_token
EMAIL_ENABLED=false
```

To enable email digests / run summaries:

```env
EMAIL_ENABLED=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=your_app_password
NOTIFY_EMAIL=you@gmail.com
```

Use port **465** + `SMTP_USE_SSL=true` for hosts that require SSL (e.g. many cPanel providers).

See [docs/SETUP.md](docs/SETUP.md) for Windows Task Scheduler, SMTP details, and troubleshooting.

### Login once (LinkedIn)

```bash
uv run jobs-applier login linkedin
```

Complete any checkpoint/CAPTCHA in the browser, wait for your feed, then press Enter.

### Dry run, then live

```bash
uv run jobs-applier test-email          # optional SMTP check
uv run jobs-applier run --dry-run       # fill forms, do not submit
uv run jobs-applier run                 # apply + email digests
uv run jobs-applier daemon              # repeat every RUN_INTERVAL_MINUTES
uv run jobs-applier status
```

## CLI

| Command | Description |
|---------|-------------|
| `jobs-applier init` | Create config files and data dirs |
| `jobs-applier login linkedin` | Save LinkedIn browser session |
| `jobs-applier scrape` | Scrape + filter only |
| `jobs-applier run` | Full pipeline |
| `jobs-applier run --dry-run` | No form submit |
| `jobs-applier test-email` | Verify SMTP |
| `jobs-applier daemon` | Scheduled loop |
| `jobs-applier status` | Today's applies + history |

## Configuration

Examples: [`.env.example`](.env.example), [`config.example.yaml`](config.example.yaml), [`profile.example.yaml`](profile.example.yaml).

| Variable | Default | Description |
|----------|---------|-------------|
| `DAILY_APPLY_CAP` | 25 | Max auto-apply attempts per day |
| `RUN_INTERVAL_MINUTES` | 120 | Daemon interval |
| `DRY_RUN` | false | Global dry-run |
| `APIFY_ACTOR_ID` | openclawai/job-board-scraper | Scraper actor |

**Costs:** Apify charges per scraped result. Keep `max_results` low while testing.

**Never commit** `.env`, `profile.yaml`, `sessions/`, `data/`, or resumes. See [SECURITY.md](SECURITY.md).

## Development

```bash
uv sync --all-extras --dev
uv run ruff check src tests
uv run ruff format src tests
uv run mypy src/jobs_applier
uv run pytest -v
```

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Ethics & disclaimer

Personal use only. Automated applications may violate job-board Terms of Service. You are responsible for:

- Reasonable daily caps
- Applying only to roles you are qualified for
- Reviewing profile/resume before live runs
- Compliance with local laws and platform rules

Authors are not liable for account restrictions or other consequences.

## Roadmap

- [ ] Workday / iCIMS adapters
- [ ] Optional LLM for unknown screening questions
- [ ] Cover letter generation
- [ ] Local dashboard

## License

MIT — see [LICENSE](LICENSE).
