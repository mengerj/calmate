"""Auto-mapping backend registry.

To add a new backend, create a module in this package, implement
:class:`~calmate.backends.base.AutoMapBackend`, and register it in
:data:`BACKEND_REGISTRY` below.  See :mod:`calmate.backends.base` for
the full contributor guide.
"""

from __future__ import annotations

from typing import Union

from calmate.backends.base import AutoMapBackend, MapSuggestion
from calmate.backends.omicverse import OmicverseBackend

BACKEND_REGISTRY: dict[str, type[AutoMapBackend]] = {
    "omicverse": OmicverseBackend,
}

__all__ = [
    "AutoMapBackend",
    "MapSuggestion",
    "OmicverseBackend",
    "BACKEND_REGISTRY",
    "get_backend",
]


def get_backend(name_or_instance: Union[str, AutoMapBackend, None]) -> AutoMapBackend | None:
    """Resolve a backend by name string or pass through an instance.

    Parameters
    ----------
    name_or_instance:
        - A string key from :data:`BACKEND_REGISTRY` (e.g. ``"omicverse"``).
        - An already-instantiated :class:`AutoMapBackend`.
        - ``None`` or ``"none"`` to disable auto-mapping.

    Returns
    -------
    An :class:`AutoMapBackend` instance, or *None* if auto-mapping is
    disabled.

    Raises
    ------
    ValueError
        If the string does not match any registered backend.
    """
    if name_or_instance is None or (isinstance(name_or_instance, str) and name_or_instance.lower() == "none"):
        return None

    if isinstance(name_or_instance, AutoMapBackend):
        return name_or_instance

    name = name_or_instance.lower()
    if name not in BACKEND_REGISTRY:
        available = ", ".join(sorted(BACKEND_REGISTRY)) or "(none)"
        raise ValueError(
            f"Unknown backend '{name}'. Available: {available}"
        )
    return BACKEND_REGISTRY[name]()
