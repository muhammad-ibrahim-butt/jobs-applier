# Jobs Applier

[![CI](https://github.com/Ibrahim8325/jobs-applier/actions/workflows/ci.yml/badge.svg)](https://github.com/Ibrahim8325/jobs-applier/actions/workflows/ci.yml)

A local-first job scraping and auto-application service. Scrapes listings from **LinkedIn, Indeed, and Glassdoor** via [Apify](https://apify.com), filters matches against your criteria, and auto-applies through **Playwright** — with email summaries after each run.

Built for developers who want to automate repetitive job applications while keeping full control of their data, credentials, and apply limits.

## Features

- **Multi-board scraping** — LinkedIn, Indeed, and Glassdoor in a single Apify run
- **Smart filtering** — keyword include/exclude, remote-only, salary floor, recency, company blocklists
- **Auto-apply adapters** — LinkedIn Easy Apply, Greenhouse, and Lever
- **Daily apply cap** — prevents over-application and account risk
- **Email notifications** — HTML summary after each pipeline run
- **Persistent browser session** — log in once, session saved locally
- **Q&A cache** — remembers answers to recurring screening questions
- **Dry-run mode** — fill forms without submitting
- **Local daemon** — runs on a schedule while your machine is on

## Architecture

```
Apify Scraper → Normalizer → Filter Engine → Apply Router
                                                  ├── LinkedIn Easy Apply
                                                  ├── Greenhouse
                                                  ├── Lever
                                                  └── Skip (unsupported)
                              ↓
                         SQLite + Email
```

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- [Apify](https://apify.com) account and API token
- Chromium (installed via Playwright)

### Install

```powershell
git clone https://github.com/Ibrahim8325/jobs-applier.git
cd jobs-applier
uv sync
uv run playwright install chromium
```

### Configure

```powershell
uv run jobs-applier init
```

Edit the generated files:

| File | Purpose |
|------|---------|
| `.env` | Apify token, SMTP credentials, paths, daily cap |
| `profile.yaml` | Your name, email, phone, work auth, default answers |
| `config.yaml` | Search queries, platforms, filter rules |
| `resume.pdf` | Your resume (path set in `.env`) |

**Required `.env` values:**

```env
APIFY_API_TOKEN=your_apify_token
SMTP_USER=your@gmail.com
SMTP_PASSWORD=your_app_password
NOTIFY_EMAIL=your@gmail.com
EMAIL_ENABLED=true
```

### LinkedIn Login (one time)

```powershell
uv run jobs-applier login linkedin
```

A browser window opens — log in manually, then press Enter in the terminal. Your session is saved to `./sessions/chromium`.

### First Run (dry run)

```powershell
uv run jobs-applier run --dry-run
```

### Production Run

```powershell
uv run jobs-applier run
```

### Daemon Mode

```powershell
uv run jobs-applier daemon
```

Runs the pipeline every `RUN_INTERVAL_MINUTES` (default: 120) while the process is alive.

## CLI Reference

| Command | Description |
|---------|-------------|
| `jobs-applier init` | Create config files and data directories |
| `jobs-applier login linkedin` | Interactive LinkedIn session bootstrap |
| `jobs-applier scrape` | Scrape and filter only (no apply) |
| `jobs-applier run` | Full pipeline: scrape → filter → apply → email |
| `jobs-applier run --dry-run` | Fill forms without submitting |
| `jobs-applier daemon` | Scheduled loop |
| `jobs-applier status` | Today's apply count and recent history |

## Configuration Reference

See [`.env.example`](.env.example), [`config.example.yaml`](config.example.yaml), and [`profile.example.yaml`](profile.example.yaml) for all options.

Key settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `DAILY_APPLY_CAP` | 25 | Max applications per day |
| `RUN_INTERVAL_MINUTES` | 120 | Daemon interval |
| `DRY_RUN` | false | Global dry-run toggle |
| `APIFY_ACTOR_ID` | openclawai/job-board-scraper | Apify actor to use |

## Project Structure

```
src/jobs_applier/
├── cli.py              # Typer CLI
├── config/             # Settings + YAML loaders
├── scrapers/           # Apify client + normalizer
├── filters/            # Filter engine
├── apply/              # Playwright adapters
├── pipeline/           # Orchestrator
├── storage/            # SQLite repositories
├── notifications/      # Email
└── scheduler/          # Daemon
```

## Development

```powershell
uv sync --all-extras --dev
uv run ruff check src tests
uv run ruff format src tests
uv run mypy src/jobs_applier
uv run pytest -v
```

## Ethics & Disclaimer

This tool is intended for **personal use only**. Automated job applications may violate platform Terms of Service. Use responsibly:

- Set reasonable daily apply caps
- Only apply to jobs you're genuinely qualified for
- Review your profile and resume before enabling auto-apply
- Respect rate limits and platform policies

The authors are not responsible for any account restrictions or consequences resulting from use of this tool.

## Roadmap

- [ ] Workday / iCIMS adapters
- [ ] Optional LLM for unknown screening questions
- [ ] Cover letter generation per job
- [ ] Local web dashboard
- [ ] Apify webhook trigger mode

## License

MIT — see [LICENSE](LICENSE).
