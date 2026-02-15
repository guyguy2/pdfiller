"""
Tests for pdfiller.memory module.
"""

import json
import pytest

from pdfiller.memory import (
    _normalize,
    flatten_defaults,
    load_defaults,
    match_field_to_defaults,
    save_defaults,
)


class TestNormalize:
    def test_snake_case(self):
        assert _normalize("first_name") == "firstname"

    def test_camel_case(self):
        assert _normalize("firstName") == "firstname"

    def test_pascal_case(self):
        assert _normalize("FirstName") == "firstname"

    def test_kebab_case(self):
        assert _normalize("first-name") == "firstname"

    def test_space_separated(self):
        assert _normalize("First Name") == "firstname"

    def test_all_forms_match(self):
        forms = ["first_name", "firstName", "FirstName", "first-name", "First Name"]
        normalized = [_normalize(f) for f in forms]
        assert len(set(normalized)) == 1


class TestFlattenDefaults:
    def test_nested(self):
        data = {
            "_meta": {"updated": "2026-01-01T00:00:00"},
            "personal": {"first_name": "Guy", "email": "guy@example.com"},
            "medical": {"physician_name": "Dr. Smith"},
        }
        flat = flatten_defaults(data)
        assert flat == {
            "first_name": "Guy",
            "email": "guy@example.com",
            "physician_name": "Dr. Smith",
        }

    def test_skips_meta(self):
        data = {"_meta": {"updated": "2026-01-01T00:00:00"}}
        assert flatten_defaults(data) == {}

    def test_empty(self):
        assert flatten_defaults({}) == {}

    def test_top_level_strings(self):
        data = {"nickname": "G"}
        assert flatten_defaults(data) == {"nickname": "G"}

    def test_skips_non_string_leaves(self):
        data = {"numbers": {"count": 42}}
        assert flatten_defaults(data) == {}

    def test_list_single_element(self):
        data = {"personal": {"phone": ["555-1234"]}}
        assert flatten_defaults(data) == {"phone": "555-1234"}

    def test_list_multiple_elements(self):
        data = {"personal": {"phone": ["555-1234", "555-5678"]}}
        assert flatten_defaults(data) == {"phone": ["555-1234", "555-5678"]}

    def test_mixed_strings_and_lists(self):
        data = {"personal": {"name": "Guy", "phone": ["555-1234", "555-5678"]}}
        flat = flatten_defaults(data)
        assert flat == {"name": "Guy", "phone": ["555-1234", "555-5678"]}

    def test_skips_empty_list(self):
        data = {"personal": {"phone": []}}
        assert flatten_defaults(data) == {}

    def test_skips_list_with_non_strings(self):
        data = {"personal": {"codes": [1, 2, 3]}}
        assert flatten_defaults(data) == {}

    def test_top_level_list(self):
        data = {"nicknames": ["G", "Guy-o"]}
        assert flatten_defaults(data) == {"nicknames": ["G", "Guy-o"]}


class TestMatchFieldToDefaults:
    def test_exact_match(self):
        defaults = {"first_name": "Guy"}
        assert match_field_to_defaults("first_name", defaults) == "Guy"

    def test_normalized_match(self):
        defaults = {"first_name": "Guy"}
        assert match_field_to_defaults("FirstName", defaults) == "Guy"
        assert match_field_to_defaults("first-name", defaults) == "Guy"
        assert match_field_to_defaults("firstName", defaults) == "Guy"

    def test_no_match(self):
        defaults = {"first_name": "Guy"}
        assert match_field_to_defaults("phone", defaults) is None

    def test_empty_defaults(self):
        assert match_field_to_defaults("anything", {}) is None

    def test_match_returns_list(self):
        defaults = {"phone": ["555-1234", "555-5678"]}
        assert match_field_to_defaults("phone", defaults) == ["555-1234", "555-5678"]

    def test_normalized_match_returns_list(self):
        defaults = {"first_name": ["Guy", "Gregory"]}
        assert match_field_to_defaults("FirstName", defaults) == ["Guy", "Gregory"]


class TestDefaultsEnvVar:
    def test_env_var_overrides_default_path(self, tmp_path, monkeypatch):
        custom_path = tmp_path / "custom" / "defaults.json"
        monkeypatch.setenv("PDFILLER_DEFAULTS", str(custom_path))
        data = {"personal": {"first_name": "EnvTest"}}
        save_defaults(data)
        assert custom_path.exists()
        loaded = load_defaults()
        assert loaded["personal"]["first_name"] == "EnvTest"

    def test_load_missing_env_var_path(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PDFILLER_DEFAULTS", str(tmp_path / "nope.json"))
        assert load_defaults() == {}


class TestLoadSaveRoundTrip:
    def test_save_and_load(self, tmp_path):
        path = tmp_path / "defaults.json"
        data = {
            "personal": {"first_name": "Guy", "last_name": "Test"},
        }
        save_defaults(data, path)
        loaded = load_defaults(path)

        assert loaded["personal"]["first_name"] == "Guy"
        assert loaded["personal"]["last_name"] == "Test"
        assert "_meta" in loaded
        assert "updated" in loaded["_meta"]

    def test_load_missing_file(self, tmp_path):
        path = tmp_path / "nonexistent.json"
        assert load_defaults(path) == {}

    def test_save_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "deep" / "nested" / "defaults.json"
        save_defaults({"key": "val"}, path)
        assert path.exists()
        loaded = load_defaults(path)
        assert loaded["key"] == "val"

    def test_round_trip_with_lists(self, tmp_path):
        path = tmp_path / "defaults.json"
        data = {
            "personal": {
                "name": "Guy",
                "phone": ["555-1234", "555-5678"],
            },
        }
        save_defaults(data, path)
        loaded = load_defaults(path)
        flat = flatten_defaults(loaded)
        assert flat["name"] == "Guy"
        assert flat["phone"] == ["555-1234", "555-5678"]

    def test_meta_timestamp_updated(self, tmp_path):
        path = tmp_path / "defaults.json"
        save_defaults({"a": "1"}, path)
        loaded = load_defaults(path)
        ts = loaded["_meta"]["updated"]
        # Should be a valid ISO timestamp
        assert "T" in ts
