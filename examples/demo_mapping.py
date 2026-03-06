"""Demo: map a mix of exact and fuzzy cell-type labels through calmate.

Some labels match Cell Ontology terms directly (e.g. "T cell"),
others are plausible free-text annotations that require human review
(e.g. "Treg cells", "reactive astroglia").

Usage:
    cd /Users/mengerj/repos/calmate
    uv run python examples/demo_mapping.py
"""

from pathlib import Path

from calmate import MappingStore, apply_labels, get_backend, map_labels

DEMO_DIR = Path("examples/_demo_output")

# Ground-truth ontology terms (for reference, not used by the mapper)
TRUE_LABELS = [
    "T cell",                   # CL:0000084
    "astrocyte",                # CL:0000127
    "regulatory T cell",        # CL:0000815
    "microglial cell",          # CL:0000129
    "oligodendrocyte",          # CL:0000128
]

# Simulated "predicted" labels -- the kind of free-text you get from
# annotation tools or collaborators.  Some are exact ontology terms,
# others are close but not identical.
PREDICTED_LABELS = [
    "T cell",                   # exact match
    "oligodendrocyte",          # exact match
    "Treg cells",               # fuzzy -- should map to "regulatory T cell"
    "reactive astroglia",       # fuzzy -- should map to "astrocyte" (or similar)
    "brain macrophages",        # fuzzy -- should map to "microglial cell"
]


def main() -> None:
    store_path = DEMO_DIR / "mappings.csv"
    cache_dir = DEMO_DIR / "cache"

    store = MappingStore(store_path)

    # Auto-detect the best available backend
    backend_obj = get_backend("omicverse")
    if backend_obj is not None and backend_obj.is_available():
        backend_name = "omicverse"
    else:
        backend_name = "none"

    print("=" * 60)
    print("CALMATE demo -- mapping predicted cell-type labels")
    print("=" * 60)
    print()
    print("Predicted labels:")
    for label in PREDICTED_LABELS:
        print(f"  - {label}")
    print()
    print(f"Backend: {backend_name}" + (" (install calmate[omicverse] to enable)" if backend_name == "none" else ""))
    print()

    map_labels(
        PREDICTED_LABELS,
        store=store,
        cache_dir=cache_dir,
        origin="demo",
        backend=backend_name,
    )

    # ------------------------------------------------------------------
    # Apply the mappings back to the predicted labels
    # ------------------------------------------------------------------
    print()
    print("=" * 60)
    print("Applying mappings to predicted labels")
    print("=" * 60)
    print()

    result = apply_labels(PREDICTED_LABELS, store)

    for orig, mapped in zip(PREDICTED_LABELS, result.mapped_labels):
        tag = " (unchanged)" if orig == mapped else ""
        print(f"  {orig:30s} -> {mapped}{tag}")

    print()
    print(result.message)

    if result.has_warnings:
        print()
        print("-" * 60)
        print("Next steps to resolve warnings:")
        print()
        print(f"  1. Interactively review unreviewed mappings:")
        print(f"     uv run calmate --store {store_path} review")
        print()
        print(f"  2. Re-run this script to see clean output.")
        print("-" * 60)
    else:
        print()
        print("All labels mapped -- no warnings.")


if __name__ == "__main__":
    main()
