"""Tests for pdfiller.config (F6 user config.toml)."""

import subprocess
import sys
from pathlib import Path

from pdfiller.config import (
    DEFAULT_OUTPUT_SUFFIX,
    Config,
    default_output_path,
    load_config,
)


def _run_cli(*args, env=None):
    """Run the pdfiller CLI in a subprocess (inherits monkeypatched env)."""
    run_env = None
    if env is not None:
        import os

        run_env = os.environ.copy()
        run_env.update(env)
    return subprocess.run(
        [sys.executable, "-m", "pdfiller.cli", *args],
        capture_output=True,
        text=True,
        env=run_env,
    )


class TestDefaultOutputPath:
    def test_appends_suffix_before_extension(self):
        assert default_output_path("form.pdf") == Path("form_filled.pdf")
        assert default_output_path(Path("/tmp/a/scan.PDF"), "_out") == Path("/tmp/a/scan_out.PDF")

    def test_custom_suffix(self):
        assert default_output_path("x.pdf", "-done") == Path("x-done.pdf")


class TestLoadConfig:
    def test_missing_file_returns_defaults(self, tmp_path):
        cfg = load_config(tmp_path / "nope.toml")
        assert cfg == Config()
        assert cfg.output_suffix == DEFAULT_OUTPUT_SUFFIX

    def test_empty_file_returns_defaults(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text("")
        assert load_config(path) == Config()

    def test_reads_all_known_keys(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text(
            'date_format = "%Y-%m-%d"\n'
            "flatten = false\n"
            "auto_fill_dates = false\n"
            'output_suffix = "-filled"\n'
        )
        cfg = load_config(path)
        assert cfg.date_format == "%Y-%m-%d"
        assert cfg.flatten is False
        assert cfg.auto_fill_dates is False
        assert cfg.output_suffix == "-filled"

    def test_partial_keys(self, tmp_path):
        path = tmp_path / "config.toml"
        path.write_text('date_format = "%d/%m/%Y"\n')
        cfg = load_config(path)
        assert cfg.date_format == "%d/%m/%Y"
        assert cfg.flatten is None
        assert cfg.auto_fill_dates is None
        assert cfg.output_suffix == DEFAULT_OUTPUT_SUFFIX

    def test_invalid_toml_warns_and_returns_defaults(self, tmp_path, caplog):
        path = tmp_path / "config.toml"
        path.write_text("date_format = [unterminated\n")
        with caplog.at_level("WARNING", logger="pdfiller.config"):
            cfg = load_config(path)
        assert cfg == Config()
        assert "invalid config" in caplog.text.lower() or "Ignoring" in caplog.text

    def test_unknown_keys_ignored_with_warning(self, tmp_path, caplog):
        path = tmp_path / "config.toml"
        path.write_text('date_format = "%Y-%m-%d"\nunknown_key = 1\n')
        with caplog.at_level("WARNING", logger="pdfiller.config"):
            cfg = load_config(path)
        assert cfg.date_format == "%Y-%m-%d"
        assert "unknown_key" in caplog.text

    def test_invalid_types_ignored(self, tmp_path, caplog):
        path = tmp_path / "config.toml"
        path.write_text(
            'date_format = 12\nflatten = "yes"\nauto_fill_dates = "no"\noutput_suffix = 3\n'
        )
        with caplog.at_level("WARNING", logger="pdfiller.config"):
            cfg = load_config(path)
        assert cfg == Config()
        assert "Ignoring" in caplog.text

    def test_env_pdfiller_config(self, tmp_path, monkeypatch):
        path = tmp_path / "custom.toml"
        path.write_text("flatten = false\n")
        monkeypatch.setenv("PDFILLER_CONFIG", str(path))
        cfg = load_config()
        assert cfg.flatten is False

    def test_exported_from_package(self):
        from pdfiller import Config as C
        from pdfiller import default_output_path as dop
        from pdfiller import load_config as lc

        assert C is Config
        assert lc is load_config
        assert dop is default_output_path


class TestDateFormatPrecedence:
    """flag > config > _meta > built-in (None)."""

    def test_config_used_when_no_flag(self, fillable_pdf_with_dates, tmp_path, monkeypatch):
        import datetime

        import pymupdf

        config_path = tmp_path / "config.toml"
        config_path.write_text('date_format = "%Y-%m-%d"\n')
        monkeypatch.setenv("PDFILLER_CONFIG", str(config_path))
        # Ensure defaults do not override via _meta
        defaults_file = tmp_path / "defaults.json"
        defaults_file.write_text("{}")
        monkeypatch.setenv("PDFILLER_DEFAULTS", str(defaults_file))

        out = tmp_path / "iso.pdf"
        result = _run_cli(
            "fill",
            "-i",
            str(fillable_pdf_with_dates),
            "-o",
            str(out),
            "--no-flatten",
        )
        assert result.returncode == 0, result.stderr
        doc = pymupdf.open(str(out))
        values = {w.field_name: w.field_value for page in doc for w in page.widgets()}
        doc.close()
        assert values["sign_date"] == datetime.date.today().strftime("%Y-%m-%d")

    def test_flag_overrides_config(self, fillable_pdf_with_dates, tmp_path, monkeypatch):
        import datetime

        import pymupdf

        config_path = tmp_path / "config.toml"
        config_path.write_text('date_format = "%d/%m/%Y"\n')
        monkeypatch.setenv("PDFILLER_CONFIG", str(config_path))
        defaults_file = tmp_path / "defaults.json"
        defaults_file.write_text("{}")
        monkeypatch.setenv("PDFILLER_DEFAULTS", str(defaults_file))

        out = tmp_path / "flag.pdf"
        result = _run_cli(
            "fill",
            "-i",
            str(fillable_pdf_with_dates),
            "-o",
            str(out),
            "--no-flatten",
            "--date-format",
            "%Y-%m-%d",
        )
        assert result.returncode == 0, result.stderr
        doc = pymupdf.open(str(out))
        values = {w.field_name: w.field_value for page in doc for w in page.widgets()}
        doc.close()
        assert values["sign_date"] == datetime.date.today().strftime("%Y-%m-%d")

    def test_config_overrides_meta(self, fillable_pdf_with_dates, tmp_path, monkeypatch):
        import datetime
        import json

        import pymupdf

        config_path = tmp_path / "config.toml"
        config_path.write_text('date_format = "%Y-%m-%d"\n')
        monkeypatch.setenv("PDFILLER_CONFIG", str(config_path))
        defaults_file = tmp_path / "defaults.json"
        defaults_file.write_text(json.dumps({"_meta": {"date_format": "%d/%m/%Y"}}))
        monkeypatch.setenv("PDFILLER_DEFAULTS", str(defaults_file))

        out = tmp_path / "cfg_over_meta.pdf"
        result = _run_cli(
            "fill",
            "-i",
            str(fillable_pdf_with_dates),
            "-o",
            str(out),
            "--no-flatten",
        )
        assert result.returncode == 0, result.stderr
        doc = pymupdf.open(str(out))
        values = {w.field_name: w.field_value for page in doc for w in page.widgets()}
        doc.close()
        assert values["sign_date"] == datetime.date.today().strftime("%Y-%m-%d")


class TestConfigFlattenAndSuffix:
    def test_config_flatten_false(self, fillable_pdf, tmp_path, monkeypatch):
        import pymupdf

        config_path = tmp_path / "config.toml"
        config_path.write_text("flatten = false\n")
        monkeypatch.setenv("PDFILLER_CONFIG", str(config_path))

        # Put input in tmp so default output is writable if used
        src = tmp_path / "in.pdf"
        src.write_bytes(Path(fillable_pdf).read_bytes())
        out = tmp_path / "out.pdf"
        result = _run_cli(
            "fill",
            "-i",
            str(src),
            "-o",
            str(out),
            "-f",
            "first_name=Alice",
        )
        assert result.returncode == 0, result.stderr
        # Unflattened form still has widgets
        doc = pymupdf.open(str(out))
        widgets = [w for page in doc for w in (page.widgets() or [])]
        doc.close()
        assert len(widgets) > 0

    def test_output_suffix_from_config(self, fillable_pdf, tmp_path, monkeypatch):
        config_path = tmp_path / "config.toml"
        config_path.write_text('output_suffix = "_done"\nflatten = false\n')
        monkeypatch.setenv("PDFILLER_CONFIG", str(config_path))

        src = tmp_path / "myform.pdf"
        src.write_bytes(Path(fillable_pdf).read_bytes())
        result = _run_cli(
            "fill",
            "-i",
            str(src),
            "-f",
            "first_name=Alice",
        )
        assert result.returncode == 0, result.stderr
        expected = tmp_path / "myform_done.pdf"
        assert expected.exists()
        assert "myform_done.pdf" in result.stdout
