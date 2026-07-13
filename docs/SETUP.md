# Setup Guide

Detailed setup instructions for Windows.

## 1. Install Prerequisites

### Python and uv

```powershell
# Install uv (if not installed)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Clone and install
cd C:\Projects\jobs-applier
uv sync
uv run playwright install chromium
```

### Apify Account

1. Sign up at [apify.com](https://apify.com)
2. Go to **Settings → Integrations → API tokens**
3. Copy your token to `.env` as `APIFY_API_TOKEN`

The default actor (`openclawai/job-board-scraper`) charges per result. Start with `max_results: 25` in `config.yaml` to control costs.

### Gmail SMTP (App Password)

1. Enable 2FA on your Google account
2. Go to [Google App Passwords](https://myaccount.google.com/apppasswords)
3. Generate a password for "Mail"
4. Set in `.env`:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@gmail.com
SMTP_PASSWORD=your_16_char_app_password
NOTIFY_EMAIL=your@gmail.com
EMAIL_ENABLED=true
```

## 2. Initialize Configuration

```powershell
uv run jobs-applier init
```

Edit these files with your real data:

- **`profile.yaml`** — name, email, phone, work authorization, screening question defaults
- **`config.yaml`** — search queries, location, filter rules
- **`.env`** — secrets and paths
- **`resume.pdf`** — place your resume in the project root (or update `RESUME_PATH`)

## 3. LinkedIn Session

```powershell
uv run jobs-applier login linkedin
```

1. A Chromium window opens to LinkedIn login
2. Log in with your credentials
3. Once you see your feed, return to the terminal and press **Enter**
4. Session is saved to `./sessions/chromium` (gitignored)

You only need to do this once unless the session expires.

## 4. Test with Dry Run

```powershell
uv run jobs-applier run --dry-run
```

This will:
- Scrape jobs via Apify
- Filter against your rules
- Open Easy Apply forms and fill them
- **Not** click Submit

Check the terminal output and `jobs-applier status` for results.

## 5. Production Run

```powershell
uv run jobs-applier run
```

## 6. Run as Daemon

### Option A: Long-running process

```powershell
uv run jobs-applier daemon
```

Keep this terminal open (or run in background). Pipeline runs every `RUN_INTERVAL_MINUTES`.

### Option B: Windows Task Scheduler

Run the helper script as Administrator:

```powershell
.\scripts\install-task.ps1
```

This registers a task that runs `uv run jobs-applier run` every 2 hours while you're logged in.

To start at login instead, open Task Scheduler and change the trigger to **At log on**.

## 7. Monitoring

```powershell
# Check today's apply count and recent history
uv run jobs-applier status

# Scrape only (no apply) to preview matches
uv run jobs-applier scrape
```

Email summaries are sent after each `run` or daemon cycle if `EMAIL_ENABLED=true`.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `APIFY_API_TOKEN is required` | Set token in `.env` |
| `Config file not found` | Run `jobs-applier init` |
| LinkedIn login fails | Delete `./sessions/chromium` and run `login linkedin` again |
| Easy Apply button not found | Job may not be Easy Apply; check `easy_apply_only` in config |
| Email not sending | Verify SMTP credentials; test with `EMAIL_ENABLED=true` |
| Daily cap reached | Wait until next day or increase `DAILY_APPLY_CAP` |
| Unknown form questions | Add answers to `profile.yaml` defaults; they auto-cache in `data/questions.json` |

## Data Locations

| Path | Contents |
|------|----------|
| `./data/applications.db` | Job and application history |
| `./data/questions.json` | Cached form answers |
| `./sessions/chromium` | Browser session (LinkedIn cookies) |
| `./profile.yaml` | Your applicant profile (gitignored) |
| `./.env` | Secrets (gitignored) |
