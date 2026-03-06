"""Tests for calmate.store.MappingStore."""

from pathlib import Path

import pandas as pd
import pytest

from calmate.store import COLUMNS, MappingStore


def _row(**overrides) -> dict:
    base = {
        "reviewed": False,
        "origin": "test",
        "predicted_label": "some cell",
        "chosen_match": "matched cell",
        "best_match": "matched cell",
        "ontology_id": "CL:0000000",
        "confidence": 0.9,
        "timestamp": "2026-01-01T00:00:00+00:00",
    }
    base.update(overrides)
    return base


class TestMappingStoreIO:
    def test_load_empty_when_no_file(self, tmp_store: Path):
        store = MappingStore(tmp_store)
        df = store.load()
        assert list(df.columns) == COLUMNS
        assert len(df) == 0

    def test_round_trip(self, tmp_store: Path):
        store = MappingStore(tmp_store)
        store.add_mappings([_row(predicted_label="alpha")])
        df = store.load()
        assert len(df) == 1
        assert df.iloc[0]["predicted_label"] == "alpha"

    def test_creates_parent_dirs(self, tmp_path: Path):
        nested = tmp_path / "a" / "b" / "mappings.csv"
        store = MappingStore(nested)
        store.add_mappings([_row()])
        assert nested.exists()


class TestAddMappings:
    def test_adds_new_rows(self, tmp_store: Path):
        store = MappingStore(tmp_store)
        added = store.add_mappings([
            _row(predicted_label="A"),
            _row(predicted_label="B"),
        ])
        assert added == 2
        assert len(store.load()) == 2

    def test_skips_existing_labels(self, tmp_store: Path):
        store = MappingStore(tmp_store)
        store.add_mappings([_row(predicted_label="A")])
        added = store.add_mappings([
            _row(predicted_label="A"),
            _row(predicted_label="B"),
        ])
        assert added == 1
        assert len(store.load()) == 2

    def test_sorted_by_label(self, tmp_store: Path):
        store = MappingStore(tmp_store)
        store.add_mappings([
            _row(predicted_label="Zebra"),
            _row(predicted_label="Alpha"),
        ])
        df = store.load()
        assert df.iloc[0]["predicted_label"] == "Alpha"
        assert df.iloc[1]["predicted_label"] == "Zebra"


class TestQueries:
    def test_has_label(self, tmp_store: Path):
        store = MappingStore(tmp_store)
        store.add_mappings([_row(predicted_label="X")])
        assert store.has_label("X")
        assert not store.has_label("Y")

    def test_get_mapping_dict(self, tmp_store: Path):
        store = MappingStore(tmp_store)
        store.add_mappings([
            _row(predicted_label="A", chosen_match="a_match", reviewed=True),
            _row(predicted_label="B", chosen_match="b_match", reviewed=False),
        ])
        all_mappings = store.get_mapping_dict(reviewed_only=False)
        assert all_mappings == {"A": "a_match", "B": "b_match"}

        reviewed_only = store.get_mapping_dict(reviewed_only=True)
        assert reviewed_only == {"A": "a_match"}

    def test_get_unreviewed(self, tmp_store: Path):
        store = MappingStore(tmp_store)
        store.add_mappings([
            _row(predicted_label="A", reviewed=True),
            _row(predicted_label="B", reviewed=False),
            _row(predicted_label="C", reviewed=False),
        ])
        unreviewed = store.get_unreviewed()
        assert len(unreviewed) == 2
        assert set(unreviewed["predicted_label"]) == {"B", "C"}

    def test_get_reviewed(self, tmp_store: Path):
        store = MappingStore(tmp_store)
        store.add_mappings([
            _row(predicted_label="A", reviewed=True),
            _row(predicted_label="B", reviewed=False),
        ])
        reviewed = store.get_reviewed()
        assert len(reviewed) == 1
        assert reviewed.iloc[0]["predicted_label"] == "A"


class TestUpdateMapping:
    def test_update_chosen_match(self, tmp_store: Path):
        store = MappingStore(tmp_store)
        store.add_mappings([_row(predicted_label="X", chosen_match="old")])
        ok = store.update_mapping("X", chosen_match="new")
        assert ok
        df = store.load()
        assert df.iloc[0]["chosen_match"] == "new"

    def test_update_reviewed(self, tmp_store: Path):
        store = MappingStore(tmp_store)
        store.add_mappings([_row(predicted_label="X", reviewed=False)])
        store.update_mapping("X", reviewed=True)
        df = store.load()
        assert df.iloc[0]["reviewed"] is True or str(df.iloc[0]["reviewed"]).lower() == "true"

    def test_update_nonexistent_returns_false(self, tmp_store: Path):
        store = MappingStore(tmp_store)
        assert not store.update_mapping("nope", chosen_match="x")


class TestMerge:
    def test_merge_new_labels(self, tmp_path: Path):
        store_a = MappingStore(tmp_path / "a.csv")
        store_b = MappingStore(tmp_path / "b.csv")

        store_a.add_mappings([_row(predicted_label="A")])
        store_b.add_mappings([_row(predicted_label="B")])

        merged = store_a.merge_from(store_b)
        assert merged == 1
        assert len(store_a.load()) == 2

    def test_merge_no_overwrite_by_default(self, tmp_path: Path):
        store_a = MappingStore(tmp_path / "a.csv")
        store_b = MappingStore(tmp_path / "b.csv")

        store_a.add_mappings([_row(predicted_label="A", chosen_match="original")])
        store_b.add_mappings([_row(predicted_label="A", chosen_match="incoming")])

        store_a.merge_from(store_b, overwrite=False)
        df = store_a.load()
        assert df[df["predicted_label"] == "A"].iloc[0]["chosen_match"] == "original"


class TestSummary:
    def test_empty_summary(self, tmp_store: Path):
        store = MappingStore(tmp_store)
        info = store.summary()
        assert info["total"] == 0

    def test_summary_counts(self, tmp_store: Path):
        store = MappingStore(tmp_store)
        store.add_mappings([
            _row(predicted_label="A", reviewed=True, origin="ds1"),
            _row(predicted_label="B", reviewed=False, origin="ds1"),
            _row(predicted_label="C", reviewed=False, origin="ds2"),
        ])
        info = store.summary()
        assert info["total"] == 3
        assert info["reviewed"] == 1
        assert info["unreviewed"] == 2
        assert info["origins"]["ds1"] == 2
        assert info["origins"]["ds2"] == 1
