# PDFiller

A simple Python library and CLI tool for filling PDF forms with automatic flattening to ensure compatibility across all PDF viewers.

## Features

- 🔧 **Fill text fields** - Set values for any text input field
- ☑️ **Check/uncheck checkboxes** - Handle checkbox fields
- 📄 **Automatic flattening** - Converts form fields to static text for universal compatibility
- 🔍 **Field discovery** - List all available fields in a PDF
- 🎯 **Preserve existing values** - Option to keep pre-filled fields
- 🛠️ **CLI and Python API** - Use from command line or as a library
- 📋 **Template generation** - Auto-generate JSON templates for forms

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
```

## API Reference

### PDFFiller Class

#### Methods

**`__init__(pdf_path: str)`**
- Initialize with a PDF file path

**`list_fields() -> List[Dict]`**
- Returns list of all form fields with their properties

**`fill_field(field_name: str, value: Any) -> PDFFiller`**
- Fill a single field. Returns self for chaining.

**`fill_fields(fields: Dict[str, Any]) -> PDFFiller`**
- Fill multiple fields at once. Returns self for chaining.

**`check_box(field_name: str) -> PDFFiller`**
- Check a checkbox field. Returns self for chaining.

**`uncheck_box(field_name: str) -> PDFFiller`**
- Uncheck a checkbox field. Returns self for chaining.

**`preserve_existing_fields(preserve: bool = True) -> PDFFiller`**
- Set whether to preserve existing field values

**`validate_fields(field_names: List[str], raise_error: bool = False) -> Dict[str, bool]`**
- Validate that field names exist in the PDF

**`save(output_path: str, flatten: bool = True) -> Path`**
- Save the filled PDF. `flatten=True` (recommended) ensures values are visible in all viewers.

**`get_field_value(field_name: str) -> Any`**
- Get the current value of a field

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
- ✓ Values are visible in all PDF viewers
- ✓ Forms can't be accidentally edited
- ✓ Consistent appearance across platforms

We recommend always using `flatten=True` (the default) when saving.

## Troubleshooting

**Q: Filled values don't show up in the PDF**
- A: Use `flatten=True` when calling `save()` (this is the default)

**Q: How do I find field names?**
- A: Use `filler.list_fields()` or run `pdfiller list -i form.pdf`

**Q: Can I fill multi-page PDFs?**
- A: Currently only single-page PDFs are supported. Multi-page support coming soon.

**Q: Field names have weird characters**
- A: Some PDFs use internal names like "field_1" or "Text1". Use the `list` command to see actual names.

## Dependencies

- **PyMuPDF (fitz)** - PDF manipulation
- Python 3.8+

## License

MIT License - Feel free to use in your projects!

## Contributing

Contributions welcome! Some areas for improvement:
- Multi-page PDF support
- Radio button support
- Dropdown/combo box support
- Batch processing multiple PDFs
- GUI interface

## Credits

Created with Claude Code for easy PDF form filling.
