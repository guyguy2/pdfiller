"""
Unit tests for pdfiller.cli command functions.

These tests call the command functions directly with mock args and a mocked
PDFFiller class, avoiding subprocess overhead and real PDF I/O.
"""

import json
from argparse import Namespace
from unittest.mock import MagicMock, patch

import pytest

from pdfiller.cli import (
    _describe_overlays,
    _format_fields_csv,
    _format_fields_json,
    _format_fields_table,
    _queue_overlays,
    defaults_command,
    export_command,
    fill_command,
    inspect_command,
    list_fields_command,
    load_values_from_json,
    template_command,
)
from pdfiller.exceptions import DefaultsValidationError, PDFFillerError

# ---------------------------------------------------------------------------
# Shared helpers and sample data
# ---------------------------------------------------------------------------

SAMPLE_FIELDS = [
    {"name": "first_name", "type": "Text", "value": "", "page": 0},
    {"name": "last_name", "type": "Text", "value": "Smith", "page": 0},
    {"name": "agree_terms", "type": "CheckBox", "value": "", "page": 0},
]


def _make_filler_mock(fields=None, page_count=1, pending=None, layouts=None):
    """Return a MagicMock that behaves like PDFFiller as a context manager."""
    filler = MagicMock()
    filler.list_fields.return_value = fields if fields is not None else SAMPLE_FIELDS
    filler.page_count = page_count
    filler.auto_fill_dates = True
    filler.pending_operations = pending or {"fields": {}, "check": [], "uncheck": []}
    filler.save.return_value = "/tmp/output.pdf"
    filler.has_form_fields.return_value = bool(fields)

    # Support get_page_layout calls
    if layouts:
        filler.get_page_layout.side_effect = lambda n: layouts[n]
    else:
        filler.get_page_layout.return_value = {
            "width": 612,
            "height": 792,
            "blocks": [
                {"text": "Sample text", "bbox": {"x0": 100, "y0": 100, "x1": 300, "y1": 120}},
            ],
        }

    # Make it usable as a context manager
    filler.__enter__ = MagicMock(return_value=filler)
    filler.__exit__ = MagicMock(return_value=False)
    return filler


# ---------------------------------------------------------------------------
# Format helpers
# ---------------------------------------------------------------------------


class TestFormatFieldsTable:
    def test_includes_field_count(self):
        output = _format_fields_table(SAMPLE_FIELDS, "form.pdf")
        assert "Found 3 fields in form.pdf" in output

    def test_includes_field_names(self):
        output = _format_fields_table(SAMPLE_FIELDS, "form.pdf")
        assert "first_name" in output
        assert "last_name" in output
        assert "agree_terms" in output

    def test_includes_types(self):
        output = _format_fields_table(SAMPLE_FIELDS, "form.pdf")
        assert "Type: Text" in output
        assert "Type: CheckBox" in output

    def test_includes_existing_value(self):
        output = _format_fields_table(SAMPLE_FIELDS, "form.pdf")
        assert "Current value: Smith" in output

    def test_omits_empty_value(self):
        output = _format_fields_table(SAMPLE_FIELDS, "form.pdf")
        # first_name has empty value - should not show "Current value" for it
        lines = output.split("\n")
        first_name_idx = next(i for i, line in enumerate(lines) if "first_name" in line)
        # The line after "first_name" should show Type, not Current value
        assert "Type:" in lines[first_name_idx + 1]

    def test_empty_fields_list(self):
        output = _format_fields_table([], "empty.pdf")
        assert "Found 0 fields" in output


class TestFormatFieldsJson:
    def test_valid_json_output(self):
        output = _format_fields_json(SAMPLE_FIELDS)
        data = json.loads(output)
        assert len(data) == 3
        assert data[0]["name"] == "first_name"

    def test_preserves_all_keys(self):
        output = _format_fields_json(SAMPLE_FIELDS)
        data = json.loads(output)
        for field in data:
            assert "name" in field
            assert "type" in field
            assert "value" in field


class TestFormatFieldsCsv:
    def test_csv_header(self):
        output = _format_fields_csv(SAMPLE_FIELDS)
        lines = output.strip().splitlines()
        assert lines[0] == "name,type,value,page"

    def test_csv_row_count(self):
        output = _format_fields_csv(SAMPLE_FIELDS)
        lines = output.strip().split("\n")
        # header + 3 data rows
        assert len(lines) == 4

    def test_csv_field_values(self):
        output = _format_fields_csv(SAMPLE_FIELDS)
        assert "first_name,Text,,0" in output
        assert "last_name,Text,Smith,0" in output


# ---------------------------------------------------------------------------
# load_values_from_json
# ---------------------------------------------------------------------------


class TestLoadValuesFromJson:
    def test_loads_valid_json(self, tmp_path):
        json_file = tmp_path / "values.json"
        json_file.write_text(json.dumps({"fields": {"name": "Alice"}}))
        result = load_values_from_json(json_file)
        assert result == {"fields": {"name": "Alice"}}

    def test_invalid_json_exits(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("not json{{{")
        with pytest.raises(SystemExit):
            load_values_from_json(bad)

    def test_missing_file_exits(self, tmp_path):
        with pytest.raises(SystemExit):
            load_values_from_json(tmp_path / "nonexistent.json")


# ---------------------------------------------------------------------------
# list_fields_command
# ---------------------------------------------------------------------------


class TestListFieldsCommand:
    def test_table_format_to_stdout(self, capsys):
        filler = _make_filler_mock()
        args = Namespace(input="form.pdf", output=None, format="table")

        with patch("pdfiller.cli.PDFFiller", return_value=filler):
            list_fields_command(args)

        out = capsys.readouterr().out
        assert "Found 3 fields" in out
        assert "first_name" in out

    def test_json_format_to_stdout(self, capsys):
        filler = _make_filler_mock()
        args = Namespace(input="form.pdf", output=None, format="json")

        with patch("pdfiller.cli.PDFFiller", return_value=filler):
            list_fields_command(args)

        out = capsys.readouterr().out
        data = json.loads(out)
        assert len(data) == 3

    def test_csv_format_to_stdout(self, capsys):
        filler = _make_filler_mock()
        args = Namespace(input="form.pdf", output=None, format="csv")

        with patch("pdfiller.cli.PDFFiller", return_value=filler):
            list_fields_command(args)

        out = capsys.readouterr().out
        assert "name,type,value,page" in out

    def test_output_to_file(self, tmp_path, capsys):
        filler = _make_filler_mock()
        out_file = str(tmp_path / "fields.json")
        args = Namespace(input="form.pdf", output=out_file, format="json")

        with patch("pdfiller.cli.PDFFiller", return_value=filler):
            list_fields_command(args)

        stdout = capsys.readouterr().out
        assert f"Saved: {out_file}" in stdout
        data = json.loads((tmp_path / "fields.json").read_text())
        assert len(data) == 3

    def test_default_format_is_table(self, capsys):
        filler = _make_filler_mock()
        # Simulate missing format attribute (defaults to 'table')
        args = Namespace(input="form.pdf", output=None)

        with patch("pdfiller.cli.PDFFiller", return_value=filler):
            list_fields_command(args)

        out = capsys.readouterr().out
        assert "Found 3 fields" in out

    def test_pdffiller_error_exits(self, capsys):
        filler = _make_filler_mock()
        filler.__enter__.side_effect = PDFFillerError("bad pdf")
        args = Namespace(input="bad.pdf", output=None, format="table")

        with patch("pdfiller.cli.PDFFiller", return_value=filler), pytest.raises(SystemExit):
            list_fields_command(args)

        err = capsys.readouterr().err
        assert "Error:" in err


# ---------------------------------------------------------------------------
# Overlay helpers
# ---------------------------------------------------------------------------


class TestQueueOverlays:
    def test_queues_all_sections(self):
        filler = _make_filler_mock()
        data = {
            "texts": [{"text": "Guy", "x": 200, "y": 150, "page": 1, "font_size": 12}],
            "boxes": [{"text": "Addr", "x0": 100, "y0": 200, "x1": 400, "y1": 260}],
            "images": [{"path": "sig.png", "x0": 100, "y0": 500, "x1": 300, "y1": 550}],
        }

        count = _queue_overlays(filler, data)

        assert count == 3
        filler.insert_text.assert_called_once_with("Guy", 200, 150, page_num=1, font_size=12)
        filler.insert_text_box.assert_called_once_with("Addr", 100, 200, 400, 260, page_num=0)
        filler.insert_image.assert_called_once_with("sig.png", 100, 500, 300, 550, page_num=0)

    def test_empty_data_queues_nothing(self):
        filler = _make_filler_mock()
        assert _queue_overlays(filler, {}) == 0
        filler.insert_text.assert_not_called()
        filler.insert_text_box.assert_not_called()
        filler.insert_image.assert_not_called()

    def test_missing_keys_exits(self, capsys):
        filler = _make_filler_mock()
        data = {"images": [{"path": "sig.png", "x0": 100}]}

        with pytest.raises(SystemExit):
            _queue_overlays(filler, data)

        err = capsys.readouterr().err
        assert "images[0]" in err
        assert "y0" in err

    def test_validates_before_queueing(self):
        """A bad entry in a later section must not leave earlier ones queued."""
        filler = _make_filler_mock()
        data = {
            "texts": [{"text": "Guy", "x": 200, "y": 150}],
            "images": [{"path": "sig.png"}],
        }

        with pytest.raises(SystemExit):
            _queue_overlays(filler, data)

        filler.insert_text.assert_not_called()


class TestDescribeOverlays:
    def test_describes_each_section(self):
        data = {
            "texts": [{"text": "Guy", "x": 200, "y": 150}],
            "boxes": [{"text": "Addr", "x0": 100, "y0": 200, "x1": 400, "y1": 260, "page": 1}],
            "images": [{"path": "sig.png", "x0": 100, "y0": 500, "x1": 300, "y1": 550}],
        }

        lines = _describe_overlays(data)

        assert lines == [
            'text "Guy" at (200, 150) on page 0',
            'text box "Addr" in (100, 200, 400, 260) on page 1',
            "image sig.png in (100, 500, 300, 550) on page 0",
        ]

    def test_empty_data(self):
        assert _describe_overlays({}) == []


# ---------------------------------------------------------------------------
# fill_command
# ---------------------------------------------------------------------------


class TestFillCommand:
    def _base_args(self, **overrides):
        """Return a Namespace with fill_command defaults, overridden by kwargs."""
        defaults = dict(
            input="form.pdf",
            output="/tmp/filled.pdf",
            values_json=None,
            field=None,
            checkbox=None,
            flatten=True,
            preserve_existing=False,
            validate=False,
            dry_run=False,
            verbose=False,
            no_auto_dates=False,
            use_defaults=False,
            strict=False,
        )
        defaults.update(overrides)
        return Namespace(**defaults)

    def test_missing_output_without_dry_run_exits(self, capsys):
        args = self._base_args(output=None, dry_run=False)
        with pytest.raises(SystemExit):
            fill_command(args)
        err = capsys.readouterr().err
        assert "-o/--output is required" in err

    def test_fill_with_field_args(self, capsys):
        filler = _make_filler_mock(
            pending={"fields": {"first_name": "Alice"}, "check": [], "uncheck": []},
        )
        args = self._base_args(field=["first_name=Alice"])

        with patch("pdfiller.cli.PDFFiller", return_value=filler):
            fill_command(args)

        filler.fill_field.assert_called_once_with("first_name", "Alice")
        filler.save.assert_called_once()
        out = capsys.readouterr().out
        assert "Done:" in out
        assert "1 fields" in out

    def test_fill_with_checkbox_args(self, capsys):
        filler = _make_filler_mock(
            pending={"fields": {}, "check": ["agree_terms"], "uncheck": []},
        )
        args = self._base_args(checkbox=["agree_terms"], field=None)

        with patch("pdfiller.cli.PDFFiller", return_value=filler):
            fill_command(args)

        filler.check_box.assert_called_once_with("agree_terms")
        out = capsys.readouterr().out
        assert "1 checkboxes" in out

    def test_fill_from_json(self, tmp_path, capsys):
        json_file = tmp_path / "vals.json"
        json_file.write_text(
            json.dumps(
                {
                    "fields": {"first_name": "Bob"},
                    "checkboxes": ["agree_terms"],
                }
            )
        )
        filler = _make_filler_mock(
            pending={"fields": {"first_name": "Bob"}, "check": ["agree_terms"], "uncheck": []},
        )
        args = self._base_args(values_json=json_file)

        with patch("pdfiller.cli.PDFFiller", return_value=filler):
            fill_command(args)

        filler.fill_fields.assert_called_once_with({"first_name": "Bob"})
        filler.check_box.assert_called_once_with("agree_terms")

    def test_bad_field_format_exits(self, capsys):
        filler = _make_filler_mock()
        args = self._base_args(field=["no_equals_sign"])

        with patch("pdfiller.cli.PDFFiller", return_value=filler), pytest.raises(SystemExit):
            fill_command(args)

        err = capsys.readouterr().err
        assert "Invalid field format" in err

    def test_dry_run_no_save(self, capsys):
        filler = _make_filler_mock(
            pending={"fields": {"first_name": "Alice"}, "check": [], "uncheck": []},
        )
        args = self._base_args(field=["first_name=Alice"], dry_run=True, output=None)

        with patch("pdfiller.cli.PDFFiller", return_value=filler):
            fill_command(args)

        filler.save.assert_not_called()
        out = capsys.readouterr().out
        assert "Dry run" in out
        assert "first_name = Alice" in out

    def test_dry_run_empty_fields(self, capsys):
        filler = _make_filler_mock(
            pending={"fields": {}, "check": [], "uncheck": []},
        )
        args = self._base_args(dry_run=True, output=None)

        with patch("pdfiller.cli.PDFFiller", return_value=filler):
            fill_command(args)

        out = capsys.readouterr().out
        assert "(no fields to fill)" in out

    def test_dry_run_shows_checkboxes(self, capsys):
        filler = _make_filler_mock(
            pending={"fields": {}, "check": ["agree_terms"], "uncheck": []},
        )
        args = self._base_args(checkbox=["agree_terms"], dry_run=True, output=None)

        with patch("pdfiller.cli.PDFFiller", return_value=filler):
            fill_command(args)

        out = capsys.readouterr().out
        assert "agree_terms = [checked]" in out

    def test_verbose_output(self, capsys):
        filler = _make_filler_mock(
            pending={"fields": {"first_name": "Alice"}, "check": ["agree_terms"], "uncheck": []},
        )
        args = self._base_args(
            field=["first_name=Alice"],
            checkbox=["agree_terms"],
            verbose=True,
        )

        with patch("pdfiller.cli.PDFFiller", return_value=filler):
            fill_command(args)

        out = capsys.readouterr().out
        assert "Fill plan" in out
        assert "first_name = Alice" in out
        assert "agree_terms [check]" in out
        assert "Auto-fill dates: enabled" in out

    def test_no_auto_dates_flag(self, capsys):
        filler = _make_filler_mock()
        filler.auto_fill_dates = False
        args = self._base_args(no_auto_dates=True, field=["first_name=X"], verbose=True)

        with patch("pdfiller.cli.PDFFiller", return_value=filler):
            fill_command(args)

        out = capsys.readouterr().out
        assert "Auto-fill dates: enabled" not in out

    def test_preserve_existing_flag(self, capsys):
        filler = _make_filler_mock()
        args = self._base_args(preserve_existing=True, field=["first_name=X"])

        with patch("pdfiller.cli.PDFFiller", return_value=filler):
            fill_command(args)

        filler.preserve_existing_fields.assert_called_once_with(True)

    def test_validate_exits_on_missing_fields(self, capsys):
        filler = _make_filler_mock()
        filler.validate_fields.return_value = {
            "first_name": True,
            "nonexistent": False,
        }
        args = self._base_args(
            field=["first_name=Alice", "nonexistent=Oops"],
            validate=True,
        )

        with patch("pdfiller.cli.PDFFiller", return_value=filler), pytest.raises(SystemExit) as e:
            fill_command(args)

        assert e.value.code == 1
        err = capsys.readouterr().err
        assert "Fields not found" in err
        assert "nonexistent" in err
        filler.save.assert_not_called()

    def test_validate_passes_when_fields_exist(self, capsys):
        filler = _make_filler_mock()
        filler.validate_fields.return_value = {"first_name": True}
        args = self._base_args(field=["first_name=Alice"], validate=True)

        with patch("pdfiller.cli.PDFFiller", return_value=filler):
            fill_command(args)

        filler.save.assert_called_once()

    def test_strict_passed_to_filler(self):
        filler = _make_filler_mock()
        args = self._base_args(field=["first_name=Alice"], strict=True)

        with patch("pdfiller.cli.PDFFiller", return_value=filler) as mock_cls:
            fill_command(args)

        assert mock_cls.call_args.kwargs["strict"] is True

    def test_use_defaults(self, capsys):
        filler = _make_filler_mock(
            fields=[
                {"name": "first_name", "type": "Text", "value": "", "page": 0},
                {"name": "email", "type": "Text", "value": "", "page": 0},
            ],
        )
        defaults_data = {"first_name": "DefaultGuy", "email": "guy@example.com"}
        args = self._base_args(use_defaults=True, dry_run=True, output=None)

        with patch("pdfiller.cli.PDFFiller", return_value=filler), patch(
            "pdfiller.cli.load_defaults", return_value={"personal": {"first_name": "DefaultGuy"}}
        ), patch("pdfiller.cli.flatten_defaults", return_value=defaults_data), patch(
            "pdfiller.cli.match_field_to_defaults", side_effect=lambda n, d: d.get(n)
        ):
            fill_command(args)

        # Should have called fill_field for each matched default
        assert filler.fill_field.call_count == 2

    def test_use_defaults_skips_list_matches(self, capsys):
        filler = _make_filler_mock(
            fields=[
                {"name": "email", "type": "Text", "value": "", "page": 0},
            ],
        )
        args = self._base_args(use_defaults=True, dry_run=True, output=None)

        def mock_match(name, defaults):
            return ["a@example.com", "b@example.com"]

        with patch("pdfiller.cli.PDFFiller", return_value=filler), patch(
            "pdfiller.cli.load_defaults", return_value={"personal": {}}
        ), patch(
            "pdfiller.cli.flatten_defaults",
            return_value={"email": ["a@example.com", "b@example.com"]},
        ), patch("pdfiller.cli.match_field_to_defaults", side_effect=mock_match):
            fill_command(args)

        # Should not call fill_field for list matches
        filler.fill_field.assert_not_called()

    def test_pdffiller_error_exits(self, capsys):
        filler = _make_filler_mock()
        filler.__enter__.side_effect = PDFFillerError("bad pdf")
        args = self._base_args(field=["first_name=X"])

        with patch("pdfiller.cli.PDFFiller", return_value=filler), pytest.raises(SystemExit):
            fill_command(args)

        err = capsys.readouterr().err
        assert "Error:" in err

    def test_field_overrides_json(self, tmp_path, capsys):
        """When both -j and -f are used, -f values override -j values."""
        json_file = tmp_path / "vals.json"
        json_file.write_text(
            json.dumps(
                {
                    "fields": {"first_name": "FromJSON"},
                    "checkboxes": [],
                }
            )
        )
        filler = _make_filler_mock(
            pending={"fields": {"first_name": "FromCLI"}, "check": [], "uncheck": []},
        )
        args = self._base_args(
            values_json=json_file,
            field=["first_name=FromCLI"],
        )

        with patch("pdfiller.cli.PDFFiller", return_value=filler):
            fill_command(args)

        # fill_fields is called first with JSON data, then fill_field with CLI override
        filler.fill_fields.assert_called_once_with({"first_name": "FromJSON"})
        filler.fill_field.assert_called_once_with("first_name", "FromCLI")

    def test_field_with_equals_in_value(self, capsys):
        """A field value containing '=' should be handled correctly."""
        filler = _make_filler_mock(
            pending={"fields": {"formula": "a=b"}, "check": [], "uncheck": []},
        )
        args = self._base_args(field=["formula=a=b"])

        with patch("pdfiller.cli.PDFFiller", return_value=filler):
            fill_command(args)

        filler.fill_field.assert_called_once_with("formula", "a=b")


# ---------------------------------------------------------------------------
# inspect_command
# ---------------------------------------------------------------------------


class TestInspectCommand:
    def test_single_page_output(self, capsys):
        filler = _make_filler_mock(page_count=1)
        args = Namespace(input="form.pdf")

        with patch("pdfiller.cli.PDFFiller", return_value=filler):
            inspect_command(args)

        out = capsys.readouterr().out
        assert "Page 0: 612x792" in out
        assert "Sample text" in out

    def test_multi_page_output(self, capsys):
        layouts = {
            0: {
                "width": 612,
                "height": 792,
                "blocks": [
                    {"text": "Page zero", "bbox": {"x0": 10, "y0": 20, "x1": 200, "y1": 40}},
                ],
            },
            1: {"width": 612, "height": 792, "blocks": []},
        }
        filler = _make_filler_mock(page_count=2, layouts=layouts)
        args = Namespace(input="form.pdf")

        with patch("pdfiller.cli.PDFFiller", return_value=filler):
            inspect_command(args)

        out = capsys.readouterr().out
        assert "Page 0:" in out
        assert "Page zero" in out
        assert "Page 1:" in out
        assert "(no text blocks)" in out

    def test_long_text_truncated(self, capsys):
        long_text = "A" * 100
        filler = _make_filler_mock(page_count=1)
        filler.get_page_layout.return_value = {
            "width": 612,
            "height": 792,
            "blocks": [
                {"text": long_text, "bbox": {"x0": 0, "y0": 0, "x1": 500, "y1": 20}},
            ],
        }
        args = Namespace(input="form.pdf")

        with patch("pdfiller.cli.PDFFiller", return_value=filler):
            inspect_command(args)

        out = capsys.readouterr().out
        assert "..." in out
        # Should be truncated to 77 chars + "..."
        assert long_text not in out

    def test_pdffiller_error_exits(self, capsys):
        filler = _make_filler_mock()
        filler.__enter__.side_effect = PDFFillerError("cannot open")
        args = Namespace(input="bad.pdf")

        with patch("pdfiller.cli.PDFFiller", return_value=filler), pytest.raises(SystemExit):
            inspect_command(args)

        err = capsys.readouterr().err
        assert "Error:" in err


# ---------------------------------------------------------------------------
# export_command
# ---------------------------------------------------------------------------


class TestExportCommand:
    def test_export_to_stdout(self, capsys):
        fields = [
            {"name": "first_name", "type": "Text", "value": "Alice", "page": 0},
            {"name": "agree", "type": "CheckBox", "value": "Yes", "page": 0},
            {"name": "empty_field", "type": "Text", "value": "", "page": 0},
            {"name": "unchecked", "type": "CheckBox", "value": "Off", "page": 0},
        ]
        filler = _make_filler_mock(fields=fields)
        args = Namespace(input="form.pdf", output=None)

        with patch("pdfiller.cli.PDFFiller", return_value=filler):
            export_command(args)

        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["fields"] == {"first_name": "Alice"}
        assert "agree" in data["checkboxes"]
        # Empty fields and "Off" checkboxes should be excluded
        assert "empty_field" not in data["fields"]
        assert "unchecked" not in data["checkboxes"]

    def test_export_to_file(self, tmp_path, capsys):
        fields = [
            {"name": "email", "type": "Text", "value": "test@example.com", "page": 0},
        ]
        filler = _make_filler_mock(fields=fields)
        out_file = str(tmp_path / "export.json")
        args = Namespace(input="form.pdf", output=out_file)

        with patch("pdfiller.cli.PDFFiller", return_value=filler):
            export_command(args)

        stdout = capsys.readouterr().out
        assert f"Saved: {out_file}" in stdout
        data = json.loads((tmp_path / "export.json").read_text())
        assert data["fields"]["email"] == "test@example.com"

    def test_export_empty_pdf(self, capsys):
        fields = [
            {"name": "first_name", "type": "Text", "value": "", "page": 0},
        ]
        filler = _make_filler_mock(fields=fields)
        args = Namespace(input="form.pdf", output=None)

        with patch("pdfiller.cli.PDFFiller", return_value=filler):
            export_command(args)

        data = json.loads(capsys.readouterr().out)
        assert data["fields"] == {}
        assert data["checkboxes"] == []

    def test_export_excludes_push_buttons(self, capsys):
        """Push buttons are actions, not state - excluded from export (C7)."""
        fields = [
            {"name": "submit_btn", "type": "Button", "value": "Yes", "page": 0},
            {"name": "agree", "type": "CheckBox", "value": "On", "page": 0},
        ]
        filler = _make_filler_mock(fields=fields)
        args = Namespace(input="form.pdf", output=None)

        with patch("pdfiller.cli.PDFFiller", return_value=filler):
            export_command(args)

        data = json.loads(capsys.readouterr().out)
        assert "submit_btn" not in data["checkboxes"]
        assert "submit_btn" not in data["fields"]
        assert "agree" in data["checkboxes"]

    def test_pdffiller_error_exits(self, capsys):
        filler = _make_filler_mock()
        filler.__enter__.side_effect = PDFFillerError("bad pdf")
        args = Namespace(input="bad.pdf", output=None)

        with patch("pdfiller.cli.PDFFiller", return_value=filler), pytest.raises(SystemExit):
            export_command(args)


# ---------------------------------------------------------------------------
# template_command
# ---------------------------------------------------------------------------


class TestTemplateCommand:
    def test_generates_template(self, tmp_path, capsys):
        filler = _make_filler_mock()
        out_file = str(tmp_path / "template.json")
        args = Namespace(input="form.pdf", output=out_file)

        with patch("pdfiller.cli.PDFFiller", return_value=filler):
            template_command(args)

        data = json.loads((tmp_path / "template.json").read_text())
        assert "fields" in data
        assert "checkboxes" in data
        assert data["fields"]["first_name"] == ""
        assert data["fields"]["last_name"] == ""
        assert "agree_terms" in data["checkboxes"]
        # Checkboxes should not appear in fields
        assert "agree_terms" not in data["fields"]

    def test_excludes_push_buttons(self, tmp_path, capsys):
        """Push buttons are actions, not state - excluded from template (C7)."""
        fields = SAMPLE_FIELDS + [{"name": "submit_btn", "type": "Button", "value": "", "page": 0}]
        filler = _make_filler_mock(fields=fields)
        out_file = str(tmp_path / "template.json")
        args = Namespace(input="form.pdf", output=out_file)

        with patch("pdfiller.cli.PDFFiller", return_value=filler):
            template_command(args)

        data = json.loads((tmp_path / "template.json").read_text())
        assert "submit_btn" not in data["checkboxes"]
        assert "submit_btn" not in data["fields"]

    def test_prints_usage_hint(self, tmp_path, capsys):
        filler = _make_filler_mock()
        out_file = str(tmp_path / "template.json")
        args = Namespace(input="form.pdf", output=out_file)

        with patch("pdfiller.cli.PDFFiller", return_value=filler):
            template_command(args)

        out = capsys.readouterr().out
        assert f"Saved: {out_file}" in out
        assert "pdfiller fill" in out

    def test_pdffiller_error_exits(self, capsys):
        filler = _make_filler_mock()
        filler.__enter__.side_effect = PDFFillerError("bad pdf")
        args = Namespace(input="bad.pdf", output="/tmp/template.json")

        with patch("pdfiller.cli.PDFFiller", return_value=filler), pytest.raises(SystemExit):
            template_command(args)


# ---------------------------------------------------------------------------
# defaults_command
# ---------------------------------------------------------------------------


class TestDefaultsCommandShow:
    def test_show_empty(self, capsys):
        args = Namespace(defaults_action="show")
        with patch("pdfiller.cli.load_defaults", return_value={}):
            defaults_command(args)
        out = capsys.readouterr().out
        assert "No defaults stored" in out

    def test_show_existing(self, capsys):
        data = {"personal": {"first_name": "Guy"}}
        args = Namespace(defaults_action="show")
        with patch("pdfiller.cli.load_defaults", return_value=data):
            defaults_command(args)
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed["personal"]["first_name"] == "Guy"


class TestDefaultsCommandGet:
    def test_get_string_value(self, capsys):
        data = {"personal": {"first_name": "Guy"}}
        args = Namespace(defaults_action="get", key="personal.first_name")
        with patch("pdfiller.cli.load_defaults", return_value=data):
            defaults_command(args)
        out = capsys.readouterr().out
        assert out.strip() == "Guy"

    def test_get_dict_value(self, capsys):
        data = {"personal": {"first_name": "Guy", "last_name": "Test"}}
        args = Namespace(defaults_action="get", key="personal")
        with patch("pdfiller.cli.load_defaults", return_value=data):
            defaults_command(args)
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed == {"first_name": "Guy", "last_name": "Test"}

    def test_get_list_value(self, capsys):
        data = {"personal": {"phone": ["555-1234", "555-5678"]}}
        args = Namespace(defaults_action="get", key="personal.phone")
        with patch("pdfiller.cli.load_defaults", return_value=data):
            defaults_command(args)
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed == ["555-1234", "555-5678"]

    def test_get_missing_key_exits(self, capsys):
        data = {"personal": {"first_name": "Guy"}}
        args = Namespace(defaults_action="get", key="personal.email")
        with patch("pdfiller.cli.load_defaults", return_value=data), pytest.raises(SystemExit):
            defaults_command(args)
        err = capsys.readouterr().err
        assert "Not found" in err


class TestDefaultsCommandSet:
    def test_set_new_value(self, capsys):
        data = {}
        args = Namespace(defaults_action="set", key="personal.first_name", value="Guy")
        with patch("pdfiller.cli.load_defaults", return_value=data), patch(
            "pdfiller.cli.save_defaults"
        ) as mock_save:
            defaults_command(args)
        mock_save.assert_called_once()
        saved = mock_save.call_args[0][0]
        assert saved["personal"]["first_name"] == "Guy"
        out = capsys.readouterr().out
        assert "Set personal.first_name = Guy" in out

    def test_set_overwrites_existing(self, capsys):
        data = {"personal": {"first_name": "Old"}}
        args = Namespace(defaults_action="set", key="personal.first_name", value="New")
        with patch("pdfiller.cli.load_defaults", return_value=data), patch(
            "pdfiller.cli.save_defaults"
        ) as mock_save:
            defaults_command(args)
        saved = mock_save.call_args[0][0]
        assert saved["personal"]["first_name"] == "New"


class TestDefaultsCommandRemove:
    def test_remove_existing(self, capsys):
        data = {"personal": {"first_name": "Guy", "last_name": "Test"}}
        args = Namespace(defaults_action="remove", key="personal.first_name")
        with patch("pdfiller.cli.load_defaults", return_value=data), patch(
            "pdfiller.cli.save_defaults"
        ) as mock_save:
            defaults_command(args)
        mock_save.assert_called_once()
        saved = mock_save.call_args[0][0]
        assert "first_name" not in saved["personal"]
        assert saved["personal"]["last_name"] == "Test"
        out = capsys.readouterr().out
        assert "Removed:" in out

    def test_remove_missing_exits(self, capsys):
        data = {"personal": {"first_name": "Guy"}}
        args = Namespace(defaults_action="remove", key="personal.email")
        with patch("pdfiller.cli.load_defaults", return_value=data), patch(
            "pdfiller.cli.save_defaults"
        ), pytest.raises(SystemExit):
            defaults_command(args)
        err = capsys.readouterr().err
        assert "Not found" in err


class TestDefaultsCommandErrors:
    def test_invalid_defaults_schema_exits_cleanly(self, capsys):
        """A corrupt-schema defaults file must produce a clean error, not a
        traceback (regression: defaults_command lacked error handling)."""
        args = Namespace(defaults_action="show")
        with patch(
            "pdfiller.cli.load_defaults", side_effect=DefaultsValidationError("bad schema")
        ), pytest.raises(SystemExit):
            defaults_command(args)
        err = capsys.readouterr().err
        assert "Error" in err

    def test_save_failure_exits_cleanly(self, capsys):
        """A validation error while saving must exit cleanly."""
        args = Namespace(defaults_action="set", key="personal.x", value="y")
        with patch("pdfiller.cli.load_defaults", return_value={}), patch(
            "pdfiller.cli.save_defaults", side_effect=DefaultsValidationError("bad")
        ), pytest.raises(SystemExit):
            defaults_command(args)
        err = capsys.readouterr().err
        assert "Error" in err


# ---------------------------------------------------------------------------
# Argument parsing via main()
# ---------------------------------------------------------------------------


class TestMainArgParsing:
    """Test that main() dispatches to the right command functions."""

    def test_no_command_exits(self):
        with patch("sys.argv", ["pdfiller"]), pytest.raises(SystemExit):
            from pdfiller.cli import main

            main()

    def test_list_dispatches(self):
        with patch("sys.argv", ["pdfiller", "list", "-i", "form.pdf"]), patch(
            "pdfiller.cli.list_fields_command"
        ) as mock_cmd:
            from pdfiller.cli import main

            main()
        mock_cmd.assert_called_once()
        args = mock_cmd.call_args[0][0]
        assert args.input == "form.pdf"
        assert args.command == "list"

    def test_fill_dispatches(self):
        with patch("sys.argv", ["pdfiller", "fill", "-i", "form.pdf", "-o", "out.pdf"]), patch(
            "pdfiller.cli.fill_command"
        ) as mock_cmd:
            from pdfiller.cli import main

            main()
        mock_cmd.assert_called_once()
        args = mock_cmd.call_args[0][0]
        assert args.input == "form.pdf"
        assert args.output == "out.pdf"

    def test_inspect_dispatches(self):
        with patch("sys.argv", ["pdfiller", "inspect", "-i", "form.pdf"]), patch(
            "pdfiller.cli.inspect_command"
        ) as mock_cmd:
            from pdfiller.cli import main

            main()
        mock_cmd.assert_called_once()

    def test_export_dispatches(self):
        with patch("sys.argv", ["pdfiller", "export", "-i", "form.pdf"]), patch(
            "pdfiller.cli.export_command"
        ) as mock_cmd:
            from pdfiller.cli import main

            main()
        mock_cmd.assert_called_once()

    def test_template_dispatches(self):
        with patch("sys.argv", ["pdfiller", "template", "-i", "form.pdf", "-o", "tpl.json"]), patch(
            "pdfiller.cli.template_command"
        ) as mock_cmd:
            from pdfiller.cli import main

            main()
        mock_cmd.assert_called_once()

    def test_defaults_show_dispatches(self):
        with patch("sys.argv", ["pdfiller", "defaults", "show"]), patch(
            "pdfiller.cli.defaults_command"
        ) as mock_cmd:
            from pdfiller.cli import main

            main()
        mock_cmd.assert_called_once()
        args = mock_cmd.call_args[0][0]
        assert args.defaults_action == "show"

    def test_defaults_no_action_exits(self):
        with patch("sys.argv", ["pdfiller", "defaults"]), pytest.raises(SystemExit):
            from pdfiller.cli import main

            main()

    def test_fill_parses_multiple_fields(self):
        with patch(
            "sys.argv",
            [
                "pdfiller",
                "fill",
                "-i",
                "f.pdf",
                "-o",
                "o.pdf",
                "-f",
                "a=1",
                "-f",
                "b=2",
                "-c",
                "check1",
            ],
        ), patch("pdfiller.cli.fill_command") as mock_cmd:
            from pdfiller.cli import main

            main()
        args = mock_cmd.call_args[0][0]
        assert args.field == ["a=1", "b=2"]
        assert args.checkbox == ["check1"]

    def test_fill_dry_run_flag(self):
        with patch(
            "sys.argv",
            [
                "pdfiller",
                "fill",
                "-i",
                "f.pdf",
                "--dry-run",
                "-f",
                "a=1",
            ],
        ), patch("pdfiller.cli.fill_command") as mock_cmd:
            from pdfiller.cli import main

            main()
        args = mock_cmd.call_args[0][0]
        assert args.dry_run is True
        assert args.output is None  # Not required for dry run

    def test_list_format_flag(self):
        with patch("sys.argv", ["pdfiller", "list", "-i", "f.pdf", "--format", "csv"]), patch(
            "pdfiller.cli.list_fields_command"
        ) as mock_cmd:
            from pdfiller.cli import main

            main()
        args = mock_cmd.call_args[0][0]
        assert args.format == "csv"
