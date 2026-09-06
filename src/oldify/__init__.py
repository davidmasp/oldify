"""Command-line interface for rotating folders into ``.old`` backups."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Annotated

from git import InvalidGitRepositoryError, NoSuchPathError, Repo
import typer

app = typer.Typer(
    add_completion=False,
    help="Rename a folder to .old, rotating existing backups through .old9.",
)


class OldifyError(Exception):
    """An expected error that can be shown directly to a CLI user."""


def _backup_path(folder: Path, number: int) -> Path:
    suffix = ".old" if number == 1 else f".old{number}"
    return folder.with_name(f"{folder.name}{suffix}")


def _gitignore_entry(folder: Path, cwd: Path) -> str:
    old_folder = _backup_path(folder, 1)
    try:
        return old_folder.resolve().relative_to(cwd.resolve()).as_posix()
    except ValueError:
        return old_folder.resolve().as_posix()


def _append_gitignore(gitignore: Path, entry: str) -> None:
    needs_leading_newline = gitignore.stat().st_size > 0
    if needs_leading_newline:
        with gitignore.open("rb") as stream:
            stream.seek(-1, 2)
            needs_leading_newline = stream.read(1) not in {b"\n", b"\r"}

    with gitignore.open("a", encoding="utf-8") as stream:
        if needs_leading_newline:
            stream.write("\n")
        stream.write(f"{entry}\n")


def _repo_root(cwd: Path) -> Path:
    try:
        repo = Repo(cwd, search_parent_directories=True)
    except (InvalidGitRepositoryError, NoSuchPathError) as error:
        raise OldifyError(f"Current directory is not a Git repository: {cwd}") from error

    if repo.working_tree_dir is None:
        raise OldifyError(f"Current directory is not a Git work tree: {cwd}")

    return Path(repo.working_tree_dir).resolve()


def oldify_folder(
    folder: Path,
    *,
    delete9: bool = False,
    nogit: bool = False,
    cwd: Path | None = None,
) -> Path:
    """Oldify *folder* and return the path of the newly created ``.old`` folder."""
    cwd = (cwd or Path.cwd()).resolve()
    folder = folder.expanduser()
    if not folder.is_absolute():
        folder = cwd / folder

    if not folder.exists():
        raise OldifyError(f"Folder does not exist: {folder}")
    if not folder.is_dir():
        raise OldifyError(f"Path is not a folder: {folder}")

    gitignore: Path | None = None
    if not nogit:
        _repo_root(cwd)
        gitignore = cwd / ".gitignore"
        if not gitignore.is_file():
            raise OldifyError(f"Current directory has no .gitignore file: {cwd}")

    occupied = 0
    for number in range(1, 10):
        backup = _backup_path(folder, number)
        if not backup.exists():
            break
        if not backup.is_dir():
            raise OldifyError(f"Backup path is not a folder: {backup}")
        occupied = number

    if occupied == 9 and not delete9:
        raise OldifyError(
            f"Cannot oldify {folder}: backups already exist through "
            f"{_backup_path(folder, 9).name}. Use --delete9 to replace the oldest backup."
        )

    if occupied == 9:
        shutil.rmtree(_backup_path(folder, 9))
        highest_to_move = 8
    else:
        highest_to_move = occupied

    for number in range(highest_to_move, 0, -1):
        _backup_path(folder, number).rename(_backup_path(folder, number + 1))

    destination = _backup_path(folder, 1)
    folder.rename(destination)

    if gitignore is not None:
        _append_gitignore(gitignore, _gitignore_entry(folder, gitignore.parent))

    return destination


@app.command()
def main(
    folder: Annotated[
        Path,
        typer.Argument(
            help="Folder to rename. Relative paths are resolved from the current directory.",
        ),
    ],
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
    """Rename FOLDER to FOLDER.old and rotate prior backups up to FOLDER.old9."""
    try:
        destination = oldify_folder(folder, delete9=delete9, nogit=nogit)
    except (OldifyError, OSError) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=1) from error

    typer.echo(f"Oldified {folder} -> {destination}")
