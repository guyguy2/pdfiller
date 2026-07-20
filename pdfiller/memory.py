"""
Defaults/memory system for auto-filling common PDF field values across sessions.

Stores user defaults in ~/.pdfiller/defaults.json (or $PDFILLER_DEFAULTS).
"""

import json
import logging
import os
import re
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

from .exceptions import DefaultsValidationError

logger = logging.getLogger(__name__)

# Type for matcher functions: (field_name, defaults_dict) -> match or None
MatcherFunc = Callable[
    [str, Dict[str, Union[str, List[str]]]],
    Optional[Union[str, List[str]]],
]

# Registry of named matchers, ordered by registration order
_matchers: OrderedDict[str, MatcherFunc] = OrderedDict()


def _default_path() -> Path:
    env = os.environ.get("PDFILLER_DEFAULTS")
    if env:
        return Path(env)
    return Path.home() / ".pdfiller" / "defaults.json"


# -- Schema validation (6.2) --


def validate_defaults(data: Dict[str, Any]) -> None:
    """Validate the structure of a defaults dict.

    Expected structure:
      - Top-level keys are category strings (e.g. "personal", "work")
      - Values are dicts mapping field names to strings or lists of strings
      - Special keys "_meta" (dict) and "_aliases" inside categories are allowed

    Raises DefaultsValidationError if the structure is invalid.
    """
    if not isinstance(data, dict):
        raise DefaultsValidationError(f"Defaults must be a dict, got {type(data).__name__}")

    for key, value in data.items():
        if key == "_meta":
            if not isinstance(value, dict):
                raise DefaultsValidationError(f"_meta must be a dict, got {type(value).__name__}")
            continue

        # Top-level string values are allowed (flat defaults)
        if isinstance(value, str):
            continue

        # Top-level list values are allowed if all elements are strings
        if isinstance(value, list):
            _validate_list_value(key, value)
            continue

        # Category dicts
        if isinstance(value, dict):
            _validate_category(key, value)
            continue

        raise DefaultsValidationError(
            f"Category '{key}' must be a dict, string, or list of strings, "
            f"got {type(value).__name__}"
        )


def _validate_list_value(key: str, value: list) -> None:
    """Validate that a list value contains only strings."""
    for i, item in enumerate(value):
        if not isinstance(item, str):
            raise DefaultsValidationError(
                f"List value for '{key}' must contain only strings, "
                f"got {type(item).__name__} at index {i}"
            )


def _validate_category(category: str, fields: dict) -> None:
    """Validate a category dict within defaults."""
    for field_name, field_value in fields.items():
        # _aliases is a special key: dict mapping alias -> canonical name
        if field_name == "_aliases":
            if not isinstance(field_value, dict):
                raise DefaultsValidationError(
                    f"_aliases in '{category}' must be a dict, got {type(field_value).__name__}"
                )
            for alias, target in field_value.items():
                if not isinstance(alias, str) or not isinstance(target, str):
                    raise DefaultsValidationError(
                        f"_aliases in '{category}' must map strings to strings, "
                        f"got {type(alias).__name__} -> {type(target).__name__}"
                    )
            continue

        if isinstance(field_value, str):
            continue

        if isinstance(field_value, list):
            _validate_list_value(f"{category}.{field_name}", field_value)
            continue

        raise DefaultsValidationError(
            f"Field '{field_name}' in '{category}' must be a string or list of strings, "
            f"got {type(field_value).__name__}"
        )


# -- Load / save --


def load_defaults(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load defaults from JSON file.

    Returns empty dict if file is missing or contains invalid JSON.
    Raises DefaultsValidationError if JSON is valid but the schema is wrong.
    """
    p = Path(path) if path else _default_path()
    if not p.exists():
        return {}
    try:
        with open(p) as f:
            data = json.load(f)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning("Ignoring invalid JSON in defaults file %s: %s", p, e)
        return {}
    validate_defaults(data)
    return data


def save_defaults(data: Dict[str, Any], path: Optional[Path] = None) -> Path:
    """Save defaults to JSON file. Creates parent dirs and adds _meta.updated timestamp.

    Raises DefaultsValidationError if data has an invalid structure.
    """
    validate_defaults(data)

    p = Path(path) if path else _default_path()
    p.parent.mkdir(parents=True, exist_ok=True)

    # Copy before injecting _meta so we don't mutate the caller's dict
    # (or its nested _meta) as a side effect of saving.
    data = dict(data)
    meta = dict(data.get("_meta", {}))
    meta["updated"] = datetime.now().isoformat(timespec="seconds")
    data["_meta"] = meta

    with open(p, "w") as f:
        json.dump(data, f, indent=2)
    return p


# -- Flatten --


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

    Skips the _meta key, _aliases keys, and any non-string leaf values.
    List values are supported: single-element lists collapse to strings,
    multi-element all-string lists are preserved as lists.
    """
    flat: Dict[str, Union[str, List[str]]] = {}
    for key, value in data.items():
        if key == "_meta":
            continue
        if isinstance(value, dict):
            for inner_key, inner_value in value.items():
                if inner_key == "_aliases":
                    continue
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


# -- Normalization --


def _normalize(name: str) -> str:
    """Normalize a field name for fuzzy matching.

    Collapses First Name / first_name / FirstName / first-name all to 'firstname'.
    """
    # Insert space before uppercase letters in camelCase/PascalCase
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
    # Replace non-alphanumeric with nothing
    s = re.sub(r"[^a-zA-Z0-9]", "", s)
    return s.lower()


# -- Plugin/extension matcher system (6.3) --


def register_matcher(name: str, func: MatcherFunc) -> None:
    """Register a named field matcher.

    Matchers are tried in registration order by match_field_to_defaults().
    A matcher function receives (field_name, defaults_dict) and returns
    the matched value or None.

    Registering a name that already exists replaces the previous matcher.
    """
    _matchers[name] = func


def unregister_matcher(name: str) -> None:
    """Remove a registered matcher by name. No-op if not found."""
    _matchers.pop(name, None)


def list_matchers() -> List[str]:
    """Return the names of all registered matchers in order."""
    return list(_matchers.keys())


def clear_matchers() -> None:
    """Remove all registered matchers, including built-in ones."""
    _matchers.clear()


# -- Built-in matchers --


def _exact_matcher(
    field_name: str, defaults: Dict[str, Union[str, List[str]]]
) -> Optional[Union[str, List[str]]]:
    """Match by exact field name."""
    if field_name in defaults:
        return defaults[field_name]
    return None


def _normalized_matcher(
    field_name: str, defaults: Dict[str, Union[str, List[str]]]
) -> Optional[Union[str, List[str]]]:
    """Match by normalized field name (case/separator insensitive)."""
    norm_field = _normalize(field_name)
    for key, value in defaults.items():
        if _normalize(key) == norm_field:
            return value
    return None


# -- Alias support (7.1) --


def _collect_aliases(data: Dict[str, Any]) -> Dict[str, str]:
    """Collect all _aliases from all categories into a flat mapping.

    Returns a dict mapping alias -> canonical field name.
    """
    aliases: Dict[str, str] = {}
    for key, value in data.items():
        if key == "_meta":
            continue
        if isinstance(value, dict) and "_aliases" in value:
            for alias, canonical in value["_aliases"].items():
                aliases[alias] = canonical
    return aliases


def build_alias_matcher(
    raw_defaults: Dict[str, Any],
) -> MatcherFunc:
    """Build a matcher function that resolves field aliases.

    Takes the raw (unflattened) defaults dict and returns a matcher that:
    1. Checks if field_name is an alias (exact match)
    2. Checks if field_name normalizes to an alias
    3. Looks up the canonical field name in the flattened defaults
    """
    aliases = _collect_aliases(raw_defaults)
    # Also build a normalized alias map for fuzzy alias matching
    norm_aliases: Dict[str, str] = {_normalize(a): c for a, c in aliases.items()}

    def _alias_matcher(
        field_name: str, defaults: Dict[str, Union[str, List[str]]]
    ) -> Optional[Union[str, List[str]]]:
        # Exact alias match
        canonical = aliases.get(field_name)
        if canonical is None:
            # Normalized alias match
            canonical = norm_aliases.get(_normalize(field_name))
        if canonical is None:
            return None
        # Look up the canonical name in flattened defaults
        return defaults.get(canonical)

    return _alias_matcher


# -- Main matching function --


def match_field_to_defaults(
    field_name: str, defaults: Dict[str, Union[str, List[str]]]
) -> Optional[Union[str, List[str]]]:
    """Match a PDF field name to a stored default value.

    Tries all registered matchers in order and returns the first match.
    Built-in matchers (exact, normalized) are registered at module load.
    """
    for matcher_func in _matchers.values():
        result = matcher_func(field_name, defaults)
        if result is not None:
            return result
    return None


# -- Register default matchers on import --


def _register_default_matchers() -> None:
    """Register the built-in exact and normalized matchers."""
    register_matcher("exact", _exact_matcher)
    register_matcher("normalized", _normalized_matcher)


_register_default_matchers()
