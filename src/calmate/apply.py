"""Apply reviewed mappings to a list of cell-type labels.

Provides :func:`apply_labels` which returns a :class:`MappingResult`
containing the mapped labels, a summary of what changed, and
ready-to-print diagnostics about unreviewed or unmapped labels.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from calmate.store import MappingStore


@dataclass
class MappingResult:
    """Result of applying ontology mappings to a list of labels.

    Attributes
    ----------
    mapped_labels:
        Output list (same length and order as the input).  Labels with a
        reviewed mapping are replaced; all others are kept as-is.
    label_map:
        ``{original: mapped}`` for input labels that were actually
        replaced with a *different* string.
    unreviewed:
        Labels that exist in the store but have not been reviewed yet.
    unmapped:
        Labels that are not present in the store at all.
    n_unique:
        Number of distinct labels in the original input.
    """

    mapped_labels: list[str]
    label_map: dict[str, str] = field(default_factory=dict)
    unreviewed: list[str] = field(default_factory=list)
    unmapped: list[str] = field(default_factory=list)
    n_unique: int = 0

    @property
    def has_warnings(self) -> bool:
        """True when there are unreviewed or unmapped labels."""
        return bool(self.unreviewed or self.unmapped)

    @property
    def message(self) -> str:
        """Human-readable summary suitable for ``print()`` or ``logging.info()``.

        Always starts with a one-line status, followed by warning blocks
        for unreviewed / unmapped labels when present.
        """
        n_replaced = len(self.label_map)
        lines: list[str] = [
            f"calmate: {n_replaced}/{self.n_unique} unique label(s) mapped to ontology terms."
        ]

        if self.unreviewed:
            lines.append("")
            lines.append(
                f"  WARNING: {len(self.unreviewed)} label(s) have unreviewed mappings "
                "and were NOT replaced:"
            )
            for lbl in self.unreviewed:
                lines.append(f"    - {lbl}")
            lines.append("  Run `calmate review` to approve or edit them.")

        if self.unmapped:
            lines.append("")
            lines.append(
                f"  WARNING: {len(self.unmapped)} label(s) are not in the mapping store at all:"
            )
            for lbl in self.unmapped:
                lines.append(f"    - {lbl}")
            lines.append("  Run `calmate map` to add them.")

        return "\n".join(lines)


def apply_labels(
    labels: list[str],
    store: MappingStore,
    *,
    reviewed_only: bool = True,
) -> MappingResult:
    """Replace predicted labels with their reviewed ontology mappings.

    Parameters
    ----------
    labels:
        Input labels (e.g. from a model prediction or dataset column).
    store:
        A :class:`MappingStore` containing the mapping database.
    reviewed_only:
        When *True* (default), only reviewed mappings are used for
        replacement.  Unreviewed labels stay unchanged and appear in
        :attr:`MappingResult.unreviewed`.

    Returns
    -------
    MappingResult
        Structured result with the mapped labels, a change log, and
        diagnostics.  Call ``result.message`` for a printable summary
        or check ``result.has_warnings`` to decide whether to raise.
    """
    replacement_map = store.get_mapping_dict(reviewed_only=reviewed_only)
    all_known = store.get_mapping_dict(reviewed_only=False)

    unique_labels = sorted(set(labels))
    unreviewed: list[str] = []
    unmapped: list[str] = []

    for lbl in unique_labels:
        if lbl in replacement_map:
            continue
        if lbl in all_known:
            unreviewed.append(lbl)
        else:
            unmapped.append(lbl)

    label_map: dict[str, str] = {}
    mapped: list[str] = []
    for lbl in labels:
        if lbl in replacement_map:
            mapped_lbl = replacement_map[lbl]
            mapped.append(mapped_lbl)
            if lbl not in label_map and mapped_lbl != lbl:
                label_map[lbl] = mapped_lbl
        else:
            mapped.append(lbl)

    return MappingResult(
        mapped_labels=mapped,
        label_map=label_map,
        unreviewed=unreviewed,
        unmapped=unmapped,
        n_unique=len(unique_labels),
    )
