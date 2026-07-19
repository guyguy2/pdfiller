"""
Core functionality for PDF form filling
"""

import logging
import os
import re
import fitz  # PyMuPDF
from typing import Dict, List, Optional, Tuple, Union, Any
from pathlib import Path
from datetime import datetime

from .exceptions import PDFFillerError, FieldNotFoundError, PDFReadError, PDFWriteError

logger = logging.getLogger(__name__)

# Default size limits (bytes)
DEFAULT_MAX_PDF_SIZE = 100 * 1024 * 1024   # 100 MB
DEFAULT_MAX_IMAGE_SIZE = 50 * 1024 * 1024  # 50 MB


class PDFFiller:
    """
    Main class for filling PDF forms

    Features:
    - Fill text fields
    - Check/uncheck checkboxes
    - Automatic flattening for compatibility
    - List available form fields
    - Preserve existing field values

    Example:
        filler = PDFFiller("input.pdf")
        filler.fill_field("name", "John Doe")
        filler.check_box("agree")
        filler.save("output.pdf", flatten=True)
    """

    def __init__(
        self,
        pdf_path: Union[str, Path],
        auto_fill_dates: bool = True,
        strict: bool = False,
        max_pdf_size: Optional[int] = DEFAULT_MAX_PDF_SIZE,
        max_image_size: Optional[int] = DEFAULT_MAX_IMAGE_SIZE,
    ):
        """
        Initialize PDFFiller with a PDF file

        Args:
            pdf_path: Path to the input PDF file
            auto_fill_dates: If True, empty date fields are filled with today's
                date during save(). Set to False to disable this behavior.
            strict: If True, validate field names exist in the PDF before
                queuing fill_field, check_box, and uncheck_box operations.
            max_pdf_size: Maximum PDF file size in bytes (default 100 MB).
                Set to None to disable the check.
            max_image_size: Maximum image file size in bytes (default 50 MB).
                Set to None to disable the check.

        Raises:
            PDFReadError: If PDF cannot be opened
            PDFFillerError: If PDF exceeds max_pdf_size
        """
        self.pdf_path = Path(pdf_path)
        self.auto_fill_dates = auto_fill_dates
        self._strict = strict
        self._max_pdf_size = max_pdf_size
        self._max_image_size = max_image_size

        if not self.pdf_path.exists():
            raise PDFReadError(f"PDF file not found: {pdf_path}")

        # Check PDF file size against the configured limit
        if self._max_pdf_size is not None:
            file_size = self.pdf_path.stat().st_size
            if file_size > self._max_pdf_size:
                raise PDFFillerError(
                    f"PDF file size ({file_size} bytes) exceeds maximum "
                    f"allowed size ({self._max_pdf_size} bytes): {pdf_path}"
                )
            if file_size > self._max_pdf_size * 0.5:
                logger.warning(
                    "PDF file size (%d bytes) is over 50%% of the "
                    "configured limit (%d bytes): %s",
                    file_size, self._max_pdf_size, pdf_path,
                )

        try:
            # Suppress non-fatal MuPDF errors (e.g. missing XObject font resources
            # in malformed PDFs) that clutter stderr but don't affect output.
            # Scope the suppression to the open call and restore the prior
            # global setting so we don't silence genuine errors elsewhere.
            prev_display_errors = fitz.TOOLS.mupdf_display_errors()
            fitz.TOOLS.mupdf_display_errors(False)
            try:
                self.doc = fitz.open(str(self.pdf_path))
            finally:
                fitz.TOOLS.mupdf_display_errors(prev_display_errors)
        except Exception as e:
            raise PDFReadError(f"Failed to open PDF: {e}")

        if self.doc.is_encrypted:
            self.doc.close()
            raise PDFReadError(f"PDF is password-protected: {pdf_path}")

        self._fields_to_fill: Dict[str, Any] = {}
        self._checkboxes_to_check: set = set()
        self._checkboxes_to_uncheck: set = set()
        self._text_overlays: list = []
        self._image_overlays: list = []
        self._preserve_existing = True
        self._saved = False

    def __enter__(self):
        """Context manager support"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close document on exit"""
        self.close()

    def close(self):
        """Close the PDF document"""
        if hasattr(self, 'doc') and self.doc:
            self.doc.close()

    @property
    def page_count(self) -> int:
        """Number of pages in the PDF."""
        return len(self.doc)

    def list_fields(self) -> List[Dict[str, Any]]:
        """
        List all form fields across all pages in the PDF

        Returns:
            List of dictionaries with field information including page number.
            Radio button and dropdown/combobox fields include an 'options' key
            listing their available choices.
        """
        fields = []

        for page_num in range(self.page_count):
            page = self.doc[page_num]
            for widget in page.widgets():
                field_info = {
                    'name': widget.field_name,
                    'type': widget.field_type_string,
                    'value': widget.field_value,
                    'page': page_num,
                    'rect': {
                        'x0': widget.rect.x0,
                        'y0': widget.rect.y0,
                        'x1': widget.rect.x1,
                        'y1': widget.rect.y1,
                    }
                }

                # Include available options for radio buttons and dropdowns
                if widget.field_type in (
                    fitz.PDF_WIDGET_TYPE_RADIOBUTTON,
                    fitz.PDF_WIDGET_TYPE_COMBOBOX,
                    fitz.PDF_WIDGET_TYPE_LISTBOX,
                ):
                    field_info['options'] = widget.choice_values or []

                fields.append(field_info)

        return fields

    def get_field_value(self, field_name: str) -> Optional[Any]:
        """
        Get the current value of a field (searches all pages)

        Args:
            field_name: Name of the field

        Returns:
            Field value or None if not found
        """
        for page_num in range(self.page_count):
            for widget in self.doc[page_num].widgets():
                if widget.field_name == field_name:
                    return widget.field_value

        return None

    def fill_field(self, field_name: str, value: Any) -> 'PDFFiller':
        """
        Fill a form field with a value

        Args:
            field_name: Name of the field to fill
            value: Value to set

        Returns:
            Self for method chaining

        Raises:
            FieldNotFoundError: If strict mode is enabled and field not found
        """
        if self._strict:
            self.validate_fields([field_name], raise_error=True)
        self._fields_to_fill[field_name] = value
        return self

    def fill_fields(self, fields: Dict[str, Any]) -> 'PDFFiller':
        """
        Fill multiple fields at once

        Args:
            fields: Dictionary of field_name: value pairs

        Returns:
            Self for method chaining

        Raises:
            FieldNotFoundError: If strict mode is enabled and a field is not found
        """
        for name, value in fields.items():
            self.fill_field(name, value)
        return self

    def fill(self, data: Dict[str, Any]) -> 'PDFFiller':
        """
        High-level fill method that auto-detects fillable vs non-fillable PDFs.

        For fillable PDFs (with AcroForm fields): delegates to fill_fields()
        to set form field values by name.

        For non-fillable PDFs: expects each key to map to a dict with
        placement coordinates, e.g.::

            {
                "Name": {"text": "Jane Doe", "x": 200, "y": 150, "page": 0},
                "Date": {"text": "3/15/2026", "x": 200, "y": 200, "page": 0},
            }

        Optional keys per entry: font_size (default 10), font_name (default
        "helv"), color (default (0,0,0)).

        Args:
            data: Field values (fillable) or coordinate-based text placements
                (non-fillable).

        Returns:
            Self for method chaining
        """
        if self.has_form_fields():
            self.fill_fields(data)
        else:
            for label, spec in data.items():
                if not isinstance(spec, dict) or "text" not in spec:
                    raise PDFFillerError(
                        f"Non-fillable PDF requires coordinate-based data for "
                        f"'{label}'. Expected a dict with at least 'text', 'x', "
                        f"and 'y' keys."
                    )
                self.insert_text(
                    text=spec["text"],
                    x=spec.get("x", 0),
                    y=spec.get("y", 0),
                    page_num=spec.get("page", 0),
                    font_size=spec.get("font_size", 10),
                    font_name=spec.get("font_name", "helv"),
                    color=spec.get("color", (0, 0, 0)),
                )
        return self

    def check_box(self, field_name: str) -> 'PDFFiller':
        """
        Check a checkbox field

        Args:
            field_name: Name of the checkbox field

        Returns:
            Self for method chaining

        Raises:
            FieldNotFoundError: If strict mode is enabled and field not found
        """
        if self._strict:
            self.validate_fields([field_name], raise_error=True)
        self._checkboxes_to_check.add(field_name)
        return self

    def uncheck_box(self, field_name: str) -> 'PDFFiller':
        """
        Uncheck a checkbox field

        Removes from the check list and explicitly unchecks it in the PDF,
        even if the box was already checked before this filler was created.

        Args:
            field_name: Name of the checkbox field

        Returns:
            Self for method chaining

        Raises:
            FieldNotFoundError: If strict mode is enabled and field not found
        """
        if self._strict:
            self.validate_fields([field_name], raise_error=True)
        self._checkboxes_to_check.discard(field_name)
        self._checkboxes_to_uncheck.add(field_name)
        return self

    def preserve_existing_fields(self, preserve: bool = True) -> 'PDFFiller':
        """
        Set whether to preserve existing field values

        Args:
            preserve: If True, only fill empty fields

        Returns:
            Self for method chaining
        """
        self._preserve_existing = preserve
        return self

    # Date fields whose value is not "today": birthdays, validity ranges, etc.
    # Auto-dating these silently corrupts the form, so they are excluded.
    _AUTO_DATE_EXCLUDED_TOKENS = frozenset({
        "birth", "dob", "expire", "expires", "expiry", "expiration",
        "effective", "start", "end", "from", "to",
    })

    @staticmethod
    def _is_date_field(field_name: str) -> bool:
        """
        Check if a field name suggests a date that should default to today

        Args:
            field_name: Name of the field to check

        Returns:
            True if the field is a date field eligible for auto-fill with
            today's date (e.g. sign_date). Fields naming other kinds of dates
            (date_of_birth, expiration_date, start_date) return False.
        """
        # Normalize camelCase boundaries (SignDate -> Sign_Date) then split into tokens
        normalized = re.sub(r"([a-z])([A-Z])", r"\1_\2", field_name).lower()
        tokens = set(re.split(r"[_\-\s]+", normalized))
        if "date" not in tokens and "dated" not in tokens:
            return False
        return not (tokens & PDFFiller._AUTO_DATE_EXCLUDED_TOKENS)

    @staticmethod
    def _format_today_date() -> str:
        """
        Get today's date formatted as M/D/YYYY (no leading zeros)

        Returns:
            Today's date as a string
        """
        today = datetime.now()
        return f"{today.month}/{today.day}/{today.year}"

    def _apply_field_updates(self):
        """Apply all queued field updates to the PDF (across all pages)"""
        for page_num in range(self.page_count):
            page = self.doc[page_num]
            for widget in page.widgets():
                field_name = widget.field_name

                # Check if this field should be updated
                if field_name in self._fields_to_fill:
                    # Skip if preserving existing and field has value
                    if self._preserve_existing and widget.field_value:
                        continue

                    value = self._fields_to_fill[field_name]

                    # Validate option value for radio buttons and dropdowns
                    if widget.field_type in (
                        fitz.PDF_WIDGET_TYPE_RADIOBUTTON,
                        fitz.PDF_WIDGET_TYPE_COMBOBOX,
                        fitz.PDF_WIDGET_TYPE_LISTBOX,
                    ):
                        options = widget.choice_values or []
                        if options and str(value) not in options:
                            raise PDFFillerError(
                                f"Invalid option '{value}' for field '{field_name}'. "
                                f"Valid options: {options}"
                            )

                    widget.field_value = str(value)
                    widget.update()

                elif field_name in self._checkboxes_to_check:
                    widget.field_value = True
                    widget.update()

                elif field_name in self._checkboxes_to_uncheck:
                    widget.field_value = False
                    widget.update()

                # Auto-fill date fields with today's date if empty and enabled
                elif self.auto_fill_dates and self._is_date_field(field_name) and not widget.field_value:
                    widget.field_value = self._format_today_date()
                    widget.update()

    def has_form_fields(self) -> bool:
        """Check whether the PDF has any AcroForm fields."""
        for page_num in range(self.page_count):
            page = self.doc[page_num]
            try:
                next(page.widgets())
                return True
            except StopIteration:
                pass
        return False

    def get_page_layout(self, page_num: int = 0) -> Dict[str, Any]:
        """Extract text blocks with positions and page dimensions.

        Useful for figuring out where to place text on non-fillable PDFs.

        Returns:
            Dict with 'width', 'height', and 'blocks' (list of text block dicts)
        """
        if page_num < 0 or page_num >= self.page_count:
            raise PDFFillerError(f"Page {page_num} out of range (0-{self.page_count - 1})")

        page = self.doc[page_num]
        rect = page.rect
        blocks = []

        for block in page.get_text("dict")["blocks"]:
            if block["type"] == 0:  # text block
                lines_text = []
                for line in block.get("lines", []):
                    spans_text = "".join(span["text"] for span in line.get("spans", []))
                    if spans_text.strip():
                        lines_text.append(spans_text)
                if lines_text:
                    blocks.append({
                        "text": "\n".join(lines_text),
                        "bbox": {
                            "x0": block["bbox"][0],
                            "y0": block["bbox"][1],
                            "x1": block["bbox"][2],
                            "y1": block["bbox"][3],
                        },
                    })

        return {
            "width": rect.width,
            "height": rect.height,
            "blocks": blocks,
        }

    def insert_text(
        self,
        text: str,
        x: float,
        y: float,
        page_num: int = 0,
        font_size: float = 10,
        font_name: str = "helv",
        color: Tuple[float, float, float] = (0, 0, 0),
    ) -> "PDFFiller":
        """Queue text insertion at specific coordinates on a page.

        Args:
            text: The text to insert
            x: X coordinate (points from left)
            y: Y coordinate (points from top)
            page_num: Target page (0-indexed)
            font_size: Font size in points
            font_name: PyMuPDF font name
            color: RGB tuple, each 0-1

        Returns:
            Self for method chaining
        """
        if page_num < 0 or page_num >= self.page_count:
            raise PDFFillerError(f"Page {page_num} out of range (0-{self.page_count - 1})")
        self._text_overlays.append({
            "type": "point",
            "text": text,
            "x": x,
            "y": y,
            "page_num": page_num,
            "font_size": font_size,
            "font_name": font_name,
            "color": color,
        })
        return self

    def insert_text_box(
        self,
        text: str,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        page_num: int = 0,
        font_size: float = 10,
        font_name: str = "helv",
        color: Tuple[float, float, float] = (0, 0, 0),
    ) -> "PDFFiller":
        """Queue text insertion in a bounding box with wrapping.

        Args:
            text: The text to insert
            x0, y0, x1, y1: Bounding box coordinates
            page_num: Target page (0-indexed)
            font_size: Font size in points
            font_name: PyMuPDF font name
            color: RGB tuple, each 0-1

        Returns:
            Self for method chaining
        """
        if page_num < 0 or page_num >= self.page_count:
            raise PDFFillerError(f"Page {page_num} out of range (0-{self.page_count - 1})")
        self._text_overlays.append({
            "type": "box",
            "text": text,
            "rect": (x0, y0, x1, y1),
            "page_num": page_num,
            "font_size": font_size,
            "font_name": font_name,
            "color": color,
        })
        return self

    def insert_image(
        self,
        image_path: Union[str, Path],
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        page_num: int = 0,
        keep_proportion: bool = True,
    ) -> "PDFFiller":
        """Queue an image insertion at specific coordinates on a page.

        Useful for placing signature images, stamps, or logos onto a PDF.

        Args:
            image_path: Path to the image file (PNG, GIF, JPEG, etc.)
            x0, y0, x1, y1: Bounding box coordinates for the image
            page_num: Target page (0-indexed)
            keep_proportion: If True, maintain aspect ratio within the box

        Returns:
            Self for method chaining

        Raises:
            PDFFillerError: If the image file does not exist
        """
        if page_num < 0 or page_num >= self.page_count:
            raise PDFFillerError(f"Page {page_num} out of range (0-{self.page_count - 1})")
        image_path = Path(image_path)
        if not image_path.exists():
            raise PDFFillerError(f"Image file not found: {image_path}")

        # Check image file size against the configured limit
        if self._max_image_size is not None:
            img_size = image_path.stat().st_size
            if img_size > self._max_image_size:
                raise PDFFillerError(
                    f"Image file size ({img_size} bytes) exceeds maximum "
                    f"allowed size ({self._max_image_size} bytes): {image_path}"
                )
            if img_size > self._max_image_size * 0.5:
                logger.warning(
                    "Image file size (%d bytes) is over 50%% of the "
                    "configured limit (%d bytes): %s",
                    img_size, self._max_image_size, image_path,
                )

        # Validate the file is a recognizable image format
        try:
            pix = fitz.Pixmap(str(image_path))
            pix = None
        except Exception:
            raise PDFFillerError(f"Invalid or unsupported image file: {image_path}")

        self._image_overlays.append({
            "image_path": str(image_path),
            "rect": (x0, y0, x1, y1),
            "page_num": page_num,
            "keep_proportion": keep_proportion,
        })
        return self

    def _apply_image_overlays(self):
        """Write all queued image overlays to their respective pages."""
        for overlay in self._image_overlays:
            page_num = overlay["page_num"]
            if page_num < 0 or page_num >= self.page_count:
                continue
            page = self.doc[page_num]
            page.insert_image(
                fitz.Rect(overlay["rect"]),
                filename=overlay["image_path"],
                keep_proportion=overlay["keep_proportion"],
            )

    def _apply_text_overlays(self):
        """Write all queued text overlays to their respective pages."""
        for overlay in self._text_overlays:
            page_num = overlay["page_num"]
            if page_num < 0 or page_num >= self.page_count:
                continue
            page = self.doc[page_num]

            if overlay["type"] == "point":
                page.insert_text(
                    (overlay["x"], overlay["y"]),
                    overlay["text"],
                    fontsize=overlay["font_size"],
                    fontname=overlay["font_name"],
                    color=overlay["color"],
                )
            elif overlay["type"] == "box":
                page.insert_textbox(
                    fitz.Rect(overlay["rect"]),
                    overlay["text"],
                    fontsize=overlay["font_size"],
                    fontname=overlay["font_name"],
                    color=overlay["color"],
                )

    def _flatten_with_overlays(self, output_path: Union[str, Path]):
        """
        Create a flattened PDF with text overlays
        This ensures filled values are visible in all PDF viewers
        """
        # First apply updates
        self._apply_field_updates()

        # Apply any queued text/image overlays for non-fillable PDFs
        self._apply_text_overlays()
        self._apply_image_overlays()

        # Save temporary version
        temp_path = Path(output_path).with_suffix('.temp.pdf')
        self.doc.save(str(temp_path), garbage=4, deflate=True)
        self.doc.close()

        try:
            # Reopen and add text overlays for form fields
            self.doc = fitz.open(str(temp_path))

            for page_num in range(self.page_count):
                page = self.doc[page_num]
                for widget in page.widgets():
                    # Overlay any field that has a visible value. This covers
                    # fields we filled, checkboxes we checked, auto-dated
                    # fields, AND values already present in the source PDF.
                    # The latter would otherwise be lost when the widget
                    # annotations are deleted below.
                    value = widget.field_value

                    if value and value not in ['Off', '']:
                        rect = widget.rect

                        # Checkboxes report their "on" state as any non-Off
                        # export value (e.g. "On", "Yes", True); render an X
                        # mark for all of them rather than the raw value.
                        if widget.field_type == fitz.PDF_WIDGET_TYPE_CHECKBOX:
                            value = 'X'
                        else:
                            value = str(value)

                        # Calculate font size based on rectangle height
                        height = rect.height
                        font_size = min(height * 0.7, 10)  # Max 10pt

                        # Position text
                        x = rect.x0 + 2
                        y = rect.y0 + (height * 0.75)

                        page.insert_text(
                            (x, y),
                            value,
                            fontsize=font_size,
                            color=(0, 0, 0),
                            fontname="helv"
                        )

            # Remove widget annotations so only the text overlays remain
            for page_num in range(self.page_count):
                page = self.doc[page_num]
                widget = page.first_widget
                while widget:
                    widget = page.delete_widget(widget)

            # Save final version
            self.doc.save(str(output_path), garbage=4, deflate=True)
        finally:
            temp_path.unlink(missing_ok=True)

    def save(self, output_path: Union[str, Path], flatten: bool = True) -> Path:
        """
        Save the filled PDF

        This method is terminal - it can only be called once per PDFFiller
        instance. Create a new instance to save again.

        Args:
            output_path: Path for the output PDF
            flatten: If True, flatten the form to ensure visibility (recommended)

        Returns:
            Path to the saved PDF

        Raises:
            PDFFillerError: If save() has already been called
            PDFWriteError: If PDF cannot be saved or output path is not writable
        """
        if self._saved:
            raise PDFFillerError(
                "save() has already been called on this filler. "
                "Create a new PDFFiller instance to save again."
            )

        output_path = Path(output_path)

        if output_path.resolve() == self.pdf_path.resolve():
            raise PDFWriteError(
                f"Output path is the same as the input PDF: {output_path}. "
                "Choose a different output path to avoid destroying the source file."
            )

        # Validate output path is writable
        if output_path.exists():
            if not os.access(str(output_path), os.W_OK):
                raise PDFWriteError(f"Output file is not writable: {output_path}")
        else:
            parent = output_path.parent
            if not os.access(str(parent), os.W_OK):
                raise PDFWriteError(f"Output directory is not writable: {parent}")

        try:
            if flatten:
                self._flatten_with_overlays(output_path)
            else:
                self._apply_field_updates()
                self._apply_text_overlays()
                self._apply_image_overlays()
                self.doc.save(str(output_path), garbage=4, deflate=True)

            self._saved = True
            return output_path

        except PDFFillerError:
            raise
        except Exception as e:
            raise PDFWriteError(f"Failed to save PDF: {e}")

    def validate_fields(self, field_names: List[str], raise_error: bool = False) -> Dict[str, bool]:
        """
        Validate that field names exist in the PDF

        Args:
            field_names: List of field names to validate
            raise_error: If True, raise FieldNotFoundError for missing fields

        Returns:
            Dictionary mapping field names to existence (True/False)

        Raises:
            FieldNotFoundError: If raise_error=True and field not found
        """
        existing_fields = {f['name'] for f in self.list_fields()}
        results = {}

        for field_name in field_names:
            exists = field_name in existing_fields
            results[field_name] = exists

            if not exists and raise_error:
                raise FieldNotFoundError(f"Field '{field_name}' not found in PDF")

        return results

    @property
    def pending_operations(self) -> Dict[str, Any]:
        """Summary of queued operations not yet saved.

        Returns:
            Dict with 'fields', 'check', and 'uncheck' keys.
        """
        return {
            "fields": dict(self._fields_to_fill),
            "check": set(self._checkboxes_to_check),
            "uncheck": set(self._checkboxes_to_uncheck),
        }

    def __repr__(self):
        return f"PDFFiller(pdf='{self.pdf_path.name}', pages={self.page_count})"
