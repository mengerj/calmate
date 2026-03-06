# CALMATE -- Cell Annotation Label Mapping with Assisted Term Editing

A Python package that maps free-text cell type labels to standardized [Cell Ontology](https://obofoundry.org/ontology/cl.html) terms, with a human-in-the-loop review workflow.

## Features

- **Two-stage mapping pipeline**: Fast direct matching via `pronto` (exact name + synonyms), with optional semantic matching via `omicverse`
- **Human-in-the-loop review**: Interactive CLI for reviewing and approving automated mappings
- **Growing mapping database**: CSV-based store that accumulates verified mappings across projects
- **Transparent audit trail**: Every mapping records its origin, confidence, review status, and timestamp

## Installation

> **Note:** calmate is not yet published on PyPI. For now, install directly from GitHub.

```bash
pip install git+https://github.com/mengerj/calmate.git
```

With the omicverse auto-mapping backend:

```bash
pip install "calmate[omicverse] @ git+https://github.com/mengerj/calmate.git"
```

Or, if you use `uv`:

```bash
uv add "calmate @ git+https://github.com/mengerj/calmate.git"
uv add "calmate[omicverse] @ git+https://github.com/mengerj/calmate.git"  # with omicverse backend
```

## Quick start

```bash
# Map cell type labels from a file (one label per line)
calmate map labels.txt

# Check mapping status
calmate status

# Interactively review unreviewed mappings
calmate review

# Apply verified mappings to a CSV file
calmate apply data.csv --column cell_type
```

## Python API

```python
from calmate import MappingStore, map_labels, apply_labels

# 1. Map a list of labels (populates the mapping store)
store = MappingStore(".calmate/mappings.csv")
map_labels(["beta cell", "T cell", "astrocyte"], store=store, origin="my_dataset")

# 2. Apply reviewed mappings to replace labels
predicted = ["beta cell", "T cell", "astrocyte", "Treg cells"]
result = apply_labels(predicted, store)

result.mapped_labels   # ["type B pancreatic cell", "T cell", "astrocyte", "Treg cells"]
result.label_map       # {"beta cell": "type B pancreatic cell"}
result.unreviewed      # ["Treg cells"]  -- still needs human review
result.unmapped        # []

# 3. Print a ready-made diagnostic message
print(result.message)
# calmate: 1/4 unique label(s) mapped to ontology terms.
#
#   WARNING: 1 label(s) have unreviewed mappings and were NOT replaced:
#     - Treg cells
#   Run `calmate review` to approve or edit them.

# 4. Optionally gate on warnings
if result.has_warnings:
    raise RuntimeError(result.message)
```

## How it works

1. **Direct match**: Each label is checked against Cell Ontology term names and synonyms (case-insensitive). Exact matches are auto-approved.
2. **Semantic match** (optional): Unmatched labels are passed to `omicverse.single.CellOntologyMapper` for embedding-based similarity matching. These suggestions require human review.
3. **Review**: Users approve, edit, or reject mappings via `calmate review` or by editing the CSV directly.

## Configuration

- **Store location**: Defaults to `.calmate/mappings.csv` in the current directory. Override with `--store` flag or `CALMATE_STORE` environment variable.
- **Cache directory**: Ontology files are cached in `.calmate/cache/`. Override with `--cache-dir`.

## License

MIT
