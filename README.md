# PDFiller

A simple Python library and CLI tool for filling PDF forms with automatic flattening to ensure compatibility across all PDF viewers.

## Features

- **Fill text fields** - Set values for any text input field
- **Check/uncheck checkboxes** - Handle checkbox fields
- **Automatic flattening** - Converts form fields to static text for universal compatibility
- **Field discovery** - List all available fields in a PDF
- **Preserve existing values** - Option to keep pre-filled fields
- **CLI and Python API** - Use from command line or as a library
- **Template generation** - Auto-generate JSON templates for forms

## Installation

```bash
pip install PyMuPDF

# Then install pdfiller
cd pdfiller
pip install -e .
```

## Quick Start

### Python API

```python
from pdfiller import PDFFiller

# Basic usage
with PDFFiller("input.pdf") as filler:
    # Fill text fields
    filler.fill_field("name", "John Doe")
    filler.fill_field("email", "john@example.com")

    # Check checkboxes
    filler.check_box("agree_to_terms")

    # Save (flatten=True ensures values are visible)
    filler.save("output.pdf", flatten=True)

# Method chaining
with PDFFiller("form.pdf") as filler:
    filler.fill_field("first_name", "Jane") \
          .fill_field("last_name", "Smith") \
          .check_box("newsletter") \
          .save("filled_form.pdf")

# Fill multiple fields at once
fields = {
    "name": "Alice Johnson",
    "address": "123 Main St",
    "city": "Springfield",
    "zip": "12345"
}

with PDFFiller("form.pdf") as filler:
    filler.fill_fields(fields)
    filler.save("output.pdf")
```

### Command Line Interface

```bash
# List all fields in a PDF
pdfiller list -i form.pdf

# Save field list to JSON
pdfiller list -i form.pdf -o fields.json

# Generate a template for filling
pdfiller template -i form.pdf -o template.json

# Fill from JSON file
pdfiller fill -i form.pdf -j values.json -o filled.pdf

# Fill specific fields from command line
pdfiller fill -i form.pdf \
    -f "name=John Doe" \
    -f "email=john@example.com" \
    -c "agree_checkbox" \
    -o filled.pdf

# Preserve existing values (only fill empty fields)
pdfiller fill -i form.pdf -j values.json -o filled.pdf --preserve-existing

# Fill a non-fillable PDF via coordinate overlays in the JSON
# ("texts", "boxes", "images" sections; see docs/USAGE.md)
pdfiller fill -i scan.pdf -j values.json -o filled.pdf
```

## API Reference

### PDFFiller Class

#### Constructor

**`__init__(pdf_path: str, auto_fill_dates: bool = True, strict: bool = False)`**
- Initialize with a PDF file path
- `auto_fill_dates` - When True, empty date fields are automatically filled with today's date during save
- `strict` - When True, `fill_field`, `check_box`, and `uncheck_box` raise `FieldNotFoundError` if the field does not exist

#### Properties

**`page_count -> int`**
- Number of pages in the PDF

#### Methods

**`has_form_fields() -> bool`**
- Check whether the PDF has any AcroForm fields. Returns True if at least one widget exists.

**`list_fields() -> List[Dict]`**
- Returns list of all form fields with their properties

**`get_field_value(field_name: str) -> Any`**
- Get the current value of a field

**`get_page_layout(page_num: int = 0) -> Dict`**
- Extract text blocks with positions and page dimensions. Returns a dict with `width`, `height`, and `blocks` (list of text block dicts with `text` and `bbox` keys). Useful for figuring out where to place text on non-fillable PDFs.

**`fill_field(field_name: str, value: Any) -> PDFFiller`**
- Fill a single field. Returns self for chaining.

**`fill_fields(fields: Dict[str, Any]) -> PDFFiller`**
- Fill multiple fields at once. Returns self for chaining.

**`check_box(field_name: str) -> PDFFiller`**
- Check a checkbox field. Returns self for chaining.

**`uncheck_box(field_name: str) -> PDFFiller`**
- Uncheck a checkbox field. Returns self for chaining.

**`insert_text(text, x, y, page_num=0, font_size=10, font_name="helv", color=(0,0,0)) -> PDFFiller`**
- Insert text at specific coordinates on a page. Coordinates are in points from the top-left corner. Returns self for chaining.

**`insert_text_box(text, x0, y0, x1, y1, page_num=0, font_size=10, font_name="helv", color=(0,0,0)) -> PDFFiller`**
- Insert text in a bounding box with automatic wrapping. Returns self for chaining.

**`insert_image(image_path, x0, y0, x1, y1, page_num=0, keep_proportion=True) -> PDFFiller`**
- Insert an image (PNG, GIF, JPEG) at specific coordinates. Useful for signatures, stamps, or logos. `keep_proportion` maintains aspect ratio within the box. Returns self for chaining.

**`preserve_existing_fields(preserve: bool = True) -> PDFFiller`**
- Set whether to preserve existing field values

**`validate_fields(field_names: List[str], raise_error: bool = False) -> Dict[str, bool]`**
- Validate that field names exist in the PDF

**`save(output_path: str, flatten: bool = True) -> Path`**
- Save the filled PDF. `flatten=True` (recommended) ensures values are visible in all viewers.

## Defaults System

PDFiller can remember common field values (name, email, address, etc.) so they are auto-filled across sessions.

### Storage

Defaults are stored in `~/.pdfiller/defaults.json`. Override the location with the `PDFILLER_DEFAULTS` environment variable.

The file uses nested categories:

```json
{
  "personal": {
    "first_name": "Guy",
    "last_name": "Smith",
    "email": "guy@example.com",
    "phone": ["555-1234", "555-5678"]
  },
  "address": {
    "street": "123 Main St",
    "city": "Springfield",
    "state": "IL",
    "zip": "62704"
  }
}
```

List values (like `phone` above) let you store multiple options. When matched, PDFiller returns the list so you can pick one.

### API

**`load_defaults(path=None) -> Dict`**
- Load defaults from JSON file. Returns empty dict if file is missing.

**`save_defaults(data: Dict, path=None) -> Path`**
- Save defaults to JSON file. Creates parent directories if needed. Adds a `_meta.updated` timestamp.

**`flatten_defaults(data: Dict) -> Dict[str, Union[str, List[str]]]`**
- Flatten nested categories into a single `{field_name: value}` dict for matching.

**`match_field_to_defaults(field_name: str, defaults: Dict) -> Optional[Union[str, List[str]]]`**
- Match a PDF field name to a stored default. Tries exact match first, then normalized fuzzy match (e.g. `first_name` matches `FirstName`). Returns the value, or None if no match.

### Example

```python
from pdfiller import PDFFiller, load_defaults, flatten_defaults, match_field_to_defaults

defaults = flatten_defaults(load_defaults())

filler = PDFFiller("form.pdf")
fields = filler.list_fields()

values = {}
for field in fields:
    match = match_field_to_defaults(field["name"], defaults)
    if isinstance(match, str):
        values[field["name"]] = match
    elif isinstance(match, list):
        print(f"{field['name']}: pick from {match}")

filler.fill_fields(values)
filler.save("form_filled.pdf")
```

## JSON Format

When using JSON files to fill PDFs, use this format:

```json
{
  "fields": {
    "field_name_1": "value1",
    "field_name_2": "value2",
    "email": "user@example.com"
  },
  "checkboxes": [
    "checkbox_field_1",
    "checkbox_field_2"
  ]
}
```

## Examples

### Example 1: Medical Consent Form

```python
from pdfiller import PDFFiller

with PDFFiller("consent_form.pdf") as filler:
    # Patient information
    filler.fill_fields({
        "patient_name": "John Smith",
        "date_of_birth": "01/15/1985",
        "physician_name": "Dr. Jane Doe",
        "medication": "Aspirin 100mg",
        "dosage": "Once daily"
    })

    # Consent checkboxes
    filler.check_box("consent_treatment")
    filler.check_box("consent_privacy")

    # Save
    filler.save("filled_consent.pdf")
```

### Example 2: Job Application

```python
from pdfiller import PDFFiller

applicant_data = {
    "first_name": "Jane",
    "last_name": "Doe",
    "email": "jane@email.com",
    "phone": "555-0123",
    "position": "Software Engineer",
    "experience_years": "5"
}

with PDFFiller("job_application.pdf") as filler:
    filler.fill_fields(applicant_data)
    filler.check_box("authorize_background_check")
    filler.save("application_filled.pdf")
```

### Example 3: Discover Fields First

```python
from pdfiller import PDFFiller

# First, see what fields are available
with PDFFiller("unknown_form.pdf") as filler:
    fields = filler.list_fields()

    print("Available fields:")
    for field in fields:
        print(f"  - {field['name']} ({field['type']})")
        if field['value']:
            print(f"    Current value: {field['value']}")
```

## Why Flattening?

PDF form fields need "appearance streams" to display properly. Not all PDF creation tools generate these correctly, causing filled values to be invisible in some viewers.

**Flattening** converts form fields into regular text annotations, ensuring:
- Values are visible in all PDF viewers
- Forms can't be accidentally edited
- Consistent appearance across platforms

We recommend always using `flatten=True` (the default) when saving.

## Troubleshooting

**Q: Filled values don't show up in the PDF**
- A: Use `flatten=True` when calling `save()` (this is the default)

**Q: How do I find field names?**
- A: Use `filler.list_fields()` or run `pdfiller list -i form.pdf`

**Q: Can I fill multi-page PDFs?**
- A: Yes! Multi-page PDFs are fully supported. Fields on all pages are listed, filled, and flattened.

**Q: Field names have weird characters**
- A: Some PDFs use internal names like "field_1" or "Text1". Use the `list` command to see actual names.

## Dependencies

- **PyMuPDF (fitz)** - PDF manipulation
- Python 3.8+

## License

MIT License - Feel free to use in your projects!

## Contributing

Contributions welcome! Some areas for improvement:
- Radio button support
- Dropdown/combo box support
- Batch processing multiple PDFs
- GUI interface

## Credits

Created with Claude Code for easy PDF form filling.
