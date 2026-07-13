# Showcase & outreach

Copy-paste material to help others find [jobs-applier](https://github.com/muhammad-ibrahim-butt/jobs-applier). Prefer **your own results** (jobs emailed, time saved) over hype.

## One-liner

> Local open-source job scraper + apply helper: Apify optional, JobSpy/Remotive/RemoteOK fallbacks, Greenhouse/Lever/Ashby auto-apply, email digest for the rest. Your resume stays on your machine.

## GitHub topics (Settings → Topics)

Suggested tags:

`job-search` `remote-jobs` `playwright` `linkedin` `python` `open-source` `automation` `apify` `greenhouse` `jobspy`

## Show HN (draft)

**Title:** Show HN: Local job applier with Apify fallbacks (JobSpy + Remotive)

**Body:**

I built a local job search assistant after free Apify credits ran out mid-week.

- Discovers jobs via Apify (optional), local JobSpy, Remotive, and RemoteOK
- Filters for remote / relevance / salary floor
- Auto-applies on LinkedIn Easy Apply (when present), Greenhouse, Lever, Ashby
- Emails one summary for everything else
- Profile, resume, and browser session never leave the machine

Repo: https://github.com/muhammad-ibrahim-butt/jobs-applier

Not trying to spam 500 applications a day — daily caps and digests are intentional.

## LinkedIn post (draft)

I open-sourced the tool I use to find remote software roles without babysitting ten job boards.

Jobs Applier runs on my laptop:

1. Scrapes (Apify if I have credits, otherwise JobSpy / Remotive / RemoteOK)
2. Filters for fit
3. Auto-applies where ATS support is solid
4. Emails me the rest to apply manually

If you are job hunting and want something local + MIT licensed:
https://github.com/muhammad-ibrahim-butt/jobs-applier

## Reddit note

Be careful in career subreddits: disclose automation, discourage ToS abuse, and emphasize **quality filters + human-in-the-loop email**. r/Python and local remote-work communities are usually a better fit than “how do I mass-apply.”

## Demo checklist (record yourself)

1. `jobs-applier run --dry-run` log (scrape → filter → summary)
2. Inbox screenshot of “N jobs need your apply”
3. `jobs-applier status` after a few days of use

Replace placeholders with real numbers after one week of honest use — that converts better than stars.
