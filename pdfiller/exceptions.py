"""
Exceptions for PDFiller
"""


class PDFFillerError(Exception):
    """Base exception for PDFiller"""

    pass


class FieldNotFoundError(PDFFillerError):
    """Raised when a form field is not found in the PDF"""

    pass


class PDFReadError(PDFFillerError):
    """Raised when PDF cannot be read"""

    pass


class PDFWriteError(PDFFillerError):
    """Raised when PDF cannot be written"""

    pass


class DefaultsValidationError(PDFFillerError):
    """Raised when defaults data has an invalid structure"""

    pass
