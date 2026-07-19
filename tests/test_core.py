"""
Tests for pdfiller.core module - multi-page, text overlay, and layout features.
"""

import logging

import fitz
import pytest

from pdfiller.core import PDFFiller, DEFAULT_MAX_PDF_SIZE, DEFAULT_MAX_IMAGE_SIZE
from pdfiller.exceptions import PDFFillerError, PDFReadError, PDFWriteError, FieldNotFoundError


class TestPackageExports:
    def test_read_write_errors_importable_from_package(self):
        from pdfiller import PDFReadError as ReadErr, PDFWriteError as WriteErr
        assert ReadErr is PDFReadError
        assert WriteErr is PDFWriteError

    def test_read_write_errors_in_all(self):
        import pdfiller
        assert "PDFReadError" in pdfiller.__all__
        assert "PDFWriteError" in pdfiller.__all__


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
        assert PDFFiller._is_date_field("dated")
        assert PDFFiller._is_date_field("date")
        assert not PDFFiller._is_date_field("first_name")
        assert not PDFFiller._is_date_field("email")
        assert not PDFFiller._is_date_field("mandate")
        assert not PDFFiller._is_date_field("candidate")
        assert not PDFFiller._is_date_field("updated_at")

    def test_is_date_field_excludes_non_signing_dates(self):
        assert not PDFFiller._is_date_field("date_of_birth")
        assert not PDFFiller._is_date_field("birth_date")
        assert not PDFFiller._is_date_field("DateOfBirth")
        assert not PDFFiller._is_date_field("dob_date")
        assert not PDFFiller._is_date_field("expiration_date")
        assert not PDFFiller._is_date_field("expiry_date")
        assert not PDFFiller._is_date_field("expire_date")
        assert not PDFFiller._is_date_field("effective-date")
        assert not PDFFiller._is_date_field("start_date")
        assert not PDFFiller._is_date_field("end_date")
        assert not PDFFiller._is_date_field("date_from")
        assert not PDFFiller._is_date_field("date_to")

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

    def test_does_not_auto_fill_excluded_date_fields(self, fillable_pdf_with_dates, tmp_path):
        out = tmp_path / "excluded_dates.pdf"

        with PDFFiller(fillable_pdf_with_dates) as f:
            f.save(out, flatten=False)

        with PDFFiller(out) as f2:
            fields = {field["name"]: field["value"] for field in f2.list_fields()}
            # Signature-adjacent dates auto-fill
            assert fields["sign_date"]
            assert fields["date_signed"]
            # Birth/expiration dates stay empty
            assert not fields["date_of_birth"]
            assert not fields["expiration_date"]

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


class TestAutoDateWithFlatten:
    def test_auto_date_survives_flatten(self, fillable_pdf_with_dates, tmp_path):
        """Save with flatten=True and auto_fill_dates=True (default).
        Verify the flattened output contains today's date in the text."""
        out = tmp_path / "flat_date.pdf"
        with PDFFiller(fillable_pdf_with_dates) as f:
            f.save(out, flatten=True)

        # After flattening, the date should be visible as text (not a field)
        doc = fitz.open(str(out))
        text = doc[0].get_text()
        today = PDFFiller._format_today_date()
        assert today in text
        doc.close()


class TestFlattenPreservesExisting:
    def test_untouched_prefilled_value_survives_flatten(self, fillable_pdf, tmp_path):
        """A field already filled in the source PDF and left untouched must
        still be visible after flattening (regression: only touched fields
        were overlaid, so pre-existing values were dropped)."""
        # Build a source PDF that carries a value but is still a live form.
        source = tmp_path / "prefilled.pdf"
        with PDFFiller(fillable_pdf) as f:
            f.fill_field("first_name", "Preexisting")
            f.save(source, flatten=False)

        # Reopen and flatten without touching first_name.
        out = tmp_path / "flattened.pdf"
        with PDFFiller(source) as f2:
            f2.save(out, flatten=True)

        doc = fitz.open(str(out))
        text = doc[0].get_text()
        doc.close()
        assert "Preexisting" in text

    def test_checked_box_renders_as_x_after_flatten(self, fillable_pdf, tmp_path):
        """A checked box should render as an X mark, not its raw export value
        (regression: only literal 'On'/True mapped to X)."""
        out = tmp_path / "checked.pdf"
        with PDFFiller(fillable_pdf) as f:
            f.check_box("agree_terms")
            f.save(out, flatten=True)

        doc = fitz.open(str(out))
        text = doc[0].get_text()
        doc.close()
        assert "X" in text


class TestUncheckBox:
    def test_uncheck_pre_checked_box(self, fillable_pdf_with_checked_box, tmp_path):
        """Unchecking a pre-checked box should result in it being unchecked after save."""
        out = tmp_path / "unchecked.pdf"
        with PDFFiller(fillable_pdf_with_checked_box) as f:
            f.uncheck_box("agree")
            f.save(out, flatten=False)

        with PDFFiller(out) as f2:
            val = f2.get_field_value("agree")
            # After unchecking, the value should be falsy (False, "Off", or empty)
            assert not val or val == "Off"

    def test_uncheck_removes_from_check_set(self, fillable_pdf_with_checked_box):
        """Calling check_box then uncheck_box should remove it from the check set."""
        with PDFFiller(fillable_pdf_with_checked_box) as f:
            f.check_box("agree")
            assert "agree" in f._checkboxes_to_check

            f.uncheck_box("agree")
            assert "agree" not in f._checkboxes_to_check
            assert "agree" in f._checkboxes_to_uncheck


class TestStrictMode:
    def test_fill_field_nonexistent_raises(self, fillable_pdf):
        """In strict mode, filling a nonexistent field raises FieldNotFoundError."""
        with PDFFiller(fillable_pdf, strict=True) as f:
            with pytest.raises(FieldNotFoundError):
                f.fill_field("nonexistent_field", "value")

    def test_check_box_nonexistent_raises(self, fillable_pdf):
        """In strict mode, checking a nonexistent checkbox raises FieldNotFoundError."""
        with PDFFiller(fillable_pdf, strict=True) as f:
            with pytest.raises(FieldNotFoundError):
                f.check_box("nonexistent_field")

    def test_fill_field_existing_works(self, fillable_pdf):
        """In strict mode, filling an existing field should work fine."""
        with PDFFiller(fillable_pdf, strict=True) as f:
            # Should not raise - first_name exists in the fillable_pdf fixture
            f.fill_field("first_name", "value")

    def test_non_strict_nonexistent_does_not_raise(self, fillable_pdf):
        """In non-strict mode (default), filling a nonexistent field does not raise."""
        with PDFFiller(fillable_pdf, strict=False) as f:
            # Should not raise
            f.fill_field("nonexistent_field", "value")


class TestSaveIsTerminal:
    def test_save_twice_raises(self, fillable_pdf, tmp_path):
        """Calling save() a second time raises PDFFillerError."""
        out1 = tmp_path / "first.pdf"
        out2 = tmp_path / "second.pdf"
        with PDFFiller(fillable_pdf) as f:
            f.save(out1, flatten=False)
            with pytest.raises(PDFFillerError, match="already been called"):
                f.save(out2, flatten=False)


class TestSaveOverInputGuard:
    def test_save_to_input_path_raises(self, fillable_pdf):
        """Saving over the source PDF raises PDFWriteError."""
        with PDFFiller(fillable_pdf) as f:
            with pytest.raises(PDFWriteError, match="input"):
                f.save(fillable_pdf, flatten=False)

    def test_save_to_input_path_via_relative_path_raises(self, fillable_pdf, monkeypatch):
        """The guard compares resolved paths, not raw strings."""
        monkeypatch.chdir(fillable_pdf.parent)
        with PDFFiller(fillable_pdf) as f:
            with pytest.raises(PDFWriteError, match="input"):
                f.save(fillable_pdf.name, flatten=False)


class TestReadOnlyOutputPath:
    def test_save_to_readonly_dir_raises(self, fillable_pdf, tmp_path):
        """Saving to a read-only directory raises PDFWriteError."""
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        # Use 0o555 (r-x) so stat/exists calls work but writes fail
        readonly_dir.chmod(0o555)

        out = readonly_dir / "output.pdf"
        try:
            with PDFFiller(fillable_pdf) as f:
                with pytest.raises(PDFWriteError):
                    f.save(out, flatten=False)
        finally:
            # Restore permissions so tmp_path cleanup works
            readonly_dir.chmod(0o755)


class TestEdgeCases:
    def test_empty_field_name(self, fillable_pdf, tmp_path):
        """Filling a field with an empty string name should not crash."""
        out = tmp_path / "empty_name.pdf"
        with PDFFiller(fillable_pdf) as f:
            f.fill_field("", "value")
            f.save(out, flatten=False)

    def test_very_long_field_value(self, fillable_pdf, tmp_path):
        """A very long field value should not crash."""
        out = tmp_path / "long_value.pdf"
        with PDFFiller(fillable_pdf) as f:
            f.fill_field("first_name", "x" * 10000)
            f.save(out, flatten=False)

    def test_unicode_field_value(self, fillable_pdf, tmp_path):
        """Unicode characters in field values should save successfully."""
        out = tmp_path / "unicode.pdf"
        with PDFFiller(fillable_pdf) as f:
            f.fill_field("first_name", "Ren\u00e9")
            f.save(out, flatten=False)

        with PDFFiller(out) as f2:
            assert f2.get_field_value("first_name") == "Ren\u00e9"

    def test_already_flattened_pdf(self, fillable_pdf, tmp_path):
        """Filling an already-flattened PDF (no widgets) should handle gracefully."""
        # First, create a flattened PDF with no widgets
        flat = tmp_path / "flattened.pdf"
        with PDFFiller(fillable_pdf) as f:
            f.fill_field("first_name", "Test")
            f.save(flat, flatten=True)

        # Now open the flattened PDF - it has no form fields
        out = tmp_path / "re_filled.pdf"
        with PDFFiller(flat) as f2:
            assert f2.has_form_fields() is False
            # Trying to fill fields should not crash - they just won't match
            f2.fill_field("first_name", "New Value")
            f2.save(out, flatten=False)

    def test_corrupted_pdf_raises(self, tmp_path):
        """Opening a file with garbage bytes should raise PDFReadError."""
        bad_pdf = tmp_path / "corrupted.pdf"
        bad_pdf.write_bytes(b"this is not a valid pdf file at all")

        with pytest.raises(PDFReadError, match="Failed to open"):
            PDFFiller(bad_pdf)


class TestFillFieldsStrictMode:
    def test_fill_fields_validates_in_strict_mode(self, fillable_pdf):
        """fill_fields() should validate each field name in strict mode."""
        with PDFFiller(fillable_pdf, strict=True) as f:
            with pytest.raises(FieldNotFoundError):
                f.fill_fields({"nonexistent_field": "value"})

    def test_fill_fields_works_in_strict_mode(self, fillable_pdf):
        """fill_fields() should work for valid fields in strict mode."""
        with PDFFiller(fillable_pdf, strict=True) as f:
            f.fill_fields({"first_name": "Alice", "last_name": "Smith"})
            ops = f.pending_operations
            assert ops["fields"]["first_name"] == "Alice"
            assert ops["fields"]["last_name"] == "Smith"


class TestPageBoundsValidation:
    def test_insert_text_invalid_page_raises(self, non_fillable_pdf):
        with PDFFiller(non_fillable_pdf) as f:
            with pytest.raises(PDFFillerError, match="out of range"):
                f.insert_text("Hello", 100, 200, page_num=5)

    def test_insert_text_box_invalid_page_raises(self, non_fillable_pdf):
        with PDFFiller(non_fillable_pdf) as f:
            with pytest.raises(PDFFillerError, match="out of range"):
                f.insert_text_box("Hello", 100, 200, 300, 250, page_num=5)

    def test_insert_image_invalid_page_raises(self, non_fillable_pdf, tiny_png):
        with PDFFiller(non_fillable_pdf) as f:
            with pytest.raises(PDFFillerError, match="out of range"):
                f.insert_image(tiny_png, 100, 200, 300, 250, page_num=5)


class TestPendingOperations:
    def test_returns_queued_fields(self, fillable_pdf):
        with PDFFiller(fillable_pdf) as f:
            f.fill_field("first_name", "Alice")
            f.check_box("agree_terms")
            ops = f.pending_operations
            assert ops["fields"] == {"first_name": "Alice"}
            assert "agree_terms" in ops["check"]
            assert len(ops["uncheck"]) == 0

    def test_returns_copy(self, fillable_pdf):
        """Modifying the returned dict should not affect internal state."""
        with PDFFiller(fillable_pdf) as f:
            f.fill_field("first_name", "Alice")
            ops = f.pending_operations
            ops["fields"]["first_name"] = "Bob"
            assert f.pending_operations["fields"]["first_name"] == "Alice"


# ---------------------------------------------------------------------------
# 1. Size/resource limits
# ---------------------------------------------------------------------------

class TestPDFSizeLimit:
    def test_exceeds_max_pdf_size_raises(self, large_pdf):
        """Opening a PDF that exceeds max_pdf_size raises PDFFillerError."""
        # The test PDF is small, so set a tiny limit to trigger the error
        with pytest.raises(PDFFillerError, match="exceeds maximum"):
            PDFFiller(large_pdf, max_pdf_size=10)

    def test_within_max_pdf_size_opens(self, large_pdf):
        """A PDF within the size limit opens normally."""
        with PDFFiller(large_pdf, max_pdf_size=10 * 1024 * 1024) as f:
            assert f.page_count == 1

    def test_max_pdf_size_none_disables_check(self, large_pdf):
        """Setting max_pdf_size=None disables the file size check."""
        with PDFFiller(large_pdf, max_pdf_size=None) as f:
            assert f.page_count == 1

    def test_warning_at_50_percent(self, large_pdf, caplog):
        """A PDF over 50% of the limit should log a warning."""
        file_size = large_pdf.stat().st_size
        # Set limit to just above file_size so it passes, but file is >50%
        limit = file_size + 100
        with caplog.at_level(logging.WARNING, logger="pdfiller.core"):
            with PDFFiller(large_pdf, max_pdf_size=limit) as f:
                assert f.page_count == 1
        assert "over 50%" in caplog.text

    def test_no_warning_below_50_percent(self, large_pdf, caplog):
        """A PDF well below 50% of the limit should not log a warning."""
        file_size = large_pdf.stat().st_size
        limit = file_size * 10  # 10x the size, so well under 50%
        with caplog.at_level(logging.WARNING, logger="pdfiller.core"):
            with PDFFiller(large_pdf, max_pdf_size=limit) as f:
                assert f.page_count == 1
        assert "over 50%" not in caplog.text

    def test_default_max_pdf_size(self):
        """Default max PDF size should be 100 MB."""
        assert DEFAULT_MAX_PDF_SIZE == 100 * 1024 * 1024


class TestImageSizeLimit:
    def test_exceeds_max_image_size_raises(self, non_fillable_pdf, tiny_png):
        """Inserting an image that exceeds max_image_size raises PDFFillerError."""
        with PDFFiller(non_fillable_pdf, max_image_size=1) as f:
            with pytest.raises(PDFFillerError, match="exceeds maximum"):
                f.insert_image(tiny_png, 100, 200, 300, 250)

    def test_within_max_image_size_works(self, non_fillable_pdf, tiny_png):
        """An image within the size limit inserts normally."""
        with PDFFiller(non_fillable_pdf, max_image_size=10 * 1024 * 1024) as f:
            f.insert_image(tiny_png, 100, 200, 300, 250)
            assert len(f._image_overlays) == 1

    def test_max_image_size_none_disables_check(self, non_fillable_pdf, tiny_png):
        """Setting max_image_size=None disables the image size check."""
        with PDFFiller(non_fillable_pdf, max_image_size=None) as f:
            f.insert_image(tiny_png, 100, 200, 300, 250)
            assert len(f._image_overlays) == 1

    def test_image_warning_at_50_percent(self, non_fillable_pdf, tiny_png, caplog):
        """An image over 50% of the limit should log a warning."""
        img_size = tiny_png.stat().st_size
        limit = img_size + 10  # just above file_size so >50%
        with caplog.at_level(logging.WARNING, logger="pdfiller.core"):
            with PDFFiller(non_fillable_pdf, max_image_size=limit) as f:
                f.insert_image(tiny_png, 100, 200, 300, 250)
        assert "over 50%" in caplog.text

    def test_default_max_image_size(self):
        """Default max image size should be 50 MB."""
        assert DEFAULT_MAX_IMAGE_SIZE == 50 * 1024 * 1024


# ---------------------------------------------------------------------------
# 2. Auto-detect fillable vs non-fillable routing
# ---------------------------------------------------------------------------

class TestFillMethod:
    def test_fillable_pdf_routes_to_fill_fields(self, fillable_pdf, tmp_path):
        """fill() on a fillable PDF should fill form fields by name."""
        out = tmp_path / "filled.pdf"
        with PDFFiller(fillable_pdf) as f:
            f.fill({"first_name": "Alice", "last_name": "Smith"})
            ops = f.pending_operations
            assert ops["fields"]["first_name"] == "Alice"
            assert ops["fields"]["last_name"] == "Smith"
            f.save(out, flatten=False)

        with PDFFiller(out) as f2:
            assert f2.get_field_value("first_name") == "Alice"
            assert f2.get_field_value("last_name") == "Smith"

    def test_non_fillable_pdf_routes_to_insert_text(self, non_fillable_pdf, tmp_path):
        """fill() on a non-fillable PDF should insert text at coordinates."""
        out = tmp_path / "filled.pdf"
        with PDFFiller(non_fillable_pdf) as f:
            f.fill({
                "Name": {"text": "Jane Doe", "x": 200, "y": 150, "page": 0},
                "Date": {"text": "3/15/2026", "x": 200, "y": 200},
            })
            assert len(f._text_overlays) == 2
            f.save(out, flatten=False)

        doc = fitz.open(str(out))
        text = doc[0].get_text()
        assert "Jane Doe" in text
        assert "3/15/2026" in text
        doc.close()

    def test_non_fillable_missing_text_key_raises(self, non_fillable_pdf):
        """fill() on non-fillable PDF with bad data format raises PDFFillerError."""
        with PDFFiller(non_fillable_pdf) as f:
            with pytest.raises(PDFFillerError, match="coordinate-based"):
                f.fill({"Name": "plain string"})

    def test_non_fillable_missing_text_in_dict_raises(self, non_fillable_pdf):
        """fill() on non-fillable PDF with dict missing 'text' raises PDFFillerError."""
        with PDFFiller(non_fillable_pdf) as f:
            with pytest.raises(PDFFillerError, match="coordinate-based"):
                f.fill({"Name": {"x": 100, "y": 200}})

    def test_fill_returns_self(self, fillable_pdf):
        """fill() returns self for method chaining."""
        with PDFFiller(fillable_pdf) as f:
            result = f.fill({"first_name": "Alice"})
            assert result is f

    def test_fill_non_fillable_optional_params(self, non_fillable_pdf, tmp_path):
        """fill() on non-fillable PDF respects optional params like font_size."""
        out = tmp_path / "styled.pdf"
        with PDFFiller(non_fillable_pdf) as f:
            f.fill({
                "Title": {
                    "text": "Big Title",
                    "x": 100,
                    "y": 100,
                    "font_size": 24,
                    "font_name": "helv",
                },
            })
            assert f._text_overlays[0]["font_size"] == 24
            f.save(out, flatten=False)


# ---------------------------------------------------------------------------
# 3. Radio button and dropdown support
# ---------------------------------------------------------------------------

class TestDropdownFields:
    def test_list_fields_includes_options(self, fillable_pdf_with_dropdown):
        """list_fields() should include options for dropdown/combobox fields."""
        with PDFFiller(fillable_pdf_with_dropdown) as f:
            fields = f.list_fields()

        by_name = {field["name"]: field for field in fields}
        assert "state" in by_name
        assert by_name["state"]["type"] == "ComboBox"
        assert "options" in by_name["state"]
        assert by_name["state"]["options"] == ["CA", "NY", "TX"]

    def test_fill_dropdown_valid_option(self, fillable_pdf_with_dropdown, tmp_path):
        """Filling a dropdown with a valid option should succeed."""
        out = tmp_path / "dropdown_filled.pdf"
        with PDFFiller(fillable_pdf_with_dropdown) as f:
            f.fill_field("state", "NY")
            f.save(out, flatten=False)

        with PDFFiller(out) as f2:
            assert f2.get_field_value("state") == "NY"

    def test_fill_dropdown_invalid_option_raises(self, fillable_pdf_with_dropdown):
        """Filling a dropdown with an invalid option should raise PDFFillerError."""
        with PDFFiller(fillable_pdf_with_dropdown) as f:
            f.fill_field("state", "ZZ")
            with pytest.raises(PDFFillerError, match="Invalid option"):
                # The validation happens during save when _apply_field_updates runs
                f._apply_field_updates()

    def test_fill_dropdown_via_fill_fields(self, fillable_pdf_with_dropdown, tmp_path):
        """fill_fields() should work for dropdown fields."""
        out = tmp_path / "dropdown_batch.pdf"
        with PDFFiller(fillable_pdf_with_dropdown) as f:
            f.fill_fields({"name": "Alice", "state": "CA"})
            f.save(out, flatten=False)

        with PDFFiller(out) as f2:
            assert f2.get_field_value("name") == "Alice"
            assert f2.get_field_value("state") == "CA"

    def test_fill_dropdown_via_fill_method(self, fillable_pdf_with_dropdown, tmp_path):
        """The high-level fill() method should work for dropdown fields."""
        out = tmp_path / "dropdown_fill.pdf"
        with PDFFiller(fillable_pdf_with_dropdown) as f:
            f.fill({"name": "Bob", "state": "TX"})
            f.save(out, flatten=False)

        with PDFFiller(out) as f2:
            assert f2.get_field_value("state") == "TX"

    def test_text_field_has_no_options(self, fillable_pdf_with_dropdown):
        """Text fields should not have an 'options' key in list_fields()."""
        with PDFFiller(fillable_pdf_with_dropdown) as f:
            fields = f.list_fields()

        by_name = {field["name"]: field for field in fields}
        assert "options" not in by_name["name"]


class TestListboxFields:
    def test_list_fields_includes_listbox_options(self, fillable_pdf_with_listbox):
        """list_fields() should include options for listbox fields."""
        with PDFFiller(fillable_pdf_with_listbox) as f:
            fields = f.list_fields()

        by_name = {field["name"]: field for field in fields}
        assert "color" in by_name
        assert by_name["color"]["type"] == "ListBox"
        assert by_name["color"]["options"] == ["Red", "Green", "Blue"]

    def test_fill_listbox_valid_option(self, fillable_pdf_with_listbox, tmp_path):
        """Filling a listbox with a valid option should succeed."""
        out = tmp_path / "listbox_filled.pdf"
        with PDFFiller(fillable_pdf_with_listbox) as f:
            f.fill_field("color", "Green")
            f.save(out, flatten=False)

        with PDFFiller(out) as f2:
            assert f2.get_field_value("color") == "Green"

    def test_fill_listbox_invalid_option_raises(self, fillable_pdf_with_listbox):
        """Filling a listbox with an invalid option should raise PDFFillerError."""
        with PDFFiller(fillable_pdf_with_listbox) as f:
            f.fill_field("color", "Purple")
            with pytest.raises(PDFFillerError, match="Invalid option"):
                f._apply_field_updates()
