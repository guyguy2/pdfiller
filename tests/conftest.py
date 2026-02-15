"""
Test fixtures that generate PDF files with PyMuPDF for testing.
"""

import fitz
import pytest
from pathlib import Path


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
