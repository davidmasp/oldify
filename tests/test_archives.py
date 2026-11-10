from __future__ import annotations

import io
import os
import tarfile
import tempfile
import unittest
import zlib
from datetime import date
from pathlib import Path
from unittest.mock import patch

from git import Repo
from typer.testing import CliRunner

from oldify import OldifyError, app, oldify_folder, oldify_path


class ArchiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name).resolve()
        self.addCleanup(self.temporary_directory.cleanup)

    def make_source(self, name: str = "example", marker: str = "new") -> Path:
        path = self.root / name
        path.mkdir()
        (path / "marker.txt").write_text(marker)
        return path

    def make_archive(self, name: str, marker: str) -> Path:
        path = self.root / name
        content = marker.encode()
        with tarfile.open(path, "w:gz") as archive:
            member = tarfile.TarInfo("example/marker.txt")
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))
        return path

    def read_marker(self, path: Path) -> str:
        with tarfile.open(path, "r:gz") as archive:
            with archive.extractfile("example/marker.txt") as stream:
                return stream.read().decode()

    def snapshot(self) -> dict[str, bytes | str]:
        return {
            str(path.relative_to(self.root)): (
                path.read_bytes() if path.is_file() else "directory"
            )
            for path in self.root.rglob("*")
        }

    def test_folder_round_trip_preserves_nested_contents_and_empty_directories(self) -> None:
        source = self.make_source("results-folder")
        (source / "nested").mkdir()
        (source / "nested" / "data.bin").write_bytes(bytes(range(256)))
        (source / "empty").mkdir()

        result = oldify_folder(source, targz=True, nogit=True, cwd=self.root)

        self.assertEqual(result, self.root / "results-folder.old.tar.gz")
        self.assertFalse(source.exists())
        restored = self.root / "restored"
        with tarfile.open(result, "r:gz") as archive:
            self.assertEqual(
                set(archive.getnames()),
                {
                    "results-folder", "results-folder/marker.txt", "results-folder/nested",
                    "results-folder/nested/data.bin", "results-folder/empty",
                },
            )
            archive.extractall(restored, filter="data")
        self.assertEqual((restored / "results-folder/marker.txt").read_text(), "new")
        self.assertEqual(
            (restored / "results-folder/nested/data.bin").read_bytes(), bytes(range(256))
        )
        self.assertTrue((restored / "results-folder/empty").is_dir())

    def test_file_round_trip_and_shared_archive_chain_with_folders(self) -> None:
        source = self.root / "report.txt"
        source.write_bytes(b"report\x00\xff\n")

        result = oldify_path(source, targz=True, nogit=True, cwd=self.root)

        self.assertEqual(result.name, "report.txt.old.tar.gz")
        self.assertFalse(source.exists())
        with tarfile.open(result, "r:gz") as archive:
            self.assertEqual(archive.getnames(), ["report.txt"])
            archive.extractall(self.root / "restored", filter="data")
        self.assertEqual((self.root / "restored/report.txt").read_bytes(), b"report\x00\xff\n")
        self.make_source("report.txt")
        oldify_folder(source, targz=True, nogit=True, cwd=self.root)
        with tarfile.open(self.root / "report.txt.old2.tar.gz", "r:gz") as archive:
            self.assertTrue(archive.getmember("report.txt").isfile())
        with tarfile.open(result, "r:gz") as archive:
            self.assertTrue(archive.getmember("report.txt").isdir())

    def test_all_compression_levels_and_default_produce_readable_archives(self) -> None:
        for level in [None, *range(10)]:
            with self.subTest(level=level):
                source = self.root / f"level-{level}"
                source.write_bytes(b"content\n" * 1000)
                with patch("oldify.core.tarfile.open", wraps=tarfile.open) as opened:
                    result = oldify_path(
                        source, targz=True, compression_level=level, nogit=True, cwd=self.root
                    )
                    self.assertEqual(
                        opened.call_args.kwargs["compresslevel"], 9 if level is None else level
                    )
                with tarfile.open(result, "r:gz") as archive:
                    self.assertEqual(
                        archive.extractfile(source.name).read(), b"content\n" * 1000
                    )
                if level is None:
                    # gzip's maximum-compression flag
                    self.assertEqual(result.read_bytes()[8], 2)

    def test_invalid_api_options_leave_everything_untouched(self) -> None:
        source = self.make_source()
        self.make_archive("example.old.tar.gz", "previous")
        (self.root / ".gitignore").write_text("keep-me\n")
        before = self.snapshot()
        for targz, level in [
            (True, -1), (True, 10), (True, 1.5), (True, True), (True, "9"),
            (False, 0), (False, 9),
        ]:
            with self.subTest(targz=targz, level=level):
                with self.assertRaisesRegex(OldifyError, "--compression-level"):
                    oldify_path(
                        source, targz=targz, compression_level=level, nogit=True, cwd=self.root
                    )
                self.assertEqual(self.snapshot(), before)

    def test_cli_options_and_errors(self) -> None:
        runner = CliRunner()
        source = self.make_source()
        for arguments in [
            ["--targz", "--compression-level", "-1"],
            ["--targz", "--compression-level", "10"],
            ["--targz", "--compression-level", "invalid"],
            ["--compression-level", "9"],
            ["--compression-level", "0"],
        ]:
            with self.subTest(arguments=arguments):
                before = self.snapshot()
                result = runner.invoke(app, ["--nogit", *arguments, str(source)])
                self.assertNotEqual(result.exit_code, 0, result.output)
                self.assertIn("compression-level", result.output)
                self.assertEqual(self.snapshot(), before)
        result = runner.invoke(
            app, ["--nogit", "--targz", "--compression-level", "0", str(source)]
        )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("example.old.tar.gz", result.output)
        self.assertEqual(self.read_marker(self.root / "example.old.tar.gz"), "new")

    @patch("oldify.core.local_date")
    def test_dated_cli_rotation_and_separate_chains(self, clock) -> None:
        clock.today.return_value = date(2026, 11, 10)
        source = self.make_source()
        current = self.make_archive("example.20261110.old.tar.gz", "today")
        unrelated = [
            self.make_archive("example.20261109.old.tar.gz", "yesterday"),
            self.make_archive("example.old.tar.gz", "undated"),
            self.make_source("example.20261110.old", "uncompressed"),
        ]
        before = {
            path: path.read_bytes() if path.is_file() else (path / "marker.txt").read_bytes()
            for path in unrelated
        }

        result = CliRunner().invoke(app, ["--nogit", "--targz", "--date", str(source)])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn(current.name, result.output)
        self.assertEqual(self.read_marker(current), "new")
        self.assertEqual(self.read_marker(self.root / "example.20261110.old2.tar.gz"), "today")
        for path in unrelated:
            self.assertEqual(
                path.read_bytes() if path.is_file() else (path / "marker.txt").read_bytes(),
                before[path],
            )
        # Rotating the ordinary chain likewise leaves the archive chain alone.
        self.make_source()
        oldify_path(source, date=True, nogit=True, cwd=self.root)
        self.assertEqual(self.read_marker(current), "new")
        self.assertEqual(
            (self.root / "example.20261110.old2/marker.txt").read_text(), "uncompressed"
        )

    def test_full_chain_and_delete9_with_and_without_date(self) -> None:
        for dated in [False, True]:
            with self.subTest(dated=dated), patch("oldify.core.local_date") as clock:
                clock.today.return_value = date(2026, 11, 10)
                source = self.make_source()
                stem = "example.20261110" if dated else "example"
                for number in range(1, 10):
                    suffix = ".old" if number == 1 else f".old{number}"
                    self.make_archive(f"{stem}{suffix}.tar.gz", str(number))
                before = self.snapshot()
                with patch("oldify.core._prepare_archive") as prepare:
                    with self.assertRaisesRegex(
                        OldifyError, rf"{stem}\.old9\.tar\.gz.*--delete9"
                    ):
                        oldify_path(source, targz=True, date=dated, nogit=True, cwd=self.root)
                    prepare.assert_not_called()
                self.assertEqual(self.snapshot(), before)

                oldify_path(
                    source, targz=True, date=dated, delete9=True, nogit=True, cwd=self.root
                )

                self.assertEqual(self.read_marker(self.root / f"{stem}.old.tar.gz"), "new")
                self.assertEqual(self.read_marker(self.root / f"{stem}.old2.tar.gz"), "1")
                self.assertEqual(self.read_marker(self.root / f"{stem}.old9.tar.gz"), "8")

    @patch("oldify.core.local_date")
    def test_gitignore_uses_exact_dated_names_without_duplicates(self, clock) -> None:
        clock.today.return_value = date(2026, 11, 10)
        Repo.init(self.root)
        gitignore = self.root / ".gitignore"
        initial = "# backups\nexample.20261110.old.tar.gz.extra\nexample.20261110.old.tar.gz"
        gitignore.write_text(initial)
        for marker in ["first", "second", "third"]:
            source = self.make_source(marker=marker)
            oldify_path(source, targz=True, date=True, cwd=self.root)
        self.assertEqual(
            gitignore.read_text(),
            initial + "\nexample.20261110.old2.tar.gz\nexample.20261110.old3.tar.gz\n",
        )
        self.assertEqual(self.read_marker(self.root / "example.20261110.old3.tar.gz"), "first")

    def test_git_requirements_and_nogit(self) -> None:
        source = self.make_source()
        for message in ["not a Git repository", "no .gitignore"]:
            with self.assertRaisesRegex(OldifyError, message):
                oldify_path(source, targz=True, cwd=self.root)
            self.assertTrue(source.exists())
            self.assertFalse((self.root / "example.old.tar.gz").exists())
            Repo.init(self.root)
        gitignore = self.root / ".gitignore"
        gitignore.write_text("leave-me-alone")
        oldify_path(source, targz=True, nogit=True, cwd=self.root)
        self.assertEqual(gitignore.read_text(), "leave-me-alone")

    def test_nested_source_gitignore_and_relative_layout(self) -> None:
        Repo.init(self.root)
        (self.root / ".gitignore").write_text("")
        parent = self.root / "nested"
        parent.mkdir()
        (parent / "report.txt").write_text("report")

        result = oldify_path(Path("nested/report.txt"), targz=True, cwd=self.root)

        self.assertEqual(
            (self.root / ".gitignore").read_text(), "nested/report.txt.old.tar.gz\n"
        )
        with tarfile.open(result, "r:gz") as archive:
            self.assertEqual(archive.getnames(), ["report.txt"])

    def test_archive_collisions_including_slots_after_a_gap_are_preflighted(self) -> None:
        source = self.make_source()
        previous = self.make_archive("example.old.tar.gz", "one")
        for slot in [2, 9]:
            for kind in ["directory", "file-link", "directory-link", "broken-link", "fifo"]:
                with self.subTest(slot=slot, kind=kind):
                    collision = self.root / f"example.old{slot}.tar.gz"
                    if kind == "directory":
                        collision.mkdir()
                    elif kind == "fifo":
                        os.mkfifo(collision)
                    else:
                        target = {
                            "file-link": previous,
                            "directory-link": source,
                            "broken-link": self.root / "missing",
                        }[kind]
                        collision.symlink_to(target)
                    before = previous.read_bytes()
                    with patch("oldify.core._prepare_archive") as prepare:
                        with self.assertRaisesRegex(
                            OldifyError, "Backup path is not a regular archive file"
                        ):
                            oldify_path(
                                source, targz=True, delete9=True, nogit=True, cwd=self.root
                            )
                        prepare.assert_not_called()
                    self.assertEqual((source / "marker.txt").read_text(), "new")
                    self.assertEqual(previous.read_bytes(), before)
                    if kind == "directory":
                        collision.rmdir()
                    else:
                        collision.unlink()

    def test_symlink_sources_and_nested_links_never_follow_external_targets(self) -> None:
        outside = self.make_source("external", "keep-me")
        for name, target in [
            ("folder-link", outside), ("file-link", outside / "marker.txt"),
            ("broken-link", self.root / "missing"),
        ]:
            with self.subTest(name=name):
                source = self.root / name
                source.symlink_to(target)
                result = oldify_path(source, targz=True, nogit=True, cwd=self.root)
                self.assertFalse(source.is_symlink())
                with tarfile.open(result, "r:gz") as archive:
                    self.assertEqual(archive.getnames(), [name])
                    self.assertTrue(archive.getmember(name).issym())
                    self.assertEqual(archive.getmember(name).linkname, str(target))
                self.assertEqual((outside / "marker.txt").read_text(), "keep-me")
        source = self.make_source()
        (source / "outside").symlink_to(outside, target_is_directory=True)
        (source / "dangling").symlink_to("missing")
        result = oldify_path(source, targz=True, nogit=True, cwd=self.root)
        with tarfile.open(result, "r:gz") as archive:
            self.assertTrue(archive.getmember("example/outside").issym())
            self.assertTrue(archive.getmember("example/dangling").issym())
            self.assertNotIn("example/outside/marker.txt", archive.getnames())
        self.assertEqual((outside / "marker.txt").read_text(), "keep-me")

    def test_archive_failures_preserve_source_full_chain_and_gitignore(self) -> None:
        Repo.init(self.root)
        (self.root / ".gitignore").write_text("keep-me\n")
        source = self.make_source()
        for number in range(1, 10):
            suffix = ".old" if number == 1 else f".old{number}"
            self.make_archive(f"example{suffix}.tar.gz", str(number))
        before = self.snapshot()
        errors = [
            tarfile.TarError("tar failed"), tarfile.CompressionError("gzip failed"),
            zlib.error("gzip failed"), OSError("write failed"),
        ]
        for error in errors:
            def fail_after_partial_write(archive, *args, **kwargs):
                archive.fileobj.write(b"partial archive")
                raise error

            with self.subTest(error=error), patch(
                "oldify.core.tarfile.TarFile.add",
                autospec=True, side_effect=fail_after_partial_write,
            ):
                with self.assertRaises((OldifyError, OSError)):
                    oldify_path(source, targz=True, delete9=True, cwd=self.root)
            self.assertEqual(self.snapshot(), before)  # also checks temporary-file cleanup
        with patch("oldify.core.os.fsync", side_effect=OSError("flush failed")):
            with self.assertRaises(OSError):
                oldify_path(source, targz=True, delete9=True, cwd=self.root)
        self.assertEqual(self.snapshot(), before)
        close = tarfile.TarFile.close

        def fail_on_close(archive):
            close(archive)
            raise OSError("close failed")

        with patch(
            "oldify.core.tarfile.TarFile.close", autospec=True, side_effect=fail_on_close
        ):
            with self.assertRaisesRegex(OSError, "close failed"):
                oldify_path(source, targz=True, delete9=True, cwd=self.root)
        self.assertEqual(self.snapshot(), before)

    def test_cli_tar_errors_are_friendly_and_leave_no_partial_archive(self) -> None:
        source = self.make_source()
        with patch("oldify.core.tarfile.open", side_effect=tarfile.TarError("tar failed")):
            result = CliRunner().invoke(app, ["--nogit", "--targz", str(source)])
        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn("Error: Cannot create archive", result.output)
        self.assertIn("tar failed", result.output)
        self.assertEqual(list(self.root.iterdir()), [source])

    def test_publication_failure_preserves_source_and_cleans_temporary(self) -> None:
        source = self.make_source()
        with patch("oldify.core.os.link", side_effect=OSError("publish failed")):
            with self.assertRaisesRegex(OSError, "publish failed"):
                oldify_path(source, targz=True, nogit=True, cwd=self.root)
        self.assertEqual(list(self.root.iterdir()), [source])
        self.assertEqual((source / "marker.txt").read_text(), "new")

    def test_removal_error_keeps_complete_published_archive(self) -> None:
        source = self.make_source()
        with patch("oldify.core.shutil.rmtree", side_effect=OSError("remove failed")):
            with self.assertRaisesRegex(OSError, "remove failed"):
                oldify_path(source, targz=True, nogit=True, cwd=self.root)
        self.assertEqual((source / "marker.txt").read_text(), "new")
        self.assertEqual(self.read_marker(self.root / "example.old.tar.gz"), "new")
        self.assertFalse(list(self.root.glob(".*.tmp")))

    def test_rejects_active_gitignore_or_its_ancestor_before_mutation(self) -> None:
        Repo.init(self.root)
        gitignore = self.root / ".gitignore"
        gitignore.write_text("keep-me\n")
        before = self.snapshot()
        for source in [gitignore, self.root, Path(".")]:
            with self.subTest(source=source):
                with self.assertRaisesRegex(OldifyError, "active .gitignore"):
                    oldify_path(source, targz=True, cwd=self.root)
                self.assertEqual(self.snapshot(), before)

    def test_rejects_missing_special_and_root_sources(self) -> None:
        special = self.root / "fifo"
        os.mkfifo(special)
        for source, message in [
            (self.root / "missing", "does not exist"), (special, "not a file or folder"),
            (Path("/"), "filesystem root"),
        ]:
            with self.subTest(source=source):
                with self.assertRaisesRegex(OldifyError, message):
                    oldify_path(source, targz=True, nogit=True, cwd=self.root)


if __name__ == "__main__":
    unittest.main()
