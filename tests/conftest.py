"""
Test fixtures that generate PDF files with PyMuPDF for testing.
"""

import struct
import zlib
from pathlib import Path

import pymupdf
import pytest

from pdfiller.memory import reset_matchers


@pytest.fixture(autouse=True)
def _isolate_matchers():
    """Restore the built-in matcher registry before and after every test.

    The matcher registry is module-level state; without this, a test that
    registers or clears matchers would leak into unrelated tests.
    """
    reset_matchers()
    yield
    reset_matchers()


@pytest.fixture(autouse=True)
def _isolate_config(monkeypatch, tmp_path_factory):
    """Point PDFILLER_CONFIG at a non-existent file so tests never read the user's config."""
    missing = tmp_path_factory.mktemp("pdfiller-config") / "config.toml"
    monkeypatch.setenv("PDFILLER_CONFIG", str(missing))


def _make_png() -> bytes:
    """Create a minimal valid 1x1 PNG image."""
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr_crc = struct.pack(">I", zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF)
    ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_data + ihdr_crc
    raw = zlib.compress(b"\x00\x00\x00\x00")
    idat_crc = struct.pack(">I", zlib.crc32(b"IDAT" + raw) & 0xFFFFFFFF)
    idat = struct.pack(">I", len(raw)) + b"IDAT" + raw + idat_crc
    iend_crc = struct.pack(">I", zlib.crc32(b"IEND") & 0xFFFFFFFF)
    iend = struct.pack(">I", 0) + b"IEND" + iend_crc
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
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)

    # Add text fields
    for name, rect in [
        ("first_name", pymupdf.Rect(100, 100, 300, 120)),
        ("last_name", pymupdf.Rect(100, 140, 300, 160)),
        ("email", pymupdf.Rect(100, 180, 300, 200)),
    ]:
        widget = pymupdf.Widget()
        widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
        widget.field_name = name
        widget.rect = rect
        page.add_widget(widget)

    # Add checkbox
    widget = pymupdf.Widget()
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_CHECKBOX
    widget.field_name = "agree_terms"
    widget.rect = pymupdf.Rect(100, 220, 120, 240)
    page.add_widget(widget)

    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def multi_page_pdf(tmp_path):
    """Create a multi-page fillable PDF with fields on different pages."""
    path = tmp_path / "multi_page.pdf"
    doc = pymupdf.open()

    # Page 0: personal info
    page0 = doc.new_page(width=612, height=792)
    for name, rect in [
        ("first_name", pymupdf.Rect(100, 100, 300, 120)),
        ("last_name", pymupdf.Rect(100, 140, 300, 160)),
    ]:
        widget = pymupdf.Widget()
        widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
        widget.field_name = name
        widget.rect = rect
        page0.add_widget(widget)

    # Page 1: contact info
    page1 = doc.new_page(width=612, height=792)
    for name, rect in [
        ("email", pymupdf.Rect(100, 100, 300, 120)),
        ("phone", pymupdf.Rect(100, 140, 300, 160)),
    ]:
        widget = pymupdf.Widget()
        widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
        widget.field_name = name
        widget.rect = rect
        page1.add_widget(widget)

    # Page 2: confirmation checkbox
    page2 = doc.new_page(width=612, height=792)
    widget = pymupdf.Widget()
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_CHECKBOX
    widget.field_name = "confirm"
    widget.rect = pymupdf.Rect(100, 100, 120, 120)
    page2.add_widget(widget)

    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def non_fillable_pdf(tmp_path):
    """Create a PDF with no form fields (plain text only)."""
    path = tmp_path / "non_fillable.pdf"
    doc = pymupdf.open()
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
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)

    # Add a text field
    widget = pymupdf.Widget()
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    widget.field_name = "name"
    widget.rect = pymupdf.Rect(100, 100, 300, 120)
    page.add_widget(widget)

    # Add a checkbox that is pre-checked
    widget = pymupdf.Widget()
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_CHECKBOX
    widget.field_name = "agree"
    widget.rect = pymupdf.Rect(100, 140, 120, 160)
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
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)

    # Add text fields including a date field
    for name, rect in [
        ("first_name", pymupdf.Rect(100, 100, 300, 120)),
        ("sign_date", pymupdf.Rect(100, 140, 300, 160)),
        ("date_signed", pymupdf.Rect(100, 180, 300, 200)),
        ("date_of_birth", pymupdf.Rect(100, 220, 300, 240)),
        ("expiration_date", pymupdf.Rect(100, 260, 300, 280)),
    ]:
        widget = pymupdf.Widget()
        widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
        widget.field_name = name
        widget.rect = rect
        page.add_widget(widget)

    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def fillable_pdf_with_dropdown(tmp_path):
    """Create a fillable PDF with a dropdown/combobox field."""
    path = tmp_path / "dropdown.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)

    # Add a text field
    widget = pymupdf.Widget()
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    widget.field_name = "name"
    widget.rect = pymupdf.Rect(100, 100, 300, 120)
    page.add_widget(widget)

    # Add a combobox/dropdown field
    widget = pymupdf.Widget()
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_COMBOBOX
    widget.field_name = "state"
    widget.rect = pymupdf.Rect(100, 140, 300, 160)
    widget.choice_values = ["CA", "NY", "TX"]
    page.add_widget(widget)

    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def fillable_pdf_with_listbox(tmp_path):
    """Create a fillable PDF with a listbox field."""
    path = tmp_path / "listbox.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)

    # Add a listbox field
    widget = pymupdf.Widget()
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_LISTBOX
    widget.field_name = "color"
    widget.rect = pymupdf.Rect(100, 100, 300, 180)
    widget.choice_values = ["Red", "Green", "Blue"]
    page.add_widget(widget)

    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def encrypted_pdf_empty_user_pw(tmp_path):
    """Create an encrypted PDF that opens with an empty user password.

    Only an owner password is set, so viewers open it without prompting but the
    file is still flagged as encrypted.
    """
    path = tmp_path / "encrypted_empty.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((100, 100), "Encrypted content", fontsize=12)
    doc.save(
        str(path),
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        owner_pw="owner-secret",
        user_pw="",
    )
    doc.close()
    return path


@pytest.fixture
def encrypted_pdf_with_user_pw(tmp_path):
    """Create an encrypted PDF protected by a non-empty user password."""
    path = tmp_path / "encrypted_user.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((100, 100), "Secret content", fontsize=12)
    doc.save(
        str(path),
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        owner_pw="owner-secret",
        user_pw="open-sesame",
    )
    doc.close()
    return path


@pytest.fixture
def large_pdf(tmp_path):
    """Create a PDF file that exceeds a small size limit for testing."""
    path = tmp_path / "large.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    # Add enough text to make the file non-trivial
    page.insert_text((100, 100), "Hello", fontsize=12)
    doc.save(str(path))
    doc.close()
    return path
