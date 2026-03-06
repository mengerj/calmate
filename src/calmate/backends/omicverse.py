"""Omicverse CellOntologyMapper backend.

Uses ``omicverse.single.CellOntologyMapper`` to map free-text cell-type
labels to Cell Ontology terms via sentence-transformer embeddings.

Required packages (installed via ``calmate[omicverse]``):
    omicverse, sentence-transformers, torch_geometric, transformers<5,
    setuptools<81
"""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from calmate.backends.base import AutoMapBackend, MapSuggestion
from calmate.ontology import CL_JSON_URL, build_label_index, download_cl_ontology, load_ontology, map_string_to_term

console = Console(stderr=True)


class OmicverseBackend(AutoMapBackend):
    """Semantic matching via omicverse CellOntologyMapper.

    This backend encodes cell-type labels and ontology terms with a
    sentence-transformer model, then picks the highest-cosine-similarity
    ontology term for each input label.
    """

    name = "omicverse"

    def is_available(self) -> bool:
        """Check that omicverse and sentence-transformers are importable."""
        try:
            import omicverse  # noqa: F401
            import sentence_transformers  # noqa: F401
            return True
        except ImportError:
            return False

    def map(
        self,
        labels: list[str],
        cache_dir: Path,
        **kwargs: object,
    ) -> list[MapSuggestion]:
        """Map *labels* using omicverse CellOntologyMapper.

        Keyword arguments
        -----------------
        model_name : str
            Sentence-transformer model (default ``"all-MiniLM-L6-v2"``).
        """
        model_name = str(kwargs.get("model_name", "all-MiniLM-L6-v2"))

        try:
            import omicverse as ov
        except ImportError as exc:
            console.print(
                f"[red]omicverse is not installed ({exc}).[/red]  "
                "Install with: uv add 'calmate[omicverse]'"
            )
            return []

        import warnings

        cl_json_path = download_cl_ontology(cache_dir, cl_url=CL_JSON_URL)

        console.print("Running semantic matching via omicverse...")
        try:
            mapper = ov.single.CellOntologyMapper(
                cl_obo_file=str(cl_json_path),
                model_name=model_name,
                local_model_dir=str(cache_dir),
            )
            results = mapper.map_cells(labels)
        except Exception as exc:
            console.print(f"[red]Semantic matching failed:[/red] {exc}")
            return []

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            owl_path = download_cl_ontology(cache_dir)
            ont = load_ontology(owl_path)
            label_index = build_label_index(ont)

        suggestions: list[MapSuggestion] = []
        for label in labels:
            if label not in results:
                continue
            entry = results[label]
            best = entry.get("best_match", "")
            if not best:
                continue

            similarity = entry.get("similarity", 0.0)
            ontology_id = entry.get("cl_id") or entry.get("ontology_id") or ""

            if not ontology_id:
                term = map_string_to_term(best, label_index)
                ontology_id = term.id if term else ""

            suggestions.append(
                MapSuggestion(
                    predicted_label=label,
                    suggested_match=best,
                    ontology_id=ontology_id,
                    confidence=float(similarity) if similarity else 0.0,
                )
            )

        console.print(
            f"  Semantic matches: [yellow]{len(suggestions)}[/yellow] (need review)"
        )
        return suggestions
