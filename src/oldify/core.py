"""File and folder validation and numbered backup rotation."""

from __future__ import annotations

import os
import shutil
import tarfile
import tempfile
import zlib
from datetime import date as local_date
from pathlib import Path

from .errors import OldifyError
from .gitignore import _append_gitignore, _gitignore_entry, _repo_root


def _backup_path(path: Path, number: int, *, targz: bool = False) -> Path:
    suffix = ".old" if number == 1 else f".old{number}"
    if targz:
        suffix += ".tar.gz"
    return path.with_name(f"{path.name}{suffix}")


def _prepare_archive(path: Path, compression_level: int) -> Path:
    """Finish and flush a sibling archive before any existing paths change."""
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=f".{path.name}.", suffix=".tar.gz.tmp", delete=False
        ) as stream:
            temporary = Path(stream.name)
            with tarfile.open(
                fileobj=stream,
                mode="w:gz",
                compresslevel=compression_level,
                dereference=False,
            ) as archive:
                archive.add(path, arcname=path.name)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise
    return temporary


def _remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def oldify_path(
    path: Path,
    *,
    delete9: bool = False,
    nogit: bool = False,
    cwd: Path | None = None,
    date: bool = False,
    targz: bool = False,
    compression_level: int | None = None,
) -> Path:
    """Rotate a file or folder, optionally dating or archiving its backup.

    Archives contain the source basename as their relative top-level member.
    Symlinks are stored as links, never followed. None selects gzip level 9;
    an explicit compression level requires targz=True.
    """
    if compression_level is not None:
        if not targz:
            raise OldifyError("--compression-level requires --targz.")
        if type(compression_level) is not int or not 0 <= compression_level <= 9:
            raise OldifyError("--compression-level must be an integer from 0 to 9.")
    level = 9 if compression_level is None else compression_level

    cwd = (cwd or Path.cwd()).resolve()
    path = path.expanduser()
    if not path.is_absolute():
        path = cwd / path
    # A parent-directory argument still needs a real basename inside the tar.
    if path.name == "..":
        path = path.resolve()
    if not path.name:
        raise OldifyError("Cannot oldify a filesystem root.")

    if not path.exists() and not (targz and path.is_symlink()):
        raise OldifyError(f"Path does not exist: {path}")
    is_folder = path.is_dir()
    if not is_folder and not path.is_file() and not (targz and path.is_symlink()):
        raise OldifyError(f"Path is not a file or folder: {path}")

    gitignore: Path | None = None
    if not nogit:
        _repo_root(cwd)
        gitignore = cwd / ".gitignore"
        if not gitignore.is_file():
            raise OldifyError(f"Current directory has no .gitignore file: {cwd}")
        if targz and (
            gitignore == path.parent.resolve() / path.name
            or (not path.is_symlink() and gitignore.resolve().is_relative_to(path.resolve()))
        ):
            raise OldifyError("Cannot archive the active .gitignore or its containing folder.")

    stem = path.with_name(f"{path.name}.{local_date.today():%Y%m%d}") if date else path
    backups = [_backup_path(stem, number, targz=targz) for number in range(1, 10)]

    occupied = 0
    for number, backup in enumerate(backups, start=1):
        if not backup.exists() and not backup.is_symlink():
            continue
        if targz:
            valid_type = backup.is_file() and not backup.is_symlink()
        else:
            valid_type = backup.is_dir() if is_folder else backup.is_file()
        if not valid_type:
            kind = "regular archive file" if targz else "folder" if is_folder else "file"
            raise OldifyError(f"Backup path is not a {kind}: {backup}")
        if number == occupied + 1:
            occupied = number

    if occupied == 9 and not delete9:
        raise OldifyError(
            f"Cannot oldify {path}: backups already exist through "
            f"{backups[8].name}. Use --delete9 to replace the oldest backup."
        )

    temporary: Path | None = None
    destination = backups[0]
    try:
        if targz:
            try:
                temporary = _prepare_archive(path, level)
            except (tarfile.TarError, zlib.error) as error:
                raise OldifyError(f"Cannot create archive for {path}: {error}") from error

        highest_to_move = min(occupied, 8)
        if occupied == 9:
            _remove_path(backups[8])
        for index in range(highest_to_move - 1, -1, -1):
            backups[index].rename(backups[index + 1])

        if temporary is not None:
            # Publish without overwriting a path that appeared after validation.
            os.link(temporary, destination)
            _remove_path(path)
        else:
            path.rename(destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

    if gitignore is not None:
        for number in range(1, highest_to_move + 2):
            entry = _gitignore_entry(backups[number - 1], gitignore.parent)
            _append_gitignore(gitignore, entry)

    return destination


def oldify_folder(
    folder: Path,
    *,
    delete9: bool = False,
    nogit: bool = False,
    cwd: Path | None = None,
    date: bool = False,
    targz: bool = False,
    compression_level: int | None = None,
) -> Path:
    """Backward-compatible entry point for :func:`oldify_path`."""
    return oldify_path(
        folder, delete9=delete9, nogit=nogit, cwd=cwd, date=date,
        targz=targz, compression_level=compression_level,
    )
