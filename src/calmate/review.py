"""Interactive terminal-based review workflow for unreviewed mappings.

Presents each unreviewed mapping with context and lets the user:
  [a]  approve -- accept the suggested ``chosen_match`` as-is
  [e]  edit    -- type a replacement ``chosen_match`` (empty input cancels)
  [b]  back   -- go back to the previous mapping
  [s]  skip    -- leave the mapping unreviewed for now
  [q]  quit    -- stop reviewing (remaining entries stay unreviewed)
"""

from __future__ import annotations

import math
import warnings
from pathlib import Path
from typing import Optional

import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from calmate.ontology import build_label_index, download_cl_ontology, load_ontology, map_string_to_term
from calmate.store import MappingStore

console = Console()


def _str(val: object) -> str:
    """Coerce a value to str, treating NaN/None as empty string."""
    if val is None:
        return ""
    if isinstance(val, float) and math.isnan(val):
        return ""
    return str(val)


def review_interactive(
    store: MappingStore,
    cache_dir: Optional[str | Path] = None,
) -> int:
    """Launch an interactive review session for unreviewed mappings.

    Parameters
    ----------
    store:
        The mapping store to review.
    cache_dir:
        Ontology cache dir (used to validate edited terms).  Defaults to
        a ``cache`` sibling of the store file.

    Returns
    -------
    Number of mappings approved during this session.
    """
    unreviewed = store.get_unreviewed()
    if unreviewed.empty:
        console.print("[green]Nothing to review -- all mappings are approved![/green]")
        return 0

    # Load ontology for validation of user edits
    if cache_dir is None:
        cache_dir = store.path.parent / "cache"
    cache_dir = Path(cache_dir)

    label_index: dict | None = None
    try:
        owl_path = download_cl_ontology(cache_dir)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ont = load_ontology(owl_path)
            label_index = build_label_index(ont)
    except Exception:
        console.print(
            "[yellow]Could not load ontology for validation -- "
            "edited terms will not be checked.[/yellow]"
        )

    total = len(unreviewed)
    approved = 0

    console.print()
    console.print(
        Panel(
            f"[bold]{total}[/bold] unreviewed mapping(s).  "
            r"Commands: [green]\[a]pprove[/green]  [cyan]\[e]dit[/cyan]  "
            r"[magenta]\[b]ack[/magenta]  [yellow]\[s]kip[/yellow]  [red]\[q]uit[/red]",
            title="calmate review",
        )
    )
    console.print()

    rows = list(unreviewed.iterrows())
    pos = 0

    while pos < len(rows):
        idx, row = rows[pos]
        label = _str(row["predicted_label"])
        best = _str(row["best_match"])
        chosen = _str(row["chosen_match"])
        origin = _str(row.get("origin", ""))
        confidence = _str(row.get("confidence", ""))

        _print_mapping_card(label, chosen, best, origin, confidence, pos + 1, total)

        while True:
            action = (
                console.input(r"\[a]pprove / \[e]dit / \[b]ack / \[s]kip / \[q]uit > ")
                .strip()
                .lower()
            )

            if action in ("a", "approve"):
                final_match = chosen if chosen else best
                ontology_id = ""
                if label_index and final_match:
                    term = map_string_to_term(final_match, label_index)
                    ontology_id = term.id if term else ""
                store.update_mapping(
                    label,
                    chosen_match=final_match,
                    ontology_id=ontology_id,
                    reviewed=True,
                )
                approved += 1
                console.print(f"  [green]Approved:[/green] {label} -> {final_match}")
                pos += 1
                break

            elif action in ("e", "edit"):
                new_match = console.input(
                    "  Enter corrected ontology term (empty to cancel): "
                ).strip()
                if not new_match:
                    console.print("  [yellow]Edit cancelled.[/yellow]")
                    continue

                ontology_id = ""
                if label_index:
                    term = map_string_to_term(new_match, label_index)
                    if term:
                        ontology_id = term.id
                        console.print(f"  [green]Validated:[/green] {term.name} ({term.id})")
                    else:
                        console.print(
                            f"  [yellow]Warning:[/yellow] '{new_match}' not found in ontology. "
                            "Saving anyway."
                        )

                store.update_mapping(
                    label,
                    chosen_match=new_match,
                    ontology_id=ontology_id,
                    reviewed=True,
                )
                approved += 1
                console.print(f"  [green]Approved:[/green] {label} -> {new_match}")
                pos += 1
                break

            elif action in ("b", "back"):
                if pos == 0:
                    console.print("  [yellow]Already at the first mapping.[/yellow]")
                    continue
                # Undo approval if the previous mapping was approved in this session
                prev_idx, prev_row = rows[pos - 1]
                prev_label = _str(prev_row["predicted_label"])
                current_data = store.get_all()
                mask = current_data["predicted_label"] == prev_label
                if mask.any() and current_data.loc[mask, "reviewed"].iloc[0]:
                    store.update_mapping(prev_label, reviewed=False)
                    approved = max(0, approved - 1)
                    console.print(f"  [magenta]Going back to:[/magenta] {prev_label}")
                    console.print(
                        f"  [dim](previous approval undone so you can re-decide)[/dim]"
                    )
                else:
                    console.print(f"  [magenta]Going back to:[/magenta] {prev_label}")
                pos -= 1
                break

            elif action in ("s", "skip"):
                console.print("  [yellow]Skipped.[/yellow]")
                pos += 1
                break

            elif action in ("q", "quit"):
                console.print(f"\n[bold]Session ended.[/bold]  Approved {approved}/{total} mapping(s).")
                return approved

            else:
                console.print("  [red]Unknown command.[/red] Use a/e/b/s/q.")

        console.print()

    console.print(f"[bold green]Review complete.[/bold green]  Approved {approved}/{total} mapping(s).")
    return approved


def _print_mapping_card(
    label: str,
    chosen: str,
    best: str,
    origin: str,
    confidence: object,
    current: int,
    total: int,
) -> None:
    """Print a rich panel summarising one mapping for review."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("key", style="bold")
    table.add_column("value")
    table.add_row("Label", label)
    table.add_row("Suggested match", chosen if chosen else best)
    if best and best != chosen:
        table.add_row("Best auto-match", best)
    if origin:
        table.add_row("Origin", str(origin))
    if confidence:
        table.add_row("Confidence", str(confidence))

    console.print(Panel(table, title=f"[{current}/{total}]", border_style="blue"))
