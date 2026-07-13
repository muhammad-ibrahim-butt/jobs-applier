# Setup Guide

Instructions for running Jobs Applier on your machine. For a short overview, see the [README](../README.md).

## 1. Install prerequisites

### Python and uv

**Windows (PowerShell):**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
git clone https://github.com/muhammad-ibrahim-butt/jobs-applier.git
cd jobs-applier
uv sync
uv run playwright install chromium
```

**macOS / Linux:**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
git clone https://github.com/muhammad-ibrahim-butt/jobs-applier.git
cd jobs-applier
uv sync
uv run playwright install chromium
```

### Apify account

1. Sign up at [apify.com](https://apify.com)
2. Settings → Integrations → API tokens
3. Put the token in `.env` as `APIFY_API_TOKEN`

The default actor charges per result. Start with a low `max_results` in `config.yaml`.

### Email (optional)

**Gmail (port 587 + STARTTLS):**

1. Enable 2FA
2. Create an [App Password](https://myaccount.google.com/apppasswords)
3. Set:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=your_app_password
NOTIFY_EMAIL=you@gmail.com
EMAIL_ENABLED=true
```

**cPanel / Namecheap-style hosts (port 465 + SSL):**

```env
SMTP_HOST=mail.yourdomain.com
SMTP_PORT=465
SMTP_USE_SSL=true
SMTP_USER=you@yourdomain.com
SMTP_PASSWORD=your_mailbox_password
NOTIFY_EMAIL=you@gmail.com
EMAIL_ENABLED=true
```

Verify with:

```bash
uv run jobs-applier test-email
```

## 2. Initialize configuration

```bash
uv run jobs-applier init
```

Edit `.env`, `profile.yaml`, `config.yaml`, and place your resume at `RESUME_PATH`.

## 3. LinkedIn session

```bash
uv run jobs-applier login linkedin
```

1. Log in in the Chromium window (complete CAPTCHA/checkpoint if shown)
2. Wait until you see your feed
3. Press Enter in the terminal

Session files live in `./sessions/chromium` (gitignored).

## 4. Dry run, then live

```bash
uv run jobs-applier run --dry-run
uv run jobs-applier status
uv run jobs-applier run
```

## 5. Keep it running

### Daemon (cross-platform)

```bash
uv run jobs-applier daemon
```

Repeats every `RUN_INTERVAL_MINUTES`.

### Windows Task Scheduler

```powershell
.\scripts\install-task.ps1
```

### macOS / Linux cron (example: every 2 hours)

```cron
0 */2 * * * cd /path/to/jobs-applier && /path/to/uv run jobs-applier run >> /tmp/jobs-applier.log 2>&1
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `APIFY_API_TOKEN is required` | Set token in `.env` |
| Config file not found | Run `jobs-applier init` from repo root |
| LinkedIn login / checkpoint | Delete `sessions/chromium` and login again; finish CAPTCHA before Enter |
| Email connection closed on 465 | Use `SMTP_USE_SSL=true` (or port 587 + STARTTLS) |
| Filtered 0 jobs | Check `remote_only`, keywords, and whether LinkedIn scrape succeeded |
| Daily cap reached | Wait or raise `DAILY_APPLY_CAP` |

## Data locations

| Path | Contents |
|------|----------|
| `./data/applications.db` | Job and application history |
| `./data/questions.json` | Cached form answers |
| `./sessions/chromium` | Browser profile (sensitive) |
| `./profile.yaml` | Applicant profile (gitignored) |
| `./.env` | Secrets (gitignored) |
