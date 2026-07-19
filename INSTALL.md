# PDFiller Installation Guide

## Quick Install

Recommended - using `uv`:

```bash
cd pdfiller
uv pip install -e .
```

Alternative - using pip:

```bash
cd pdfiller
pip install -e .
```

This installs:
- The `pdfiller` Python package
- The `pdfiller` command-line tool
- All dependencies (PyMuPDF)

## Verify Installation

```bash
# Test CLI
pdfiller --help

# Test Python import
python -c "from pdfiller import PDFFiller; print('PDFiller installed successfully')"
```

## Dependencies

PDFiller requires:
- Python 3.8+
- PyMuPDF (fitz) >= 1.23.0

Dependencies are automatically installed with the package.

## Alternative: Use Without Installing

If you don't want to install the package:

```bash
# Install only the dependency
pip install PyMuPDF

# Use directly
cd pdfiller
python -m pdfiller.cli --help

# Or import in your scripts
import sys
sys.path.insert(0, '/path/to/pdfiller')
from pdfiller import PDFFiller
```

## For Development

Using `uv` (recommended):

```bash
# Clone/download the pdfiller directory
cd pdfiller

# Install in development mode
uv pip install -e .

# Run tests
uv run pytest tests/
```

Using pip:

```bash
# Clone/download the pdfiller directory
cd pdfiller

# Install in development mode
pip install -e .

# Run tests
python -m pytest tests/
```

## Uninstall

```bash
pip uninstall pdfiller
```

## Platform-Specific Notes

### macOS

```bash
# May need to use pip3
pip3 install -e .
```

### Windows

```bash
# Use pip in Command Prompt or PowerShell
pip install -e .
```

### Linux

```bash
# May need sudo for system-wide install
sudo pip install -e .

# Or install for user only
pip install --user -e .
```

## Troubleshooting

### ImportError: No module named 'fitz'

**Solution**: Install PyMuPDF:
```bash
pip install PyMuPDF
```

### Permission denied during install

**Solution**: Use `--user` flag:
```bash
pip install --user -e .
```

### Command 'pdfiller' not found after install

**Solution**: Add pip's bin directory to PATH, or use:
```bash
python -m pdfiller.cli
```

## Using in Claude Code

PDFiller is designed to work seamlessly with Claude Code:

```python
# In any Claude Code session
from pdfiller import PDFFiller

with PDFFiller("form.pdf") as filler:
    filler.fill_field("name", "Value")
    filler.save("output.pdf")
```

Or via CLI:

```bash
pdfiller fill -i form.pdf -f "name=Value" -o output.pdf
```

## Next Steps

After installation:

1. Read [USAGE.md](USAGE.md) for detailed usage guide
2. Try examples in `examples/` directory
3. Run `pdfiller --help` to see CLI options
4. Check [README.md](README.md) for API reference
