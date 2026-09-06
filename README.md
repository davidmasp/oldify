# oldify

`oldify` is a small Python CLI for moving a folder out of the way by renaming it
to `<folder>.old`. If older backups already exist, it rotates them through
numbered names up to `<folder>.old9`.

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

Rename a folder and update `.gitignore`:

```console
oldify path/to/folder
```

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

- Relative folder paths are resolved from the current working directory.
- The target path must exist and must be a directory.
- Existing backup paths must also be directories. If a backup name exists as a
  file, the command fails instead of overwriting it.
- Without `--nogit`, the current working directory must be inside a Git
  repository and contain a local `.gitignore` file.
- Without `--delete9`, a full backup chain through `.old9` fails without
  changing any folders.
- With `--delete9`, the existing `.old9` directory is deleted before the rest of
  the backups rotate.

## Development

Run the test suite with:

```console
uv run python -m unittest discover -s tests
```

The package exposes a `typer` application at `oldify:app` and installs the
`oldify` console script declared in `pyproject.toml`.
