# Contributing

Thanks for helping improve Jobs Applier.

## Setup

```bash
git clone https://github.com/Ibrahim8325/jobs-applier.git
cd jobs-applier
uv sync --all-extras --dev
uv run playwright install chromium
```

## Checks (required for PRs)

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src/jobs_applier
uv run pytest -v
```

CI runs the same suite on Python 3.11–3.13.

## Guidelines

- Keep diffs focused; match existing style and layering (scrape → filter → apply → notify).
- Prefer fixing shared helpers once over per-call-site patches.
- Do not commit secrets, real `profile.yaml`, sessions, or resumes.
- Add/adjust unit tests for pure logic (filters, normalizer, router). Avoid live Apify/LinkedIn in CI.
- Update README or `docs/SETUP.md` when behavior or config changes.

## Pull requests

1. Fork and create a feature branch
2. Make changes + tests
3. Open a PR with a short summary and test plan

By contributing, you agree that your contributions are licensed under the MIT License.
