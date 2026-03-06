"""Tests for calmate.ontology helpers."""

from calmate.ontology import _normalize, build_label_index, map_string_to_term


class TestNormalize:
    def test_basic(self):
        assert _normalize("T Cell") == "t cell"

    def test_extra_whitespace(self):
        assert _normalize("  some   cell  ") == "some cell"

    def test_empty(self):
        assert _normalize("") == ""

    def test_none_safe(self):
        assert _normalize(None) == ""


class TestMapStringToTerm:
    def test_returns_none_for_empty(self):
        assert map_string_to_term("", {}) is None
        assert map_string_to_term("  ", {}) is None

    def test_returns_none_for_missing(self):
        assert map_string_to_term("unknown", {"t cell": object()}) is None

    def test_case_insensitive_lookup(self):
        sentinel = object()
        idx = {"t cell": sentinel}
        assert map_string_to_term("T Cell", idx) is sentinel
        assert map_string_to_term("t cell", idx) is sentinel
        assert map_string_to_term("T CELL", idx) is sentinel
