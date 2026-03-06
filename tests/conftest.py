import pytest
from pathlib import Path


@pytest.fixture
def tmp_store(tmp_path: Path) -> Path:
    """Return a path for a temporary mapping store CSV."""
    return tmp_path / "mappings.csv"


@pytest.fixture
def tmp_cache(tmp_path: Path) -> Path:
    """Return a temporary cache directory."""
    cache = tmp_path / "cache"
    cache.mkdir()
    return cache
