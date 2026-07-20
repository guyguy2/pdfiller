# PDFiller Improvement Plan

Actionable improvements from a full architecture and UX review (2026-07-19) of `core.py`, `cli.py`, `memory.py`, `exceptions.py`, tests, packaging, and docs.

This file is the project **memory and log**: what is done, what is in flight, and what is still backlog. Pair with `docs/NEXT_SESSION.md` for a short handoff; keep durable detail here.

Each item has a stable ID (C = correctness, U = UX/CLI, A = architecture, P = packaging/tooling, S = security/privacy, F = feature idea), an effort tag, and a verification criterion where applicable.

Effort: **S** = under an hour, **M** = a few hours, **L** = a day or more.

---

## Status (2026-07-20)

| Area | State |
|------|--------|
| Review plan C/U/A/P/S items | **Done** (appendix) |
| **A5** `fill()` box/image placements | **Done**, released in **1.3.0** |
| **P8** example / PII hygiene | **Done**, released in **1.3.0** |
| **F6** user config.toml | **Done**, released in **1.4.0** |
| Package version | **1.4.0** |
| Working tree expectation | Clean after 1.4.0 commit |
| Tests | 394 pass (`uv run pytest tests/ -q`); keep ruff clean |
| Remaining product backlog | F1-F5, F7-F13 (section 7) |

All review-plan items and F6 are complete. No required next step; product features are optional.

---

## 1. Next session

No open ship queue. If continuing product work, pick from section 7 (opportunistic):

| Order | Item | Notes |
|-------|------|--------|
| 1 | F5 Rich CLI | Tables/progress; low risk UX polish |
| 2 | F4 Field grouping | Builds on defaults / batch mental model |
| 3 | F1 PDF/A | Compliance-oriented; needs research |
| - | F2, F3, F7-F13 | Larger or niche; only if a real need appears |

Per-item workflow: implement, tests, `uv run pytest tests/ -q` + ruff, CHANGELOG, move item to appendix, commit.

### F6 reference (released 1.4.0)

User config at `~/.pdfiller/config.toml` or `$PDFILLER_CONFIG`.

```toml
date_format = "%Y-%m-%d"
flatten = true
auto_fill_dates = true
output_suffix = "_filled"
```

| Key | Meaning |
|-----|---------|
| `date_format` | strftime for auto-filled date fields |
| `flatten` | default flatten for fill/batch (`--no-flatten` overrides) |
| `auto_fill_dates` | default auto-date on/off (`--no-auto-dates` overrides) |
| `output_suffix` | when fill omits `-o`, write `<stem><suffix>.pdf` next to input (default `_filled`) |

API: `pdfiller.Config`, `load_config()`, `default_output_path()`.  
Date format precedence: **flag > config.toml > `_meta.date_format` > built-in M/D/YYYY**.  
Dependency: `tomli` only for Python &lt; 3.11 (stdlib `tomllib` on 3.11+).

---

## 2. Correctness and Safety

(all items completed - see appendix)

---

## 3. UX and CLI Usability

(all items completed - see appendix)

---

## 4. Architecture and Extensibility

(all items completed - see appendix)

---

## 5. Packaging, Tooling, and Tests

(all items completed - see appendix)

---

## 6. Security and Privacy

(all items completed - see appendix)

---

## 7. Feature Ideas (backlog)

### Medium-term (moderate effort)

- **F1. PDF/A output** - compliance for archival/legal use
- **F2. Watch mode** - monitor a directory, auto-fill new PDFs using a template
- **F3. Conditional logic** - fill field B only if field A has value X (medical/legal forms)
- **F4. Field grouping** - group related fields (address block) for batch operations
- **F5. Rich CLI output** - `rich` library for tables, progress bars, color

### Long-term (significant effort)

- **F7. Smart field detection for non-fillable PDFs** - detect underlines, "Name: ___" patterns to propose placements
- **F8. TUI interface** - interactive terminal UI for browsing and filling fields
- **F9. Web interface** - simple Flask/FastAPI upload-and-fill app
- **F10. Digital signature support** - cryptographic signatures, not just image stamps
- **F11. PDF merge/split** - combine filled pages from multiple PDFs
- **F12. OCR integration** - handle scanned PDFs by OCRing text positions first
- **F13. Cloud storage** - Dropbox/Google Drive integration for input/output

---

## Session log (recent)

### 2026-07-20 - Ship F6 as 1.4.0

- Committed user config feature and released **1.4.0**.
- No remaining review-plan or F6 work; backlog is optional F* only.

### 2026-07-20 (earlier) - Implement F6 (pre-release)

- Implemented `pdfiller/config.py` and wired fill/batch CLI.
- Fill without `-o` defaults to `<stem>_filled.pdf`.
- Tests + docs; then shipped as 1.4.0.

### 2026-07-20 (mid) - Close A5/P8, ship 1.3.0

- **A5** - library `fill()` box + image placements; tests; commit `b47b5d0`.
- **P8** - gitignore filled examples, local BSA form, `.claude/skills/`, `.firecrawl/`.
- Released **1.3.0** (prior unreleased batch + A5/P8).
- Review-plan C/U/A/P/S queues emptied.

### 2026-07-20 (earlier) - Large unreleased batch then 1.2.0 / 1.3.0 prep

- U6, U7, U8, U9, A1-A4, A6, S2, P4, P5+P6, P7 and related work (see appendix under 1.3.0).
- 1.2.0 breaking preserve-existing flip and C/U items (see appendix).

### 2026-07-19 - Initial plan items

- C1-C3, C6, P1 and earlier audit work (see appendix).

---

## Appendix: Completed Items

### Released as 1.4.0 (2026-07-20)

- **F6** - User config `~/.pdfiller/config.toml` (or `$PDFILLER_CONFIG`) with `date_format`, `flatten`, `auto_fill_dates`, `output_suffix`; `pdfiller.config.Config` / `load_config()` / `default_output_path()`; CLI precedence flag > config > `_meta` > built-in; fill without `-o` uses `<stem><suffix>.pdf`

### Released as 1.3.0 (2026-07-20)

- **A5** - `fill()` non-fillable placements accept point text, wrapped boxes, and images; discrimination via optional `type` or keys (`path`/`image` for images, `x0`/`rect` for boxes); helpers `_queue_fill_placement` and `_placement_rect`
- **P8** - Filled example outputs stay out of git via `examples/*_filled.pdf`; blank real-world form `examples/680-001_AB.pdf` is gitignored (local use only, not shipped); local tooling dirs `.claude/skills/` and `.firecrawl/` gitignored. Tracked examples remain the sanitized demo only. No history scrub needed (PII never committed)
- **U6** - `defaults add <key> <value>` appends to a list default (creates a one-element list if absent, promotes an existing string leaf to a two-element list); new `_add_nested` helper backs it
- **U9** - Unified read-only output via a shared `_write_output(text, path)` helper; `list`, `export`, and `template` all default to stdout and accept `-o`; `template` no longer requires `-o`
- **A4** - CLI dispatch now uses `set_defaults(func=...)` per subparser and calls `args.func(args)`; the command if-chain is gone (one special case remains for the `defaults` no-action help). Internal refactor, no user-facing change
- **A2** - Added `reset_matchers()` (exported from `pdfiller`) restoring the built-in exact/normalized matchers; added an autouse `_isolate_matchers` conftest fixture so matcher-registry state no longer leaks across tests
- **A6** - New `pdfiller/fields.py` centralizes widget-type predicates (`is_choice_widget`, `is_checkbox`, `is_checkbox_type`, `is_push_button_type`); `core` and `cli` import them, removing the duplicated choice tuples and CLI `_CHECKBOX_FIELD_TYPES`/`_PUSH_BUTTON_FIELD_TYPES`. Internal refactor, no user-facing change
- **S2** - `fill --redact` masks field values in `--verbose`/`--dry-run` output (shows names and `[redacted, N chars]`), keeping values out of logs and shell history; overlay text is redacted too
- **P4** - Added `pdfiller/py.typed` marker (ships in the wheel) so type checkers use the package's inline hints
- **P7** - Added `pytest-cov` to the dev group; `uv run pytest --cov=pdfiller` reports coverage (currently ~90%)
- **U7** - Configurable auto-date format: `date_format` strftime param on `PDFFiller`, `--date-format` flag on `fill`/`batch`, and `_meta.date_format` defaults key; later extended by F6 so precedence is flag > config > `_meta` > default M/D/YYYY
- **U8** - Encrypted PDFs now try an empty user password automatically and accept a `password` param (`--password` on all PDF-opening commands); wrong/missing password still raises `PDFReadError`
- **P5+P6** - Bumped `requires-python` to >=3.9 (dropped EOL 3.8 classifier, ruff target py39), modernized annotations to built-in generics, and switched `import fitz` to the canonical `import pymupdf` throughout source and tests
- **A3** - New `pdfiller/overlays.py` with `PointTextOverlay`/`BoxTextOverlay`/`ImageOverlay` dataclasses replacing raw overlay dicts; `_apply_text_overlays` dispatches by `isinstance`; `pending_operations` emits the same dict shape via `asdict` (public behavior unchanged). Internal refactor
- **A1** - Split overlay apply logic (`apply_text_overlays`/`apply_image_overlays`) into `overlays.py` and flattening (`flatten_to_file` plus widget-render/strip helpers) into a new `flatten.py`; `PDFFiller` methods are now thin facades. `core.py` dropped from 898 to 805 lines at A1 (later grew with A5/F6 helpers); no public API change from the split

### Released as 1.2.0 (2026-07-20)

- **C8** - Library preserve-existing default flipped to False (overwrite), matching the CLI; opt in via `preserve_existing_fields(True)`; breaking change, version bumped to 1.2.0
- **C9** - Preserve-existing skips collected during save and exposed via `skipped_operations`; `fill --verbose` prints a skip line per field; dead page-range checks removed from `_apply_text_overlays`/`_apply_image_overlays`
- **C12** - `pending_operations` extended with `text_overlays`, `image_overlays`, and computed `auto_date_fields`; `--dry-run` renders unchecks and auto-date targets
- **U4** - `batch --name-from <column>` (collision appends row sequence), reserved `_output` CSV column for per-row names, and `--map field=column` for mismatched CSV headers
- **U3** - `list` table format now shows "Page: N" for every field and "Options: [...]" for dropdown/radio/listbox fields
- **U5** - `fill --use-defaults` prints a stderr notice naming skipped multi-value fields and their stored options
- **C10** - CLI configures a stderr logging handler for the `pdfiller` logger, so a corrupt defaults file prints "Warning: Ignoring invalid JSON in defaults file <path>: <error>" instead of being silent
- **C11** - `save_defaults` writes atomically via temp file + `os.replace`; simulated write failure leaves the original file intact and no temp file behind
- **S1** - `save_defaults` creates the defaults file with mode 0600 (via `mkstemp`) and a newly created parent directory with mode 0700
- **P3** - Adopted `ruff` (lint + format) with config in pyproject.toml; codebase reformatted, all findings fixed
- **C5** - Flatten now renders field values with `insert_textbox` clipped to the widget rect, shrinking font stepwise until the text fits; long and multiline values stay inside the field
- **U1** - Fill JSON schema extended with `texts`, `boxes`, `images` overlay sections; CLI can fill non-fillable PDFs and place signatures end to end; overlays shown in `--dry-run`/`--verbose`
- **C4** - Flatten temp file now unique per call via `tempfile.NamedTemporaryFile`; concurrent fills to the same output path no longer collide
- **C7** - Push buttons excluded from `template` and `export` output entirely (they are actions, not state); regressed test updated
- **U2** - `--strict` flag on `fill` and `batch` (passes library strict mode); `--validate` now exits non-zero without saving when fields are missing

### Completed 2026-07-19 (pre-1.2.0 plan items)

- **C1** - Auto-date heuristic now excludes non-signing date fields; `_is_date_field()` rejects tokens `birth`, `dob`, `expire`, `expires`, `expiry`, `expiration`, `effective`, `start`, `end`, `from`, `to`
- **C2** - `save()` raises `PDFWriteError` when the output path resolves to the input PDF; corrected the misdescribed 1.1.0 CHANGELOG "save guard" entry
- **C3** - `batch` CLI command exits 1 when any CSV row fails
- **C6** - `PDFReadError` and `PDFWriteError` exported from `pdfiller` package (`__init__.py` imports and `__all__`)
- **P1** - Removed unused `numpy` and `pillow` runtime dependencies; PyMuPDF is the only runtime dependency

### Dropped

- **P2 (CI)** - dropped 2026-07-20: local solo project, tests run each session; revisit if the repo gains a GitHub remote or collaborators

### From the original audit (legacy numbering)

- **1.10** - Removed emojis from README.md features list, "Why Flattening" section, and INSTALL.md
- **1.11** - Fixed template command checkbox detection (`field_type == 'CheckBox'` instead of catching push buttons); see C7 for the current regression
- **2.6** - Added 57 direct unit tests for CLI command functions (test_cli_unit.py) alongside existing subprocess integration tests
- **3.9** - Added batch/CSV mode: `pdfiller batch -i form.pdf --csv data.csv --output-dir ./filled/`
- **3.10** - Added CLI defaults subcommands (`show`, `get`, `set`, `remove`) and `--use-defaults` flag on fill
- **4.6** - Added CHANGELOG.md following Keep a Changelog format
- **4.8** - Same as 1.10 (README emojis removed)
- **5.6** - Added configurable max_pdf_size (100MB) and max_image_size (50MB) with warnings at 50%
- **6.1** - Added high-level `fill()` method that auto-detects fillable vs non-fillable and routes accordingly
- **6.2** - Added `validate_defaults()` with schema validation, called automatically in load/save
- **6.3** - Added plugin/extension matcher system with `register_matcher()`, `unregister_matcher()`, `list_matchers()`
- **7.1 Radio/dropdown** - Added radio button, combobox, and listbox support with option validation
- **7.1 Field aliases** - Added `_aliases` key support in defaults with `build_alias_matcher()`
- **7.1 Batch CLI** - Same as 3.9
- **7.1 CLI defaults** - Same as 3.10
