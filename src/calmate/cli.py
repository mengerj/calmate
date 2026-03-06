"""Click CLI for CALMATE.

Commands
--------
calmate map <file>       -- map labels from a text/csv file
calmate status           -- show mapping store summary
calmate review           -- interactively review unreviewed mappings
calmate apply <file>     -- apply mappings to a CSV column
calmate export [dest]    -- copy the mapping store CSV
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from calmate.mapper import map_labels
from calmate.review import review_interactive
from calmate.store import MappingStore

console = Console()

DEFAULT_STORE = ".calmate/mappings.csv"


def _resolve_store(ctx: click.Context) -> MappingStore:
    return MappingStore(ctx.obj["store"])


# ------------------------------------------------------------------
# Root group
# ------------------------------------------------------------------


@click.group()
@click.option(
    "--store",
    type=click.Path(),
    default=None,
    envvar="CALMATE_STORE",
    help=f"Path to the mapping CSV.  [default: {DEFAULT_STORE}]",
)
@click.version_option(package_name="calmate")
@click.pass_context
def cli(ctx: click.Context, store: str | None) -> None:
    """CALMATE -- Cell Annotation Label Mapping with Assisted Term Editing."""
    ctx.ensure_object(dict)
    ctx.obj["store"] = store or DEFAULT_STORE


# ------------------------------------------------------------------
# map
# ------------------------------------------------------------------


@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--column", "-c", default=None, help="Column name when FILE is a CSV/TSV.")
@click.option("--origin", "-o", default="unknown", help="Provenance tag for new mappings.")
@click.option("--cache-dir", type=click.Path(), default=None, help="Ontology / model cache directory.")
@click.option("--force", is_flag=True, help="Re-map labels that already exist in the store.")
@click.option(
    "--backend", "-b", default="omicverse",
    help='Auto-mapping backend name, or "none" to skip.  [default: omicverse]',
)
@click.option(
    "--backend-option", "backend_options", multiple=True,
    help="KEY=VALUE option forwarded to the backend (repeatable).",
)
@click.pass_context
def map_cmd(
    ctx: click.Context,
    file: str,
    column: str | None,
    origin: str,
    cache_dir: str | None,
    force: bool,
    backend: str,
    backend_options: tuple[str, ...],
) -> None:
    """Map cell-type labels to Cell Ontology terms.

    FILE can be a plain text file (one label per line) or a CSV/TSV.
    When a CSV/TSV is given, use --column to specify which column holds the labels.
    """
    labels = _read_labels(file, column)
    if not labels:
        console.print("[red]No labels found in input file.[/red]")
        raise SystemExit(1)

    console.print(f"Read [bold]{len(labels)}[/bold] unique label(s) from {file}")

    kwargs = _parse_backend_options(backend_options)

    store = _resolve_store(ctx)
    map_labels(
        labels,
        store=store,
        cache_dir=cache_dir,
        origin=origin,
        force=force,
        backend=backend,
        **kwargs,
    )


# ------------------------------------------------------------------
# status
# ------------------------------------------------------------------


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show a summary of the mapping store."""
    store = _resolve_store(ctx)
    if not store.path.exists():
        console.print(f"[yellow]No store found at {store.path}[/yellow]")
        return

    info = store.summary()

    table = Table(title="CALMATE Mapping Store", show_lines=True)
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")

    table.add_row("Store path", str(store.path))
    table.add_row("Total mappings", str(info["total"]))
    table.add_row("Reviewed", f"[green]{info['reviewed']}[/green]")
    table.add_row("Unreviewed", f"[yellow]{info['unreviewed']}[/yellow]")

    if info["origins"]:
        origins_str = "\n".join(f"  {k}: {v}" for k, v in sorted(info["origins"].items()))
        table.add_row("Origins", origins_str)

    console.print(table)

    # Show unreviewed labels if any
    unreviewed = store.get_unreviewed()
    if not unreviewed.empty:
        console.print()
        ur_table = Table(title="Unreviewed Mappings", show_lines=False)
        ur_table.add_column("Label", style="bold")
        ur_table.add_column("Suggested Match")
        ur_table.add_column("Origin")
        for _, row in unreviewed.iterrows():
            chosen = _safe_str(row["chosen_match"])
            best = _safe_str(row["best_match"])
            match = chosen if chosen else best if best else "(none)"
            ur_table.add_row(
                _safe_str(row["predicted_label"]),
                match,
                _safe_str(row.get("origin", "")),
            )
        console.print(ur_table)


# ------------------------------------------------------------------
# review
# ------------------------------------------------------------------


@cli.command()
@click.option("--cache-dir", type=click.Path(), default=None, help="Ontology cache directory.")
@click.pass_context
def review(ctx: click.Context, cache_dir: str | None) -> None:
    """Interactively review unreviewed mappings."""
    store = _resolve_store(ctx)
    if not store.path.exists():
        console.print(f"[yellow]No store found at {store.path}[/yellow]")
        return
    review_interactive(store, cache_dir=cache_dir)


# ------------------------------------------------------------------
# apply
# ------------------------------------------------------------------


@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--column", "-c", required=True, help="Column containing cell-type labels.")
@click.option("--output", "-o", type=click.Path(), default=None, help="Output file path.  [default: stdout]")
@click.option("--reviewed-only/--all", default=True, help="Only use reviewed mappings.")
@click.pass_context
def apply(
    ctx: click.Context,
    file: str,
    column: str,
    output: str | None,
    reviewed_only: bool,
) -> None:
    """Apply verified mappings to a CSV file.

    Adds a ``<column>_mapped`` column with the ontology-mapped labels.
    """
    import pandas as pd

    store = _resolve_store(ctx)
    mapping_dict = store.get_mapping_dict(reviewed_only=reviewed_only)

    if not mapping_dict:
        console.print("[yellow]No mappings available to apply.[/yellow]")
        raise SystemExit(1)

    sep = "\t" if file.endswith((".tsv", ".tab")) else ","
    df = pd.read_csv(file, sep=sep)

    if column not in df.columns:
        console.print(f"[red]Column '{column}' not found in {file}.[/red]")
        raise SystemExit(1)

    mapped_col = f"{column}_mapped"
    df[mapped_col] = df[column].map(lambda x: mapping_dict.get(x, x))

    n_mapped = int((df[column] != df[mapped_col]).sum())
    console.print(f"Mapped [green]{n_mapped}[/green] / {len(df)} cell(s).")

    if output:
        df.to_csv(output, sep=sep, index=False)
        console.print(f"Written to {output}")
    else:
        click.echo(df.to_csv(sep=sep, index=False))


# ------------------------------------------------------------------
# export
# ------------------------------------------------------------------


@cli.command()
@click.argument("dest", type=click.Path(), default="calmate_mappings.csv")
@click.pass_context
def export(ctx: click.Context, dest: str) -> None:
    """Export the mapping store to a standalone CSV file."""
    store = _resolve_store(ctx)
    if not store.path.exists():
        console.print(f"[yellow]No store found at {store.path}[/yellow]")
        return
    shutil.copy2(store.path, dest)
    console.print(f"Exported to [bold]{dest}[/bold]")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _parse_backend_options(options: tuple[str, ...]) -> dict[str, str]:
    """Parse ``KEY=VALUE`` pairs into a dict."""
    result: dict[str, str] = {}
    for opt in options:
        if "=" not in opt:
            raise click.BadParameter(
                f"Expected KEY=VALUE format, got: {opt!r}",
                param_hint="--backend-option",
            )
        key, _, value = opt.partition("=")
        result[key.strip()] = value.strip()
    return result


def _safe_str(val: object) -> str:
    """Coerce a value to str, treating NaN/None as empty string."""
    import math
    if val is None:
        return ""
    if isinstance(val, float) and math.isnan(val):
        return ""
    return str(val)


def _read_labels(file: str, column: str | None) -> list[str]:
    """Read unique non-empty labels from a text file or CSV column."""
    path = Path(file)
    suffix = path.suffix.lower()

    if suffix in (".csv", ".tsv", ".tab"):
        import pandas as pd

        sep = "\t" if suffix in (".tsv", ".tab") else ","
        df = pd.read_csv(path, sep=sep)
        if column is None:
            if len(df.columns) == 1:
                column = df.columns[0]
            else:
                raise click.UsageError(
                    f"CSV has {len(df.columns)} columns -- use --column to specify which one."
                )
        if column not in df.columns:
            raise click.UsageError(f"Column '{column}' not found.  Available: {list(df.columns)}")
        raw = df[column].dropna().astype(str).unique().tolist()
    else:
        raw = path.read_text().splitlines()

    return sorted({l.strip() for l in raw if l.strip()})
