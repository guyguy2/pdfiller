"""
PDFiller - A simple library for filling PDF forms
Handles both fillable and non-fillable PDFs with automatic flattening for compatibility
"""

from .core import PDFFiller
from .exceptions import (
    DefaultsValidationError,
    FieldNotFoundError,
    PDFFillerError,
    PDFReadError,
    PDFWriteError,
)
from .memory import (
    build_alias_matcher,
    clear_matchers,
    flatten_defaults,
    list_matchers,
    load_defaults,
    match_field_to_defaults,
    register_matcher,
    save_defaults,
    unregister_matcher,
    validate_defaults,
)

__version__ = "1.2.0"
__all__ = [
    "PDFFiller",
    "PDFFillerError",
    "FieldNotFoundError",
    "DefaultsValidationError",
    "PDFReadError",
    "PDFWriteError",
    "load_defaults",
    "save_defaults",
    "flatten_defaults",
    "match_field_to_defaults",
    "validate_defaults",
    "register_matcher",
    "unregister_matcher",
    "list_matchers",
    "clear_matchers",
    "build_alias_matcher",
]
