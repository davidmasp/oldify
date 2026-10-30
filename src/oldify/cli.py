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
    help="Rename a file or folder to .old, rotating existing backups through .old9.",
)


@app.command()
def main(
    path: Annotated[
        Path,
        typer.Argument(
            help="File or folder to rename. Relative paths are resolved from the current directory.",
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
            help="Delete .old9 when all nine backup slots are occupied.",
        ),
    ] = False,
    nogit: Annotated[
        bool,
        typer.Option(
            "--nogit",
            help="Skip the Git repository/.gitignore requirement and do not update .gitignore.",
        ),
    ] = False,
) -> None:
    """Rename PATH to PATH.old and rotate prior backups up to PATH.old9."""
    try:
        destination = oldify_path(path, delete9=delete9, nogit=nogit)
    except (OldifyError, OSError) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=1) from error

    typer.echo(f"Oldified {path} -> {destination}")
