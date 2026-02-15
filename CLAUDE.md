# PDFiller - Claude Code Integration

## Project

Python library for filling PDF forms using PyMuPDF. Supports fillable (AcroForm) and non-fillable PDFs.

- Runtime: Python 3.8+, managed with `uv`
- Tests: `uv run pytest tests/ -v`
- Main entry: `pdfiller.core.PDFFiller`

## PDF Filling Workflow

When asked to fill a PDF, follow these steps:

### 1. Inspect the PDF

```python
from pdfiller import PDFFiller

filler = PDFFiller("path/to/form.pdf")

if filler.has_form_fields():
    # Fillable PDF - list the form fields
    fields = filler.list_fields()
    for f in fields:
        print(f"Page {f['page']}: {f['name']} ({f['type']}) = {f['value']}")
else:
    # Non-fillable PDF - examine the layout to find where to place text
    for page_num in range(filler.page_count):
        layout = filler.get_page_layout(page_num)
        print(f"Page {page_num}: {layout['width']}x{layout['height']}")
        for block in layout['blocks']:
            print(f"  [{block['bbox']['x0']:.0f},{block['bbox']['y0']:.0f}] {block['text'][:60]}")
```

### 2. Load defaults

```python
from pdfiller import load_defaults, flatten_defaults, match_field_to_defaults

defaults = flatten_defaults(load_defaults())
```

### 3. Match fields to defaults, identify gaps

```python
auto_filled = {}
needs_choice = {}
missing = []

for field in fields:
    name = field['name']
    match = match_field_to_defaults(name, defaults)
    if isinstance(match, list):
        needs_choice[name] = match
    elif match:
        auto_filled[name] = match
    else:
        missing.append(name)
```

### 4. Show the user the plan

Present what will be auto-filled, what needs a choice, and what is missing. Example:

```
Found 8 fields in form.pdf:

Auto-filled from defaults:
  - first_name: "Guy"
  - last_name: "Smith"
  - email: "guy@example.com"

Multiple values stored - pick one:
  - phone: ["555-1234", "555-5678"]

Need your input:
  - date_of_birth (Text)
  - policy_number (Text)
  - agree_terms (CheckBox)
```

### 5. Check for signature fields

If any field name or page text suggests a signature (e.g., "signature", "sign here", "Signature line"),
ask the user if they want to place a signature image. Do NOT automatically sign.

```
Signature field detected:
  - "signature" on page 2 at (100, 500, 350, 550)

Do you want to place a signature image? If so, provide the path to a PNG or GIF file.
```

If the user provides an image path:

```python
filler.insert_image("path/to/signature.png", x0=100, y0=500, x1=350, y1=550, page_num=2)
```

### 6. Fill and save

```python
# Fillable PDF
filler.fill_fields(auto_filled)
filler.fill_fields(user_provided_values)
filler.check_box("agree_terms")  # for checkboxes
filler.save("form_filled.pdf", flatten=True)

# Non-fillable PDF
filler.insert_text("Guy Smith", x=200, y=150, page_num=0, font_size=11)
filler.insert_text_box("123 Main St\nAnytown, ST 12345", 100, 200, 400, 260, page_num=0)
filler.insert_image("signature.png", 100, 500, 300, 550)  # if user provided one
filler.save("form_filled.pdf")
```

### 7. Optionally update defaults

If the user provided new reusable values, ask if they should be remembered:

```python
from pdfiller import save_defaults, load_defaults

data = load_defaults()
data.setdefault("personal", {})
data["personal"]["date_of_birth"] = "1990-01-15"
save_defaults(data)
```

## Output naming

Use `<original_name>_filled.pdf` by default (e.g., `form.pdf` -> `form_filled.pdf`).

## Code standards

- No emojis in code, comments, or output
- Run tests with `uv run pytest tests/ -v` before finishing
- Keep changes minimal and focused
