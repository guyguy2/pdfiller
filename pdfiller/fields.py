"""
Field-type predicates shared across the library and CLI.

PyMuPDF exposes a widget's type two ways: the numeric ``widget.field_type``
constant and the ``widget.field_type_string`` name (e.g. "CheckBox", "Button").
Widget-holding code (``core``) uses the numeric predicates; code that only has
``list_fields()`` output (the CLI) uses the string predicates. Both live here so
the type groupings are defined in exactly one place.
"""

import pymupdf

# Widget types that carry a fixed set of choices.
CHOICE_WIDGET_TYPES = (
    pymupdf.PDF_WIDGET_TYPE_RADIOBUTTON,
    pymupdf.PDF_WIDGET_TYPE_COMBOBOX,
    pymupdf.PDF_WIDGET_TYPE_LISTBOX,
)

# String type names as reported by widget.field_type_string.
CHECKBOX_TYPE_STRING = "CheckBox"
PUSH_BUTTON_TYPE_STRING = "Button"


def is_choice_widget(widget) -> bool:
    """True if the widget is a radio button, combobox, or listbox."""
    return widget.field_type in CHOICE_WIDGET_TYPES


def is_checkbox(widget) -> bool:
    """True if the widget is a checkbox."""
    return widget.field_type == pymupdf.PDF_WIDGET_TYPE_CHECKBOX


def is_checkbox_type(type_string: str) -> bool:
    """True if a field_type_string names a checkbox."""
    return type_string == CHECKBOX_TYPE_STRING


def is_push_button_type(type_string: str) -> bool:
    """True if a field_type_string names a push button (an action, not state)."""
    return type_string == PUSH_BUTTON_TYPE_STRING
