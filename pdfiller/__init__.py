"""
PDFiller - A simple library for filling PDF forms
Handles both fillable and non-fillable PDFs with automatic flattening for compatibility
"""

from .core import PDFFiller
from .exceptions import (
    PDFFillerError,
    FieldNotFoundError,
    DefaultsValidationError,
    PDFReadError,
    PDFWriteError,
)
from .memory import (
    load_defaults,
    save_defaults,
    flatten_defaults,
    match_field_to_defaults,
    validate_defaults,
    register_matcher,
    unregister_matcher,
    list_matchers,
    clear_matchers,
    build_alias_matcher,
)

__version__ = "1.1.0"
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
