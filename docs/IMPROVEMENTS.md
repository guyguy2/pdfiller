# PDFiller Improvement Plan

Actionable improvements from a full architecture and UX review (2026-07-19) of `core.py`, `cli.py`, `memory.py`, `exceptions.py`, tests, packaging, and docs. Completed work is listed in the appendix at the bottom.

Each item has a stable ID (C = correctness, U = UX/CLI, A = architecture, P = packaging/tooling, S = security/privacy, F = feature idea), an effort tag, and a verification criterion.

Effort: **S** = under an hour, **M** = a few hours, **L** = a day or more.

---

## 1. Recommended Order

| Order | Item | Why first |
|-------|------|-----------|
| 1 | Everything else | Opportunistic |

---

## 2. Correctness and Safety

(all current items completed - see appendix)

---

## 3. UX and CLI Usability

- **U7. Date format hardcoded US style** (S)
  `_format_today_date()` always emits M/D/YYYY (`core.py:366`).
  *Fix:* `date_format` strftime parameter on `PDFFiller`, `--date-format` CLI flag; consider `_meta.date_format` defaults key for persistence.
  *Verify:* `--date-format %Y-%m-%d` produces ISO dates in auto-filled fields.

- **U8. Encrypted PDFs rejected outright** (S)
  Many "protected" PDFs open with an empty user password; users may legitimately have the password (`core.py:106`).
  *Fix:* try `doc.authenticate("")` before failing; add optional `password` parameter and `--password` flag.
  *Verify:* fixture encrypted with empty user password opens; wrong password still raises `PDFReadError`.

---

## 4. Architecture and Extensibility

- **A1. `core.py` heading toward god class** (M)
  `PDFFiller` handles form filling, overlay drawing, flattening, size policy, and date heuristics (838 lines).
  *Fix:* before adding features, split `_flatten_with_overlays` and helpers into `flatten.py`, and overlay queue/apply logic into `overlays.py`, keeping `PDFFiller` as facade.
  *Verify:* no public API change; tests pass unmodified.

- **A3. Overlay dicts are stringly typed** (S)
  `_text_overlays` entries are raw dicts with a `type` discriminator (`core.py:502`).
  *Fix:* small `@dataclass TextOverlay` / `BoxOverlay` / `ImageOverlay`; makes `pending_operations` richer for free (pairs with C12).
  *Verify:* type checker clean; behavior unchanged.

- **A5. `fill()` non-fillable spec only supports point text** (S)
  Coordinate-dict schema accepts `text/x/y` but not the box form or images, so the high-level API covers less than the low-level one (`core.py:228`).
  *Fix:* extend spec with `"box"` and `"image"` entry types; align with the U1 JSON schema so library and CLI share one format.
  *Verify:* `fill()` places a wrapped text box and an image on a non-fillable fixture.

---

## 5. Packaging, Tooling, and Tests

- **P5. Python 3.8 is EOL** (M)
  3.8 (EOL Oct 2024) forces `Optional[X]`/`Dict` syntax and blocks modern PyMuPDF.
  *Fix:* bump `requires-python` to >=3.9 (or 3.10); modernize annotations opportunistically; CHANGELOG entry.
  *Verify:* classifiers match.

- **P6. Legacy `fitz` import** (S)
  Canonical import is now `import pymupdf`; `import fitz` is the deprecated alias.
  *Fix:* switch when bumping the PyMuPDF floor (pair with P5).
  *Verify:* no `import fitz` remains; tests pass.

- **P8. Example PDFs may contain real data** (S) - partially done 2026-07-20
  Inspection confirmed `examples/680-001_AB_filled.pdf` contains real PII (names, DOB, phone). Neither PDF was ever committed, so no history scrub is needed. `examples/*_filled.pdf` is now in .gitignore.
  *Remaining:* decide fate of the blank `examples/680-001_AB.pdf` (real-world form, still untracked) - replace with a sanitized demo form or drop it.
  *Verify:* repo contains no PII; examples/ holds only sanitized demo files.

---

## 6. Security and Privacy

---

## 7. Feature Ideas

### Medium-term (moderate effort)

- **F1. PDF/A output** - compliance for archival/legal use
- **F2. Watch mode** - monitor a directory, auto-fill new PDFs using a template
- **F3. Conditional logic** - fill field B only if field A has value X (medical/legal forms)
- **F4. Field grouping** - group related fields (address block) for batch operations
- **F5. Rich CLI output** - `rich` library for tables, progress bars, color
- **F6. Config file** - `~/.pdfiller/config.toml` for default settings (flatten mode, date format, output naming); natural home for U7's date format

### Long-term (significant effort)

- **F7. Smart field detection for non-fillable PDFs** - detect underlines, "Name: ___" patterns to propose placements
- **F8. TUI interface** - interactive terminal UI for browsing and filling fields
- **F9. Web interface** - simple Flask/FastAPI upload-and-fill app
- **F10. Digital signature support** - cryptographic signatures, not just image stamps
- **F11. PDF merge/split** - combine filled pages from multiple PDFs
- **F12. OCR integration** - handle scanned PDFs by OCRing text positions first
- **F13. Cloud storage** - Dropbox/Google Drive integration for input/output

---

## Appendix: Completed Items

From this improvement plan (completed 2026-07-20, unreleased):

- **U6** - `defaults add <key> <value>` appends to a list default (creates a one-element list if absent, promotes an existing string leaf to a two-element list); new `_add_nested` helper backs it
- **U9** - Unified read-only output via a shared `_write_output(text, path)` helper; `list`, `export`, and `template` all default to stdout and accept `-o`; `template` no longer requires `-o`
- **A4** - CLI dispatch now uses `set_defaults(func=...)` per subparser and calls `args.func(args)`; the command if-chain is gone (one special case remains for the `defaults` no-action help). Internal refactor, no user-facing change
- **A2** - Added `reset_matchers()` (exported from `pdfiller`) restoring the built-in exact/normalized matchers; added an autouse `_isolate_matchers` conftest fixture so matcher-registry state no longer leaks across tests
- **A6** - New `pdfiller/fields.py` centralizes widget-type predicates (`is_choice_widget`, `is_checkbox`, `is_checkbox_type`, `is_push_button_type`); `core` and `cli` import them, removing the duplicated choice tuples and CLI `_CHECKBOX_FIELD_TYPES`/`_PUSH_BUTTON_FIELD_TYPES`. Internal refactor, no user-facing change
- **S2** - `fill --redact` masks field values in `--verbose`/`--dry-run` output (shows names and `[redacted, N chars]`), keeping values out of logs and shell history; overlay text is redacted too
- **P4** - Added `pdfiller/py.typed` marker (ships in the wheel) so type checkers use the package's inline hints
- **P7** - Added `pytest-cov` to the dev group; `uv run pytest --cov=pdfiller` reports coverage (currently ~90%)

From this improvement plan (completed 2026-07-20, released as 1.2.0):

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

From this improvement plan (completed 2026-07-19):

- **C1** - Auto-date heuristic now excludes non-signing date fields; `_is_date_field()` rejects tokens `birth`, `dob`, `expire`, `expires`, `expiry`, `expiration`, `effective`, `start`, `end`, `from`, `to`
- **C2** - `save()` raises `PDFWriteError` when the output path resolves to the input PDF; corrected the misdescribed 1.1.0 CHANGELOG "save guard" entry
- **C3** - `batch` CLI command exits 1 when any CSV row fails
- **C6** - `PDFReadError` and `PDFWriteError` exported from `pdfiller` package (`__init__.py` imports and `__all__`)
- **P1** - Removed unused `numpy` and `pillow` runtime dependencies; PyMuPDF is the only runtime dependency

Dropped:

- **P2 (CI)** - dropped 2026-07-20: local solo project, tests run each session; revisit if the repo gains a GitHub remote or collaborators

From the original audit (numbering refers to that audit's scheme):

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
