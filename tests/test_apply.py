"""Tests for calmate.apply -- apply_labels() and MappingResult."""

from pathlib import Path

import pytest

from calmate.apply import MappingResult, apply_labels
from calmate.store import MappingStore


def _seed_store(store: MappingStore, rows: list[dict]) -> None:
    """Helper to populate a store with pre-built rows."""
    store.add_mappings(rows)


def _row(label: str, match: str, reviewed: bool = True, **kw) -> dict:
    return {
        "predicted_label": label,
        "chosen_match": match,
        "best_match": match,
        "ontology_id": kw.get("ontology_id", ""),
        "confidence": kw.get("confidence", 1.0),
        "origin": kw.get("origin", "test"),
        "reviewed": reviewed,
        "timestamp": "2025-01-01T00:00:00+00:00",
    }


class TestApplyLabelsAllReviewed:
    """All labels have reviewed mappings -- straightforward replacement."""

    def test_replaces_labels(self, tmp_store: Path) -> None:
        store = MappingStore(tmp_store)
        _seed_store(store, [
            _row("T cell", "T cell", reviewed=True),
            _row("beta cell", "type B pancreatic cell", reviewed=True),
        ])

        result = apply_labels(["T cell", "beta cell", "T cell"], store)

        assert result.mapped_labels == ["T cell", "type B pancreatic cell", "T cell"]
        assert result.label_map == {"beta cell": "type B pancreatic cell"}
        assert result.unreviewed == []
        assert result.unmapped == []
        assert not result.has_warnings

    def test_label_map_only_includes_changed(self, tmp_store: Path) -> None:
        store = MappingStore(tmp_store)
        _seed_store(store, [_row("astrocyte", "astrocyte", reviewed=True)])

        result = apply_labels(["astrocyte"], store)

        assert result.mapped_labels == ["astrocyte"]
        assert result.label_map == {}


class TestApplyLabelsUnreviewed:
    """Some labels have unreviewed mappings and should not be replaced."""

    def test_unreviewed_kept_as_is(self, tmp_store: Path) -> None:
        store = MappingStore(tmp_store)
        _seed_store(store, [
            _row("T cell", "T cell", reviewed=True),
            _row("Treg cells", "regulatory T cell", reviewed=False),
        ])

        result = apply_labels(["T cell", "Treg cells"], store)

        assert result.mapped_labels == ["T cell", "Treg cells"]
        assert result.unreviewed == ["Treg cells"]
        assert result.unmapped == []
        assert result.has_warnings

    def test_reviewed_only_false_replaces_unreviewed(self, tmp_store: Path) -> None:
        store = MappingStore(tmp_store)
        _seed_store(store, [
            _row("Treg cells", "regulatory T cell", reviewed=False),
        ])

        result = apply_labels(["Treg cells"], store, reviewed_only=False)

        assert result.mapped_labels == ["regulatory T cell"]
        assert result.label_map == {"Treg cells": "regulatory T cell"}
        assert result.unreviewed == []
        assert not result.has_warnings


class TestApplyLabelsUnmapped:
    """Labels that are not in the store at all."""

    def test_unmapped_kept_as_is(self, tmp_store: Path) -> None:
        store = MappingStore(tmp_store)
        _seed_store(store, [_row("T cell", "T cell", reviewed=True)])

        result = apply_labels(["T cell", "goblet cell"], store)

        assert result.mapped_labels == ["T cell", "goblet cell"]
        assert result.unmapped == ["goblet cell"]
        assert result.has_warnings

    def test_empty_store(self, tmp_store: Path) -> None:
        store = MappingStore(tmp_store)

        result = apply_labels(["T cell"], store)

        assert result.mapped_labels == ["T cell"]
        assert result.unmapped == ["T cell"]
        assert result.has_warnings


class TestApplyLabelsMixed:
    """Mix of reviewed, unreviewed, and unmapped."""

    def test_mixed_scenario(self, tmp_store: Path) -> None:
        store = MappingStore(tmp_store)
        _seed_store(store, [
            _row("T cell", "T cell", reviewed=True),
            _row("beta cell", "type B pancreatic cell", reviewed=True),
            _row("Treg cells", "regulatory T cell", reviewed=False),
        ])

        labels = ["T cell", "Treg cells", "beta cell", "unknown cell"]
        result = apply_labels(labels, store)

        assert result.mapped_labels == [
            "T cell", "Treg cells", "type B pancreatic cell", "unknown cell"
        ]
        assert result.label_map == {"beta cell": "type B pancreatic cell"}
        assert result.unreviewed == ["Treg cells"]
        assert result.unmapped == ["unknown cell"]
        assert result.has_warnings


class TestMappingResultMessage:
    """The .message property produces useful diagnostics."""

    def test_clean_message(self, tmp_store: Path) -> None:
        store = MappingStore(tmp_store)
        _seed_store(store, [_row("beta cell", "type B pancreatic cell")])

        result = apply_labels(["beta cell"], store)
        msg = result.message

        assert "1/1" in msg
        assert "WARNING" not in msg

    def test_unreviewed_warning(self, tmp_store: Path) -> None:
        store = MappingStore(tmp_store)
        _seed_store(store, [_row("Treg cells", "regulatory T cell", reviewed=False)])

        result = apply_labels(["Treg cells"], store)
        msg = result.message

        assert "WARNING" in msg
        assert "Treg cells" in msg
        assert "calmate review" in msg

    def test_unmapped_warning(self, tmp_store: Path) -> None:
        store = MappingStore(tmp_store)

        result = apply_labels(["unknown cell"], store)
        msg = result.message

        assert "WARNING" in msg
        assert "unknown cell" in msg
        assert "calmate map" in msg

    def test_both_warnings(self, tmp_store: Path) -> None:
        store = MappingStore(tmp_store)
        _seed_store(store, [_row("Treg cells", "regulatory T cell", reviewed=False)])

        result = apply_labels(["Treg cells", "unknown cell"], store)
        msg = result.message

        assert "calmate review" in msg
        assert "calmate map" in msg


class TestMappingResultHasWarnings:

    def test_no_warnings(self) -> None:
        r = MappingResult(mapped_labels=["a"], label_map={}, unreviewed=[], unmapped=[])
        assert not r.has_warnings

    def test_has_unreviewed(self) -> None:
        r = MappingResult(mapped_labels=["a"], unreviewed=["a"])
        assert r.has_warnings

    def test_has_unmapped(self) -> None:
        r = MappingResult(mapped_labels=["a"], unmapped=["a"])
        assert r.has_warnings
