# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `list` table format now shows the page number for every field and the options list for dropdown/radio/listbox fields
- `fill --use-defaults` prints a stderr notice naming fields skipped because the stored default holds multiple values, along with the stored options
- CLI now routes library warnings to stderr, so a corrupt defaults file is reported (file path and parse error) instead of silently appearing as "No defaults stored"
- CLI overlay support: the fill JSON schema accepts `texts`, `boxes`, and `images` sections that place content by coordinates, enabling non-fillable PDFs (and signature placement) end to end from the CLI; entries appear in `--dry-run` and `--verbose` output
- `--strict` flag on `fill` and `batch` passing library strict mode through; missing fields, checkboxes, or invalid choice values fail immediately instead of being silently skipped
- Guard in `save()` raising `PDFWriteError` when the output path resolves to the input PDF, preventing destruction of the source file
- `PDFReadError` and `PDFWriteError` are now exported from the `pdfiller` package
- Adopted `ruff` for linting and formatting (config in `pyproject.toml`, added to the dev dependency group); codebase reformatted and all findings fixed

### Changed

- `fill --validate` now exits non-zero (without writing output) when any provided field name is missing; previously it only printed a warning and saved anyway
- `template` and `export` no longer classify push buttons as checkboxes; push buttons are excluded from output entirely

### Fixed

- `save_defaults()` now writes atomically (temp file + `os.replace`), so a crash mid-write can no longer corrupt the defaults file
- `save_defaults()` creates the defaults file with mode 0600 and a newly created parent directory with mode 0700, since defaults typically hold PII
- Flatten temp file now gets a unique name via `tempfile.NamedTemporaryFile`, so concurrent fills targeting the same output path no longer clobber each other's temp file
- Flattening now renders field values with `insert_textbox` clipped to the widget rect, shrinking the font stepwise until the text fits; long values no longer overflow the field and multiline values render on separate lines
- Auto-date no longer fills non-signing date fields such as `date_of_birth`, `expiration_date`, `effective_date`, and `start_date`/`end_date`; only signature-adjacent dates (e.g. `sign_date`, `date_signed`) default to today
- `batch` CLI command exits non-zero when any CSV row fails, so scripts and cron jobs can detect partial failure
- Corrected the 1.1.0 changelog entry that described the one-shot `save()` restriction as an input-overwrite guard

### Removed

- Unused runtime dependencies `numpy` and `pillow`

## [1.1.0] - 2026-02-16

### Added

- Core PDF filling engine with support for fillable (AcroForm) and non-fillable PDFs
- Text insertion (`insert_text`), text box insertion (`insert_text_box`), and image insertion (`insert_image`) for non-fillable PDFs
- Form field listing, filling, checkbox toggling (`check_box`, `uncheck_box`), and page layout inspection
- Automatic flattening of filled forms on save
- Auto-date filling for empty date fields, controllable via `auto_fill_dates` parameter
- Defaults system for storing and matching reusable field values (`pdfiller.memory`)
- Support for `PDFILLER_DEFAULTS` env var to override defaults file path
- Strict mode to reject unknown field names during fill
- One-shot save guard: `save()` raises if called twice on the same instance
- Output path validation to ensure the target directory exists
- CLI with subcommands: `list`, `fill`, `template`, `inspect`, `export`
- CLI `--dry-run` flag and verbose fill output
- CLI list format options: table, JSON, and CSV
- CLI `inspect` command for examining non-fillable PDF layouts
- CLI `export` command to extract field values to JSON
- Image file format validation in `insert_image()`
- Detection and rejection of password-protected PDFs with a clear error message
- Test suite covering core functionality, memory/defaults, CLI commands, and env var overrides

### Fixed

- Cross-platform date formatting
- Temp file cleanup with try/finally in `_flatten_with_overlays`
- Checkbox detection in the `template` CLI command
- CLI error handling and bullet character rendering

### Changed

- Improved `__repr__`, `has_form_fields`, and consistent use of `self.page_count`

### Removed

- Unused `PDFField` and `CheckboxField` dataclasses
