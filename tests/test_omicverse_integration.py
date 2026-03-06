"""Integration test for OmicverseBackend.

Skipped when the omicverse extra is not installed.  When it IS installed,
this test actually calls the omicverse mapper with real labels and
asserts that non-empty suggestions are returned -- catching the class
of bugs where the import succeeds but the mapping silently produces
no results.
"""

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import pytest

from calmate.backends.omicverse import OmicverseBackend


def _semantic_extra_installed() -> bool:
    try:
        version("omicverse")
        version("sentence-transformers")
        return True
    except PackageNotFoundError:
        return False


needs_semantic = pytest.mark.skipif(
    not _semantic_extra_installed(),
    reason="omicverse extra not installed (uv sync --extra omicverse)",
)


@needs_semantic
class TestOmicverseBackendIntegration:
    """End-to-end test that downloads the ontology and runs the mapper."""

    def test_is_available(self):
        backend = OmicverseBackend()
        assert backend.is_available(), (
            "OmicverseBackend.is_available() returned False even though "
            "omicverse and sentence-transformers are installed"
        )

    def test_map_returns_suggestions(self, tmp_path: Path):
        backend = OmicverseBackend()
        labels = ["Treg cells", "reactive astroglia", "brain macrophages"]

        suggestions = backend.map(labels, cache_dir=tmp_path)

        assert len(suggestions) > 0, (
            f"OmicverseBackend.map() returned no suggestions for {labels}. "
            "This likely means the mapper silently failed."
        )
        for s in suggestions:
            assert s.predicted_label in labels
            assert s.suggested_match, (
                f"Empty suggested_match for '{s.predicted_label}'"
            )

    def test_map_result_fields(self, tmp_path: Path):
        backend = OmicverseBackend()
        suggestions = backend.map(["T regulatory cell"], cache_dir=tmp_path)

        if suggestions:
            s = suggestions[0]
            assert isinstance(s.confidence, float)
            assert s.confidence >= 0.0
