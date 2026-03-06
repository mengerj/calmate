"""Two-stage cell-type label mapping pipeline.

Stage 1 -- **direct match**: Uses pronto to look up each label against
Cell Ontology term names and synonyms (case-insensitive).  Exact hits
are automatically marked as reviewed.

Stage 2 -- **auto-map backend** (optional): Labels that could not be
resolved in stage 1 are passed to a pluggable :class:`AutoMapBackend`
(default: :class:`OmicverseBackend`) for automated matching.  These
results are stored as *unreviewed* and require human approval.

See :mod:`calmate.backends.base` for how to implement custom backends.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Optional, Union

from rich.console import Console
from rich.progress import Progress

from calmate.backends import get_backend
from calmate.backends.base import AutoMapBackend
from calmate.ontology import (
    build_label_index,
    download_cl_ontology,
    load_ontology,
    map_string_to_term,
)
from calmate.store import MappingStore, _now_iso

console = Console(stderr=True)


def map_labels(
    labels: list[str],
    store: MappingStore,
    *,
    cache_dir: Optional[str | Path] = None,
    origin: str = "unknown",
    force: bool = False,
    backend: Union[str, AutoMapBackend, None] = "omicverse",
    **backend_kwargs: object,
) -> int:
    """Run the two-stage mapping pipeline and persist results.

    Parameters
    ----------
    labels:
        Free-text cell-type labels to map.
    store:
        Target :class:`MappingStore` where mappings are recorded.
    cache_dir:
        Directory for ontology and model caches.  Defaults to a ``cache``
        sibling of the store file.
    origin:
        Provenance tag written into each new row.
    force:
        When *True*, re-map labels that already exist in *store*.
    backend:
        Auto-mapping backend for stage 2.  Accepts a registered name
        string (e.g. ``"omicverse"``), an :class:`AutoMapBackend`
        instance, or ``None`` / ``"none"`` to skip auto-mapping.
    **backend_kwargs:
        Extra keyword arguments forwarded to the backend's
        :meth:`~AutoMapBackend.map` method (e.g. ``model_name``).

    Returns
    -------
    Number of new mappings added to the store.
    """
    unique_labels = sorted(set(labels))

    if not force:
        existing = store.load()
        if not existing.empty:
            known = set(existing["predicted_label"])
            unique_labels = [l for l in unique_labels if l not in known]
        if not unique_labels:
            console.print("[green]All labels already in store -- nothing to do.[/green]")
            return 0

    if cache_dir is None:
        cache_dir = store.path.parent / "cache"
    cache_dir = Path(cache_dir)

    console.print(f"Mapping [bold]{len(unique_labels)}[/bold] label(s)...")

    # Stage 1: direct ontology match
    owl_path = download_cl_ontology(cache_dir)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ont = load_ontology(owl_path)
        label_index = build_label_index(ont)

    direct_hits: list[dict] = []
    remaining: list[str] = []

    with Progress(console=console, transient=True) as progress:
        task = progress.add_task("Direct matching...", total=len(unique_labels))
        for label in unique_labels:
            term = map_string_to_term(label, label_index)
            if term is not None:
                direct_hits.append(
                    _make_row(
                        predicted_label=label,
                        chosen_match=term.name,
                        best_match=term.name,
                        ontology_id=term.id,
                        confidence=1.0,
                        origin=origin,
                        reviewed=True,
                    )
                )
            else:
                remaining.append(label)
            progress.advance(task)

    console.print(
        f"  Direct matches: [green]{len(direct_hits)}[/green]  |  "
        f"Remaining: [yellow]{len(remaining)}[/yellow]"
    )

    # Stage 2: auto-map backend (optional)
    backend_hits: list[dict] = []
    resolved_backend = get_backend(backend)

    if remaining and resolved_backend is not None:
        if not resolved_backend.is_available():
            console.print(
                f"[yellow]Backend '{resolved_backend.name}' is not available "
                f"(missing dependencies). Skipping auto-mapping.[/yellow]"
            )
        else:
            suggestions = resolved_backend.map(
                remaining, cache_dir, **backend_kwargs
            )
            for s in suggestions:
                backend_hits.append(
                    _make_row(
                        predicted_label=s.predicted_label,
                        chosen_match=s.suggested_match,
                        best_match=s.suggested_match,
                        ontology_id=s.ontology_id,
                        confidence=s.confidence,
                        origin=origin,
                        reviewed=False,
                    )
                )

    all_new = direct_hits + backend_hits

    # Stage 3: labels that no stage could resolve
    matched_labels = {r["predicted_label"] for r in all_new}
    for label in remaining:
        if label not in matched_labels:
            all_new.append(
                _make_row(
                    predicted_label=label,
                    chosen_match="",
                    best_match="",
                    ontology_id="",
                    confidence=0.0,
                    origin=origin,
                    reviewed=False,
                )
            )

    added = store.add_mappings(all_new)
    console.print(f"[bold green]{added}[/bold green] new mapping(s) written to store.")
    return added


def _make_row(
    *,
    predicted_label: str,
    chosen_match: str,
    best_match: str,
    ontology_id: str,
    confidence: float,
    origin: str,
    reviewed: bool,
) -> dict:
    return {
        "reviewed": reviewed,
        "origin": origin,
        "predicted_label": predicted_label,
        "chosen_match": chosen_match,
        "best_match": best_match,
        "ontology_id": ontology_id,
        "confidence": confidence,
        "timestamp": _now_iso(),
    }
