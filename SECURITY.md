# Security Policy

## Reporting a vulnerability

If you discover a security issue in Jobs Applier, please email the maintainer listed in `pyproject.toml` (or open a private GitHub security advisory) **before** public disclosure.

Do not file a public issue that includes credentials, session cookies, or sample `.env` files with real secrets.

## Secrets and local data

Never commit:

- `.env` (API tokens, SMTP passwords)
- `profile.yaml` (PII)
- `sessions/` (browser cookies / LinkedIn login state)
- `data/` (SQLite DB, question cache)
- `resume.pdf` or other personal documents

This repository ships only `*.example` templates. Run `jobs-applier init` to create local copies.

If you accidentally push secrets:

1. Rotate the exposed token/password immediately (Apify, SMTP, etc.)
2. Remove the file from git history (`git filter-repo` / BFG)
3. Force-push only if you understand the impact on collaborators

## LinkedIn sessions

The Chromium user-data directory under `sessions/` is equivalent to being logged in. Treat it like a password. Do not share or upload that folder.
