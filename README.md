# oldify

`oldify` is a small Python CLI for moving a file or folder out of the way by
renaming it to `<path>.old`. If older backups already exist, it rotates them
through numbered names up to `<path>.old9`.

For example, running `oldify example` renames:

```text
example      -> example.old
example.old  -> example.old2
example.old2 -> example.old3
```

The command is intentionally conservative: by default it only runs from a
directory inside a Git repository that already has a local `.gitignore`, and it
appends the new `.old` path to that file after a successful rename.

## Requirements

- Python 3.13 or newer
- [`uv`](https://docs.astral.sh/uv/) for local installation and development

## Installation

Install directly from this project:

```console
uv tool install .
```

Then run:

```console
oldify path/to/folder
```

## Usage

Show the installed version:

```console
oldify --version
```

Rename a file or folder and update `.gitignore`:

```console
oldify path/to/folder
oldify path/to/report.txt
```

Files use the same naming scheme: `report.txt` becomes `report.txt.old`, and
existing backups rotate to `report.txt.old2` through `report.txt.old9`.

Skip the Git repository and `.gitignore` checks:

```console
oldify --nogit path/to/folder
```

Delete the oldest backup when all backup slots from `.old` through `.old9` are
already occupied:

```console
oldify --delete9 path/to/folder
```

Combine both options when needed:

```console
oldify --nogit --delete9 path/to/folder
```

## Behavior

- Relative paths are resolved from the current working directory.
- The target path must exist and must be a regular file or directory.
- Existing backup paths must match the target type: files for a file, directories
  for a directory. A conflicting type causes an error before any paths change.
- Without `--nogit`, the current working directory must be inside a Git
  repository and contain a local `.gitignore` file.
- Without `--delete9`, a full backup chain through `.old9` fails without
  changing any files or folders.
- With `--delete9`, the existing `.old9` file or folder is deleted before the rest of
  the backups rotate.

## Development

Run the test suite with:

```console
uv run python -m unittest discover -s tests
```

The package exposes a `typer` application at `oldify:app` and installs the
`oldify` console script declared in `pyproject.toml`.

For Python callers, `oldify_path()` accepts either a file or folder. The existing
`oldify_folder()` function remains available with the same arguments and also
supports both types.
