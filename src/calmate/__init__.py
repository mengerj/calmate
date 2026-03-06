"""CALMATE -- Cell Annotation Label Mapping with Assisted Term Editing."""

__version__ = "0.1.0"

from calmate.backends import AutoMapBackend, MapSuggestion, get_backend
from calmate.mapper import map_labels
from calmate.store import MappingStore

__all__ = [
    "AutoMapBackend",
    "MapSuggestion",
    "MappingStore",
    "get_backend",
    "map_labels",
    "__version__",
]
