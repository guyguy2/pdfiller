"""
Tests for pdfiller.cli module.
"""

import csv
import io
import json
import subprocess
import sys



def run_cli(*args, env=None):
    """Run the pdfiller CLI and return the result."""
    run_env = None
    if env:
        import os
        run_env = os.environ.copy()
        run_env.update(env)
    result = subprocess.run(
        [sys.executable, "-m", "pdfiller.cli", *args],
        capture_output=True,
        text=True,
        env=run_env,
    )
    return result


class TestListCommand:
    def test_list_fields(self, fillable_pdf):
        result = run_cli("list", "-i", str(fillable_pdf))
        assert result.returncode == 0
        assert "first_name" in result.stdout
        assert "last_name" in result.stdout

    def test_list_fields_json_output(self, fillable_pdf, tmp_path):
        out = tmp_path / "fields.json"
        result = run_cli("list", "-i", str(fillable_pdf), "--format", "json", "-o", str(out))
        assert result.returncode == 0
        data = json.loads(out.read_text())
        names = [f["name"] for f in data]
        assert "first_name" in names

    def test_list_format_json_stdout(self, fillable_pdf):
        result = run_cli("list", "-i", str(fillable_pdf), "--format", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        names = [f["name"] for f in data]
        assert "first_name" in names

    def test_list_format_csv_stdout(self, fillable_pdf):
        result = run_cli("list", "-i", str(fillable_pdf), "--format", "csv")
        assert result.returncode == 0
        reader = csv.reader(io.StringIO(result.stdout))
        rows = list(reader)
        header = rows[0]
        assert header == ["name", "type", "value", "page"]
        names = [row[0] for row in rows[1:]]
        assert "first_name" in names

    def test_list_format_csv_to_file(self, fillable_pdf, tmp_path):
        out = tmp_path / "fields.csv"
        result = run_cli("list", "-i", str(fillable_pdf), "--format", "csv", "-o", str(out))
        assert result.returncode == 0
        reader = csv.reader(io.StringIO(out.read_text()))
        rows = list(reader)
        assert rows[0] == ["name", "type", "value", "page"]
        assert len(rows) > 1

    def test_list_format_table_to_file(self, fillable_pdf, tmp_path):
        out = tmp_path / "fields.txt"
        result = run_cli("list", "-i", str(fillable_pdf), "--format", "table", "-o", str(out))
        assert result.returncode == 0
        content = out.read_text()
        assert "first_name" in content
        assert "Type:" in content

    def test_list_missing_pdf(self, tmp_path):
        result = run_cli("list", "-i", str(tmp_path / "nope.pdf"))
        assert result.returncode != 0
        assert "Error" in result.stderr


class TestFillCommand:
    def test_fill_with_field_args(self, fillable_pdf, tmp_path):
        out = tmp_path / "filled.pdf"
        result = run_cli(
            "fill", "-i", str(fillable_pdf),
            "-o", str(out),
            "-f", "first_name=Alice",
        )
        assert result.returncode == 0
        assert "Done:" in result.stdout
        assert out.exists()

    def test_fill_from_json(self, fillable_pdf, tmp_path):
        values = tmp_path / "values.json"
        values.write_text(json.dumps({
            "fields": {"first_name": "Bob"},
            "checkboxes": ["agree_terms"],
        }))
        out = tmp_path / "filled.pdf"
        result = run_cli(
            "fill", "-i", str(fillable_pdf),
            "-o", str(out),
            "-j", str(values),
        )
        assert result.returncode == 0
        assert out.exists()

    def test_fill_bad_field_format(self, fillable_pdf, tmp_path):
        out = tmp_path / "filled.pdf"
        result = run_cli(
            "fill", "-i", str(fillable_pdf),
            "-o", str(out),
            "-f", "no_equals_sign",
        )
        assert result.returncode != 0
        assert "Invalid field format" in result.stderr

    def test_fill_bad_json(self, fillable_pdf, tmp_path):
        bad_json = tmp_path / "bad.json"
        bad_json.write_text("not valid json{{{")
        out = tmp_path / "filled.pdf"
        result = run_cli(
            "fill", "-i", str(fillable_pdf),
            "-o", str(out),
            "-j", str(bad_json),
        )
        assert result.returncode != 0
        assert "Invalid JSON" in result.stderr

    def test_fill_missing_output(self, fillable_pdf):
        result = run_cli(
            "fill", "-i", str(fillable_pdf),
            "-f", "first_name=Test",
        )
        assert result.returncode != 0

    def test_dry_run(self, fillable_pdf):
        result = run_cli(
            "fill", "-i", str(fillable_pdf),
            "-f", "first_name=Alice",
            "--dry-run",
        )
        assert result.returncode == 0
        assert "Dry run" in result.stdout
        assert "first_name = Alice" in result.stdout

    def test_verbose_shows_fields(self, fillable_pdf, tmp_path):
        out = tmp_path / "filled.pdf"
        result = run_cli(
            "fill", "-i", str(fillable_pdf),
            "-o", str(out),
            "-f", "first_name=Alice",
            "-v",
        )
        assert result.returncode == 0
        assert "Fill plan" in result.stdout
        assert "first_name = Alice" in result.stdout
        assert "Done:" in result.stdout

    def test_verbose_shows_checkboxes(self, fillable_pdf, tmp_path):
        out = tmp_path / "filled.pdf"
        result = run_cli(
            "fill", "-i", str(fillable_pdf),
            "-o", str(out),
            "-c", "agree_terms",
            "-v",
        )
        assert result.returncode == 0
        assert "agree_terms [check]" in result.stdout

    def test_verbose_shows_auto_date_note(self, fillable_pdf, tmp_path):
        out = tmp_path / "filled.pdf"
        result = run_cli(
            "fill", "-i", str(fillable_pdf),
            "-o", str(out),
            "-f", "first_name=Alice",
            "--verbose",
        )
        assert result.returncode == 0
        assert "Auto-fill dates: enabled" in result.stdout


class TestTemplateCommand:
    def test_generate_template(self, fillable_pdf, tmp_path):
        out = tmp_path / "template.json"
        result = run_cli("template", "-i", str(fillable_pdf), "-o", str(out))
        assert result.returncode == 0
        data = json.loads(out.read_text())
        assert "fields" in data
        assert "checkboxes" in data
        assert "first_name" in data["fields"]
        assert "agree_terms" in data["checkboxes"]


class TestInspectCommand:
    def test_inspect_non_fillable(self, non_fillable_pdf):
        result = run_cli("inspect", "-i", str(non_fillable_pdf))
        assert result.returncode == 0
        assert "Page 0:" in result.stdout
        assert "612x792" in result.stdout

    def test_inspect_fillable(self, fillable_pdf):
        result = run_cli("inspect", "-i", str(fillable_pdf))
        assert result.returncode == 0
        assert "Page 0:" in result.stdout


class TestExportCommand:
    def test_export_to_stdout(self, fillable_pdf, tmp_path):
        # Fill without flattening so fields are preserved
        out = tmp_path / "filled.pdf"
        run_cli("fill", "-i", str(fillable_pdf), "-o", str(out),
                "-f", "first_name=Alice", "--no-flatten")
        result = run_cli("export", "-i", str(out))
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["fields"]["first_name"] == "Alice"

    def test_export_to_file(self, fillable_pdf, tmp_path):
        out = tmp_path / "filled.pdf"
        run_cli("fill", "-i", str(fillable_pdf), "-o", str(out),
                "-f", "first_name=Bob", "--no-flatten")
        export_out = tmp_path / "exported.json"
        result = run_cli("export", "-i", str(out), "-o", str(export_out))
        assert result.returncode == 0
        data = json.loads(export_out.read_text())
        assert data["fields"]["first_name"] == "Bob"

    def test_export_empty_pdf(self, fillable_pdf):
        result = run_cli("export", "-i", str(fillable_pdf))
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["fields"] == {}


class TestNestedHelpers:
    """Unit tests for dot-notation dict helpers used by defaults commands."""

    def test_get_nested_simple(self):
        from pdfiller.cli import _get_nested
        data = {"personal": {"first_name": "Guy"}}
        assert _get_nested(data, "personal.first_name") == "Guy"

    def test_get_nested_top_level(self):
        from pdfiller.cli import _get_nested
        data = {"nickname": "G"}
        assert _get_nested(data, "nickname") == "G"

    def test_get_nested_missing(self):
        from pdfiller.cli import _get_nested
        data = {"personal": {"first_name": "Guy"}}
        assert _get_nested(data, "personal.email") is None

    def test_get_nested_missing_intermediate(self):
        from pdfiller.cli import _get_nested
        data = {"personal": {"first_name": "Guy"}}
        assert _get_nested(data, "medical.physician") is None

    def test_set_nested_creates_path(self):
        from pdfiller.cli import _set_nested
        data = {}
        _set_nested(data, "personal.first_name", "Guy")
        assert data == {"personal": {"first_name": "Guy"}}

    def test_set_nested_top_level(self):
        from pdfiller.cli import _set_nested
        data = {}
        _set_nested(data, "nickname", "G")
        assert data == {"nickname": "G"}

    def test_set_nested_overwrites(self):
        from pdfiller.cli import _set_nested
        data = {"personal": {"first_name": "Old"}}
        _set_nested(data, "personal.first_name", "New")
        assert data["personal"]["first_name"] == "New"

    def test_remove_nested_existing(self):
        from pdfiller.cli import _remove_nested
        data = {"personal": {"first_name": "Guy", "last_name": "Test"}}
        assert _remove_nested(data, "personal.first_name") is True
        assert "first_name" not in data["personal"]
        assert data["personal"]["last_name"] == "Test"

    def test_remove_nested_missing(self):
        from pdfiller.cli import _remove_nested
        data = {"personal": {"first_name": "Guy"}}
        assert _remove_nested(data, "personal.email") is False

    def test_remove_nested_top_level(self):
        from pdfiller.cli import _remove_nested
        data = {"nickname": "G", "other": "val"}
        assert _remove_nested(data, "nickname") is True
        assert "nickname" not in data


class TestDefaultsShow:
    def test_show_empty(self, tmp_path):
        defaults_file = tmp_path / "defaults.json"
        env = {"PDFILLER_DEFAULTS": str(defaults_file)}
        result = run_cli("defaults", "show", env=env)
        assert result.returncode == 0
        assert "No defaults stored" in result.stdout

    def test_show_existing(self, tmp_path):
        defaults_file = tmp_path / "defaults.json"
        defaults_file.write_text(json.dumps({
            "personal": {"first_name": "Guy"},
            "_meta": {"updated": "2026-01-01T00:00:00"},
        }))
        env = {"PDFILLER_DEFAULTS": str(defaults_file)}
        result = run_cli("defaults", "show", env=env)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["personal"]["first_name"] == "Guy"


class TestDefaultsGet:
    def test_get_nested_value(self, tmp_path):
        defaults_file = tmp_path / "defaults.json"
        defaults_file.write_text(json.dumps({
            "personal": {"first_name": "Guy", "phone": ["555-1234", "555-5678"]},
        }))
        env = {"PDFILLER_DEFAULTS": str(defaults_file)}
        result = run_cli("defaults", "get", "personal.first_name", env=env)
        assert result.returncode == 0
        assert result.stdout.strip() == "Guy"

    def test_get_dict_value(self, tmp_path):
        defaults_file = tmp_path / "defaults.json"
        defaults_file.write_text(json.dumps({
            "personal": {"first_name": "Guy", "last_name": "Test"},
        }))
        env = {"PDFILLER_DEFAULTS": str(defaults_file)}
        result = run_cli("defaults", "get", "personal", env=env)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["first_name"] == "Guy"

    def test_get_list_value(self, tmp_path):
        defaults_file = tmp_path / "defaults.json"
        defaults_file.write_text(json.dumps({
            "personal": {"phone": ["555-1234", "555-5678"]},
        }))
        env = {"PDFILLER_DEFAULTS": str(defaults_file)}
        result = run_cli("defaults", "get", "personal.phone", env=env)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data == ["555-1234", "555-5678"]

    def test_get_missing_key(self, tmp_path):
        defaults_file = tmp_path / "defaults.json"
        defaults_file.write_text(json.dumps({"personal": {"first_name": "Guy"}}))
        env = {"PDFILLER_DEFAULTS": str(defaults_file)}
        result = run_cli("defaults", "get", "personal.email", env=env)
        assert result.returncode != 0
        assert "Not found" in result.stderr

    def test_get_top_level_key(self, tmp_path):
        defaults_file = tmp_path / "defaults.json"
        defaults_file.write_text(json.dumps({"nickname": "G"}))
        env = {"PDFILLER_DEFAULTS": str(defaults_file)}
        result = run_cli("defaults", "get", "nickname", env=env)
        assert result.returncode == 0
        assert result.stdout.strip() == "G"


class TestDefaultsSet:
    def test_set_new_value(self, tmp_path):
        defaults_file = tmp_path / "defaults.json"
        env = {"PDFILLER_DEFAULTS": str(defaults_file)}
        result = run_cli("defaults", "set", "personal.first_name", "Guy", env=env)
        assert result.returncode == 0
        assert "Set personal.first_name = Guy" in result.stdout
        # Verify the file was created with the right content
        data = json.loads(defaults_file.read_text())
        assert data["personal"]["first_name"] == "Guy"

    def test_set_updates_existing(self, tmp_path):
        defaults_file = tmp_path / "defaults.json"
        defaults_file.write_text(json.dumps({
            "personal": {"first_name": "Old"},
        }))
        env = {"PDFILLER_DEFAULTS": str(defaults_file)}
        result = run_cli("defaults", "set", "personal.first_name", "New", env=env)
        assert result.returncode == 0
        data = json.loads(defaults_file.read_text())
        assert data["personal"]["first_name"] == "New"

    def test_set_top_level_key(self, tmp_path):
        defaults_file = tmp_path / "defaults.json"
        env = {"PDFILLER_DEFAULTS": str(defaults_file)}
        result = run_cli("defaults", "set", "nickname", "G", env=env)
        assert result.returncode == 0
        data = json.loads(defaults_file.read_text())
        assert data["nickname"] == "G"

    def test_set_creates_intermediate_keys(self, tmp_path):
        defaults_file = tmp_path / "defaults.json"
        env = {"PDFILLER_DEFAULTS": str(defaults_file)}
        result = run_cli("defaults", "set", "medical.physician_name", "Dr. Smith", env=env)
        assert result.returncode == 0
        data = json.loads(defaults_file.read_text())
        assert data["medical"]["physician_name"] == "Dr. Smith"


class TestDefaultsRemove:
    def test_remove_existing_key(self, tmp_path):
        defaults_file = tmp_path / "defaults.json"
        defaults_file.write_text(json.dumps({
            "personal": {"first_name": "Guy", "last_name": "Test"},
        }))
        env = {"PDFILLER_DEFAULTS": str(defaults_file)}
        result = run_cli("defaults", "remove", "personal.first_name", env=env)
        assert result.returncode == 0
        assert "Removed" in result.stdout
        data = json.loads(defaults_file.read_text())
        assert "first_name" not in data["personal"]
        assert data["personal"]["last_name"] == "Test"

    def test_remove_missing_key(self, tmp_path):
        defaults_file = tmp_path / "defaults.json"
        defaults_file.write_text(json.dumps({"personal": {"first_name": "Guy"}}))
        env = {"PDFILLER_DEFAULTS": str(defaults_file)}
        result = run_cli("defaults", "remove", "personal.email", env=env)
        assert result.returncode != 0
        assert "Not found" in result.stderr

    def test_remove_top_level_key(self, tmp_path):
        defaults_file = tmp_path / "defaults.json"
        defaults_file.write_text(json.dumps({"nickname": "G", "other": "val"}))
        env = {"PDFILLER_DEFAULTS": str(defaults_file)}
        result = run_cli("defaults", "remove", "nickname", env=env)
        assert result.returncode == 0
        data = json.loads(defaults_file.read_text())
        assert "nickname" not in data
        assert data["other"] == "val"


class TestDefaultsNoAction:
    def test_defaults_no_action_shows_help(self):
        result = run_cli("defaults")
        assert result.returncode != 0


class TestFillWithDefaults:
    def test_fill_uses_defaults(self, fillable_pdf, tmp_path):
        defaults_file = tmp_path / "defaults.json"
        defaults_file.write_text(json.dumps({
            "personal": {"first_name": "DefaultGuy", "email": "guy@example.com"},
        }))
        env = {"PDFILLER_DEFAULTS": str(defaults_file)}
        result = run_cli(
            "fill", "-i", str(fillable_pdf),
            "-d", "--dry-run",
            env=env,
        )
        assert result.returncode == 0
        assert "first_name = DefaultGuy" in result.stdout
        assert "email = guy@example.com" in result.stdout

    def test_fill_field_overrides_default(self, fillable_pdf, tmp_path):
        defaults_file = tmp_path / "defaults.json"
        defaults_file.write_text(json.dumps({
            "personal": {"first_name": "DefaultGuy"},
        }))
        env = {"PDFILLER_DEFAULTS": str(defaults_file)}
        result = run_cli(
            "fill", "-i", str(fillable_pdf),
            "-d", "-f", "first_name=Override",
            "--dry-run",
            env=env,
        )
        assert result.returncode == 0
        # The -f override should take precedence over the default
        assert "first_name = Override" in result.stdout

    def test_fill_defaults_skips_list_values(self, fillable_pdf, tmp_path):
        defaults_file = tmp_path / "defaults.json"
        defaults_file.write_text(json.dumps({
            "personal": {
                "first_name": "Guy",
                "email": ["a@example.com", "b@example.com"],
            },
        }))
        env = {"PDFILLER_DEFAULTS": str(defaults_file)}
        result = run_cli(
            "fill", "-i", str(fillable_pdf),
            "-d", "--dry-run",
            env=env,
        )
        assert result.returncode == 0
        assert "first_name = Guy" in result.stdout
        # email has multiple values - should be skipped
        assert "email" not in result.stdout


class TestBatchCommand:
    def test_batch_fills_multiple_pdfs(self, fillable_pdf, tmp_path):
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("first_name,last_name,email\nAlice,Smith,a@x.com\nBob,Jones,b@x.com\n")
        out_dir = tmp_path / "filled"
        result = run_cli(
            "batch", "-i", str(fillable_pdf),
            "--csv", str(csv_file),
            "--output-dir", str(out_dir),
        )
        assert result.returncode == 0
        assert "Filled 2 PDFs from data.csv" in result.stdout
        assert (out_dir / "fillable_filled_001.pdf").exists()
        assert (out_dir / "fillable_filled_002.pdf").exists()

    def test_batch_creates_output_dir(self, fillable_pdf, tmp_path):
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("first_name\nAlice\n")
        out_dir = tmp_path / "new_dir" / "nested"
        assert not out_dir.exists()
        result = run_cli(
            "batch", "-i", str(fillable_pdf),
            "--csv", str(csv_file),
            "--output-dir", str(out_dir),
        )
        assert result.returncode == 0
        assert out_dir.exists()
        assert (out_dir / "fillable_filled_001.pdf").exists()

    def test_batch_default_output_dir(self, fillable_pdf, tmp_path, monkeypatch):
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("first_name\nAlice\n")
        monkeypatch.chdir(tmp_path)
        result = run_cli(
            "batch", "-i", str(fillable_pdf),
            "--csv", str(csv_file),
        )
        assert result.returncode == 0
        assert (tmp_path / "fillable_filled_001.pdf").exists()

    def test_batch_missing_csv(self, fillable_pdf, tmp_path):
        result = run_cli(
            "batch", "-i", str(fillable_pdf),
            "--csv", str(tmp_path / "nope.csv"),
            "--output-dir", str(tmp_path),
        )
        assert result.returncode != 0
        assert "CSV file not found" in result.stderr

    def test_batch_empty_csv(self, fillable_pdf, tmp_path):
        csv_file = tmp_path / "empty.csv"
        csv_file.write_text("first_name,last_name\n")
        result = run_cli(
            "batch", "-i", str(fillable_pdf),
            "--csv", str(csv_file),
            "--output-dir", str(tmp_path),
        )
        assert result.returncode != 0
        assert "no data rows" in result.stderr

    def test_batch_no_flatten(self, fillable_pdf, tmp_path):
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("first_name\nAlice\n")
        out_dir = tmp_path / "filled"
        result = run_cli(
            "batch", "-i", str(fillable_pdf),
            "--csv", str(csv_file),
            "--output-dir", str(out_dir),
            "--no-flatten",
        )
        assert result.returncode == 0
        assert (out_dir / "fillable_filled_001.pdf").exists()
        # Verify fields are preserved (not flattened)
        import fitz
        doc = fitz.open(str(out_dir / "fillable_filled_001.pdf"))
        page = doc[0]
        has_widgets = any(True for _ in page.widgets())
        doc.close()
        assert has_widgets

    def test_batch_reports_row_errors(self, fillable_pdf, tmp_path):
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("first_name\nAlice\nBob\n")
        out_dir = tmp_path / "filled"
        out_dir.mkdir()
        # Create the first output file as a read-only file to cause a write error
        blocker = out_dir / "fillable_filled_001.pdf"
        blocker.write_bytes(b"blocked")
        blocker.chmod(0o444)
        try:
            result = run_cli(
                "batch", "-i", str(fillable_pdf),
                "--csv", str(csv_file),
                "--output-dir", str(out_dir),
            )
            # Row 1 should fail, row 2 should succeed
            assert result.returncode != 0
            assert "Filled 1 PDFs" in result.stdout
            assert "Errors (1):" in result.stderr
            assert "Row 1:" in result.stderr
        finally:
            blocker.chmod(0o644)

    def test_batch_sequential_numbering(self, fillable_pdf, tmp_path):
        csv_file = tmp_path / "data.csv"
        rows = "first_name\n" + "\n".join(f"Person{i}" for i in range(1, 12)) + "\n"
        csv_file.write_text(rows)
        out_dir = tmp_path / "filled"
        result = run_cli(
            "batch", "-i", str(fillable_pdf),
            "--csv", str(csv_file),
            "--output-dir", str(out_dir),
        )
        assert result.returncode == 0
        assert "Filled 11 PDFs" in result.stdout
        assert (out_dir / "fillable_filled_001.pdf").exists()
        assert (out_dir / "fillable_filled_010.pdf").exists()
        assert (out_dir / "fillable_filled_011.pdf").exists()

    def test_batch_field_values_applied(self, fillable_pdf, tmp_path):
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("first_name,last_name\nAlice,Smith\nBob,Jones\n")
        out_dir = tmp_path / "filled"
        result = run_cli(
            "batch", "-i", str(fillable_pdf),
            "--csv", str(csv_file),
            "--output-dir", str(out_dir),
            "--no-flatten",
        )
        assert result.returncode == 0
        # Verify actual field values in the output PDFs
        from pdfiller.core import PDFFiller
        with PDFFiller(out_dir / "fillable_filled_001.pdf") as f:
            assert f.get_field_value("first_name") == "Alice"
            assert f.get_field_value("last_name") == "Smith"
        with PDFFiller(out_dir / "fillable_filled_002.pdf") as f:
            assert f.get_field_value("first_name") == "Bob"
            assert f.get_field_value("last_name") == "Jones"


class TestNoCommand:
    def test_no_command_shows_help(self):
        result = run_cli()
        assert result.returncode != 0
