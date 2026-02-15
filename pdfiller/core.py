"""
Core functionality for PDF form filling
"""

import fitz  # PyMuPDF
from typing import Dict, List, Optional, Tuple, Union, Any
from pathlib import Path
from datetime import datetime

from .exceptions import PDFFillerError, FieldNotFoundError, PDFReadError, PDFWriteError


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

    def __init__(self, pdf_path: Union[str, Path]):
        """
        Initialize PDFFiller with a PDF file

        Args:
            pdf_path: Path to the input PDF file

        Raises:
            PDFReadError: If PDF cannot be opened
        """
        self.pdf_path = Path(pdf_path)

        if not self.pdf_path.exists():
            raise PDFReadError(f"PDF file not found: {pdf_path}")

        try:
            # Suppress non-fatal MuPDF errors (e.g. missing XObject font resources
            # in malformed PDFs) that clutter stderr but don't affect output.
            fitz.TOOLS.mupdf_display_errors(False)
            self.doc = fitz.open(str(self.pdf_path))
        except Exception as e:
            raise PDFReadError(f"Failed to open PDF: {e}")

        self._fields_to_fill: Dict[str, Any] = {}
        self._checkboxes_to_check: set = set()
        self._text_overlays: list = []
        self._image_overlays: list = []
        self._preserve_existing = True

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
            List of dictionaries with field information including page number
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
        """
        self._fields_to_fill[field_name] = value
        return self

    def fill_fields(self, fields: Dict[str, Any]) -> 'PDFFiller':
        """
        Fill multiple fields at once

        Args:
            fields: Dictionary of field_name: value pairs

        Returns:
            Self for method chaining
        """
        self._fields_to_fill.update(fields)
        return self

    def check_box(self, field_name: str) -> 'PDFFiller':
        """
        Check a checkbox field

        Args:
            field_name: Name of the checkbox field

        Returns:
            Self for method chaining
        """
        self._checkboxes_to_check.add(field_name)
        return self

    def uncheck_box(self, field_name: str) -> 'PDFFiller':
        """
        Uncheck a checkbox field (removes from check list)

        Args:
            field_name: Name of the checkbox field

        Returns:
            Self for method chaining
        """
        self._checkboxes_to_check.discard(field_name)
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

    @staticmethod
    def _is_date_field(field_name: str) -> bool:
        """
        Check if a field name suggests it's a date field

        Args:
            field_name: Name of the field to check

        Returns:
            True if the field name suggests it contains a date
        """
        field_lower = field_name.lower()
        date_indicators = ['date', '_date', '-date', 'dated']
        return any(indicator in field_lower for indicator in date_indicators)

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
                    widget.field_value = value
                    widget.update()

                elif field_name in self._checkboxes_to_check:
                    widget.field_value = True
                    widget.update()

                # Auto-fill date fields with today's date if empty
                elif self._is_date_field(field_name) and not widget.field_value:
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
        image_path = Path(image_path)
        if not image_path.exists():
            raise PDFFillerError(f"Image file not found: {image_path}")

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
                    field_name = widget.field_name

                    # Only overlay fields we filled
                    if field_name in self._fields_to_fill or field_name in self._checkboxes_to_check:
                        value = widget.field_value

                        if value and value not in ['Off', '']:
                            rect = widget.rect

                            # Convert checkbox values
                            if value in ['On', True]:
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

        Args:
            output_path: Path for the output PDF
            flatten: If True, flatten the form to ensure visibility (recommended)

        Returns:
            Path to the saved PDF

        Raises:
            PDFWriteError: If PDF cannot be saved
        """
        output_path = Path(output_path)

        try:
            if flatten:
                self._flatten_with_overlays(output_path)
            else:
                self._apply_field_updates()
                self._apply_text_overlays()
                self._apply_image_overlays()
                self.doc.save(str(output_path), garbage=4, deflate=True)

            return output_path

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

    def __repr__(self):
        count = 0
        for page_num in range(self.page_count):
            for _ in self.doc[page_num].widgets():
                count += 1
        return f"PDFFiller(pdf='{self.pdf_path.name}', fields={count})"
