"""
Defaults/memory system for auto-filling common PDF field values across sessions.

Stores user defaults in ~/.pdfiller/defaults.json (or $PDFILLER_DEFAULTS).
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


def _default_path() -> Path:
    env = os.environ.get("PDFILLER_DEFAULTS")
    if env:
        return Path(env)
    return Path.home() / ".pdfiller" / "defaults.json"


def load_defaults(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load defaults from JSON file. Returns empty dict if file is missing."""
    p = Path(path) if path else _default_path()
    if not p.exists():
        return {}
    with open(p) as f:
        return json.load(f)


def save_defaults(data: Dict[str, Any], path: Optional[Path] = None) -> Path:
    """Save defaults to JSON file. Creates parent dirs and adds _meta.updated timestamp."""
    p = Path(path) if path else _default_path()
    p.parent.mkdir(parents=True, exist_ok=True)

    data.setdefault("_meta", {})
    data["_meta"]["updated"] = datetime.now().isoformat(timespec="seconds")

    with open(p, "w") as f:
        json.dump(data, f, indent=2)
    return p


def _coerce_list(value: list) -> Optional[Union[str, List[str]]]:
    """Coerce a list value for flattening.

    Single-element string lists collapse to a plain string.
    Multi-element all-string lists are kept as-is.
    Empty lists and lists containing non-strings are skipped.
    """
    if not value:
        return None
    if not all(isinstance(v, str) for v in value):
        return None
    if len(value) == 1:
        return value[0]
    return value


def flatten_defaults(data: Dict[str, Any]) -> Dict[str, Union[str, List[str]]]:
    """Flatten nested defaults to a flat {field_name: value} dict.

    Skips the _meta key and any non-string leaf values.
    List values are supported: single-element lists collapse to strings,
    multi-element all-string lists are preserved as lists.
    """
    flat: Dict[str, Union[str, List[str]]] = {}
    for key, value in data.items():
        if key == "_meta":
            continue
        if isinstance(value, dict):
            for inner_key, inner_value in value.items():
                if isinstance(inner_value, str):
                    flat[inner_key] = inner_value
                elif isinstance(inner_value, list):
                    coerced = _coerce_list(inner_value)
                    if coerced is not None:
                        flat[inner_key] = coerced
        elif isinstance(value, str):
            flat[key] = value
        elif isinstance(value, list):
            coerced = _coerce_list(value)
            if coerced is not None:
                flat[key] = coerced
    return flat


def _normalize(name: str) -> str:
    """Normalize a field name for fuzzy matching.

    Collapses First Name / first_name / FirstName / first-name all to 'firstname'.
    """
    # Insert space before uppercase letters in camelCase/PascalCase
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
    # Replace non-alphanumeric with nothing
    s = re.sub(r"[^a-zA-Z0-9]", "", s)
    return s.lower()


def match_field_to_defaults(
    field_name: str, defaults: Dict[str, Union[str, List[str]]]
) -> Optional[Union[str, List[str]]]:
    """Match a PDF field name to a stored default value.

    Tries exact match first, then normalized match.
    Returns the matched value or None.
    """
    # Exact match
    if field_name in defaults:
        return defaults[field_name]

    # Normalized match
    norm_field = _normalize(field_name)
    for key, value in defaults.items():
        if _normalize(key) == norm_field:
            return value

    return None
