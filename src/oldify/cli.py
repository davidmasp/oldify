"""Command-line interface for rotating files and folders into .old backups."""

from __future__ import annotations

from importlib.metadata import version as package_version
from pathlib import Path
from typing import Annotated

import typer

from .core import oldify_path
from .errors import OldifyError


def _show_version(value: bool) -> bool:
    if value:
        typer.echo(f"oldify {package_version('oldify')}")
        raise typer.Exit()
    return value


app = typer.Typer(
    add_completion=False,
    help="Back up a file or folder to .old, optionally as .tar.gz, rotating through .old9.",
)


@app.command()
def main(
    path: Annotated[
        Path,
        typer.Argument(
            help="File or folder to back up. Relative paths are resolved from the current directory.",
        ),
    ],
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_show_version,
            is_eager=True,
            help="Show the installed version and exit.",
        ),
    ] = False,
    delete9: Annotated[
        bool,
        typer.Option(
            "--delete9",
            help="Delete the oldest backup when all nine slots in the selected chain are occupied.",
        ),
    ] = False,
    nogit: Annotated[
        bool,
        typer.Option(
            "--nogit",
            help="Skip the Git repository/.gitignore requirement and do not update .gitignore.",
        ),
    ] = False,
    date: Annotated[
        bool,
        typer.Option("--date", help="Include today's local date in backup names (YYYYMMDD)."),
    ] = False,
    targz: Annotated[
        bool,
        typer.Option("--targz", help="Store the backup as a gzip-compressed tar archive (.tar.gz)."),
    ] = False,
    compression_level: Annotated[
        int | None,
        typer.Option(
            "--compression-level",
            help="Gzip compression level, 0 through 9 (default: 9). Requires --targz.",
        ),
    ] = None,
) -> None:
    """Back up PATH and rotate prior backups up to the ninth slot."""
    try:
        destination = oldify_path(
            path, delete9=delete9, nogit=nogit, date=date,
            targz=targz, compression_level=compression_level,
        )
    except (OldifyError, OSError) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=1) from error

    typer.echo(f"Oldified {path} -> {destination}")
