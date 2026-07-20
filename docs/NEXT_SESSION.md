# Next Session Handoff

Last updated: 2026-07-20. Full log: `docs/IMPROVEMENTS.md`.

## Snapshot

- Branch `main`; version **1.4.0** (F6 user config shipped).
- Review C/U/A/P/S and F6: all done. Product backlog only: F1-F5, F7-F13.
- Tests: `uv run pytest tests/ -q`; keep ruff clean.

## Next work

No required queue. Optional product picks: F5 (rich CLI), F4 (field grouping), F1 (PDF/A), or other F*.

## F6 one-liner

`~/.pdfiller/config.toml` / `$PDFILLER_CONFIG`: `date_format`, `flatten`, `auto_fill_dates`, `output_suffix`. Fill without `-o` -> `<stem>_filled.pdf`. Precedence: flag > config > `_meta` > built-in.
