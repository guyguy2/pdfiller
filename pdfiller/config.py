"""
User configuration for PDFiller CLI defaults.

Loads settings from ~/.pdfiller/config.toml (or $PDFILLER_CONFIG).
Missing or invalid files yield empty defaults; CLI flags still override.
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:  # pragma: no cover - dev env should have tomli on 3.9/3.10
        tomllib = None  # type: ignore[assignment]

# Default suffix when fill is run without -o: form.pdf -> form_filled.pdf
DEFAULT_OUTPUT_SUFFIX = "_filled"


@dataclass(frozen=True)
class Config:
    """Resolved user config. None fields mean "use built-in CLI default"."""

    date_format: str | None = None
    flatten: bool | None = None
    auto_fill_dates: bool | None = None
    output_suffix: str = DEFAULT_OUTPUT_SUFFIX


def _config_path() -> Path:
    env = os.environ.get("PDFILLER_CONFIG")
    if env:
        return Path(env)
    return Path.home() / ".pdfiller" / "config.toml"


def load_config(path: str | Path | None = None) -> Config:
    """Load config from TOML.

    Returns a Config with only recognized keys applied. Missing file, empty
    file, or unreadable/invalid TOML yields Config() defaults (with a warning
    for parse errors). Unknown keys are ignored with a warning.
    """
    p = Path(path) if path is not None else _config_path()
    if not p.exists():
        return Config()

    if tomllib is None:
        logger.warning(
            "Ignoring config file %s: TOML support requires Python 3.11+ or the 'tomli' package",
            p,
        )
        return Config()

    try:
        with open(p, "rb") as f:
            raw = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as e:
        logger.warning("Ignoring invalid config file %s: %s", p, e)
        return Config()

    if not isinstance(raw, dict):
        logger.warning("Ignoring config file %s: root must be a table", p)
        return Config()

    return _parse_config(raw, source=p)


def _parse_config(raw: dict[str, Any], *, source: Path) -> Config:
    """Validate and extract known keys from a raw TOML table."""
    known = {"date_format", "flatten", "auto_fill_dates", "output_suffix"}
    unknown = set(raw) - known
    if unknown:
        logger.warning(
            "Ignoring unknown config keys in %s: %s",
            source,
            ", ".join(sorted(unknown)),
        )

    date_format: str | None = None
    if "date_format" in raw:
        val = raw["date_format"]
        if isinstance(val, str) and val:
            date_format = val
        else:
            logger.warning("Ignoring invalid date_format in %s: expected non-empty string", source)

    flatten: bool | None = None
    if "flatten" in raw:
        val = raw["flatten"]
        if isinstance(val, bool):
            flatten = val
        else:
            logger.warning("Ignoring invalid flatten in %s: expected boolean", source)

    auto_fill_dates: bool | None = None
    if "auto_fill_dates" in raw:
        val = raw["auto_fill_dates"]
        if isinstance(val, bool):
            auto_fill_dates = val
        else:
            logger.warning("Ignoring invalid auto_fill_dates in %s: expected boolean", source)

    output_suffix = DEFAULT_OUTPUT_SUFFIX
    if "output_suffix" in raw:
        val = raw["output_suffix"]
        if isinstance(val, str):
            output_suffix = val
        else:
            logger.warning("Ignoring invalid output_suffix in %s: expected string", source)

    return Config(
        date_format=date_format,
        flatten=flatten,
        auto_fill_dates=auto_fill_dates,
        output_suffix=output_suffix,
    )


def default_output_path(input_pdf: str | Path, suffix: str = DEFAULT_OUTPUT_SUFFIX) -> Path:
    """Build form_filled.pdf style path next to the input PDF."""
    p = Path(input_pdf)
    return p.with_name(f"{p.stem}{suffix}{p.suffix}")
