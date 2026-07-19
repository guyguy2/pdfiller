# PDFiller Improvement Plan

Actionable improvements from a full architecture and UX review (2026-07-19) of `core.py`, `cli.py`, `memory.py`, `exceptions.py`, tests, packaging, and docs. Completed work is listed in the appendix at the bottom.

Each item has a stable ID (C = correctness, U = UX/CLI, A = architecture, P = packaging/tooling, S = security/privacy, F = feature idea), an effort tag, and a verification criterion.

Effort: **S** = under an hour, **M** = a few hours, **L** = a day or more.

---

## 1. Recommended Order

| Order | Item | Why first |
|-------|------|-----------|
| 1 | P3 ruff | Locks in quality before further work |
| 2 | C5 flatten textbox rendering | Most visible output-quality win |
| 3 | U1 CLI overlay support | Closes biggest workflow gap |
| 4 | Everything else | Opportunistic |

---

## 2. Correctness and Safety

### High priority

- **C4. Temp file collision in `_flatten_with_overlays`** (S)
  Temp path is derived deterministically from the output path (`.temp.pdf` suffix, `core.py:646`). Two concurrent fills targeting the same output (batch mode, parallel invocations) clobber each other's temp file.
  *Fix:* `tempfile.NamedTemporaryFile(dir=output_dir, suffix=".pdf", delete=False)`.
  *Verify:* temp name unique per call; existing flatten tests still pass.

- **C5. Flatten overlay ignores multiline and overflowing values** (M)
  The flatten pass (`core.py:683`) renders every field value with a single `insert_text` call at a fixed offset. Long values overflow the field rect; multiline text field values render as one line.
  *Fix:* use `insert_textbox` clipped to the widget rect; shrink font size stepwise until the text fits.
  *Verify:* test with a long value and a multiline value - rendered text stays inside the widget rect (assert via `get_text` positions).

### Medium priority

- **C7. Push buttons treated as checkboxes again** (S)
  `_CHECKBOX_FIELD_TYPES = ("CheckBox", "Button")` (`cli.py:18`) makes `template` and `export` classify push buttons (PyMuPDF type string "Button") as checkboxes. Original audit item 1.11 fixed exactly this; a unit test (`test_cli_unit.py:628`) now locks in the regressed behavior.
  *Fix:* decide intentionally. Push buttons are actions, not state - drop "Button" and update the test, or document why it is included.
  *Verify:* `template` on a PDF with a push button excludes it from `checkboxes`.

- **C8. Library and CLI disagree on preserve-existing default** (M)
  Library defaults to `_preserve_existing = True` (fill only empty fields, `core.py:113`); CLI passes `args.preserve_existing`, default False (overwrite). A library user calling `fill_field()` on a pre-filled field is silently ignored - surprising for an API named "fill".
  *Fix:* flip the library default to False (opt in via `preserve_existing_fields(True)`); document as breaking change in CHANGELOG; bump minor version. Alternative: keep and document prominently in README + docstring.
  *Verify:* tests updated for chosen default; README and USAGE describe it.

- **C9. Silent skips are invisible** (M)
  Preserve-existing skips, and out-of-range page `continue`s in `_apply_image_overlays`/`_apply_text_overlays` (dead defensiveness - `insert_*` already validates pages), report nothing.
  *Fix:* collect skipped operations during save; expose as return metadata or log; show in `fill --verbose`. Remove the dead page checks.
  *Verify:* verbose fill on a pre-filled field prints a skip line.

- **C10. `load_defaults` hides corruption** (S)
  Invalid JSON in defaults.json returns `{}` with only `logger.warning` (`memory.py:140`), and the CLI never configures logging - user sees "No defaults stored" with no hint the file is broken.
  *Fix:* in CLI paths, print a stderr warning naming the file and the parse error.
  *Verify:* test - corrupt defaults file plus `defaults show` prints warning to stderr.

- **C11. `save_defaults` is not atomic** (S)
  Crash mid-write corrupts defaults.json, the only copy of the user's stored data (`memory.py:163`).
  *Fix:* write to a temp file in the same directory, then `os.replace()`.
  *Verify:* existing save/load tests pass; simulated failure leaves the original intact.

- **C12. `pending_operations` and `--dry-run` omit half the state** (M)
  Neither includes unchecks, text overlays, image overlays, or auto-date targets that `save()` will fill (`core.py:788`, `cli.py:165`).
  *Fix:* extend `pending_operations` with `uncheck`, `text_overlays`, `image_overlays`, `auto_date_fields` (computed); render all in dry-run output.
  *Verify:* dry-run on a PDF with an empty `sign_date` lists it as auto-date.

---

## 3. UX and CLI Usability

- **U1. CLI cannot fill non-fillable PDFs** (M)
  Library supports `insert_text`, `insert_text_box`, `insert_image`; `inspect` finds coordinates; but no CLI verb acts on them - the non-fillable workflow dead-ends at the CLI.
  *Fix:* extend the fill JSON schema with overlay sections:
  ```json
  {
    "fields": {"name": "Guy"},
    "checkboxes": ["agree"],
    "texts": [{"text": "Guy Smith", "x": 200, "y": 150, "page": 0}],
    "boxes": [{"text": "123 Main St", "x0": 100, "y0": 200, "x1": 400, "y1": 260, "page": 0}],
    "images": [{"path": "sig.png", "x0": 100, "y0": 500, "x1": 300, "y1": 550, "page": 1}]
  }
  ```
  *Verify:* `fill -j` with only overlay sections produces correct output on a non-fillable fixture; covers signature placement end to end.

- **U2. `--strict` not exposed in CLI** (S)
  Library strict mode has no flag on `fill` or `batch`; `--validate` only warns.
  *Fix:* add `--strict` (passes `strict=True`); make `--validate` exit non-zero on missing fields, or fold both into one flag.
  *Verify:* `fill --strict -f nosuchfield=x` exits 1 with a clear message.

- **U3. `list` table format hides page and options** (S)
  Default table omits page number and dropdown/radio options; JSON shows both (`cli.py:35`).
  *Fix:* add "Page: N" and "Options: [...]" lines to table output.
  *Verify:* table output for the dropdown fixture shows options.

- **U4. Batch output naming and column mapping** (M)
  Outputs are `stem_filled_001.pdf`; no way to name from row data or map mismatched CSV headers.
  *Fix:* support a reserved `_output` CSV column or `--name-from <column>`; add `--map field=column`; optionally reuse the defaults matcher for fuzzy header matching.
  *Verify:* batch with `--name-from name` produces `stem_guy.pdf` style names; collision appends sequence.

- **U5. Multi-value defaults unusable from CLI** (S)
  When a default holds a list (two phone numbers), `fill --use-defaults` silently skips the field (`cli.py:116`).
  *Fix:* print a notice listing skipped multi-value fields and their options so the user knows to pass `-f phone=...`.
  *Verify:* test - list-valued default produces stderr notice naming field and options.

- **U6. `defaults set` cannot store lists** (S)
  `_set_nested` only stores strings; multi-value defaults require hand-editing JSON.
  *Fix:* add `defaults add key value` appending to (or creating) a list.
  *Verify:* `defaults add personal.phone 555-1234` twice yields a two-element list in `defaults show`.

- **U7. Date format hardcoded US style** (S)
  `_format_today_date()` always emits M/D/YYYY (`core.py:353`).
  *Fix:* `date_format` strftime parameter on `PDFFiller`, `--date-format` CLI flag; consider `_meta.date_format` defaults key for persistence.
  *Verify:* `--date-format %Y-%m-%d` produces ISO dates in auto-filled fields.

- **U8. Encrypted PDFs rejected outright** (S)
  Many "protected" PDFs open with an empty user password; users may legitimately have the password (`core.py:104`).
  *Fix:* try `doc.authenticate("")` before failing; add optional `password` parameter and `--password` flag.
  *Verify:* fixture encrypted with empty user password opens; wrong password still raises `PDFReadError`.

- **U9. Inconsistent stdout/file output plumbing** (S)
  `list` writes via `open()`, `export` via `Path.write_text`, `template` requires `-o` while others default to stdout.
  *Fix:* unify - every read-only command prints to stdout by default and accepts `-o`; one shared `_write_output(text, path)` helper.
  *Verify:* `template -i form.pdf` (no `-o`) prints JSON to stdout.

---

## 4. Architecture and Extensibility

- **A1. `core.py` heading toward god class** (M)
  `PDFFiller` handles form filling, overlay drawing, flattening, size policy, and date heuristics (801 lines).
  *Fix:* before adding features, split `_flatten_with_overlays` and helpers into `flatten.py`, and overlay queue/apply logic into `overlays.py`, keeping `PDFFiller` as facade.
  *Verify:* no public API change; tests pass unmodified.

- **A2. Global mutable matcher registry** (S)
  `memory._matchers` is module-level state; registrations leak across tests and libraries, and `clear_matchers()` removes built-ins with no way to restore them.
  *Fix:* add `reset_matchers()` (re-registers built-ins); consider an instance-based `MatcherRegistry` with module functions delegating to a default instance.
  *Verify:* `clear_matchers(); reset_matchers()` restores exact/normalized behavior; autouse fixture isolates tests.

- **A3. Overlay dicts are stringly typed** (S)
  `_text_overlays` entries are raw dicts with a `type` discriminator (`core.py:483`).
  *Fix:* small `@dataclass TextOverlay` / `BoxOverlay` / `ImageOverlay`; makes `pending_operations` richer for free (pairs with C12).
  *Verify:* type checker clean; behavior unchanged.

- **A4. CLI dispatch boilerplate** (S)
  `if args.command == ...` chain duplicates the subparser list (`cli.py:533`).
  *Fix:* `set_defaults(func=...)` per subparser; call `args.func(args)`.
  *Verify:* all CLI tests pass.

- **A5. `fill()` non-fillable spec only supports point text** (S)
  Coordinate-dict schema accepts `text/x/y` but not the box form or images, so the high-level API covers less than the low-level one (`core.py:226`).
  *Fix:* extend spec with `"box"` and `"image"` entry types; align with the U1 JSON schema so library and CLI share one format.
  *Verify:* `fill()` places a wrapped text box and an image on a non-fillable fixture.

- **A6. Field-type predicates duplicated** (S)
  Choice-widget type tuple appears in `list_fields()` and `_apply_field_updates()`; checkbox semantics live in three places (core apply, flatten overlay, CLI `_CHECKBOX_FIELD_TYPES`).
  *Fix:* centralize `is_choice_widget(widget)`, `is_checkbox(widget)` in one module; CLI imports the same predicates.
  *Verify:* single definition site; grep finds no stray type tuples.

---

## 5. Packaging, Tooling, and Tests

- **P3. No lint/format config** (S)
  *Fix:* adopt `ruff` (lint + format), config in pyproject.toml. Adoption cost is low now; it will not be later.
  *Verify:* `ruff check .` clean.

- **P4. No `py.typed` marker** (S)
  Type hints exist throughout but type checkers ignore installed packages without `py.typed`.
  *Fix:* add marker file; consider running mypy/pyright locally.
  *Verify:* `pyright` resolves `PDFFiller` types from an installed wheel.

- **P5. Python 3.8 is EOL** (M)
  3.8 (EOL Oct 2024) forces `Optional[X]`/`Dict` syntax and blocks modern PyMuPDF.
  *Fix:* bump `requires-python` to >=3.9 (or 3.10); modernize annotations opportunistically; CHANGELOG entry.
  *Verify:* classifiers match.

- **P6. Legacy `fitz` import** (S)
  Canonical import is now `import pymupdf`; `import fitz` is the deprecated alias.
  *Fix:* switch when bumping the PyMuPDF floor (pair with P5).
  *Verify:* no `import fitz` remains; tests pass.

- **P7. No coverage measurement** (S)
  *Fix:* add `pytest-cov` to dev group so gaps like the C5 overflow paths become visible.
  *Verify:* `uv run pytest --cov=pdfiller` produces a coverage report.

- **P8. Example PDFs may contain real data** (S) - partially done 2026-07-20
  Inspection confirmed `examples/680-001_AB_filled.pdf` contains real PII (names, DOB, phone). Neither PDF was ever committed, so no history scrub is needed. `examples/*_filled.pdf` is now in .gitignore.
  *Remaining:* decide fate of the blank `examples/680-001_AB.pdf` (real-world form, still untracked) - replace with a sanitized demo form or drop it.
  *Verify:* repo contains no PII; examples/ holds only sanitized demo files.

---

## 6. Security and Privacy

- **S1. Defaults file permissions** (S)
  `~/.pdfiller/defaults.json` typically holds PII (names, addresses, phones).
  *Fix:* `save_defaults()` creates file with mode 0600 and directory 0700.
  *Verify:* test asserts permissions after save on POSIX.

- **S2. Values leak into logs and shell history** (S)
  `fill --verbose` and dry-run print full field values - fine interactively, but persisted when scripted or run in CI.
  *Fix:* `--redact` flag printing masked values or lengths.
  *Verify:* `--dry-run --redact` shows field names but no values.

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
