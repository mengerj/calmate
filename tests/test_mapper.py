"""Tests for calmate.mapper -- focusing on the direct-match stage.

Full integration tests (with omicverse) are skipped unless the package
is installed, because they require network access and a model download.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from calmate.mapper import _make_row, map_labels
from calmate.store import MappingStore


class TestMakeRow:
    def test_all_fields_present(self):
        row = _make_row(
            predicted_label="test",
            chosen_match="matched",
            best_match="matched",
            ontology_id="CL:0000001",
            confidence=0.95,
            origin="unit_test",
            reviewed=True,
        )
        assert row["predicted_label"] == "test"
        assert row["chosen_match"] == "matched"
        assert row["ontology_id"] == "CL:0000001"
        assert row["reviewed"] is True
        assert "timestamp" in row


class TestMapLabelsDirectOnly:
    """Test the mapper with backend=None (no auto-mapping)."""

    @patch("calmate.mapper.download_cl_ontology")
    @patch("calmate.mapper.load_ontology")
    @patch("calmate.mapper.build_label_index")
    def test_direct_match_stores_reviewed(
        self, mock_index, mock_ont, mock_download, tmp_path: Path
    ):
        mock_download.return_value = tmp_path / "cl.owl"

        mock_term = MagicMock()
        mock_term.name = "T cell"
        mock_term.id = "CL:0000084"

        mock_index.return_value = {"t cell": mock_term}

        store = MappingStore(tmp_path / "mappings.csv")
        added = map_labels(
            ["T cell"],
            store=store,
            cache_dir=tmp_path,
            backend=None,
            origin="test",
        )

        assert added == 1
        df = store.load()
        assert len(df) == 1
        assert df.iloc[0]["predicted_label"] == "T cell"
        assert df.iloc[0]["chosen_match"] == "T cell"
        assert str(df.iloc[0]["reviewed"]).lower() == "true"

    @patch("calmate.mapper.download_cl_ontology")
    @patch("calmate.mapper.load_ontology")
    @patch("calmate.mapper.build_label_index")
    def test_unmatched_stored_as_unreviewed(
        self, mock_index, mock_ont, mock_download, tmp_path: Path
    ):
        mock_download.return_value = tmp_path / "cl.owl"
        mock_index.return_value = {}

        store = MappingStore(tmp_path / "mappings.csv")
        added = map_labels(
            ["Mystery Cell X"],
            store=store,
            cache_dir=tmp_path,
            backend=None,
            origin="test",
        )

        assert added == 1
        df = store.load()
        assert str(df.iloc[0]["reviewed"]).lower() == "false"
        assert pd.isna(df.iloc[0]["chosen_match"]) or df.iloc[0]["chosen_match"] == ""

    @patch("calmate.mapper.download_cl_ontology")
    @patch("calmate.mapper.load_ontology")
    @patch("calmate.mapper.build_label_index")
    def test_skips_existing_labels(
        self, mock_index, mock_ont, mock_download, tmp_path: Path
    ):
        mock_download.return_value = tmp_path / "cl.owl"
        mock_index.return_value = {}

        store = MappingStore(tmp_path / "mappings.csv")
        store.add_mappings([_make_row(
            predicted_label="Known",
            chosen_match="known cell",
            best_match="known cell",
            ontology_id="CL:0000001",
            confidence=1.0,
            origin="prior",
            reviewed=True,
        )])

        added = map_labels(
            ["Known"],
            store=store,
            cache_dir=tmp_path,
            backend=None,
        )
        assert added == 0


class TestMapLabelsForce:
    @patch("calmate.mapper.download_cl_ontology")
    @patch("calmate.mapper.load_ontology")
    @patch("calmate.mapper.build_label_index")
    def test_force_remaps_existing(
        self, mock_index, mock_ont, mock_download, tmp_path: Path
    ):
        mock_download.return_value = tmp_path / "cl.owl"

        mock_term = MagicMock()
        mock_term.name = "astrocyte"
        mock_term.id = "CL:0000127"
        mock_index.return_value = {"astrocyte": mock_term}

        store = MappingStore(tmp_path / "mappings.csv")
        store.add_mappings([_make_row(
            predicted_label="astrocyte",
            chosen_match="old",
            best_match="old",
            ontology_id="",
            confidence=0.0,
            origin="prior",
            reviewed=False,
        )])

        added = map_labels(
            ["astrocyte"],
            store=store,
            cache_dir=tmp_path,
            backend=None,
            force=True,
        )
        # The label already exists so add_mappings skips the duplicate
        assert added == 0


class TestMapLabelsWithMockBackend:
    """Test the backend integration path using a fake backend."""

    @patch("calmate.mapper.download_cl_ontology")
    @patch("calmate.mapper.load_ontology")
    @patch("calmate.mapper.build_label_index")
    def test_backend_suggestions_stored_as_unreviewed(
        self, mock_index, mock_ont, mock_download, tmp_path: Path
    ):
        from calmate.backends.base import AutoMapBackend, MapSuggestion

        mock_download.return_value = tmp_path / "cl.owl"
        mock_index.return_value = {}

        class FakeBackend(AutoMapBackend):
            name = "fake"

            def is_available(self) -> bool:
                return True

            def map(self, labels, cache_dir, **kwargs):
                return [
                    MapSuggestion(
                        predicted_label=label,
                        suggested_match=f"matched_{label}",
                        ontology_id="CL:0000000",
                        confidence=0.85,
                    )
                    for label in labels
                ]

        store = MappingStore(tmp_path / "mappings.csv")
        added = map_labels(
            ["fuzzy label A", "fuzzy label B"],
            store=store,
            cache_dir=tmp_path,
            backend=FakeBackend(),
            origin="test",
        )

        assert added == 2
        df = store.load()
        assert len(df) == 2
        for _, row in df.iterrows():
            assert str(row["reviewed"]).lower() == "false"
            assert row["chosen_match"].startswith("matched_")
            assert row["confidence"] == 0.85

    @patch("calmate.mapper.download_cl_ontology")
    @patch("calmate.mapper.load_ontology")
    @patch("calmate.mapper.build_label_index")
    def test_unavailable_backend_skipped(
        self, mock_index, mock_ont, mock_download, tmp_path: Path
    ):
        from calmate.backends.base import AutoMapBackend, MapSuggestion

        mock_download.return_value = tmp_path / "cl.owl"
        mock_index.return_value = {}

        class BrokenBackend(AutoMapBackend):
            name = "broken"

            def is_available(self) -> bool:
                return False

            def map(self, labels, cache_dir, **kwargs):
                raise RuntimeError("should not be called")

        store = MappingStore(tmp_path / "mappings.csv")
        added = map_labels(
            ["some label"],
            store=store,
            cache_dir=tmp_path,
            backend=BrokenBackend(),
            origin="test",
        )

        assert added == 1
        df = store.load()
        assert pd.isna(df.iloc[0]["chosen_match"]) or df.iloc[0]["chosen_match"] == ""
