"""Verify that the omicverse extra is fully importable.

These tests are only collected when omicverse is *installed* as a
package (checked via importlib.metadata, which does NOT import it).
If the package is installed but fails to import -- e.g. because a
transitive dependency like torch_geometric is missing -- the test
fails with a clear error rather than being silently skipped.
"""

from importlib.metadata import PackageNotFoundError, version

import pytest


def _omicverse_installed() -> bool:
    """Check whether omicverse is installed without importing it."""
    try:
        version("omicverse")
        return True
    except PackageNotFoundError:
        return False


needs_omicverse = pytest.mark.skipif(
    not _omicverse_installed(),
    reason="omicverse is not installed (install with: uv add 'calmate[omicverse]')",
)


@needs_omicverse
class TestOmicverseImport:
    def test_omicverse_importable(self):
        """omicverse is installed and can be imported without error.

        Common failure modes include a missing transitive dependency
        (``torch_geometric``) or a version-incompatible one
        (``transformers>=5`` removing symbols omicverse relies on).
        """
        try:
            import omicverse  # noqa: F401
        except ImportError as exc:
            name = getattr(exc, "name", None) or ""
            hint = f"  Try: uv add {name}" if name else ""
            pytest.fail(
                f"omicverse is installed but cannot be imported: {exc}.{hint}"
            )

    def test_cell_ontology_mapper_accessible(self):
        """The CellOntologyMapper class we rely on is reachable."""
        try:
            import omicverse as ov
        except ImportError as exc:
            name = getattr(exc, "name", None) or ""
            hint = f"  Try: uv add {name}" if name else ""
            pytest.fail(
                f"omicverse is installed but cannot be imported: {exc}.{hint}"
            )

        assert hasattr(ov, "single"), "omicverse.single module not found"
        assert hasattr(ov.single, "CellOntologyMapper"), (
            "omicverse.single.CellOntologyMapper not found -- "
            "you may need omicverse >= 1.6"
        )

    def test_sentence_transformers_importable(self):
        """sentence-transformers is required by CellOntologyMapper at runtime."""
        try:
            import sentence_transformers  # noqa: F401
        except ImportError as exc:
            pytest.fail(
                f"sentence-transformers is not installed: {exc}. "
                "Try: uv add sentence-transformers"
            )
