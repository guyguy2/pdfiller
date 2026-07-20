"""
Command-line interface for PDFiller
"""

import argparse
import csv
import io
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict

from .core import PDFFiller
from .exceptions import PDFFillerError
from .memory import flatten_defaults, load_defaults, match_field_to_defaults, save_defaults

# Field types treated as checkboxes (toggled, not assigned a text value).
# Push buttons (PyMuPDF type "Button") are actions, not state, and are
# excluded from both template and export output.
_CHECKBOX_FIELD_TYPES = ("CheckBox",)
_PUSH_BUTTON_FIELD_TYPES = ("Button",)

# Required keys per overlay section in the fill JSON schema
_OVERLAY_REQUIRED_KEYS = {
    "texts": ("text", "x", "y"),
    "boxes": ("text", "x0", "y0", "x1", "y1"),
    "images": ("path", "x0", "y0", "x1", "y1"),
}


def load_values_from_json(json_path: Path) -> Dict[str, Any]:
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


def _queue_overlays(filler: PDFFiller, data: Dict[str, Any]) -> int:
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


def _describe_overlays(data: Dict[str, Any]) -> list:
    """Human-readable one-line descriptions of overlay entries for dry-run/verbose."""
    lines = []
    for entry in data.get("texts", []):
        lines.append(
            f'text "{entry["text"]}" at ({entry["x"]}, {entry["y"]}) on page {entry.get("page", 0)}'
        )
    for entry in data.get("boxes", []):
        lines.append(
            f'text box "{entry["text"]}" in '
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


def _format_fields_table(fields, input_path: str) -> str:
    """Format fields as a human-readable table."""
    lines = [f"\nFound {len(fields)} fields in {input_path}:\n"]
    for field in fields:
        lines.append(f"  - {field['name']}")
        lines.append(f"    Type: {field['type']}")
        if "page" in field:
            lines.append(f"    Page: {field['page']}")
        if field.get("options"):
            lines.append(f"    Options: [{', '.join(field['options'])}]")
        if field["value"]:
            lines.append(f"    Current value: {field['value']}")
        lines.append("")
    return "\n".join(lines)


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
        with PDFFiller(args.input) as filler:
            fields = filler.list_fields()

            fmt = getattr(args, "format", None) or "table"

            if fmt == "json":
                output = _format_fields_json(fields)
            elif fmt == "csv":
                output = _format_fields_csv(fields)
            else:
                output = _format_fields_table(fields, args.input)

            if args.output:
                with open(args.output, "w") as f:
                    f.write(output)
                print(f"Saved: {args.output}")
            else:
                print(output, end="" if fmt == "csv" else "\n")

    except PDFFillerError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def fill_command(args):
    """Fill PDF fields from JSON or command-line arguments"""
    if not args.dry_run and not args.output:
        print("Error: -o/--output is required unless --dry-run is used", file=sys.stderr)
        sys.exit(1)
    try:
        auto_dates = not getattr(args, "no_auto_dates", False)
        strict = getattr(args, "strict", False)
        with PDFFiller(args.input, auto_fill_dates=auto_dates, strict=strict) as filler:
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

            # Dry run: show what would be filled without saving
            if args.dry_run:
                print(f"Dry run for {args.input}:")
                if ops["fields"]:
                    for name, value in ops["fields"].items():
                        print(f"  {name} = {value}")
                if ops["check"]:
                    for name in ops["check"]:
                        print(f"  {name} = [checked]")
                overlay_lines = _describe_overlays(data)
                for line in overlay_lines:
                    print(f"  {line}")
                if not ops["fields"] and not ops["check"] and not overlay_lines:
                    print("  (no fields to fill)")
                return

            # Verbose output before save
            verbose = getattr(args, "verbose", False)
            if verbose:
                print(f"Fill plan for {args.input}:")

                if ops["fields"]:
                    print("  Fields:")
                    for name, value in ops["fields"].items():
                        print(f"    {name} = {value}")

                if ops["check"]:
                    print("  Checkboxes:")
                    for name in ops["check"]:
                        print(f"    {name} [check]")

                overlay_lines = _describe_overlays(data)
                if overlay_lines:
                    print("  Overlays:")
                    for line in overlay_lines:
                        print(f"    {line}")

                if filler.auto_fill_dates:
                    print("  Auto-fill dates: enabled (empty date fields will use today's date)")

                if args.preserve_existing:
                    existing_fields = filler.list_fields()
                    skipped = [
                        f["name"]
                        for f in existing_fields
                        if f["value"] and f["name"] in ops["fields"]
                    ]
                    if skipped:
                        print("  Skipped (preserve existing):")
                        for name in skipped:
                            print(f"    {name}")

            # Save the filled PDF
            output_path = filler.save(args.output, flatten=args.flatten)
            summary = f"{filled_count} fields, {checked_count} checkboxes"
            if overlay_count:
                summary += f", {overlay_count} overlays"
            print(f"Done: {output_path} ({summary})")

    except PDFFillerError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def inspect_command(args):
    """Inspect a non-fillable PDF's text layout"""
    try:
        with PDFFiller(args.input) as filler:
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
        with PDFFiller(args.input) as filler:
            fields = filler.list_fields()
            data = {
                "fields": {},
                "checkboxes": [],
            }
            for field in fields:
                name = field["name"]
                value = field["value"]
                field_type = field["type"]
                if field_type in _PUSH_BUTTON_FIELD_TYPES:
                    continue
                if field_type in _CHECKBOX_FIELD_TYPES:
                    if value and value not in ("Off", ""):
                        data["checkboxes"].append(name)
                elif value:
                    data["fields"][name] = value

            output = json.dumps(data, indent=2)
            if args.output:
                Path(args.output).write_text(output)
                print(f"Saved: {args.output}")
            else:
                print(output)

    except PDFFillerError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _get_nested(data: Dict[str, Any], key: str) -> Any:
    """Get a value from a nested dict using dot notation (e.g., 'personal.phone')."""
    parts = key.split(".")
    current = data
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _set_nested(data: Dict[str, Any], key: str, value: str) -> None:
    """Set a value in a nested dict using dot notation (e.g., 'personal.phone')."""
    parts = key.split(".")
    current = data
    for part in parts[:-1]:
        current = current.setdefault(part, {})
    current[parts[-1]] = value


def _remove_nested(data: Dict[str, Any], key: str) -> bool:
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

    filled = 0
    errors = []

    for i, row in enumerate(rows, start=1):
        seq = f"{i:03d}"
        output_file = output_dir / f"{stem}_filled_{seq}.pdf"
        try:
            with PDFFiller(
                args.input,
                auto_fill_dates=not args.no_auto_dates,
                strict=getattr(args, "strict", False),
            ) as filler:
                # Every CSV column is applied as a field value by name. Checkbox
                # columns are set through the same path, so they only toggle when
                # the cell holds the checkbox export value (e.g. "On"/"Off"), not
                # an arbitrary truthy string.
                for field_name, value in row.items():
                    if value is None:
                        continue
                    filler.fill_field(field_name, value)
                filler.save(str(output_file), flatten=args.flatten)
            filled += 1
        except Exception as e:
            errors.append((i, str(e)))

    print(f"Filled {filled} PDFs from {csv_path.name}")
    if errors:
        print(f"Errors ({len(errors)}):", file=sys.stderr)
        for row_num, msg in errors:
            print(f"  Row {row_num}: {msg}", file=sys.stderr)
        sys.exit(1)


def template_command(args):
    """Generate a template JSON file for filling a PDF"""
    try:
        with PDFFiller(args.input) as filler:
            fields = filler.list_fields()

            # Create template structure
            template = {"fields": {}, "checkboxes": []}

            for field in fields:
                field_name = field["name"]
                field_type = field["type"]

                if field_type in _PUSH_BUTTON_FIELD_TYPES:
                    continue
                if field_type in _CHECKBOX_FIELD_TYPES:
                    template["checkboxes"].append(field_name)
                else:
                    template["fields"][field_name] = ""

            # Save template
            with open(args.output, "w") as f:
                json.dump(template, f, indent=2)

            print(f"Saved: {args.output}")
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
    fill_parser.add_argument("-i", "--input", required=True, help="Input PDF file")
    fill_parser.add_argument("-o", "--output", help="Output PDF file (required unless --dry-run)")
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
        help="Do not flatten the PDF (not recommended)",
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
        "--no-auto-dates",
        action="store_true",
        help="Disable automatic date filling for empty date fields",
    )
    fill_parser.add_argument(
        "-d", "--use-defaults", action="store_true", help="Auto-fill fields from stored defaults"
    )

    # Batch command
    batch_parser = subparsers.add_parser("batch", help="Fill a PDF for each row in a CSV file")
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
        help="Do not flatten the PDFs (not recommended)",
    )
    batch_parser.add_argument(
        "--no-auto-dates",
        action="store_true",
        help="Disable automatic date filling for empty date fields",
    )
    batch_parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail a row when a CSV column does not match a form field",
    )

    # Inspect command
    inspect_parser = subparsers.add_parser(
        "inspect", help="Inspect text layout of a non-fillable PDF"
    )
    inspect_parser.add_argument("-i", "--input", required=True, help="Input PDF file")

    # Export command
    export_parser = subparsers.add_parser("export", help="Extract field values from a filled PDF")
    export_parser.add_argument("-i", "--input", required=True, help="Input PDF file")
    export_parser.add_argument(
        "-o", "--output", help="Output JSON file (prints to stdout if omitted)"
    )

    # Template command
    template_parser = subparsers.add_parser("template", help="Generate template JSON for a PDF")
    template_parser.add_argument("-i", "--input", required=True, help="Input PDF file")
    template_parser.add_argument("-o", "--output", required=True, help="Output JSON template file")

    # Defaults command
    defaults_parser = subparsers.add_parser("defaults", help="Manage stored defaults")
    defaults_sub = defaults_parser.add_subparsers(dest="defaults_action", help="Defaults action")

    defaults_sub.add_parser("show", help="Display current defaults")

    get_parser = defaults_sub.add_parser("get", help="Get a specific default value")
    get_parser.add_argument("key", help="Key in dot notation (e.g., personal.phone)")

    set_parser = defaults_sub.add_parser("set", help="Set a default value")
    set_parser.add_argument("key", help="Key in dot notation (e.g., personal.phone)")
    set_parser.add_argument("value", help="Value to store")

    remove_parser = defaults_sub.add_parser("remove", help="Remove a default value")
    remove_parser.add_argument("key", help="Key in dot notation (e.g., personal.phone)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Execute command
    if args.command == "list":
        list_fields_command(args)
    elif args.command == "fill":
        fill_command(args)
    elif args.command == "batch":
        batch_command(args)
    elif args.command == "inspect":
        inspect_command(args)
    elif args.command == "export":
        export_command(args)
    elif args.command == "template":
        template_command(args)
    elif args.command == "defaults":
        if not args.defaults_action:
            defaults_parser.print_help()
            sys.exit(1)
        defaults_command(args)


if __name__ == "__main__":
    main()
