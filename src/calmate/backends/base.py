"""Base classes and registry for auto-mapping backends.

This module defines the contract that every auto-mapping backend must
follow.  If you want to add a new backend to calmate, this is the only
file you need to read.

Quick start for contributors
-----------------------------

1. Create a new file in ``src/calmate/backends/`` (e.g. ``my_backend.py``).

2. Subclass :class:`AutoMapBackend` and implement the two required
   methods::

       from calmate.backends.base import AutoMapBackend, MapSuggestion

       class MyBackend(AutoMapBackend):
           name = "my_backend"

           def is_available(self) -> bool:
               # Return False if required packages are not installed.
               try:
                   import some_library
                   return True
               except ImportError:
                   return False

           def map(self, labels, cache_dir, **kwargs):
               # Return a list of MapSuggestion for every label you
               # could match.  Omit labels you cannot resolve.
               ...

3. Register your backend in ``src/calmate/backends/__init__.py`` by
   adding it to :data:`BACKEND_REGISTRY`::

       from calmate.backends.my_backend import MyBackend
       BACKEND_REGISTRY["my_backend"] = MyBackend

That's it -- calmate will now accept ``--backend my_backend`` on the CLI
and ``backend="my_backend"`` in the Python API.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class MapSuggestion:
    """A single suggested mapping returned by a backend.

    Attributes
    ----------
    predicted_label:
        The original free-text label that was submitted.
    suggested_match:
        The ontology term name suggested by the backend.
    ontology_id:
        The ontology term ID (e.g. ``CL:0000084``), or ``""`` if the
        backend could not determine one.
    confidence:
        A float between 0 and 1 indicating the backend's confidence.
        Backends that cannot provide a meaningful score should use 0.0.
    """

    predicted_label: str
    suggested_match: str
    ontology_id: str = ""
    confidence: float = 0.0


class AutoMapBackend(ABC):
    """Abstract base class for automated cell-type mapping backends.

    Every backend must set a :attr:`name` class attribute (a short
    string used as the registry key, e.g. ``"omicverse"``) and
    implement :meth:`map` and :meth:`is_available`.
    """

    name: str

    @abstractmethod
    def is_available(self) -> bool:
        """Return ``True`` if this backend's runtime dependencies are
        installed and it is ready to use.

        This method must **not** import heavy libraries at module level;
        instead do a lazy ``try: import ... except ImportError`` inside
        the method body.
        """
        ...

    @abstractmethod
    def map(
        self,
        labels: list[str],
        cache_dir: Path,
        **kwargs: object,
    ) -> list[MapSuggestion]:
        """Map *labels* to ontology terms.

        Parameters
        ----------
        labels:
            Non-empty list of free-text cell-type labels to resolve.
        cache_dir:
            Directory where the backend may cache downloaded models,
            ontology files, etc.
        **kwargs:
            Backend-specific options (e.g. ``model_name``).  Passed
            through from the CLI via ``--backend-option key=value``.

        Returns
        -------
        A list of :class:`MapSuggestion` instances -- one for each
        label that could be matched.  Labels that the backend could
        not resolve should simply be *omitted* from the list (do not
        return a suggestion with an empty ``suggested_match``).
        """
        ...
