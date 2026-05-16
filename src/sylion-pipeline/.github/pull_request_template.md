# Pull Request

## Summary

<!-- One-line description of what this PR does. -->

## Related issue / ticket

<!-- Link: Closes #<issue>, Fixes #<issue>, Refs #<issue> -->

## Type of change

- [ ] Bug fix (non-breaking)
- [ ] New feature (non-breaking)
- [ ] Breaking change (requires version bump + migration guide)
- [ ] Refactor / code quality
- [ ] CI / tooling
- [ ] Documentation only
- [ ] Security fix

---

## Checklist

### Tests
- [ ] New or updated unit tests added for changed logic (`tests/`)
- [ ] `pytest tests/ --cov --cov-fail-under=75` passes locally
- [ ] No existing tests broken

### Security & compliance
- [ ] `bandit -r . -ll` has no new HIGH/CRITICAL findings
- [ ] `safety check --file requirements.in` passes (no known CVEs introduced)
- [ ] No secrets, API keys, or passwords committed (checked with `gitleaks detect`)
- [ ] `.env.example` updated if new env vars were added (`python scripts/env_lint.py`)

### Code quality
- [ ] `ruff check .` passes (no lint errors)
- [ ] `ruff format .` applied (or `--check` passes)
- [ ] `mypy .` passes (or new ignores are documented)
- [ ] Agent manifest is valid: `python scripts/validate_agents_manifest.py --strict`

### Documentation
- [ ] `CHANGELOG.md` updated (under `[Unreleased]` section)
- [ ] Docstrings added/updated for public functions and classes
- [ ] README updated if CLI interface or configuration changed
- [ ] Relevant `docs/` files updated (FAQ, quickstart, migration guide, etc.)

### Architecture Decision Records (ADR)
- [ ] If this PR introduces a significant architectural decision: new `docs/ADR_XXXX_*.md` created
- [ ] If this PR resolves or supersedes an existing ADR: that ADR is updated

### Deployment / ops
- [ ] `requirements.in` updated if new dependencies added (run `scripts/regen-lock.sh` to update lock file)
- [ ] Dockerfile updated if runtime environment changed
- [ ] No migration required — OR — migration script provided in `migrations/`

---

## Testing notes

<!-- How to manually test / reproduce the fix. Steps, commands, or screenshots. -->

## Screenshots / recordings (UI changes)

<!-- Attach before/after screenshots or screen recordings if the dashboard changed. -->

## Reviewer notes

<!-- Anything specific reviewers should focus on or be aware of. -->
