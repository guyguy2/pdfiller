"""
Flattening: render a form's field values as static text and strip the widgets,
so filled values are visible in every PDF viewer.
"""

import logging
import tempfile
from pathlib import Path
from typing import Union

import pymupdf

from .fields import is_checkbox

logger = logging.getLogger(__name__)


def _insert_fitted_textbox(page, rect, text: str, font_size: float) -> None:
    """Render text clipped to rect, shrinking the font stepwise until it fits.

    insert_textbox writes nothing and returns a negative value when the text
    does not fit, so each attempt is safe to retry at a smaller size.
    """
    min_font_size = 2.0
    while font_size >= min_font_size:
        leftover = page.insert_textbox(
            rect, text, fontsize=font_size, color=(0, 0, 0), fontname="helv"
        )
        if leftover >= 0:
            return
        font_size -= 0.5
    logger.warning(
        "Field value does not fit its widget rect even at %.1fpt; value not rendered: %.40r",
        min_font_size,
        text,
    )


def _render_widget_values(doc) -> None:
    """Draw each widget's visible value as static text on its page."""
    for page_num in range(len(doc)):
        page = doc[page_num]
        for widget in page.widgets():
            # Overlay any field that has a visible value. This covers fields we
            # filled, checkboxes we checked, auto-dated fields, AND values
            # already present in the source PDF, which would otherwise be lost
            # when the widget annotations are deleted.
            value = widget.field_value
            if value and value not in ["Off", ""]:
                rect = widget.rect
                height = rect.height
                font_size = min(height * 0.7, 10)  # Max 10pt

                # Checkboxes report their "on" state as any non-Off export value
                # (e.g. "On", "Yes", True); render an X mark rather than the raw
                # value.
                if is_checkbox(widget):
                    x = rect.x0 + 2
                    y = rect.y0 + (height * 0.75)
                    page.insert_text(
                        (x, y), "X", fontsize=font_size, color=(0, 0, 0), fontname="helv"
                    )
                else:
                    _insert_fitted_textbox(page, rect, str(value), font_size)


def _strip_widgets(doc) -> None:
    """Delete all widget annotations, leaving only the static text overlays."""
    for page_num in range(len(doc)):
        page = doc[page_num]
        widget = page.first_widget
        while widget:
            widget = page.delete_widget(widget)


def flatten_to_file(doc, output_path: Union[str, Path]):
    """Flatten an open document's field values and save to output_path.

    Saves the document to a unique temp file, reopens it, renders each field's
    value as static text, strips the widget annotations, and writes the result.
    Closes the passed-in document and returns the reopened flattened document so
    the caller can adopt it as its live handle.
    """
    output_path = Path(output_path)
    # Unique temp name so concurrent flattens to the same output path cannot
    # clobber each other's temp file.
    with tempfile.NamedTemporaryFile(
        dir=output_path.parent, prefix=output_path.stem + ".", suffix=".temp.pdf", delete=False
    ) as tf:
        temp_path = Path(tf.name)
    doc.save(str(temp_path), garbage=4, deflate=True)
    doc.close()

    try:
        flattened = pymupdf.open(str(temp_path))
        _render_widget_values(flattened)
        _strip_widgets(flattened)
        flattened.save(str(output_path), garbage=4, deflate=True)
    finally:
        temp_path.unlink(missing_ok=True)
    return flattened
