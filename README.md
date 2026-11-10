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

Include the current local calendar date in backup names:

```console
oldify --date path/to/folder
oldify --date path/to/report.txt
```

On November 10, 2026, these create `folder.20261110.old` and
`report.txt.20261110.old`. Repeated runs on the same day rotate that day's
backups through `.old2` to `.old9`. Other dates and undated backups have
separate chains. `--delete9` applies to the selected chain, and `.gitignore`
entries use the resulting dated names.

Store a file or folder as a gzip-compressed tar archive instead of renaming it:

```console
oldify --nogit --targz results-folder
oldify --targz --compression-level 6 report.txt
oldify --targz --date results-folder
```

The first command creates `results-folder.old.tar.gz` and removes the source
after the archive is published. `--compression-level` accepts integers from
**0** (no compression) through **9** (maximum compression, the default).
Supplying it explicitly without `--targz` is an error, even for level 9.

Names always follow `source-name[.YYYYMMDD].old[N][.tar.gz]`: on November 10,
2026, the dated archive example creates `results-folder.20261110.old.tar.gz`.
Repeated runs rotate it to `results-folder.20261110.old2.tar.gz` through
`results-folder.20261110.old9.tar.gz`. Archives and renamed backups have
independent chains, as do different dates. Archive slots accept regular files
regardless of whether the original source was a file or folder.
`--delete9` discards only the selected chain's ninth backup when that chain is full.
Without `--nogit`, exact final archive names, including rotated names, are added
to the local `.gitignore` without duplicate entries. `--nogit` leaves it untouched.

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
- The target path must exist and must be a regular file or directory. Archive
  mode also accepts symlinks, including dangling symlinks, and stores the link itself.
- In ordinary mode, existing backup paths must match the target type: files for
  a file, directories for a directory. A conflicting type causes an error before
  any paths change.
- Without `--nogit`, the current working directory must be inside a Git
  repository and contain a local `.gitignore` file.
- Without `--delete9`, a full backup chain through `.old9` fails without
  changing any files or folders.
- With `--delete9`, the existing `.old9` file or folder is deleted before the rest of
  the backups rotate.

### Archive layout and safety

An archive has one relative top-level member named after the original source,
without the date or backup suffix. For example, `results-folder.old.tar.gz`
contains `results-folder/` and its nested contents; `report.txt.old.tar.gz`
contains `report.txt`. Member names never include absolute host paths.
Empty directories and file metadata supported by tar are preserved. Symlinks
retain their link targets verbatim and are never followed while archiving;
removing a source symlink only unlinks it, leaving external targets intact.

Options, source paths, Git requirements, all nine backup path types, and full-chain
limits are checked before mutation. Archive backup slots reject directories,
special files, and all symlinks (including broken ones). The active `.gitignore`
and any folder containing it cannot be archived unless `--nogit` is used.

The complete archive is written, closed, and flushed in a temporary sibling file
before any backup is rotated or deleted. Creation/compression failures preserve
the source, existing backups, and `.gitignore`, and remove the temporary file.
After preparation, backups rotate and the archive is published without overwriting
an occupied destination; only then is the source removed and `.gitignore` updated.
Later filesystem errors are reported without rolling back completed rotation.
If source removal fails, the complete published archive remains available, though
a directory may have been partially removed. Avoid changing the source or its
backup chain while oldify is running.

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
Both functions accept `date=True` to use the same dated naming as `--date`.
They also accept `targz=True` and `compression_level=0` through `9` (omitting the
level selects 9). An explicit `compression_level` requires `targz=True`.
