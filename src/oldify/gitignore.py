"""Git repository discovery and local .gitignore updates."""

from __future__ import annotations

from pathlib import Path

from .errors import OldifyError


def _gitignore_entry(old_folder: Path, cwd: Path) -> str:
    try:
        return old_folder.resolve().relative_to(cwd.resolve()).as_posix()
    except ValueError:
        return old_folder.resolve().as_posix()


def _append_gitignore(gitignore: Path, entry: str) -> None:
    if gitignore.is_file():
        try:
            existing = gitignore.read_text(encoding="utf-8").splitlines()
            if entry in existing:
                return
        except OSError:
            pass

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
    from git import InvalidGitRepositoryError, NoSuchPathError, Repo

    try:
        repo = Repo(cwd, search_parent_directories=True)
    except (InvalidGitRepositoryError, NoSuchPathError) as error:
        raise OldifyError(f"Current directory is not a Git repository: {cwd}") from error

    if repo.working_tree_dir is None:
        raise OldifyError(f"Current directory is not a Git work tree: {cwd}")

    return Path(repo.working_tree_dir).resolve()
