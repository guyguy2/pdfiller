# PDFiller Improvement Plan

Comprehensive analysis of the PDFiller codebase (v1.1.0) with actionable improvements organized by category.

---

## 1. Code Quality

### 1.1 Remove dead code: `PDFField` and `CheckboxField` dataclasses
- `core.py:14-33` - These are defined and exported but never used anywhere in the codebase (not in core, cli, tests, or examples)
- Either remove them or integrate them into `list_fields()` as return types

### 1.2 Expensive `__repr__` on PDFFiller
- `core.py:582-584` - Calls `list_fields()` which iterates every widget on every page, just to show a count
- Cache the field count or compute it with a lightweight counter instead of building full dicts

### 1.3 Platform-dependent date formatting
- `core.py:236` - `%-m/%-d/%Y` only works on Linux/macOS; Windows requires `%#m/%#d/%Y`
- Use a cross-platform approach: `str(today.month)` + `str(today.day)` + `str(today.year)`

### 1.4 Auto-date filling is implicit magic
- `core.py:259-262` - Date fields are silently auto-filled during `_apply_field_updates()` with no opt-in
- This side effect happens during `save()`, which is surprising. A user calling `filler.save()` on a PDF they only wanted to flatten would get unexpected date values injected
- Make this opt-in via a flag (e.g., `auto_fill_dates=False` by default on `__init__` or `save`)

### 1.5 Temp file leak in `_flatten_with_overlays`
- `core.py:472-524` - If an error occurs between `self.doc.save(str(temp_path))` on line 473 and `temp_path.unlink()` on line 524, the temp file is orphaned
- Wrap in try/finally to ensure cleanup

### 1.6 `_flatten_with_overlays` mutates internal state
- `core.py:474` - Calls `self.doc.close()` then reopens the doc from the temp file
- After `save()`, the filler's internal document is now pointing at the temp-derived doc, not the original. Calling `save()` twice would produce unexpected results
- Document this limitation or make `save()` terminal (close the filler after saving)

### 1.7 `has_form_fields` uses a wasteful generator
- `core.py:268` - `any(True for _ in page.widgets())` allocates a generator just to check existence
- Simplify to: `try: next(page.widgets()); return True except StopIteration: pass`

### 1.8 No validation of field names until save time
- `fill_field()` and `check_box()` silently queue values for non-existent fields
- These are only discovered if the user explicitly calls `validate_fields()`
- Consider an optional `strict` mode that validates on `fill_field()`

### 1.9 `uncheck_box` doesn't actually uncheck
- `core.py:186-197` - Only removes a field from the "to check" set
- If a checkbox is already checked in the PDF, calling `uncheck_box()` does nothing. There's no way to explicitly uncheck a pre-checked box

### 1.10 Inconsistent use of `len(self.doc)` vs `self.page_count`
- `core.py` uses `len(self.doc)` directly in most methods instead of the `page_count` property defined at line 97

---

## 2. Testing

### 2.1 Duplicated `_make_png()` helper
- `test_core.py` lines 180, 200, 231, 253 - The same PNG generation function is copied 4 times
- Extract to a shared `conftest.py` fixture (e.g., `@pytest.fixture def tiny_png(tmp_path)`)

### 2.2 No CLI tests at all
- `cli.py` has 200 lines of code with zero test coverage
- Add tests for: `list`, `fill`, `template` commands, error handling, JSON loading, argument parsing

### 2.3 No tests for error/edge paths
- Permission denied on save
- Corrupted/password-protected PDF input
- Empty field names, extremely long values
- Unicode characters in field names and values
- Filling a PDF that was already flattened (no widgets left)
- Calling `save()` twice on the same filler

### 2.4 No tests for the memory module's env var path
- `memory.py:16-18` - `PDFILLER_DEFAULTS` env var is untested

### 2.5 Missing test for flatten + auto-date interaction
- No test verifies what happens when auto-date fills a field and then flattening renders it

---

## 3. CLI and Developer UX

### 3.1 No `inspect` command for non-fillable PDFs
- The CLI has `list` for fillable PDFs but no way to inspect non-fillable PDF layouts
- Add: `pdfiller inspect -i form.pdf` that calls `get_page_layout()` and prints text block positions

### 3.2 No `--dry-run` flag
- Users can't preview what would be filled without actually creating an output file
- Add `--dry-run` to `fill` that lists which fields would be filled and with what values

### 3.3 No output about what was actually filled
- `fill_command` only prints "Done: path" - no feedback on how many fields were filled, which were skipped, or which were missing

### 3.4 No `-v/--verbose` flag
- No way to get detailed output about the filling process

### 3.5 No `--format` option for `list` output
- Currently either prints human-readable or JSON. Add `--format table|json|csv` for flexibility

### 3.6 Template command doesn't distinguish field types well
- `cli.py:119` - Checkbox detection relies on `'Button' in field_type` which could false-positive on push buttons
- The generated template could include field types as comments or metadata

### 3.7 No data export command
- No way to extract current field values from a filled PDF back to JSON
- Add: `pdfiller export -i filled.pdf -o data.json`

### 3.8 CLI uses raw `print` with emoji bullet
- `cli.py:37` - Uses a bullet character that may not render on all terminals
- Use a plain dash or configurable output format

---

## 4. Documentation

### 4.1 README claims multi-page is not supported
- `README.md:225` - FAQ says "Currently only single-page PDFs are supported" but multi-page has been implemented and tested
- `README.md:242-246` - Contributing section still lists "Multi-page PDF support" as a TODO
- `USAGE.md:397` - Same outdated claim

### 4.2 README missing API docs for newer methods
- `get_page_layout()`, `insert_text()`, `insert_text_box()`, `insert_image()` are not documented in the README API Reference section
- These are core features for non-fillable PDF handling

### 4.3 No documentation for the memory/defaults system
- The `load_defaults`, `save_defaults`, `flatten_defaults`, `match_field_to_defaults` functions are exported but not mentioned in README or USAGE.md
- `~/.pdfiller/defaults.json` structure is undocumented

### 4.4 INSTALL.md doesn't mention `uv`
- Project uses `uv` (per CLAUDE.md and pyproject.toml) but INSTALL.md only references `pip`

### 4.5 Examples use emojis
- `quickstart.py` and `medication_form_example.py` use emoji characters, violating the project's code standards

### 4.6 No CHANGELOG
- No record of what changed between versions

### 4.7 CLAUDE.md workflow doesn't mention auto-date
- The fill-pdf workflow in CLAUDE.md doesn't mention the auto-date feature, so Claude Code may not inform users about it

---

## 5. Robustness and Error Handling

### 5.1 No validation of image file format
- `insert_image()` at `core.py:409-411` checks file existence but not whether the file is actually a valid image
- Invalid image files will fail at save time with an unhelpful PyMuPDF error

### 5.2 No handling of password-protected PDFs
- `fitz.open()` will fail on encrypted PDFs with a generic error
- Detect and raise a specific `PDFReadError` with guidance

### 5.3 No handling of read-only output paths
- `save()` will fail with a generic PyMuPDF error if the output path is not writable
- Check permissions before attempting the save

### 5.4 `load_values_from_json` has no error handling for malformed JSON
- `cli.py:15-19` - Will throw a raw `json.JSONDecodeError` with no user-friendly message

### 5.5 CLI `fill` command doesn't handle bad `--field` format
- `cli.py:74` - `name, value = field_spec.split('=', 1)` will throw `ValueError` if no `=` is present

### 5.6 No max size or resource limits
- Very large PDFs or images could cause memory issues without any guard

---

## 6. Architecture

### 6.1 No separation between fillable and non-fillable strategies
- `PDFFiller` handles both fillable and non-fillable PDFs in one class
- The user has to know which methods to call for each type
- Consider a higher-level `fill()` method that auto-detects and routes, or a factory pattern

### 6.2 No schema for defaults.json
- `memory.py` loads and saves arbitrary JSON with no validation
- A schema (even informal) would catch user errors in the defaults file

### 6.3 No plugin / extension mechanism
- Field matching logic in `match_field_to_defaults` is hardcoded to exact + normalized matching
- No way to add custom matchers (e.g., regex patterns, aliases, or semantic matching)

### 6.4 `save()` is doing too much
- `save()` applies fields, applies overlays, manages temp files, flattens, and writes
- Consider breaking into explicit phases: `apply() -> flatten() -> write()`

---

## 7. Feature Ideas

### 7.1 Near-term (low effort, high value)

- **Radio button support** - Common in real forms, currently unsupported
- **Dropdown/combobox support** - Same as above
- **`pdfiller export` CLI command** - Extract filled values back to JSON
- **`pdfiller inspect` CLI command** - Show layout for non-fillable PDFs
- **Batch CLI mode** - `pdfiller fill -i form.pdf --csv data.csv --output-dir ./filled/`
- **Default field aliases** - Map common variations (e.g., "fname" -> "first_name") in defaults

### 7.2 Medium-term (moderate effort)

- **PDF/A output** - Compliance for archival/legal use
- **Watch mode** - Monitor a directory and auto-fill new PDFs using a template
- **Conditional logic** - Fill field B only if field A has value X (useful for medical/legal forms)
- **Field grouping** - Group related fields (e.g., address block) for easier batch operations
- **Rich CLI output** - Use `rich` library for tables, progress bars, colored output
- **Config file** - `~/.pdfiller/config.toml` for default settings (flatten mode, date format, output naming)

### 7.3 Long-term (significant effort)

- **Smart field detection for non-fillable PDFs** - Use text patterns/ML to detect where form fields would be (e.g., underlines, "Name: ___")
- **TUI interface** - Interactive terminal UI for browsing fields and filling values
- **Web interface** - Simple Flask/FastAPI app for uploading and filling PDFs in a browser
- **Digital signature support** - Proper cryptographic signatures, not just image stamps
- **PDF merge/split** - Combine filled pages from multiple PDFs
- **OCR integration** - Handle scanned PDFs by OCRing text positions first
- **Cloud storage** - Direct integration with Dropbox, Google Drive for input/output

---

## 8. Quick Wins

Sorted by effort (lowest first), these can be done in under an hour each:

1. Fix outdated multi-page claims in README.md and USAGE.md
2. Extract `_make_png()` to a test fixture
3. Add try/finally cleanup for temp file in `_flatten_with_overlays`
4. Make auto-date filling opt-in
5. Fix cross-platform date formatting
6. Add `--dry-run` flag to CLI fill command
7. Add basic CLI tests
8. Remove or use the `PDFField`/`CheckboxField` dataclasses
9. Document the memory/defaults system in README
10. Add the missing API methods to README docs
