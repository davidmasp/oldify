"""File and folder validation and numbered backup rotation."""

from __future__ import annotations

import shutil
from pathlib import Path

from .errors import OldifyError
from .gitignore import _append_gitignore, _gitignore_entry, _repo_root


def _backup_path(path: Path, number: int) -> Path:
    suffix = ".old" if number == 1 else f".old{number}"
    return path.with_name(f"{path.name}{suffix}")


def oldify_path(
    path: Path,
    *,
    delete9: bool = False,
    nogit: bool = False,
    cwd: Path | None = None,
) -> Path:
    """Rotate a file or folder and return its new ``.old`` path."""
    cwd = (cwd or Path.cwd()).resolve()
    path = path.expanduser()
    if not path.is_absolute():
        path = cwd / path

    if not path.exists():
        raise OldifyError(f"Path does not exist: {path}")
    is_folder = path.is_dir()
    if not is_folder and not path.is_file():
        raise OldifyError(f"Path is not a file or folder: {path}")

    gitignore: Path | None = None
    if not nogit:
        _repo_root(cwd)
        gitignore = cwd / ".gitignore"
        if not gitignore.is_file():
            raise OldifyError(f"Current directory has no .gitignore file: {cwd}")

    occupied = 0
    for number in range(1, 10):
        backup = _backup_path(path, number)
        if not backup.exists() and not backup.is_symlink():
            break
        if not (backup.is_dir() if is_folder else backup.is_file()):
            kind = "folder" if is_folder else "file"
            raise OldifyError(f"Backup path is not a {kind}: {backup}")
        occupied = number

    if occupied == 9 and not delete9:
        raise OldifyError(
            f"Cannot oldify {path}: backups already exist through "
            f"{_backup_path(path, 9).name}. Use --delete9 to replace the oldest backup."
        )

    if occupied == 9:
        oldest = _backup_path(path, 9)
        if oldest.is_dir() and not oldest.is_symlink():
            shutil.rmtree(oldest)
        else:
            oldest.unlink()
        highest_to_move = 8
    else:
        highest_to_move = occupied

    for number in range(highest_to_move, 0, -1):
        _backup_path(path, number).rename(_backup_path(path, number + 1))

    destination = _backup_path(path, 1)
    path.rename(destination)

    if gitignore is not None:
        for number in range(1, highest_to_move + 2):
            entry = _gitignore_entry(_backup_path(path, number), gitignore.parent)
            _append_gitignore(gitignore, entry)

    return destination


def oldify_folder(
    folder: Path,
    *,
    delete9: bool = False,
    nogit: bool = False,
    cwd: Path | None = None,
) -> Path:
    """Backward-compatible entry point for :func:`oldify_path`."""
    return oldify_path(folder, delete9=delete9, nogit=nogit, cwd=cwd)
