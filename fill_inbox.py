#!/usr/bin/env python3
"""Interactively fill every PDF in an inbox directory using stored defaults.

For each fillable PDF: fields that match a stored default are filled
automatically. Fields with no match, or with more than one stored value,
are asked about at the terminal. Signature-like fields are asked about
separately (path to an image, or skip). Non-fillable PDFs are skipped -
those need the coordinate-overlay workflow (see /fill-pdf) instead.

Usage: fill_inbox.py [inbox_dir]
  inbox_dir defaults to ~/pdfiller-inbox
"""

import sys
from pathlib import Path

from pdfiller import PDFFiller, flatten_defaults, load_defaults, match_field_to_defaults
from pdfiller.fields import is_checkbox_type, is_push_button_type

_YES = {"y", "yes"}


def _prompt(text: str) -> str:
    try:
        return input(text).strip()
    except EOFError:
        return ""


def _resolve_choice(name: str, candidates: list) -> str:
    """Ask the user to pick from a numbered list, or type their own value."""
    print(f"  '{name}' - multiple options:")
    for i, opt in enumerate(candidates, 1):
        print(f"    {i}. {opt}")
    while True:
        raw = _prompt(f"  Choose 1-{len(candidates)}, type a value, or leave blank to skip: ")
        if not raw:
            return ""
        if raw.isdigit() and 1 <= int(raw) <= len(candidates):
            return candidates[int(raw) - 1]
        return raw


def _resolve_field(name: str, match, options: list) -> str:
    """Determine the value for one field, asking the user when needed."""
    if options:
        candidates = list(dict.fromkeys(options + ([match] if isinstance(match, str) else [])))
        if isinstance(match, str) and match in options:
            return match
        return _resolve_choice(name, candidates)
    if isinstance(match, str):
        return match
    if isinstance(match, list):
        return _resolve_choice(name, match)
    return _prompt(f"  '{name}' - no default found, enter value (blank to skip): ")


def _handle_signature(filler: PDFFiller, field: dict) -> None:
    name = field["name"]
    print(f"  Signature field detected: '{name}' on page {field['page']}")
    path = _prompt("  Path to signature image (PNG/GIF), or leave blank to skip: ")
    if not path:
        return
    rect = field["rect"]
    filler.insert_image(path, rect["x0"], rect["y0"], rect["x1"], rect["y1"], page_num=field["page"])


def fill_one(pdf_path: Path, output_dir: Path, defaults: dict) -> None:
    print(f"\n=== {pdf_path.name} ===")
    with PDFFiller(pdf_path) as filler:
        if not filler.has_form_fields():
            print("  Not a fillable form - skipping (use /fill-pdf for scanned/overlay forms).")
            return

        fields = filler.list_fields()

        for field in fields:
            name = field["name"]
            ftype = field.get("type", "")

            if is_push_button_type(ftype):
                continue

            if "signature" in name.lower():
                _handle_signature(filler, field)
                continue

            match = match_field_to_defaults(name, defaults)

            if is_checkbox_type(ftype):
                if isinstance(match, str):
                    if match.lower() in _YES:
                        filler.check_box(name)
                    continue
                answer = _prompt(f"  Check '{name}'? [y/N]: ")
                if answer.lower() in _YES:
                    filler.check_box(name)
                continue

            if match is None and PDFFiller._is_date_field(name):
                continue  # left empty; auto-fill-dates fills it on save

            value = _resolve_field(name, match, field.get("options") or [])
            if value:
                filler.fill_field(name, value)

        output_path = output_dir / f"{pdf_path.stem}_filled.pdf"
        saved = filler.save(str(output_path))
        print(f"  Saved: {saved}")


def main():
    inbox = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "pdfiller-inbox"
    output_dir = inbox / "filled"
    output_dir.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(set(inbox.glob("*.pdf")) | set(inbox.glob("*.PDF")))
    if not pdfs:
        print(f"No PDFs found in {inbox}")
        return

    defaults = flatten_defaults(load_defaults())

    filled, errors = 0, 0
    for pdf in pdfs:
        try:
            fill_one(pdf, output_dir, defaults)
            filled += 1
        except Exception as e:
            print(f"  ERROR: {e}", file=sys.stderr)
            errors += 1

    print(f"\nDone: {filled} filled, {errors} errors")
    print(f"Output: {output_dir}")


if __name__ == "__main__":
    main()
