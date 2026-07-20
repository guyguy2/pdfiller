# Next Session Handoff

Last worked: 2026-07-20. Improvement plan C/U/A/P/S items are complete; shipped as 1.3.0.

## State

- Branch `main`; version **1.3.0** in `pyproject.toml` and `pdfiller/__init__.py`.
- 378 tests pass (`uv run pytest tests/ -q`); keep `ruff check` / `ruff format --check` clean.
- All review-plan work items closed (see `docs/IMPROVEMENTS.md` appendix). Remaining backlog is feature ideas F1-F13 only.

## This session closed

- **A5** - `fill()` non-fillable box + image placements (+ tests).
- **P8** - gitignore for filled examples, local BSA blank form, `.claude/skills/`, `.firecrawl/`.
- **1.3.0** - CHANGELOG `[Unreleased]` batch moved under `[1.3.0] - 2026-07-20`; version bumped.

## If continuing product work

Prefer **F6** (config file `~/.pdfiller/config.toml`) as the next feature: natural home for date format, flatten default, output naming, and other defaults currently split across flags and `_meta`.

## Module map

- `pdfiller/fields.py` - widget-type predicates
- `pdfiller/overlays.py` - overlay dataclasses + apply helpers
- `pdfiller/flatten.py` - flatten_to_file + widget render/strip
- `pdfiller/core.py` - `PDFFiller` facade (includes `fill()` placement discrimination)

## Per-item workflow

Implement, add tests per verify criterion, run `uv run pytest tests/ -q` and ruff, update CHANGELOG.md, move items in IMPROVEMENTS.md, then commit.
