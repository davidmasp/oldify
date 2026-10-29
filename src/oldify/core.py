"""Folder validation and numbered backup rotation."""

from __future__ import annotations

import shutil
from pathlib import Path

from .errors import OldifyError
from .gitignore import _append_gitignore, _gitignore_entry, _repo_root


def _backup_path(folder: Path, number: int) -> Path:
    suffix = ".old" if number == 1 else f".old{number}"
    return folder.with_name(f"{folder.name}{suffix}")


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
        for number in range(1, highest_to_move + 2):
            entry = _gitignore_entry(_backup_path(folder, number), gitignore.parent)
            _append_gitignore(gitignore, entry)

    return destination
