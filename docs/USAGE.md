# PDFiller Usage Guide

Complete guide for using PDFiller to fill PDF forms.

## Table of Contents

1. [Installation](#installation)
2. [Quick Start](#quick-start)
3. [Python API](#python-api)
4. [Command Line Interface](#command-line-interface)
5. [Common Patterns](#common-patterns)
6. [Troubleshooting](#troubleshooting)

## Installation

### Option 1: Install as Package

```bash
cd pdfiller
pip install -e .
```

This installs the `pdfiller` command globally.

### Option 2: Use Directly

```bash
pip install PyMuPDF
python -m pdfiller.cli --help
```

## Quick Start

### 1. Discover Fields in Your PDF

Before filling a form, see what fields are available:

```bash
# CLI
pdfiller list -i myform.pdf

# Python
from pdfiller import PDFFiller

with PDFFiller("myform.pdf") as filler:
    fields = filler.list_fields()
    for field in fields:
        print(f"{field['name']}: {field['type']}")
```

### 2. Fill the Form

```python
from pdfiller import PDFFiller

with PDFFiller("myform.pdf") as filler:
    # Fill text fields
    filler.fill_field("name", "John Doe")
    filler.fill_field("email", "john@example.com")

    # Check boxes
    filler.check_box("agree")

    # Save (flatten=True makes it compatible with all viewers)
    filler.save("filled.pdf", flatten=True)
```

## Python API

### Basic Usage

```python
from pdfiller import PDFFiller

# Using context manager (recommended)
with PDFFiller("input.pdf") as filler:
    filler.fill_field("fieldname", "value")
    filler.save("output.pdf")

# Manual close
filler = PDFFiller("input.pdf")
filler.fill_field("fieldname", "value")
filler.save("output.pdf")
filler.close()
```

### Fill Multiple Fields

```python
data = {
    "first_name": "Jane",
    "last_name": "Smith",
    "email": "jane@email.com",
    "phone": "555-0123"
}

with PDFFiller("form.pdf") as filler:
    filler.fill_fields(data)
    filler.save("output.pdf")
```

### Method Chaining

```python
with PDFFiller("form.pdf") as filler:
    (filler
        .fill_field("name", "John")
        .fill_field("age", "30")
        .check_box("consent")
        .save("output.pdf"))
```

### Preserve Existing Values

Only fill empty fields, keep pre-filled values:

```python
with PDFFiller("partially_filled.pdf") as filler:
    filler.preserve_existing_fields(True)
    filler.fill_fields(my_data)
    filler.save("output.pdf")
```

### Validate Field Names

```python
with PDFFiller("form.pdf") as filler:
    # Check if fields exist
    fields = ["name", "email", "invalid_field"]
    results = filler.validate_fields(fields)

    for field, exists in results.items():
        print(f"{field}: {'✓' if exists else '✗'}")

    # Raise error if field doesn't exist
    filler.validate_fields(["name"], raise_error=True)
```

### Get Current Field Values

```python
with PDFFiller("form.pdf") as filler:
    current_name = filler.get_field_value("name")
    print(f"Current name: {current_name}")
```

### Checkboxes

```python
with PDFFiller("form.pdf") as filler:
    # Check a box
    filler.check_box("agree_terms")

    # Uncheck a box (remove from check list)
    filler.uncheck_box("newsletter")

    filler.save("output.pdf")
```

## Command Line Interface

### List Fields

```bash
# Print to console
pdfiller list -i form.pdf

# Save to JSON
pdfiller list -i form.pdf -o fields.json
```

### Generate Template

Creates a JSON template you can fill in:

```bash
pdfiller template -i form.pdf -o template.json

# Edit template.json with your values
# Then use it to fill the form:
pdfiller fill -i form.pdf -j template.json -o filled.pdf
```

### Fill from JSON

Create a `values.json`:

```json
{
  "fields": {
    "name": "John Doe",
    "email": "john@example.com",
    "address": "123 Main St"
  },
  "checkboxes": [
    "agree_terms",
    "newsletter"
  ]
}
```

Fill the PDF:

```bash
pdfiller fill -i form.pdf -j values.json -o filled.pdf
```

### Fill from Command Line

```bash
# Fill specific fields
pdfiller fill -i form.pdf \
    -f "name=John Doe" \
    -f "email=john@example.com" \
    -f "phone=555-0123" \
    -c "agree_checkbox" \
    -c "consent_checkbox" \
    -o filled.pdf
```

### Preserve Existing Values

```bash
pdfiller fill -i form.pdf -j values.json -o filled.pdf --preserve-existing
```

### No Flattening (Not Recommended)

```bash
# Keep form editable (may not display in all viewers)
pdfiller fill -i form.pdf -j values.json -o filled.pdf --no-flatten
```

### Validate Before Filling

```bash
pdfiller fill -i form.pdf -j values.json -o filled.pdf --validate
```

## Common Patterns

### Pattern 1: Form with Pre-filled Header

Many forms have some fields already filled (like student info). Only fill the empty parts:

```python
with PDFFiller("form_with_header.pdf") as filler:
    # Keep existing values
    filler.preserve_existing_fields(True)

    # Only fill the new parts
    filler.fill_fields({
        "physician_name": "Dr. Smith",
        "medication": "Aspirin",
        "dosage": "100mg"
    })

    filler.save("completed.pdf")
```

### Pattern 2: Batch Processing

Fill multiple forms with different data:

```python
from pdfiller import PDFFiller

applicants = [
    {"name": "John Doe", "email": "john@example.com"},
    {"name": "Jane Smith", "email": "jane@example.com"},
]

template = "application_template.pdf"

for i, applicant in enumerate(applicants):
    with PDFFiller(template) as filler:
        filler.fill_fields(applicant)
        filler.save(f"application_{i+1}.pdf")
```

### Pattern 3: Conditional Checkboxes

```python
def fill_medical_form(patient_data):
    with PDFFiller("medical_form.pdf") as filler:
        # Fill text fields
        filler.fill_fields(patient_data)

        # Conditional checkboxes
        if patient_data.get("has_allergies"):
            filler.check_box("allergies_yes")
        else:
            filler.check_box("allergies_no")

        if patient_data.get("consent_given"):
            filler.check_box("patient_consent")

        filler.save("patient_form.pdf")
```

### Pattern 4: Form Template + Data

```python
import json

# Load form template
with open("form_mapping.json") as f:
    field_mapping = json.load(f)

# Load user data
with open("user_data.json") as f:
    user_data = json.load(f)

# Map user data to form fields
form_data = {
    field_mapping[key]: value
    for key, value in user_data.items()
    if key in field_mapping
}

# Fill form
with PDFFiller("form.pdf") as filler:
    filler.fill_fields(form_data)
    filler.save("filled.pdf")
```

### Pattern 5: Dynamic Field Discovery

```python
def auto_fill_form(pdf_path, data_dict):
    """Automatically fill any matching fields"""
    with PDFFiller(pdf_path) as filler:
        # Get available fields
        available_fields = {f['name'] for f in filler.list_fields()}

        # Only fill fields that exist
        valid_data = {
            key: value
            for key, value in data_dict.items()
            if key in available_fields
        }

        filler.fill_fields(valid_data)
        filler.save("auto_filled.pdf")

        # Report which fields were filled
        print(f"Filled {len(valid_data)} fields")
        unused = set(data_dict.keys()) - available_fields
        if unused:
            print(f"Unused data fields: {unused}")
```

## Troubleshooting

### Problem: Filled values don't show up

**Solution**: Always use `flatten=True` when saving (this is the default):

```python
filler.save("output.pdf", flatten=True)  # ✓ Correct
```

### Problem: FieldNotFoundError

**Solution**: List fields first to get exact names:

```python
with PDFFiller("form.pdf") as filler:
    fields = filler.list_fields()
    print([f['name'] for f in fields])
```

### Problem: Checkbox not checking

**Solution**: Checkbox field names may not be obvious. Use `list` to find them:

```bash
pdfiller list -i form.pdf | grep -i checkbox
```

Then check using the exact field name:

```python
filler.check_box("exact_field_name_from_list")
```

### Problem: Text is cut off or too small

**Solution**: The library auto-sizes text to fit the field. If text is too long, consider abbreviating or splitting into multiple fields.

### Problem: Special characters not displaying

**Solution**: PyMuPDF's default font supports most characters. For special Unicode, the library uses Helvetica which has good coverage.

### Problem: Multi-page forms

**Solution**: Multi-page PDFs are fully supported. All fields across all pages are listed, filled, and flattened automatically.

## Best Practices

1. **Always use `flatten=True`** - Ensures compatibility
2. **List fields first** - See exactly what fields are available
3. **Use context managers** - Ensures resources are cleaned up
4. **Preserve existing values** - When appropriate, use `preserve_existing_fields(True)`
5. **Validate field names** - Use `validate_fields()` before filling
6. **Use JSON for complex forms** - Easier to maintain than code
7. **Generate templates** - Use `pdfiller template` to create starter JSON

## Tips

- Field names are case-sensitive
- Use `list_fields()` to see current values
- The library handles checkboxes automatically when flattening
- Flatten=False keeps forms editable but may not display correctly
- Empty strings are treated as "don't fill"
- Method chaining makes code more readable

## Getting Help

If you encounter issues:

1. Run `pdfiller list -i yourform.pdf` to inspect the PDF
2. Check field names match exactly (case-sensitive)
3. Try with `flatten=True`
4. Verify PyMuPDF is installed: `python -c "import fitz; print(fitz.__version__)"`

## Examples

See the `examples/` directory for complete working examples:

- `quickstart.py` - Basic usage patterns
- `medication_form_example.py` - Real-world medical form example
