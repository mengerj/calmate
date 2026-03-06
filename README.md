# CALMATE -- Cell Annotation Label Mapping with Assisted Term Editing

A Python package that maps free-text cell type labels to standardized [Cell Ontology](https://obofoundry.org/ontology/cl.html) terms, with a human-in-the-loop review workflow.

## Features

- **Two-stage mapping pipeline**: Fast direct matching via `pronto` (exact name + synonyms), with optional semantic matching via `omicverse`
- **Human-in-the-loop review**: Interactive CLI for reviewing and approving automated mappings
- **Growing mapping database**: CSV-based store that accumulates verified mappings across projects
- **Transparent audit trail**: Every mapping records its origin, confidence, review status, and timestamp

## Installation

```bash
uv add calmate
```

With the omicverse auto-mapping backend:

```bash
uv add "calmate[omicverse]"
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
from calmate import MappingStore, map_labels

# Map a list of labels
store = MappingStore(".calmate/mappings.csv")
map_labels(["beta cell", "T cell", "astrocyte"], store=store, origin="my_dataset")

# Load and apply verified mappings
mappings = store.get_mapping_dict(reviewed_only=True)
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
