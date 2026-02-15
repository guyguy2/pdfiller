"""
Command-line interface for PDFiller
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any

from .core import PDFFiller
from .exceptions import PDFFillerError


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


def list_fields_command(args):
    """List all fields in a PDF"""
    try:
        with PDFFiller(args.input) as filler:
            fields = filler.list_fields()

            if args.output:
                # Save to JSON
                with open(args.output, 'w') as f:
                    json.dump(fields, f, indent=2)
                print(f"Saved: {args.output}")
            else:
                # Print to console
                print(f"\nFound {len(fields)} fields in {args.input}:\n")
                for field in fields:
                    print(f"  - {field['name']}")
                    print(f"    Type: {field['type']}")
                    if field['value']:
                        print(f"    Current value: {field['value']}")
                    print()

    except PDFFillerError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def fill_command(args):
    """Fill PDF fields from JSON or command-line arguments"""
    try:
        with PDFFiller(args.input) as filler:

            # Set preserve mode
            filler.preserve_existing_fields(args.preserve_existing)

            # Load values from JSON if provided
            if args.values_json:
                data = load_values_from_json(args.values_json)

                # Separate text fields and checkboxes
                text_fields = data.get('fields', {})
                checkboxes = data.get('checkboxes', [])

                # Fill text fields
                filler.fill_fields(text_fields)

                # Check checkboxes
                for checkbox in checkboxes:
                    filler.check_box(checkbox)

            # Override with command-line field arguments
            if args.field:
                for field_spec in args.field:
                    if '=' not in field_spec:
                        print(f"Error: Invalid field format '{field_spec}', expected name=value", file=sys.stderr)
                        sys.exit(1)
                    name, value = field_spec.split('=', 1)
                    filler.fill_field(name, value)

            # Check command-line checkbox arguments
            if args.checkbox:
                for checkbox in args.checkbox:
                    filler.check_box(checkbox)

            # Validate fields if requested
            if args.validate:
                all_fields = list(text_fields.keys()) if args.values_json else []
                if args.field:
                    all_fields.extend([f.split('=')[0] for f in args.field])

                if all_fields:
                    results = filler.validate_fields(all_fields)
                    invalid = [name for name, exists in results.items() if not exists]
                    if invalid:
                        print(f"Warning: Fields not found: {', '.join(invalid)}", file=sys.stderr)

            # Save the filled PDF
            output_path = filler.save(args.output, flatten=args.flatten)
            print(f"Done: {output_path}")

    except PDFFillerError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def template_command(args):
    """Generate a template JSON file for filling a PDF"""
    try:
        with PDFFiller(args.input) as filler:
            fields = filler.list_fields()

            # Create template structure
            template = {
                "fields": {},
                "checkboxes": []
            }

            for field in fields:
                field_name = field['name']
                field_type = field['type']

                if 'Button' in field_type:
                    template['checkboxes'].append(field_name)
                else:
                    template['fields'][field_name] = ""

            # Save template
            with open(args.output, 'w') as f:
                json.dump(template, f, indent=2)

            print(f"Saved: {args.output}")
            print(f"  Edit this file and use with: pdfiller fill -i {args.input} -j {args.output} -o output.pdf")

    except PDFFillerError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="PDFiller - Fill PDF forms from the command line",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all fields in a PDF
  pdfiller list -i form.pdf

  # Fill fields from JSON
  pdfiller fill -i form.pdf -j values.json -o filled.pdf

  # Fill specific fields
  pdfiller fill -i form.pdf -f "name=John Doe" -f "age=30" -c agree_checkbox -o filled.pdf

  # Generate a template JSON
  pdfiller template -i form.pdf -o template.json
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # List command
    list_parser = subparsers.add_parser('list', help='List all fields in a PDF')
    list_parser.add_argument('-i', '--input', required=True, help='Input PDF file')
    list_parser.add_argument('-o', '--output', help='Output JSON file (optional)')

    # Fill command
    fill_parser = subparsers.add_parser('fill', help='Fill PDF form fields')
    fill_parser.add_argument('-i', '--input', required=True, help='Input PDF file')
    fill_parser.add_argument('-o', '--output', required=True, help='Output PDF file')
    fill_parser.add_argument('-j', '--values-json', help='JSON file with field values')
    fill_parser.add_argument('-f', '--field', action='append', help='Field to fill (name=value)')
    fill_parser.add_argument('-c', '--checkbox', action='append', help='Checkbox to check')
    fill_parser.add_argument('--no-flatten', dest='flatten', action='store_false',
                             help='Do not flatten the PDF (not recommended)')
    fill_parser.add_argument('--preserve-existing', action='store_true',
                             help='Preserve existing field values')
    fill_parser.add_argument('--validate', action='store_true',
                             help='Validate field names before filling')

    # Template command
    template_parser = subparsers.add_parser('template', help='Generate template JSON for a PDF')
    template_parser.add_argument('-i', '--input', required=True, help='Input PDF file')
    template_parser.add_argument('-o', '--output', required=True, help='Output JSON template file')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Execute command
    if args.command == 'list':
        list_fields_command(args)
    elif args.command == 'fill':
        fill_command(args)
    elif args.command == 'template':
        template_command(args)


if __name__ == '__main__':
    main()
