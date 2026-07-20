"""
Tests for pdfiller.memory module.
"""

import os
import stat
from unittest import mock

import pytest

from pdfiller.exceptions import DefaultsValidationError
from pdfiller.memory import (
    _normalize,
    _register_default_matchers,
    build_alias_matcher,
    clear_matchers,
    flatten_defaults,
    list_matchers,
    load_defaults,
    match_field_to_defaults,
    register_matcher,
    reset_matchers,
    save_defaults,
    unregister_matcher,
    validate_defaults,
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

    def test_skips_aliases_key(self):
        data = {
            "personal": {
                "first_name": "Guy",
                "_aliases": {"fname": "first_name"},
            }
        }
        flat = flatten_defaults(data)
        assert flat == {"first_name": "Guy"}
        assert "_aliases" not in flat


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


class TestLoadCorruptJson:
    def test_corrupt_json_returns_empty(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("not valid json{{{")
        assert load_defaults(path) == {}

    def test_empty_file_returns_empty(self, tmp_path):
        path = tmp_path / "empty.json"
        path.write_text("")
        assert load_defaults(path) == {}

    def test_corrupt_json_logs_warning(self, tmp_path, caplog):
        path = tmp_path / "bad.json"
        path.write_text("not valid json{{{")
        with caplog.at_level("WARNING"):
            assert load_defaults(path) == {}
        assert any("invalid json" in r.message.lower() for r in caplog.records)


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

    def test_save_does_not_mutate_caller_dict(self, tmp_path):
        """save_defaults must not inject _meta into the caller's dict."""
        path = tmp_path / "defaults.json"
        data = {"personal": {"first_name": "Guy"}}
        save_defaults(data, path)
        assert "_meta" not in data

    def test_save_does_not_mutate_caller_meta(self, tmp_path):
        """An existing _meta passed in must not be mutated in place."""
        path = tmp_path / "defaults.json"
        meta = {"note": "keep"}
        data = {"_meta": meta, "personal": {"first_name": "Guy"}}
        save_defaults(data, path)
        assert "updated" not in meta
        assert meta == {"note": "keep"}


class TestAtomicSave:
    def test_failed_write_leaves_original_intact(self, tmp_path):
        path = tmp_path / "defaults.json"
        save_defaults({"personal": {"first_name": "Guy"}}, path)

        with mock.patch(
            "pdfiller.memory.json.dump", side_effect=OSError("disk full")
        ), pytest.raises(OSError):
            save_defaults({"personal": {"first_name": "Other"}}, path)

        loaded = load_defaults(path)
        assert loaded["personal"]["first_name"] == "Guy"

    def test_failed_write_leaves_no_temp_file(self, tmp_path):
        path = tmp_path / "defaults.json"
        with mock.patch(
            "pdfiller.memory.json.dump", side_effect=OSError("disk full")
        ), pytest.raises(OSError):
            save_defaults({"a": "1"}, path)
        assert list(tmp_path.iterdir()) == []


@pytest.mark.skipif(os.name != "posix", reason="POSIX file permissions")
class TestSavePermissions:
    def test_file_mode_0600(self, tmp_path):
        path = tmp_path / "defaults.json"
        save_defaults({"a": "1"}, path)
        assert stat.S_IMODE(path.stat().st_mode) == 0o600

    def test_created_dir_mode_0700(self, tmp_path):
        path = tmp_path / "newdir" / "defaults.json"
        save_defaults({"a": "1"}, path)
        assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700

    def test_overwrite_resets_file_mode(self, tmp_path):
        path = tmp_path / "defaults.json"
        path.write_text("{}")
        os.chmod(path, 0o644)
        save_defaults({"a": "1"}, path)
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


# -- Tests for schema validation (6.2) --


class TestValidateDefaults:
    def test_valid_nested(self):
        data = {
            "personal": {"first_name": "Guy", "phone": ["555-1234"]},
            "work": {"company": "Acme"},
        }
        validate_defaults(data)  # should not raise

    def test_valid_with_meta(self):
        data = {
            "_meta": {"updated": "2026-01-01T00:00:00"},
            "personal": {"first_name": "Guy"},
        }
        validate_defaults(data)  # should not raise

    def test_valid_top_level_strings(self):
        data = {"nickname": "G", "color": "blue"}
        validate_defaults(data)  # should not raise

    def test_valid_top_level_list(self):
        data = {"nicknames": ["G", "Guy-o"]}
        validate_defaults(data)  # should not raise

    def test_valid_empty(self):
        validate_defaults({})  # should not raise

    def test_valid_with_aliases(self):
        data = {
            "personal": {
                "first_name": "Guy",
                "_aliases": {"fname": "first_name"},
            }
        }
        validate_defaults(data)  # should not raise

    def test_not_a_dict(self):
        with pytest.raises(DefaultsValidationError, match="must be a dict"):
            validate_defaults("not a dict")

    def test_meta_not_a_dict(self):
        with pytest.raises(DefaultsValidationError, match="_meta must be a dict"):
            validate_defaults({"_meta": "bad"})

    def test_category_value_wrong_type(self):
        with pytest.raises(DefaultsValidationError, match="must be a dict, string"):
            validate_defaults({"personal": 42})

    def test_field_wrong_type(self):
        with pytest.raises(DefaultsValidationError, match="must be a string or list"):
            validate_defaults({"personal": {"age": 30}})

    def test_nested_too_deeply(self):
        with pytest.raises(DefaultsValidationError, match="must be a string or list"):
            validate_defaults({"personal": {"address": {"street": "123 Main"}}})

    def test_list_with_non_strings(self):
        with pytest.raises(DefaultsValidationError, match="must contain only strings"):
            validate_defaults({"personal": {"codes": [1, 2, 3]}})

    def test_top_level_list_with_non_strings(self):
        with pytest.raises(DefaultsValidationError, match="must contain only strings"):
            validate_defaults({"codes": [1, 2, 3]})

    def test_aliases_not_a_dict(self):
        with pytest.raises(DefaultsValidationError, match="_aliases.*must be a dict"):
            validate_defaults({"personal": {"_aliases": "bad"}})

    def test_aliases_non_string_values(self):
        with pytest.raises(DefaultsValidationError, match="_aliases.*must map strings"):
            validate_defaults({"personal": {"_aliases": {"fname": 123}}})

    def test_load_validates(self, tmp_path):
        """load_defaults raises on valid JSON with invalid schema."""
        path = tmp_path / "bad_schema.json"
        import json

        path.write_text(json.dumps({"personal": {"age": 42}}))
        with pytest.raises(DefaultsValidationError):
            load_defaults(path)

    def test_save_validates(self, tmp_path):
        """save_defaults rejects invalid data before writing."""
        path = tmp_path / "defaults.json"
        with pytest.raises(DefaultsValidationError):
            save_defaults({"personal": {"age": 42}}, path)
        # File should not have been created
        assert not path.exists()


# -- Tests for plugin/extension matcher system (6.3) --


class TestMatcherRegistry:
    """Test the register/unregister/list matcher system."""

    def setup_method(self):
        """Reset matchers to defaults before each test."""
        clear_matchers()
        _register_default_matchers()

    def teardown_method(self):
        """Restore default matchers after each test."""
        clear_matchers()
        _register_default_matchers()

    def test_default_matchers_registered(self):
        names = list_matchers()
        assert "exact" in names
        assert "normalized" in names

    def test_default_matcher_order(self):
        names = list_matchers()
        assert names.index("exact") < names.index("normalized")

    def test_register_custom_matcher(self):
        def prefix_matcher(field_name, defaults):
            for key, value in defaults.items():
                if field_name.startswith(key):
                    return value
            return None

        register_matcher("prefix", prefix_matcher)
        assert "prefix" in list_matchers()

        defaults = {"addr": "123 Main St"}
        assert match_field_to_defaults("addr_line_1", defaults) == "123 Main St"

    def test_custom_matcher_tried_after_builtins(self):
        call_log = []

        def logging_matcher(field_name, defaults):
            call_log.append(field_name)
            return None

        register_matcher("logger", logging_matcher)

        defaults = {"first_name": "Guy"}
        # Exact match should win, custom matcher may or may not be called
        result = match_field_to_defaults("first_name", defaults)
        assert result == "Guy"

    def test_custom_matcher_used_when_builtins_fail(self):
        def suffix_matcher(field_name, defaults):
            for key, value in defaults.items():
                if field_name.endswith(key):
                    return value
            return None

        register_matcher("suffix", suffix_matcher)

        defaults = {"name": "Guy"}
        # "applicant_name" won't match exact or normalized "name",
        # but suffix matcher should find it
        result = match_field_to_defaults("applicant_name", defaults)
        assert result == "Guy"

    def test_unregister_matcher(self):
        register_matcher("dummy", lambda f, d: None)
        assert "dummy" in list_matchers()
        unregister_matcher("dummy")
        assert "dummy" not in list_matchers()

    def test_unregister_nonexistent_is_noop(self):
        unregister_matcher("nonexistent")  # should not raise

    def test_clear_matchers(self):
        clear_matchers()
        assert list_matchers() == []
        # With no matchers, nothing matches
        assert match_field_to_defaults("first_name", {"first_name": "Guy"}) is None

    def test_replace_existing_matcher(self):
        """Re-registering the same name replaces the matcher."""

        def always_match(field_name, defaults):
            return "always"

        register_matcher("exact", always_match)
        result = match_field_to_defaults("anything", {"other": "value"})
        assert result == "always"

    def test_matcher_order_preserved(self):
        """Matchers are tried in registration order."""
        clear_matchers()

        def first_matcher(field_name, defaults):
            return "first"

        def second_matcher(field_name, defaults):
            return "second"

        register_matcher("first", first_matcher)
        register_matcher("second", second_matcher)

        result = match_field_to_defaults("anything", {})
        assert result == "first"

    def test_reset_matchers_restores_builtins_after_clear(self):
        """reset_matchers() rebuilds the exact/normalized baseline."""
        clear_matchers()
        assert list_matchers() == []

        reset_matchers()
        assert list_matchers() == ["exact", "normalized"]
        assert match_field_to_defaults("first_name", {"first_name": "Guy"}) == "Guy"

    def test_reset_matchers_drops_custom_registrations(self):
        register_matcher("custom", lambda f, d: "x")
        assert "custom" in list_matchers()

        reset_matchers()
        assert list_matchers() == ["exact", "normalized"]


# -- Tests for field aliases (7.1) --


class TestFieldAliases:
    """Test the _aliases support and alias matcher."""

    def setup_method(self):
        clear_matchers()
        _register_default_matchers()

    def teardown_method(self):
        clear_matchers()
        _register_default_matchers()

    def test_build_alias_matcher_exact(self):
        raw = {
            "personal": {
                "first_name": "Guy",
                "_aliases": {"fname": "first_name", "given_name": "first_name"},
            }
        }
        flat = flatten_defaults(raw)
        matcher = build_alias_matcher(raw)
        register_matcher("alias", matcher)

        assert match_field_to_defaults("fname", flat) == "Guy"
        assert match_field_to_defaults("given_name", flat) == "Guy"

    def test_build_alias_matcher_normalized(self):
        """Aliases are also matched after normalization."""
        raw = {
            "personal": {
                "first_name": "Guy",
                "_aliases": {"fname": "first_name"},
            }
        }
        flat = flatten_defaults(raw)
        matcher = build_alias_matcher(raw)
        register_matcher("alias", matcher)

        # "FName" normalizes to "fname" which is an alias
        assert match_field_to_defaults("FName", flat) == "Guy"

    def test_alias_to_list_value(self):
        raw = {
            "personal": {
                "phone": ["555-1234", "555-5678"],
                "_aliases": {"telephone": "phone", "cell": "phone"},
            }
        }
        flat = flatten_defaults(raw)
        matcher = build_alias_matcher(raw)
        register_matcher("alias", matcher)

        assert match_field_to_defaults("telephone", flat) == ["555-1234", "555-5678"]
        assert match_field_to_defaults("cell", flat) == ["555-1234", "555-5678"]

    def test_alias_no_match(self):
        raw = {
            "personal": {
                "first_name": "Guy",
                "_aliases": {"fname": "first_name"},
            }
        }
        flat = flatten_defaults(raw)
        matcher = build_alias_matcher(raw)
        register_matcher("alias", matcher)

        assert match_field_to_defaults("zzz_unknown", flat) is None

    def test_alias_target_missing_from_defaults(self):
        """If alias points to a field not in defaults, returns None."""
        raw = {
            "personal": {
                "_aliases": {"fname": "first_name"},
            }
        }
        flat = flatten_defaults(raw)
        matcher = build_alias_matcher(raw)
        register_matcher("alias", matcher)

        assert match_field_to_defaults("fname", flat) is None

    def test_multiple_categories_aliases(self):
        raw = {
            "personal": {
                "first_name": "Guy",
                "_aliases": {"fname": "first_name"},
            },
            "work": {
                "company": "Acme",
                "_aliases": {"employer": "company", "org": "company"},
            },
        }
        flat = flatten_defaults(raw)
        matcher = build_alias_matcher(raw)
        register_matcher("alias", matcher)

        assert match_field_to_defaults("fname", flat) == "Guy"
        assert match_field_to_defaults("employer", flat) == "Acme"
        assert match_field_to_defaults("org", flat) == "Acme"

    def test_alias_does_not_shadow_exact_match(self):
        """If a field has an exact match, it wins over alias (exact is first)."""
        raw = {
            "personal": {
                "first_name": "Guy",
                "fname": "Francis",
                "_aliases": {"fname": "first_name"},
            }
        }
        flat = flatten_defaults(raw)
        matcher = build_alias_matcher(raw)
        register_matcher("alias", matcher)

        # "fname" is in flat directly as "Francis" - exact matcher wins
        assert match_field_to_defaults("fname", flat) == "Francis"

    def test_aliases_skipped_in_flatten(self):
        raw = {
            "personal": {
                "first_name": "Guy",
                "_aliases": {"fname": "first_name"},
            }
        }
        flat = flatten_defaults(raw)
        assert "_aliases" not in flat
        assert "fname" not in flat

    def test_no_aliases_returns_noop_matcher(self):
        """build_alias_matcher on data with no aliases still works."""
        raw = {"personal": {"first_name": "Guy"}}
        flat = flatten_defaults(raw)
        matcher = build_alias_matcher(raw)
        register_matcher("alias", matcher)

        # No aliases, so alias matcher always returns None
        assert match_field_to_defaults("fname", flat) is None
        # But exact/normalized still work
        assert match_field_to_defaults("first_name", flat) == "Guy"

    def test_round_trip_with_aliases(self, tmp_path):
        """Aliases survive save/load round-trip and work correctly."""
        path = tmp_path / "defaults.json"
        data = {
            "personal": {
                "first_name": "Guy",
                "_aliases": {"fname": "first_name"},
            }
        }
        save_defaults(data, path)
        loaded = load_defaults(path)

        flat = flatten_defaults(loaded)
        matcher = build_alias_matcher(loaded)
        register_matcher("alias", matcher)

        assert match_field_to_defaults("fname", flat) == "Guy"
