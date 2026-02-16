"""
Test fixtures that generate PDF files with PyMuPDF for testing.
"""

import struct
import zlib

import fitz
import pytest
from pathlib import Path


def _make_png() -> bytes:
    """Create a minimal valid 1x1 PNG image."""
    sig = b'\x89PNG\r\n\x1a\n'
    ihdr_data = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)
    ihdr_crc = struct.pack('>I', zlib.crc32(b'IHDR' + ihdr_data) & 0xffffffff)
    ihdr = struct.pack('>I', 13) + b'IHDR' + ihdr_data + ihdr_crc
    raw = zlib.compress(b'\x00\x00\x00\x00')
    idat_crc = struct.pack('>I', zlib.crc32(b'IDAT' + raw) & 0xffffffff)
    idat = struct.pack('>I', len(raw)) + b'IDAT' + raw + idat_crc
    iend_crc = struct.pack('>I', zlib.crc32(b'IEND') & 0xffffffff)
    iend = struct.pack('>I', 0) + b'IEND' + iend_crc
    return sig + ihdr + idat + iend


@pytest.fixture
def tiny_png(tmp_path) -> Path:
    """Provide a minimal valid PNG file for image insertion tests."""
    img = tmp_path / "test_image.png"
    img.write_bytes(_make_png())
    return img


@pytest.fixture
def tmp_pdf_dir(tmp_path):
    """Provide a temporary directory for PDF files."""
    return tmp_path


@pytest.fixture
def fillable_pdf(tmp_path):
    """Create a single-page fillable PDF with text and checkbox fields."""
    path = tmp_path / "fillable.pdf"
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)

    # Add text fields
    for i, (name, rect) in enumerate([
        ("first_name", fitz.Rect(100, 100, 300, 120)),
        ("last_name", fitz.Rect(100, 140, 300, 160)),
        ("email", fitz.Rect(100, 180, 300, 200)),
    ]):
        widget = fitz.Widget()
        widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
        widget.field_name = name
        widget.rect = rect
        page.add_widget(widget)

    # Add checkbox
    widget = fitz.Widget()
    widget.field_type = fitz.PDF_WIDGET_TYPE_CHECKBOX
    widget.field_name = "agree_terms"
    widget.rect = fitz.Rect(100, 220, 120, 240)
    page.add_widget(widget)

    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def multi_page_pdf(tmp_path):
    """Create a multi-page fillable PDF with fields on different pages."""
    path = tmp_path / "multi_page.pdf"
    doc = fitz.open()

    # Page 0: personal info
    page0 = doc.new_page(width=612, height=792)
    for name, rect in [
        ("first_name", fitz.Rect(100, 100, 300, 120)),
        ("last_name", fitz.Rect(100, 140, 300, 160)),
    ]:
        widget = fitz.Widget()
        widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
        widget.field_name = name
        widget.rect = rect
        page0.add_widget(widget)

    # Page 1: contact info
    page1 = doc.new_page(width=612, height=792)
    for name, rect in [
        ("email", fitz.Rect(100, 100, 300, 120)),
        ("phone", fitz.Rect(100, 140, 300, 160)),
    ]:
        widget = fitz.Widget()
        widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
        widget.field_name = name
        widget.rect = rect
        page1.add_widget(widget)

    # Page 2: confirmation checkbox
    page2 = doc.new_page(width=612, height=792)
    widget = fitz.Widget()
    widget.field_type = fitz.PDF_WIDGET_TYPE_CHECKBOX
    widget.field_name = "confirm"
    widget.rect = fitz.Rect(100, 100, 120, 120)
    page2.add_widget(widget)

    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def non_fillable_pdf(tmp_path):
    """Create a PDF with no form fields (plain text only)."""
    path = tmp_path / "non_fillable.pdf"
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((100, 100), "Name: _______________", fontsize=12)
    page.insert_text((100, 140), "Date: _______________", fontsize=12)
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def fillable_pdf_with_checked_box(tmp_path):
    """Create a fillable PDF with a checkbox that is pre-checked."""
    path = tmp_path / "checked_box.pdf"
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)

    # Add a text field
    widget = fitz.Widget()
    widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
    widget.field_name = "name"
    widget.rect = fitz.Rect(100, 100, 300, 120)
    page.add_widget(widget)

    # Add a checkbox that is pre-checked
    widget = fitz.Widget()
    widget.field_type = fitz.PDF_WIDGET_TYPE_CHECKBOX
    widget.field_name = "agree"
    widget.rect = fitz.Rect(100, 140, 120, 160)
    page.add_widget(widget)

    # Check the box by setting field_value and updating
    for w in page.widgets():
        if w.field_name == "agree":
            w.field_value = True
            w.update()
            break

    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def fillable_pdf_with_dates(tmp_path):
    """Create a fillable PDF with date fields for testing auto-date functionality."""
    path = tmp_path / "fillable_with_dates.pdf"
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)

    # Add text fields including a date field
    for name, rect in [
        ("first_name", fitz.Rect(100, 100, 300, 120)),
        ("sign_date", fitz.Rect(100, 140, 300, 160)),
    ]:
        widget = fitz.Widget()
        widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
        widget.field_name = name
        widget.rect = rect
        page.add_widget(widget)

    doc.save(str(path))
    doc.close()
    return path
