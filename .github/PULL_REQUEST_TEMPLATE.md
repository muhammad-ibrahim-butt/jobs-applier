## Summary
<!-- What changed and why -->

## Test plan
- [ ] `uv run ruff check src tests`
- [ ] `uv run mypy src/jobs_applier`
- [ ] `uv run pytest -v`
- [ ] No secrets (`.env`, `profile.yaml`, sessions, resumes) in the diff
