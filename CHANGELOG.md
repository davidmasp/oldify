# Changelog

## 0.1.5 - 2026-11-10

### Added

- `--date` adds the current local date to backup names, such as
  `results.20261110.old`, with a separate rotation chain for each date.
- `--targz` archives files and folders as `.old.tar.gz` backups and composes
  with dated names. Archives rotate independently from uncompressed backups.
- `--compression-level` selects gzip compression from 0 through 9, defaulting
  to maximum compression (9). Requires `--targz`.
- Both Python entry points accept `date`, `targz`, and `compression_level`.

### Changed

- Validate all nine backup paths before changing the selected backup chain.
- Prepare archives completely before rotating backups or removing the source.
  Archive creation failures preserve existing data and clean up temporary files.
- Preserve symlinks as links when archiving and reject symlinks in archive
  backup slots to protect external targets.
- Expand regression coverage for `.gitignore` duplicate prevention, dated
  rotation, archive contents, compression options, and failure handling.
