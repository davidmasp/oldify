# oldify

`oldify` is a small CLI that renames a folder to `<folder>.old`. Existing
backups rotate to `.old2`, `.old3`, and so on through `.old9`.

## Install

Install directly from this project with uv:

```console
uv tool install .
```

Then run:

```console
oldify path/to/folder
```

By default, the current directory must be a Git repository with a `.gitignore`
file. The new `.old` path is appended to the end of `.gitignore` after a
successful rename. Use `--nogit` to skip that requirement and leave
`.gitignore` untouched.

If all nine backup names are occupied, the command fails without changing
anything. Pass `--delete9` to delete the oldest backup and continue rotating:

```console
oldify --delete9 path/to/folder
```

Use both options when appropriate:

```console
oldify --nogit --delete9 path/to/folder
```
