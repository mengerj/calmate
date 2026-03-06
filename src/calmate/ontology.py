"""Ontology download, indexing, and term lookup using pronto.

Provides utilities to:
- Download the Cell Ontology (CL) OWL file
- Build a case-insensitive label+synonym index
- Look up free-text strings against the index
"""

from __future__ import annotations

import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

import pronto

CL_OWL_URL = "https://purl.obolibrary.org/obo/cl/cl-base.owl"
CL_JSON_URL = "https://purl.obolibrary.org/obo/cl/cl-base.json"


def download_cl_ontology(
    cache_dir: Path,
    cl_url: str = CL_OWL_URL,
    force_download: bool = False,
) -> Path:
    """Download Cell Ontology if not already cached.

    Parameters
    ----------
    cache_dir:
        Directory to store the downloaded file.
    cl_url:
        URL of the ontology release.
    force_download:
        Re-download even when the file already exists.

    Returns
    -------
    Path to the local ontology file.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    local_path = cache_dir / Path(cl_url).name

    if local_path.exists() and local_path.stat().st_size > 0 and not force_download:
        return local_path

    try:
        urllib.request.urlretrieve(cl_url, local_path)
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Failed to download ontology from {cl_url}") from exc
    except Exception as exc:
        if local_path.exists():
            local_path.unlink()
        raise RuntimeError(f"Error downloading ontology: {exc}") from exc

    if not local_path.exists() or local_path.stat().st_size == 0:
        raise RuntimeError("Downloaded ontology file is empty or missing")

    return local_path


def _normalize(text: str) -> str:
    """Lowercase and collapse whitespace for robust dictionary keys."""
    return " ".join(text.lower().split()) if text else ""


def build_label_index(ont: pronto.Ontology) -> dict[str, pronto.Term]:
    """Build a normalized-string -> Term index from names and synonyms.

    Only non-obsolete terms are included.  The first term encountered for
    a given normalized key wins (setdefault).
    """
    idx: dict[str, pronto.Term] = {}
    for term in ont.terms():
        if term.obsolete:
            continue
        if term.name:
            idx.setdefault(_normalize(term.name), term)
        for syn in term.synonyms:
            syn_text = getattr(syn, "description", None) or getattr(syn, "desc", None)
            if not syn_text:
                try:
                    syn_text = str(syn)
                except Exception:
                    syn_text = None
            if syn_text:
                idx.setdefault(_normalize(syn_text), term)
    return idx


def map_string_to_term(
    text: str,
    label_index: dict[str, pronto.Term],
) -> Optional[pronto.Term]:
    """Look up a free-text string in the label index (case-insensitive)."""
    if not text or not text.strip():
        return None
    return label_index.get(_normalize(text))


def load_ontology(path: str | Path) -> pronto.Ontology:
    """Load an ontology file and return the pronto Ontology object."""
    try:
        return pronto.Ontology(str(path))
    except Exception as exc:
        raise RuntimeError(f"Failed to load ontology from {path}") from exc
