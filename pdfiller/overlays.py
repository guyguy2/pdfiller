"""
Typed overlay records queued for non-fillable content (text and images).

These replace the raw dicts previously stored on PDFFiller. `pending_operations`
still exposes them as plain dicts (via dataclasses.asdict) so the public shape,
including the "type" discriminator on text overlays, is unchanged.
"""

from dataclasses import dataclass

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
