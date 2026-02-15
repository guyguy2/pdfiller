"""
Tests for pdfiller.core module - multi-page, text overlay, and layout features.
"""

import fitz
import pytest

from pdfiller.core import PDFFiller
from pdfiller.exceptions import PDFFillerError, PDFReadError


class TestOpenErrors:
    def test_missing_file_raises(self):
        with pytest.raises(PDFReadError, match="not found"):
            PDFFiller("/nonexistent/file.pdf")

    def test_encrypted_pdf_raises(self, tmp_path):
        path = tmp_path / "encrypted.pdf"
        doc = fitz.open()
        doc.new_page()
        perm = fitz.PDF_PERM_ACCESSIBILITY
        encrypt_meth = fitz.PDF_ENCRYPT_AES_256
        doc.save(str(path), encryption=encrypt_meth, owner_pw="owner", user_pw="user", permissions=perm)
        doc.close()

        with pytest.raises(PDFReadError, match="password-protected"):
            PDFFiller(path)


class TestPageCount:
    def test_single_page(self, fillable_pdf):
        with PDFFiller(fillable_pdf) as f:
            assert f.page_count == 1

    def test_multi_page(self, multi_page_pdf):
        with PDFFiller(multi_page_pdf) as f:
            assert f.page_count == 3


class TestMultiPageListFields:
    def test_lists_fields_from_all_pages(self, multi_page_pdf):
        with PDFFiller(multi_page_pdf) as f:
            fields = f.list_fields()

        names = [field["name"] for field in fields]
        assert "first_name" in names
        assert "last_name" in names
        assert "email" in names
        assert "phone" in names
        assert "confirm" in names
        assert len(fields) == 5

    def test_fields_include_page_number(self, multi_page_pdf):
        with PDFFiller(multi_page_pdf) as f:
            fields = f.list_fields()

        by_name = {field["name"]: field for field in fields}
        assert by_name["first_name"]["page"] == 0
        assert by_name["last_name"]["page"] == 0
        assert by_name["email"]["page"] == 1
        assert by_name["phone"]["page"] == 1
        assert by_name["confirm"]["page"] == 2

    def test_single_page_fields_have_page_zero(self, fillable_pdf):
        with PDFFiller(fillable_pdf) as f:
            fields = f.list_fields()

        for field in fields:
            assert field["page"] == 0


class TestMultiPageGetFieldValue:
    def test_finds_field_on_later_page(self, multi_page_pdf, tmp_path):
        out = tmp_path / "out.pdf"
        with PDFFiller(multi_page_pdf) as f:
            f.fill_field("email", "test@example.com")
            f.save(out, flatten=False)

        with PDFFiller(out) as f:
            assert f.get_field_value("email") == "test@example.com"

    def test_returns_none_for_missing(self, multi_page_pdf):
        with PDFFiller(multi_page_pdf) as f:
            assert f.get_field_value("nonexistent") is None


class TestMultiPageFillAndSave:
    def test_fill_fields_across_pages(self, multi_page_pdf, tmp_path):
        out = tmp_path / "filled.pdf"
        with PDFFiller(multi_page_pdf) as f:
            f.fill_fields({
                "first_name": "Guy",
                "email": "guy@example.com",
            })
            f.save(out, flatten=False)

        with PDFFiller(out) as f:
            assert f.get_field_value("first_name") == "Guy"
            assert f.get_field_value("email") == "guy@example.com"

    def test_fill_with_flatten(self, multi_page_pdf, tmp_path):
        out = tmp_path / "flattened.pdf"
        with PDFFiller(multi_page_pdf) as f:
            f.fill_fields({"first_name": "Test", "phone": "555-1234"})
            f.save(out, flatten=True)

        # Verify the output exists and is a valid PDF
        doc = fitz.open(str(out))
        assert len(doc) == 3
        doc.close()


class TestHasFormFields:
    def test_fillable_pdf(self, fillable_pdf):
        with PDFFiller(fillable_pdf) as f:
            assert f.has_form_fields() is True

    def test_non_fillable_pdf(self, non_fillable_pdf):
        with PDFFiller(non_fillable_pdf) as f:
            assert f.has_form_fields() is False


class TestGetPageLayout:
    def test_returns_dimensions(self, non_fillable_pdf):
        with PDFFiller(non_fillable_pdf) as f:
            layout = f.get_page_layout(0)

        assert layout["width"] == 612
        assert layout["height"] == 792

    def test_returns_text_blocks(self, non_fillable_pdf):
        with PDFFiller(non_fillable_pdf) as f:
            layout = f.get_page_layout(0)

        assert len(layout["blocks"]) > 0
        block = layout["blocks"][0]
        assert "text" in block
        assert "bbox" in block
        assert "x0" in block["bbox"]

    def test_invalid_page_raises(self, non_fillable_pdf):
        with PDFFiller(non_fillable_pdf) as f:
            with pytest.raises(PDFFillerError):
                f.get_page_layout(99)


class TestInsertText:
    def test_queues_overlay(self, non_fillable_pdf):
        with PDFFiller(non_fillable_pdf) as f:
            f.insert_text("Hello", 100, 200)
            assert len(f._text_overlays) == 1
            assert f._text_overlays[0]["type"] == "point"
            assert f._text_overlays[0]["text"] == "Hello"

    def test_saves_with_text(self, non_fillable_pdf, tmp_path):
        out = tmp_path / "with_text.pdf"
        with PDFFiller(non_fillable_pdf) as f:
            f.insert_text("Inserted Text", 200, 300, font_size=14)
            f.save(out, flatten=False)

        # Verify the text was written
        doc = fitz.open(str(out))
        text = doc[0].get_text()
        assert "Inserted Text" in text
        doc.close()

    def test_chaining(self, non_fillable_pdf):
        with PDFFiller(non_fillable_pdf) as f:
            result = f.insert_text("A", 10, 20).insert_text("B", 30, 40)
            assert result is f
            assert len(f._text_overlays) == 2


class TestInsertTextBox:
    def test_queues_box_overlay(self, non_fillable_pdf):
        with PDFFiller(non_fillable_pdf) as f:
            f.insert_text_box("Boxed text", 100, 200, 300, 250)
            assert len(f._text_overlays) == 1
            assert f._text_overlays[0]["type"] == "box"

    def test_saves_with_text_box(self, non_fillable_pdf, tmp_path):
        out = tmp_path / "with_box.pdf"
        with PDFFiller(non_fillable_pdf) as f:
            f.insert_text_box("Box Content", 100, 300, 400, 350)
            f.save(out, flatten=False)

        doc = fitz.open(str(out))
        text = doc[0].get_text()
        assert "Box Content" in text
        doc.close()


class TestInsertImage:
    def test_queues_image_overlay(self, non_fillable_pdf, tiny_png):
        with PDFFiller(non_fillable_pdf) as f:
            f.insert_image(tiny_png, 100, 200, 300, 250)
            assert len(f._image_overlays) == 1
            assert f._image_overlays[0]["image_path"] == str(tiny_png)

    def test_saves_with_image(self, non_fillable_pdf, tiny_png, tmp_path):
        out = tmp_path / "with_image.pdf"
        with PDFFiller(non_fillable_pdf) as f:
            f.insert_image(tiny_png, 100, 400, 300, 450)
            f.save(out, flatten=False)

        doc = fitz.open(str(out))
        assert len(doc[0].get_images()) > 0
        doc.close()

    def test_missing_image_raises(self, non_fillable_pdf):
        with PDFFiller(non_fillable_pdf) as f:
            with pytest.raises(PDFFillerError):
                f.insert_image("/nonexistent/image.png", 0, 0, 100, 100)

    def test_invalid_image_format_raises(self, non_fillable_pdf, tmp_path):
        bad_img = tmp_path / "not_an_image.png"
        bad_img.write_text("this is not a PNG")
        with PDFFiller(non_fillable_pdf) as f:
            with pytest.raises(PDFFillerError, match="Invalid or unsupported"):
                f.insert_image(bad_img, 0, 0, 100, 100)

    def test_chaining(self, non_fillable_pdf, tiny_png):
        with PDFFiller(non_fillable_pdf) as f:
            result = f.insert_image(tiny_png, 10, 20, 100, 50).insert_image(tiny_png, 30, 40, 120, 70)
            assert result is f
            assert len(f._image_overlays) == 2

    def test_image_on_specific_page(self, multi_page_pdf, tiny_png, tmp_path):
        out = tmp_path / "img_page2.pdf"
        with PDFFiller(multi_page_pdf) as f:
            f.insert_image(tiny_png, 100, 300, 300, 350, page_num=1)
            f.save(out, flatten=False)

        doc = fitz.open(str(out))
        assert len(doc[0].get_images()) == 0
        assert len(doc[1].get_images()) > 0
        doc.close()


class TestInsertTextMultiPage:
    def test_text_on_specific_page(self, multi_page_pdf, tmp_path):
        out = tmp_path / "text_page2.pdf"
        with PDFFiller(multi_page_pdf) as f:
            f.insert_text("Page 2 Note", 100, 300, page_num=1)
            f.save(out, flatten=False)

        doc = fitz.open(str(out))
        assert "Page 2 Note" not in doc[0].get_text()
        assert "Page 2 Note" in doc[1].get_text()
        doc.close()


class TestAutoDateFilling:
    def test_is_date_field(self):
        assert PDFFiller._is_date_field("sign_date")
        assert PDFFiller._is_date_field("SignDate")
        assert PDFFiller._is_date_field("date_signed")
        assert PDFFiller._is_date_field("effective-date")
        assert PDFFiller._is_date_field("dated")
        assert not PDFFiller._is_date_field("first_name")
        assert not PDFFiller._is_date_field("email")

    def test_format_today_date(self):
        date_str = PDFFiller._format_today_date()
        # Format should be M/D/YYYY or MM/DD/YYYY
        assert "/" in date_str
        parts = date_str.split("/")
        assert len(parts) == 3
        assert len(parts[2]) == 4  # year should be 4 digits

    def test_auto_fills_empty_date_fields(self, fillable_pdf_with_dates, tmp_path):
        out = tmp_path / "auto_date.pdf"

        with PDFFiller(fillable_pdf_with_dates) as f:
            # Don't explicitly fill the date field
            f.save(out, flatten=False)

        # Verify the date field was auto-filled
        with PDFFiller(out) as f2:
            fields = f2.list_fields()
            date_field = next(field for field in fields if field["name"] == "sign_date")
            assert date_field["value"]  # Should have a value
            assert "/" in date_field["value"]  # Should be a date format

    def test_does_not_overwrite_existing_date(self, fillable_pdf_with_dates, tmp_path):
        out = tmp_path / "preserve_date.pdf"

        with PDFFiller(fillable_pdf_with_dates) as f:
            f.fill_field("sign_date", "12/25/2025")
            f.save(out, flatten=False)

        # Verify the explicitly set date was preserved
        with PDFFiller(out) as f2:
            fields = f2.list_fields()
            date_field = next(field for field in fields if field["name"] == "sign_date")
            assert date_field["value"] == "12/25/2025"

    def test_auto_fill_dates_disabled(self, fillable_pdf_with_dates, tmp_path):
        out = tmp_path / "no_auto_date.pdf"

        with PDFFiller(fillable_pdf_with_dates, auto_fill_dates=False) as f:
            f.save(out, flatten=False)

        with PDFFiller(out) as f2:
            fields = f2.list_fields()
            date_field = next(field for field in fields if field["name"] == "sign_date")
            assert not date_field["value"]
