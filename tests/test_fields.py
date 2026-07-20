"""
Tests for pdfiller.fields type predicates.
"""

import pymupdf

from pdfiller.fields import (
    is_checkbox,
    is_checkbox_type,
    is_choice_widget,
    is_push_button_type,
)


class _FakeWidget:
    def __init__(self, field_type):
        self.field_type = field_type


class TestWidgetPredicates:
    def test_is_choice_widget_true_for_choice_types(self):
        for t in (
            pymupdf.PDF_WIDGET_TYPE_RADIOBUTTON,
            pymupdf.PDF_WIDGET_TYPE_COMBOBOX,
            pymupdf.PDF_WIDGET_TYPE_LISTBOX,
        ):
            assert is_choice_widget(_FakeWidget(t))

    def test_is_choice_widget_false_for_others(self):
        for t in (pymupdf.PDF_WIDGET_TYPE_TEXT, pymupdf.PDF_WIDGET_TYPE_CHECKBOX):
            assert not is_choice_widget(_FakeWidget(t))

    def test_is_checkbox(self):
        assert is_checkbox(_FakeWidget(pymupdf.PDF_WIDGET_TYPE_CHECKBOX))
        assert not is_checkbox(_FakeWidget(pymupdf.PDF_WIDGET_TYPE_TEXT))


class TestStringPredicates:
    def test_is_checkbox_type(self):
        assert is_checkbox_type("CheckBox")
        assert not is_checkbox_type("Text")
        assert not is_checkbox_type("Button")

    def test_is_push_button_type(self):
        assert is_push_button_type("Button")
        assert not is_push_button_type("CheckBox")
        assert not is_push_button_type("Text")
