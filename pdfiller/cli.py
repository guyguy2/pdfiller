"""
Command-line interface for PDFiller
"""

import argparse
import csv
import io
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Optional

from rich.console import Console
from rich.markup import escape
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn, TimeElapsedColumn
from rich.table import Table

from .config import Config, default_output_path, load_config
from .core import PDFFiller
from .exceptions import PDFFillerError
from .fields import is_checkbox_type, is_push_button_type
from .memory import flatten_defaults, load_defaults, match_field_to_defaults, save_defaults

# Shared consoles: stdout for tables/status, stderr for progress (keeps stdout clean).
_stdout_console = Console(highlight=False)
_stderr_console = Console(stderr=True, highlight=False)

# Required keys per overlay section in the fill JSON schema
_OVERLAY_REQUIRED_KEYS = {
    "texts": ("text", "x", "y"),
    "boxes": ("text", "x0", "y0", "x1", "y1"),
    "images": ("path", "x0", "y0", "x1", "y1"),
}


def load_values_from_json(json_path: Path) -> dict[str, Any]:
    """Load field values from JSON file"""
    try:
        with open(json_path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {json_path}: {e}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"Error: Cannot read {json_path}: {e}", file=sys.stderr)
        sys.exit(1)
    return data


def _queue_overlays(filler: PDFFiller, data: dict[str, Any]) -> int:
    """Queue text/box/image overlays from the fill JSON spec.

    Returns the number of overlays queued. Exits with an error message if an
    entry is missing required keys.
    """
    for section, required in _OVERLAY_REQUIRED_KEYS.items():
        for i, entry in enumerate(data.get(section, [])):
            missing = [k for k in required if k not in entry]
            if missing:
                print(
                    f"Error: {section}[{i}] is missing required keys: {', '.join(missing)}",
                    file=sys.stderr,
                )
                sys.exit(1)

    count = 0
    for entry in data.get("texts", []):
        kwargs = {"font_size": entry["font_size"]} if "font_size" in entry else {}
        filler.insert_text(
            entry["text"], entry["x"], entry["y"], page_num=entry.get("page", 0), **kwargs
        )
        count += 1
    for entry in data.get("boxes", []):
        kwargs = {"font_size": entry["font_size"]} if "font_size" in entry else {}
        filler.insert_text_box(
            entry["text"],
            entry["x0"],
            entry["y0"],
            entry["x1"],
            entry["y1"],
            page_num=entry.get("page", 0),
            **kwargs,
        )
        count += 1
    for entry in data.get("images", []):
        filler.insert_image(
            entry["path"],
            entry["x0"],
            entry["y0"],
            entry["x1"],
            entry["y1"],
            page_num=entry.get("page", 0),
        )
        count += 1
    return count


def _resolve_date_format(args, config: Optional[Config] = None) -> Optional[str]:
    """Resolve the date format for auto-filled date fields.

    Precedence: --date-format flag, then config.toml date_format, then
    `_meta.date_format` in stored defaults, then None (built-in M/D/YYYY).
    """
    explicit = getattr(args, "date_format", None)
    if explicit:
        return explicit
    if config is None:
        config = load_config()
    if config.date_format:
        return config.date_format
    fmt = load_defaults().get("_meta", {}).get("date_format")
    return fmt if isinstance(fmt, str) else None


def _resolve_auto_fill_dates(args, config: Config) -> bool:
    """Whether to auto-fill empty date fields.

    --no-auto-dates always wins; otherwise config.auto_fill_dates if set; else True.
    """
    if getattr(args, "no_auto_dates", False):
        return False
    if config.auto_fill_dates is not None:
        return config.auto_fill_dates
    return True


def _resolve_fill_output(args, config: Config) -> Optional[str]:
    """Output path for fill: explicit -o, else <stem><suffix>.pdf next to input."""
    if args.output:
        return args.output
    if args.dry_run:
        return None
    return str(default_output_path(args.input, config.output_suffix))


def _redact_value(value: Any) -> str:
    """Mask a field value for logging, revealing only its length.

    Used by --redact so field names still appear in --verbose/--dry-run output
    while the values themselves stay out of logs and shell history.
    """
    return f"[redacted, {len(str(value))} chars]"


def _describe_overlays(data: dict[str, Any], redact: bool = False) -> list:
    """Human-readable one-line descriptions of overlay entries for dry-run/verbose."""
    lines = []
    for entry in data.get("texts", []):
        text = _redact_value(entry["text"]) if redact else f'"{entry["text"]}"'
        lines.append(f"text {text} at ({entry['x']}, {entry['y']}) on page {entry.get('page', 0)}")
    for entry in data.get("boxes", []):
        text = _redact_value(entry["text"]) if redact else f'"{entry["text"]}"'
        lines.append(
            f"text box {text} in "
            f"({entry['x0']}, {entry['y0']}, {entry['x1']}, {entry['y1']}) "
            f"on page {entry.get('page', 0)}"
        )
    for entry in data.get("images", []):
        lines.append(
            f"image {entry['path']} in "
            f"({entry['x0']}, {entry['y0']}, {entry['x1']}, {entry['y1']}) "
            f"on page {entry.get('page', 0)}"
        )
    return lines


def _write_output(text: str, path: Optional[str]) -> None:
    """Write command output to a file or stdout.

    With a path, writes the text verbatim and prints a "Saved:" notice.
    Without a path, writes to stdout, ensuring exactly one trailing newline
    (text that already ends in a newline, such as CSV, is left untouched).
    """
    if path:
        Path(path).write_text(text)
        print(f"Saved: {path}")
    else:
        sys.stdout.write(text if text.endswith("\n") else text + "\n")


def _format_fields_table(fields, input_path: str) -> str:
    """Format fields as a human-readable rich table (plain text, no color).

    Returned as a string so callers can write to a file or stdout via
    ``_write_output``. Color is disabled so file captures stay clean.
    """
    table = Table(
        title=f"Found {len(fields)} fields in {input_path}",
        show_header=True,
        header_style="bold",
        expand=False,
    )
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Type")
    table.add_column("Page", justify="right")
    table.add_column("Value")
    table.add_column("Options")

    for field in fields:
        options = field.get("options") or []
        page = field.get("page", "")
        page_str = "" if page == "" or page is None else str(page)
        table.add_row(
            escape(field["name"]),
            escape(field.get("type", "")),
            page_str,
            escape(str(field.get("value") or "")),
            escape(", ".join(options) if options else ""),
        )

    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False, width=120, highlight=False)
    console.print(table)
    return buf.getvalue()


def _ops_rows(ops: dict[str, Any], data: dict[str, Any], redact: bool) -> list[tuple[str, str]]:
    """Build (field, value) rows for dry-run / verbose fill plans."""
    rows: list[tuple[str, str]] = []
    for name, value in (ops.get("fields") or {}).items():
        shown = _redact_value(value) if redact else str(value)
        rows.append((name, shown))
    for name in ops.get("check") or []:
        rows.append((name, "[checked]"))
    for name in ops.get("uncheck") or []:
        rows.append((name, "[unchecked]"))
    for name in ops.get("auto_date_fields") or []:
        rows.append((name, "[auto-date: today]"))
    for line in _describe_overlays(data, redact=redact):
        # Overlay lines already look like "text '...' at ..."
        rows.append((line, ""))
    return rows


def _print_ops_table(title: str, rows: list[tuple[str, str]], empty_msg: str) -> None:
    """Print a Field/Value table for fill dry-run or verbose plans.

    Cell text is escaped so values like ``[checked]`` or ``[redacted, N chars]``
    are not interpreted as rich markup.
    """
    _stdout_console.print(f"[bold]{escape(title)}[/bold]")
    if not rows:
        _stdout_console.print(f"  {escape(empty_msg)}")
        return
    table = Table(show_header=True, header_style="bold", expand=False)
    table.add_column("Field", style="cyan", no_wrap=True)
    table.add_column("Value", overflow="fold")
    for field, value in rows:
        table.add_row(escape(str(field)), escape(str(value)))
    _stdout_console.print(table)


def _format_fields_json(fields) -> str:
    """Format fields as JSON."""
    return json.dumps(fields, indent=2)


def _format_fields_csv(fields) -> str:
    """Format fields as CSV with columns: name, type, value, page."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["name", "type", "value", "page"])
    for field in fields:
        writer.writerow(
            [
                field["name"],
                field["type"],
                field.get("value", ""),
                field.get("page", ""),
            ]
        )
    return buf.getvalue()


def list_fields_command(args):
    """List all fields in a PDF"""
    try:
        with PDFFiller(args.input, password=getattr(args, "password", None)) as filler:
            fields = filler.list_fields()

            fmt = getattr(args, "format", None) or "table"

            if fmt == "json":
                output = _format_fields_json(fields)
            elif fmt == "csv":
                output = _format_fields_csv(fields)
            else:
                output = _format_fields_table(fields, args.input)

            _write_output(output, args.output)

    except PDFFillerError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def fill_command(args):
    """Fill PDF fields from JSON or command-line arguments"""
    try:
        config = load_config()
        auto_dates = _resolve_auto_fill_dates(args, config)
        strict = getattr(args, "strict", False)
        date_format = _resolve_date_format(args, config)
        output_path = _resolve_fill_output(args, config)
        # Flatten: --no-flatten sets args.flatten False; otherwise config then True
        flatten = (
            args.flatten
            if args.flatten is not None
            else (config.flatten if config.flatten is not None else True)
        )
        with PDFFiller(
            args.input,
            auto_fill_dates=auto_dates,
            strict=strict,
            date_format=date_format,
            password=getattr(args, "password", None),
        ) as filler:
            # Set preserve mode
            filler.preserve_existing_fields(args.preserve_existing)

            # Auto-fill from stored defaults if requested
            if args.use_defaults:
                defaults_data = flatten_defaults(load_defaults())
                if defaults_data:
                    pdf_fields = filler.list_fields()
                    multi_value_skipped = {}
                    for field in pdf_fields:
                        name = field["name"]
                        match = match_field_to_defaults(name, defaults_data)
                        if isinstance(match, str):
                            filler.fill_field(name, match)
                        elif isinstance(match, list):
                            # Multiple stored values - user must pick one
                            multi_value_skipped[name] = match
                    if multi_value_skipped:
                        print(
                            "Notice: skipped fields with multiple stored defaults; "
                            "pass -f name=value to choose:",
                            file=sys.stderr,
                        )
                        for name, options in multi_value_skipped.items():
                            print(f"  {name}: {', '.join(options)}", file=sys.stderr)

            # Load values from JSON if provided
            data = {}
            overlay_count = 0
            if args.values_json:
                data = load_values_from_json(args.values_json)

                # Separate text fields and checkboxes
                text_fields = data.get("fields", {})
                checkboxes = data.get("checkboxes", [])

                # Fill text fields
                filler.fill_fields(text_fields)

                # Check checkboxes
                for checkbox in checkboxes:
                    filler.check_box(checkbox)

                # Queue coordinate overlays (texts, boxes, images) for
                # non-fillable PDFs or additions on top of form fields
                overlay_count = _queue_overlays(filler, data)

            # Override with command-line field arguments
            if args.field:
                for field_spec in args.field:
                    if "=" not in field_spec:
                        print(
                            f"Error: Invalid field format '{field_spec}', expected name=value",
                            file=sys.stderr,
                        )
                        sys.exit(1)
                    name, value = field_spec.split("=", 1)
                    filler.fill_field(name, value)

            # Check command-line checkbox arguments
            if args.checkbox:
                for checkbox in args.checkbox:
                    filler.check_box(checkbox)

            # Validate fields if requested
            if args.validate:
                all_fields = list(text_fields.keys()) if args.values_json else []
                if args.field:
                    all_fields.extend([f.split("=")[0] for f in args.field])

                if all_fields:
                    results = filler.validate_fields(all_fields)
                    invalid = [name for name, exists in results.items() if not exists]
                    if invalid:
                        print(f"Error: Fields not found: {', '.join(invalid)}", file=sys.stderr)
                        sys.exit(1)

            # Collect summary info via public API
            ops = filler.pending_operations
            filled_count = len(ops["fields"])
            checked_count = len(ops["check"])

            redact = getattr(args, "redact", False)

            # Dry run: show what would be filled without saving
            if args.dry_run:
                rows = _ops_rows(ops, data, redact=redact)
                _print_ops_table(f"Dry run for {args.input}:", rows, "(no fields to fill)")
                return

            # Verbose output before save
            verbose = getattr(args, "verbose", False)
            if verbose:
                # Exclude auto-date from the main table when dates are off; when
                # on, list them under a note so the plan matches save behavior.
                plan_ops = {
                    "fields": ops.get("fields") or {},
                    "check": ops.get("check") or [],
                    "uncheck": ops.get("uncheck") or [],
                    "auto_date_fields": [],
                }
                rows = _ops_rows(plan_ops, data, redact=redact)
                _print_ops_table(f"Fill plan for {args.input}:", rows, "(no fields to fill)")
                if filler.auto_fill_dates:
                    _stdout_console.print(
                        "  [dim]Auto-fill dates: enabled "
                        "(empty date fields will use today's date)[/dim]"
                    )
                    for name in ops.get("auto_date_fields") or []:
                        _stdout_console.print(
                            f"    [cyan]{escape(name)}[/cyan] = {escape('[auto-date: today]')}"
                        )

            # Save the filled PDF
            saved_path = filler.save(output_path, flatten=flatten)

            # Report operations the save skipped (e.g. preserve-existing)
            if verbose:
                for entry in filler.skipped_operations:
                    existing = (
                        _redact_value(entry["existing_value"])
                        if redact
                        else f"'{entry['existing_value']}'"
                    )
                    # Plain text so path-like values and quotes stay intact
                    print(f"  Skipped {entry['field']} (kept existing value {existing})")
            summary = f"{filled_count} fields, {checked_count} checkboxes"
            if overlay_count:
                summary += f", {overlay_count} overlays"
            # Plain print: long paths must not soft-wrap mid-token for scripts/tests
            print(f"Done: {saved_path} ({summary})")

    except PDFFillerError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def inspect_command(args):
    """Inspect a non-fillable PDF's text layout"""
    try:
        with PDFFiller(args.input, password=getattr(args, "password", None)) as filler:
            for page_num in range(filler.page_count):
                layout = filler.get_page_layout(page_num)
                print(f"Page {page_num}: {layout['width']:.0f}x{layout['height']:.0f}")
                for block in layout["blocks"]:
                    bbox = block["bbox"]
                    text = block["text"].replace("\n", " ")
                    if len(text) > 80:
                        text = text[:77] + "..."
                    coords = (
                        f"[{bbox['x0']:.0f},{bbox['y0']:.0f} - {bbox['x1']:.0f},{bbox['y1']:.0f}]"
                    )
                    print(f"  {coords} {text}")
                if not layout["blocks"]:
                    print("  (no text blocks)")

    except PDFFillerError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def export_command(args):
    """Extract current field values from a PDF to JSON"""
    try:
        with PDFFiller(args.input, password=getattr(args, "password", None)) as filler:
            fields = filler.list_fields()
            data = {
                "fields": {},
                "checkboxes": [],
            }
            for field in fields:
                name = field["name"]
                value = field["value"]
                field_type = field["type"]
                if is_push_button_type(field_type):
                    continue
                if is_checkbox_type(field_type):
                    if value and value not in ("Off", ""):
                        data["checkboxes"].append(name)
                elif value:
                    data["fields"][name] = value

            output = json.dumps(data, indent=2)
            _write_output(output, args.output)

    except PDFFillerError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _get_nested(data: dict[str, Any], key: str) -> Any:
    """Get a value from a nested dict using dot notation (e.g., 'personal.phone')."""
    parts = key.split(".")
    current = data
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _set_nested(data: dict[str, Any], key: str, value: str) -> None:
    """Set a value in a nested dict using dot notation (e.g., 'personal.phone')."""
    parts = key.split(".")
    current = data
    for part in parts[:-1]:
        current = current.setdefault(part, {})
    current[parts[-1]] = value


def _add_nested(data: dict[str, Any], key: str, value: str) -> None:
    """Append a value to a list in a nested dict using dot notation.

    Creates a one-element list if the key is absent. Promotes an existing
    string leaf to a two-element list. Appends if the leaf is already a list.
    """
    parts = key.split(".")
    current = data
    for part in parts[:-1]:
        current = current.setdefault(part, {})
    last = parts[-1]
    existing = current.get(last)
    if existing is None:
        current[last] = [value]
    elif isinstance(existing, str):
        current[last] = [existing, value]
    elif isinstance(existing, list):
        existing.append(value)
    else:
        raise PDFFillerError(
            f"Cannot add to '{key}': existing value is a {type(existing).__name__}, "
            "not a string or list"
        )


def _remove_nested(data: dict[str, Any], key: str) -> bool:
    """Remove a value from a nested dict using dot notation. Returns True if removed."""
    parts = key.split(".")
    current = data
    for part in parts[:-1]:
        if not isinstance(current, dict) or part not in current:
            return False
        current = current[part]
    if not isinstance(current, dict) or parts[-1] not in current:
        return False
    del current[parts[-1]]
    return True


def defaults_command(args):
    """Manage stored defaults"""
    action = args.defaults_action

    try:
        if action == "show":
            data = load_defaults()
            if not data:
                print("No defaults stored.")
                return
            print(json.dumps(data, indent=2))

        elif action == "get":
            data = load_defaults()
            value = _get_nested(data, args.key)
            if value is None:
                print(f"Not found: {args.key}", file=sys.stderr)
                sys.exit(1)
            if isinstance(value, (dict, list)):
                print(json.dumps(value, indent=2))
            else:
                print(value)

        elif action == "set":
            data = load_defaults()
            _set_nested(data, args.key, args.value)
            save_defaults(data)
            print(f"Set {args.key} = {args.value}")

        elif action == "add":
            data = load_defaults()
            _add_nested(data, args.key, args.value)
            save_defaults(data)
            print(f"Added {args.value!r} to {args.key}")

        elif action == "remove":
            data = load_defaults()
            if _remove_nested(data, args.key):
                save_defaults(data)
                print(f"Removed: {args.key}")
            else:
                print(f"Not found: {args.key}", file=sys.stderr)
                sys.exit(1)

    except PDFFillerError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _sanitize_filename_part(value: str) -> str:
    """Make a CSV cell value safe to embed in an output filename."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip()).strip("._")


def _batch_output_path(
    output_dir: Path, stem: str, row, name_from: Optional[str], seq: int, used: set
) -> Path:
    """Resolve the output path for one batch row.

    Naming precedence: reserved '_output' CSV column, then --name-from column,
    then the default '<stem>_filled_<seq>.pdf'. Collisions with earlier rows
    get the sequence number appended.
    """
    name = None
    override = (row.get("_output") or "").strip()
    if override:
        if not override.lower().endswith(".pdf"):
            override += ".pdf"
        name = override
    elif name_from:
        part = _sanitize_filename_part(row.get(name_from) or "")
        if part:
            name = f"{stem}_{part}.pdf"

    if name is None:
        name = f"{stem}_filled_{seq:03d}.pdf"
    elif name in used:
        name = f"{Path(name).stem}_{seq:03d}.pdf"

    used.add(name)
    return output_dir / name


def _parse_field_maps(map_args) -> dict[str, str]:
    """Parse --map field=column arguments into a {field: column} dict."""
    maps = {}
    for spec in map_args or []:
        if "=" not in spec:
            print(f"Error: Invalid map format '{spec}', expected field=column", file=sys.stderr)
            sys.exit(1)
        field, column = spec.split("=", 1)
        maps[field] = column
    return maps


def batch_command(args):
    """Fill a PDF once per row in a CSV file, producing one output PDF per row."""
    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"Error: CSV file not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    stem = input_path.stem
    field_maps = _parse_field_maps(getattr(args, "map", None))
    name_from = getattr(args, "name_from", None)

    try:
        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except Exception as e:
        print(f"Error: Cannot read CSV {csv_path}: {e}", file=sys.stderr)
        sys.exit(1)

    if not rows:
        print("Error: CSV file has no data rows", file=sys.stderr)
        sys.exit(1)

    if name_from and name_from not in rows[0]:
        print(f"Error: --name-from column '{name_from}' not in CSV header", file=sys.stderr)
        sys.exit(1)

    missing_map_columns = [c for c in field_maps.values() if c not in rows[0]]
    if missing_map_columns:
        print(
            f"Error: --map column(s) not in CSV header: {', '.join(missing_map_columns)}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Columns consumed by --map fill their mapped field instead of one
    # matching their own name; '_output' is reserved for output naming.
    consumed_columns = set(field_maps.values()) | {"_output"}

    filled = 0
    errors = []
    used_names: set = set()
    config = load_config()
    date_format = _resolve_date_format(args, config)
    auto_dates = _resolve_auto_fill_dates(args, config)
    flatten = (
        args.flatten
        if args.flatten is not None
        else (config.flatten if config.flatten is not None else True)
    )

    def _fill_row(i: int, row) -> None:
        nonlocal filled
        output_file = _batch_output_path(output_dir, stem, row, name_from, i, used_names)
        try:
            with PDFFiller(
                args.input,
                auto_fill_dates=auto_dates,
                strict=getattr(args, "strict", False),
                date_format=date_format,
                password=getattr(args, "password", None),
            ) as filler:
                # Every CSV column is applied as a field value by name. Checkbox
                # columns are set through the same path, so they only toggle when
                # the cell holds the checkbox export value (e.g. "On"/"Off"), not
                # an arbitrary truthy string.
                for field_name, value in row.items():
                    if value is None or field_name in consumed_columns:
                        continue
                    filler.fill_field(field_name, value)
                for field_name, column in field_maps.items():
                    value = row.get(column)
                    if value is None:
                        continue
                    filler.fill_field(field_name, value)
                filler.save(str(output_file), flatten=flatten)
            filled += 1
        except Exception as e:
            errors.append((i, str(e)))

    # Progress bar on stderr when interactive; quiet loop in pipes/CI/tests.
    if _stderr_console.is_terminal:
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=_stderr_console,
            transient=True,
        ) as progress:
            task_id = progress.add_task("Batch fill", total=len(rows))
            for i, row in enumerate(rows, start=1):
                _fill_row(i, row)
                progress.advance(task_id)
    else:
        for i, row in enumerate(rows, start=1):
            _fill_row(i, row)

    print(f"Filled {filled} PDFs from {csv_path.name}")
    if errors:
        print(f"Errors ({len(errors)}):", file=sys.stderr)
        for row_num, msg in errors:
            print(f"  Row {row_num}: {msg}", file=sys.stderr)
        sys.exit(1)


def template_command(args):
    """Generate a template JSON file for filling a PDF"""
    try:
        with PDFFiller(args.input, password=getattr(args, "password", None)) as filler:
            fields = filler.list_fields()

            # Create template structure
            template = {"fields": {}, "checkboxes": []}

            for field in fields:
                field_name = field["name"]
                field_type = field["type"]

                if is_push_button_type(field_type):
                    continue
                if is_checkbox_type(field_type):
                    template["checkboxes"].append(field_name)
                else:
                    template["fields"][field_name] = ""

            output = json.dumps(template, indent=2)
            _write_output(output, args.output)
            if args.output:
                print(
                    f"  Edit this file and use with: "
                    f"pdfiller fill -i {args.input} -j {args.output} -o output.pdf"
                )

    except PDFFillerError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _configure_logging() -> None:
    """Route library warnings (e.g. corrupt defaults file) to stderr.

    Without this, load_defaults() silently swallows JSON parse errors and the
    user just sees "No defaults stored" with no hint the file is broken.
    """
    pkg_logger = logging.getLogger("pdfiller")
    if not pkg_logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("Warning: %(message)s"))
        pkg_logger.addHandler(handler)
        pkg_logger.setLevel(logging.WARNING)


def main():
    """Main CLI entry point"""
    _configure_logging()
    parser = argparse.ArgumentParser(
        description="PDFiller - Fill PDF forms from the command line",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all fields in a PDF
  pdfiller list -i form.pdf

  # Fill fields from JSON
  pdfiller fill -i form.pdf -j values.json -o filled.pdf

  # Fill a non-fillable PDF with coordinate overlays (see 'inspect' for coordinates)
  # values.json: {"texts": [{"text": "Guy", "x": 200, "y": 150, "page": 0}],
  #               "images": [{"path": "sig.png", "x0": 100, "y0": 500, "x1": 300, "y1": 550}]}
  pdfiller fill -i scan.pdf -j values.json -o filled.pdf

  # Fill specific fields
  pdfiller fill -i form.pdf -f "name=John Doe" -f "age=30" -c agree_checkbox -o filled.pdf

  # Generate a template JSON
  pdfiller template -i form.pdf -o template.json

  # Batch fill from CSV (one PDF per row)
  pdfiller batch -i form.pdf --csv data.csv --output-dir ./filled/
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # List command
    list_parser = subparsers.add_parser("list", help="List all fields in a PDF")
    list_parser.set_defaults(func=list_fields_command)
    list_parser.add_argument("-i", "--input", required=True, help="Input PDF file")
    list_parser.add_argument("-o", "--output", help="Save output to file (optional)")
    list_parser.add_argument(
        "--format",
        choices=["table", "json", "csv"],
        default="table",
        help="Output format (default: table)",
    )

    # Fill command
    fill_parser = subparsers.add_parser("fill", help="Fill PDF form fields")
    fill_parser.set_defaults(func=fill_command)
    fill_parser.add_argument("-i", "--input", required=True, help="Input PDF file")
    fill_parser.add_argument(
        "-o",
        "--output",
        help=(
            "Output PDF file (default: <input_stem><suffix>.pdf next to the input; "
            "suffix from config output_suffix, default _filled)"
        ),
    )
    fill_parser.add_argument(
        "-j",
        "--values-json",
        help=(
            "JSON file with field values; optional overlay sections "
            "'texts', 'boxes', 'images' place content by coordinates "
            "(works on non-fillable PDFs)"
        ),
    )
    fill_parser.add_argument("-f", "--field", action="append", help="Field to fill (name=value)")
    fill_parser.add_argument("-c", "--checkbox", action="append", help="Checkbox to check")
    fill_parser.add_argument(
        "--no-flatten",
        dest="flatten",
        action="store_false",
        default=None,
        help="Do not flatten the PDF (overrides config flatten; not recommended)",
    )
    fill_parser.add_argument(
        "--preserve-existing", action="store_true", help="Preserve existing field values"
    )
    fill_parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate field names before filling; exit non-zero if any are missing",
    )
    fill_parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail immediately when a field, checkbox, or dropdown value does not exist",
    )
    fill_parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be filled without saving"
    )
    fill_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Print detailed info about fields being filled"
    )
    fill_parser.add_argument(
        "--redact",
        action="store_true",
        help="Mask field values in --verbose/--dry-run output (shows names and lengths only)",
    )
    fill_parser.add_argument(
        "--no-auto-dates",
        action="store_true",
        help="Disable automatic date filling for empty date fields",
    )
    fill_parser.add_argument(
        "--date-format",
        help=(
            "strftime pattern for auto-filled date fields (e.g. %%Y-%%m-%%d); "
            "overrides config.toml and _meta.date_format"
        ),
    )
    fill_parser.add_argument(
        "-d", "--use-defaults", action="store_true", help="Auto-fill fields from stored defaults"
    )

    # Batch command
    batch_parser = subparsers.add_parser("batch", help="Fill a PDF for each row in a CSV file")
    batch_parser.set_defaults(func=batch_command)
    batch_parser.add_argument("-i", "--input", required=True, help="Input PDF file")
    batch_parser.add_argument(
        "--csv", required=True, help="CSV file with field values (header = field names)"
    )
    batch_parser.add_argument(
        "--output-dir", default=".", help="Output directory (default: current directory)"
    )
    batch_parser.add_argument(
        "--no-flatten",
        dest="flatten",
        action="store_false",
        default=None,
        help="Do not flatten the PDFs (overrides config flatten; not recommended)",
    )
    batch_parser.add_argument(
        "--no-auto-dates",
        action="store_true",
        help="Disable automatic date filling for empty date fields",
    )
    batch_parser.add_argument(
        "--date-format",
        help=(
            "strftime pattern for auto-filled date fields (e.g. %%Y-%%m-%%d); "
            "overrides config.toml and _meta.date_format"
        ),
    )
    batch_parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail a row when a CSV column does not match a form field",
    )
    batch_parser.add_argument(
        "--name-from",
        help=(
            "Name each output PDF from this CSV column "
            "(e.g. --name-from name yields <stem>_<value>.pdf); "
            "a reserved '_output' CSV column overrides this per row"
        ),
    )
    batch_parser.add_argument(
        "--map",
        action="append",
        help="Map a form field to a CSV column (field=column); repeatable",
    )

    # Inspect command
    inspect_parser = subparsers.add_parser(
        "inspect", help="Inspect text layout of a non-fillable PDF"
    )
    inspect_parser.set_defaults(func=inspect_command)
    inspect_parser.add_argument("-i", "--input", required=True, help="Input PDF file")

    # Export command
    export_parser = subparsers.add_parser("export", help="Extract field values from a filled PDF")
    export_parser.set_defaults(func=export_command)
    export_parser.add_argument("-i", "--input", required=True, help="Input PDF file")
    export_parser.add_argument(
        "-o", "--output", help="Output JSON file (prints to stdout if omitted)"
    )

    # Template command
    template_parser = subparsers.add_parser("template", help="Generate template JSON for a PDF")
    template_parser.set_defaults(func=template_command)
    template_parser.add_argument("-i", "--input", required=True, help="Input PDF file")
    template_parser.add_argument(
        "-o", "--output", help="Output JSON template file (prints to stdout if omitted)"
    )

    # Every command that opens a PDF accepts an optional password. An empty
    # password is tried automatically, so this is only needed for PDFs with a
    # non-empty user password.
    for pdf_parser in (
        list_parser,
        fill_parser,
        batch_parser,
        inspect_parser,
        export_parser,
        template_parser,
    ):
        pdf_parser.add_argument(
            "--password", help="Password for an encrypted PDF (empty password is tried first)"
        )

    # Defaults command
    defaults_parser = subparsers.add_parser("defaults", help="Manage stored defaults")
    defaults_parser.set_defaults(func=defaults_command)
    defaults_sub = defaults_parser.add_subparsers(dest="defaults_action", help="Defaults action")

    defaults_sub.add_parser("show", help="Display current defaults")

    get_parser = defaults_sub.add_parser("get", help="Get a specific default value")
    get_parser.add_argument("key", help="Key in dot notation (e.g., personal.phone)")

    set_parser = defaults_sub.add_parser("set", help="Set a default value")
    set_parser.add_argument("key", help="Key in dot notation (e.g., personal.phone)")
    set_parser.add_argument("value", help="Value to store")

    add_parser = defaults_sub.add_parser(
        "add", help="Append a value to a list default (creates the list if absent)"
    )
    add_parser.add_argument("key", help="Key in dot notation (e.g., personal.phone)")
    add_parser.add_argument("value", help="Value to append")

    remove_parser = defaults_sub.add_parser("remove", help="Remove a default value")
    remove_parser.add_argument("key", help="Key in dot notation (e.g., personal.phone)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # The defaults command has nested subcommands; with no action, show its help.
    if args.command == "defaults" and not args.defaults_action:
        defaults_parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
