"""
Tests for pdfiller.cli module.
"""

import json
import subprocess
import sys

import pytest


def run_cli(*args):
    """Run the pdfiller CLI and return the result."""
    result = subprocess.run(
        [sys.executable, "-m", "pdfiller.cli", *args],
        capture_output=True,
        text=True,
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
        result = run_cli("list", "-i", str(fillable_pdf), "-o", str(out))
        assert result.returncode == 0
        data = json.loads(out.read_text())
        names = [f["name"] for f in data]
        assert "first_name" in names

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


class TestNoCommand:
    def test_no_command_shows_help(self):
        result = run_cli()
        assert result.returncode != 0
