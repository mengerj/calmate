"""CSV-backed mapping store for cell-type -> ontology-term mappings.

The store manages a single CSV file with the following columns:

    reviewed, origin, predicted_label, chosen_match, best_match,
    ontology_id, confidence, timestamp

All public methods work on :class:`pandas.DataFrame` rows that follow
this schema.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

COLUMNS = [
    "reviewed",
    "origin",
    "predicted_label",
    "chosen_match",
    "best_match",
    "ontology_id",
    "confidence",
    "timestamp",
]


def _empty_df() -> pd.DataFrame:
    return pd.DataFrame(columns=COLUMNS)


class MappingStore:
    """Persistent CSV store for cell-type ontology mappings.

    Parameters
    ----------
    path:
        Path to the CSV file.  Created on first write if it does not exist.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    # ------------------------------------------------------------------
    # I/O
    # ------------------------------------------------------------------

    def _ensure_parent(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> pd.DataFrame:
        """Load the mapping CSV into a DataFrame.

        Returns an empty DataFrame with the correct schema when the file
        does not exist yet.
        """
        if not self.path.exists():
            return _empty_df()
        try:
            df = pd.read_csv(self.path)
            for col in COLUMNS:
                if col not in df.columns:
                    df[col] = "" if col not in ("reviewed", "confidence") else None
            return df
        except Exception as exc:
            raise RuntimeError(f"Could not read mapping store at {self.path}") from exc

    def save(self, df: pd.DataFrame) -> None:
        """Persist *df* to the CSV file, creating parent directories."""
        self._ensure_parent()
        df = df[COLUMNS]
        df.to_csv(self.path, index=False)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_mapping_dict(
        self,
        reviewed_only: bool = False,
    ) -> dict[str, str]:
        """Return ``{predicted_label: chosen_match}`` dictionary.

        Parameters
        ----------
        reviewed_only:
            If *True*, only include rows where ``reviewed`` is ``True``.
        """
        df = self.load()
        if df.empty:
            return {}
        if reviewed_only:
            df = df[df["reviewed"].astype(str).str.strip().str.lower().isin(["true", "1", "yes"])]
        return dict(zip(df["predicted_label"], df["chosen_match"]))

    def get_unreviewed(self) -> pd.DataFrame:
        """Return rows that have not yet been reviewed."""
        df = self.load()
        if df.empty:
            return df
        mask = ~df["reviewed"].astype(str).str.strip().str.lower().isin(["true", "1", "yes"])
        return df[mask].reset_index(drop=True)

    def get_reviewed(self) -> pd.DataFrame:
        """Return rows that have been reviewed."""
        df = self.load()
        if df.empty:
            return df
        mask = df["reviewed"].astype(str).str.strip().str.lower().isin(["true", "1", "yes"])
        return df[mask].reset_index(drop=True)

    def has_label(self, predicted_label: str) -> bool:
        """Check whether *predicted_label* already exists in the store."""
        df = self.load()
        if df.empty:
            return False
        return predicted_label in df["predicted_label"].values

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def add_mappings(self, new_rows: list[dict]) -> int:
        """Append new mapping rows, skipping labels that already exist.

        Returns the number of rows actually added.
        """
        if not new_rows:
            return 0

        df = self.load()
        existing_labels = set(df["predicted_label"]) if not df.empty else set()

        to_add = []
        for row in new_rows:
            if row.get("predicted_label") in existing_labels:
                continue
            full_row = {col: row.get(col, "") for col in COLUMNS}
            full_row.setdefault("timestamp", _now_iso())
            if "timestamp" not in row:
                full_row["timestamp"] = _now_iso()
            to_add.append(full_row)

        if not to_add:
            return 0

        new_df = pd.DataFrame(to_add, columns=COLUMNS)
        combined = pd.concat([df, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["predicted_label"], keep="first")
        combined = combined.sort_values("predicted_label").reset_index(drop=True)
        self.save(combined)
        return len(to_add)

    def update_mapping(
        self,
        predicted_label: str,
        *,
        chosen_match: Optional[str] = None,
        ontology_id: Optional[str] = None,
        reviewed: Optional[bool] = None,
    ) -> bool:
        """Update fields for an existing mapping row.

        Returns *True* if the label was found and updated.
        """
        df = self.load()
        if df.empty:
            return False
        mask = df["predicted_label"] == predicted_label
        if not mask.any():
            return False
        if chosen_match is not None:
            df.loc[mask, "chosen_match"] = chosen_match
        if ontology_id is not None:
            df.loc[mask, "ontology_id"] = ontology_id
        if reviewed is not None:
            df.loc[mask, "reviewed"] = reviewed
        df.loc[mask, "timestamp"] = _now_iso()
        self.save(df)
        return True

    def merge_from(self, other: MappingStore, overwrite: bool = False) -> int:
        """Merge mappings from *other* store into this one.

        Parameters
        ----------
        other:
            Another :class:`MappingStore` to import from.
        overwrite:
            If *True*, existing labels are overwritten with the incoming
            values.  Otherwise only new labels are added.

        Returns
        -------
        Number of rows added or updated.
        """
        incoming = other.load()
        if incoming.empty:
            return 0

        df = self.load()
        existing_labels = set(df["predicted_label"]) if not df.empty else set()
        count = 0

        new_rows = []
        for _, row in incoming.iterrows():
            label = row["predicted_label"]
            if label in existing_labels:
                if overwrite:
                    df.loc[df["predicted_label"] == label, COLUMNS] = row[COLUMNS].values
                    count += 1
            else:
                new_rows.append(row)
                count += 1

        if new_rows:
            new_df = pd.DataFrame(new_rows, columns=COLUMNS)
            df = pd.concat([df, new_df], ignore_index=True)

        df = df.sort_values("predicted_label").reset_index(drop=True)
        self.save(df)
        return count

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(self) -> dict:
        """Return a summary dict with counts and origin breakdown."""
        df = self.load()
        total = len(df)
        if total == 0:
            return {"total": 0, "reviewed": 0, "unreviewed": 0, "origins": {}}

        reviewed_mask = df["reviewed"].astype(str).str.strip().str.lower().isin(["true", "1", "yes"])
        n_reviewed = int(reviewed_mask.sum())
        origins = df.groupby("origin").size().to_dict() if "origin" in df.columns else {}
        return {
            "total": total,
            "reviewed": n_reviewed,
            "unreviewed": total - n_reviewed,
            "origins": origins,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
