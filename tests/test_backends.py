"""Tests for the backend registry and interface contract."""

import pytest

from calmate.backends import BACKEND_REGISTRY, get_backend
from calmate.backends.base import AutoMapBackend, MapSuggestion


class TestMapSuggestion:
    def test_defaults(self):
        s = MapSuggestion(predicted_label="x", suggested_match="y")
        assert s.ontology_id == ""
        assert s.confidence == 0.0

    def test_all_fields(self):
        s = MapSuggestion(
            predicted_label="Treg",
            suggested_match="regulatory T cell",
            ontology_id="CL:0000815",
            confidence=0.92,
        )
        assert s.predicted_label == "Treg"
        assert s.confidence == 0.92


class TestGetBackend:
    def test_none_string(self):
        assert get_backend("none") is None
        assert get_backend("None") is None

    def test_none_value(self):
        assert get_backend(None) is None

    def test_omicverse_registered(self):
        backend = get_backend("omicverse")
        assert backend is not None
        assert backend.name == "omicverse"

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown backend"):
            get_backend("nonexistent_backend")

    def test_passthrough_instance(self):
        class Dummy(AutoMapBackend):
            name = "dummy"
            def is_available(self): return True
            def map(self, labels, cache_dir, **kw): return []

        inst = Dummy()
        assert get_backend(inst) is inst


class TestBackendRegistry:
    def test_omicverse_in_registry(self):
        assert "omicverse" in BACKEND_REGISTRY

    def test_all_entries_are_backend_subclasses(self):
        for name, cls in BACKEND_REGISTRY.items():
            assert issubclass(cls, AutoMapBackend), (
                f"Registry entry '{name}' is not an AutoMapBackend subclass"
            )

    def test_all_entries_instantiate(self):
        for name, cls in BACKEND_REGISTRY.items():
            instance = cls()
            assert instance.name == name
