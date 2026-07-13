# Jobs Applier

[![CI](https://github.com/muhammad-ibrahim-butt/jobs-applier/actions/workflows/ci.yml/badge.svg)](https://github.com/muhammad-ibrahim-butt/jobs-applier/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Local job search assistant:** scrape remote roles, auto-apply where the ATS is reliable, and email yourself everything else — without uploading your resume to a SaaS.

**Apify is optional.** When cloud scrape credits run out, the app falls back to local JobSpy plus free Remotive / RemoteOK APIs.

```
Discover (Apify → JobSpy → Remotive → RemoteOK)
    → Filter (remote, salary, relevance)
    → Auto-apply (LinkedIn Easy Apply · Greenhouse · Lever · Ashby)
    → One email with jobs that need your click
```

## Why this exists

Most auto-appliers either spam LinkedIn Easy Apply only, or lock discovery behind a paid API. This project is for people who:

- Want **privacy** (profile, resume, and browser session stay on your machine)
- Need **fallbacks** when Apify free tier is exhausted
- Prefer a **digest** for company sites you still want to review by hand

## Features

- Multi-source scraping with fallback (Apify → JobSpy → Remotive → RemoteOK)
- Config-driven filters (remote-only, keywords, blocklists, relevance, recency)
- Auto-apply: LinkedIn Easy Apply (when flagged), Greenhouse, Lever, Ashby — with ATS handoff from LinkedIn when possible
- One practical email per run
- Daily apply cap, dry-run mode, SQLite history
- Daemon / Task Scheduler while your PC is on

## Quick start

**Prerequisites:** Python 3.11+, [uv](https://docs.astral.sh/uv/), Playwright Chromium. Apify token only if you enable the `apify` scrape source.

```bash
git clone https://github.com/muhammad-ibrahim-butt/jobs-applier.git
cd jobs-applier
uv sync
uv run playwright install chromium
uv run jobs-applier init
```

Edit `.env`, `profile.yaml`, `config.yaml`, put your resume at `RESUME_PATH`.

**Apify optional** — leave `APIFY_API_TOKEN` empty and keep `jobspy` / `remotive` / `remoteok` in `search.sources` (see `config.example.yaml`).

```bash
uv run jobs-applier login linkedin   # once
uv run jobs-applier test-email       # optional
uv run jobs-applier run --dry-run
uv run jobs-applier run
uv run jobs-applier daemon           # every RUN_INTERVAL_MINUTES
```

Windows schedule without a long-lived terminal: [`scripts/install-task.ps1`](scripts/install-task.ps1).

Full setup: [docs/SETUP.md](docs/SETUP.md). Sharing / outreach notes: [docs/SHOWCASE.md](docs/SHOWCASE.md).

## CLI

| Command | Description |
|---------|-------------|
| `jobs-applier init` | Create config files and data dirs |
| `jobs-applier login linkedin` | Save LinkedIn browser session |
| `jobs-applier scrape` | Scrape + filter only |
| `jobs-applier run` | Full pipeline |
| `jobs-applier run --dry-run` | Fill forms, do not submit |
| `jobs-applier test-email` | Verify SMTP |
| `jobs-applier daemon` | Scheduled loop |
| `jobs-applier status` | Today's applies + history |

## Configuration

Examples: [`.env.example`](.env.example), [`config.example.yaml`](config.example.yaml), [`profile.example.yaml`](profile.example.yaml).

| Variable | Default | Description |
|----------|---------|-------------|
| `DAILY_APPLY_CAP` | 25 | Max auto-apply attempts per day |
| `RUN_INTERVAL_MINUTES` | 180 | Daemon interval (keep high on free scrape tiers) |
| `DRY_RUN` | false | Global dry-run |
| `APIFY_ACTOR_ID` | openclawai/job-board-scraper | Optional Apify actor |

**Never commit** `.env`, `profile.yaml`, `sessions/`, `data/`, or resumes. See [SECURITY.md](SECURITY.md).

## Development

```bash
uv sync --extra dev
uv run ruff check src tests
uv run ruff format src tests
uv run mypy src
uv run pytest -v
```

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Ethics & disclaimer

Personal use only. Automated applications may violate job-board Terms of Service. You are responsible for reasonable caps, qualified applications, and compliance with platform rules. Authors are not liable for account restrictions.

## Roadmap

- [ ] Workday adapter
- [ ] Optional LLM for unknown screening questions
- [ ] Cover letter generation
- [ ] Local dashboard

## License

MIT — see [LICENSE](LICENSE).
