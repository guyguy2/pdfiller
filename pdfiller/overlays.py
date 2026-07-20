"""
Typed overlay records queued for non-fillable content (text and images).

These replace the raw dicts previously stored on PDFFiller. `pending_operations`
still exposes them as plain dicts (via dataclasses.asdict) so the public shape,
including the "type" discriminator on text overlays, is unchanged.
"""

from dataclasses import dataclass

import pymupdf

RGB = tuple


@dataclass
class PointTextOverlay:
    """Text placed at a single (x, y) point."""

    text: str
    x: float
    y: float
    page_num: int
    font_size: float
    font_name: str
    color: RGB
    type: str = "point"


@dataclass
class BoxTextOverlay:
    """Text wrapped inside a bounding box rectangle."""

    text: str
    rect: tuple
    page_num: int
    font_size: float
    font_name: str
    color: RGB
    type: str = "box"


@dataclass
class ImageOverlay:
    """An image placed inside a bounding box rectangle."""

    image_path: str
    rect: tuple
    page_num: int
    keep_proportion: bool


def apply_text_overlays(doc, overlays) -> None:
    """Write queued text overlays to their pages in an open document.

    page_num was validated when each overlay was queued.
    """
    for overlay in overlays:
        page = doc[overlay.page_num]
        if isinstance(overlay, PointTextOverlay):
            page.insert_text(
                (overlay.x, overlay.y),
                overlay.text,
                fontsize=overlay.font_size,
                fontname=overlay.font_name,
                color=overlay.color,
            )
        elif isinstance(overlay, BoxTextOverlay):
            page.insert_textbox(
                pymupdf.Rect(overlay.rect),
                overlay.text,
                fontsize=overlay.font_size,
                fontname=overlay.font_name,
                color=overlay.color,
            )


def apply_image_overlays(doc, overlays) -> None:
    """Write queued image overlays to their pages in an open document."""
    for overlay in overlays:
        page = doc[overlay.page_num]
        page.insert_image(
            pymupdf.Rect(overlay.rect),
            filename=overlay.image_path,
            keep_proportion=overlay.keep_proportion,
        )
