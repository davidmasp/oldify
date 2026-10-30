from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from git import Repo
from typer.testing import CliRunner

from oldify import OldifyError, app, oldify_folder, oldify_path


class OldifyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def make_path(self, name: str, marker: str = "original") -> Path:
        folder = self.root / name
        folder.mkdir()
        (folder / "marker.txt").write_text(marker, encoding="utf-8")
        return folder

    def read_marker(self, path: Path) -> str:
        return (path / "marker.txt").read_text()

    def make_git_repo(self) -> None:
        Repo.init(self.root)

    def test_renames_path_and_appends_gitignore_at_end(self) -> None:
        self.make_git_repo()
        (self.root / ".gitignore").write_text("*.pyc", encoding="utf-8")
        folder = self.make_path("example")

        result = oldify_folder(folder, cwd=self.root)

        self.assertEqual(result, self.root / "example.old")
        self.assertFalse(folder.exists())
        self.assertEqual(self.read_marker(result), "original")
        self.assertEqual((self.root / ".gitignore").read_text(), "*.pyc\nexample.old\n")

    def test_discovers_git_repo_from_subdirectory(self) -> None:
        self.make_git_repo()
        (self.root / ".gitignore").write_text("*.pyc\n", encoding="utf-8")
        nested = self.root / "analysis" / "repeated_barcodes"
        nested.mkdir(parents=True)
        (nested / ".gitignore").write_text("*.tmp\n", encoding="utf-8")
        self.make_path("analysis/repeated_barcodes/example")

        result = oldify_folder(Path("example"), cwd=nested)

        self.assertEqual(result, (nested / "example.old").resolve())
        self.assertEqual((self.root / ".gitignore").read_text(), "*.pyc\n")
        self.assertEqual(
            (nested / ".gitignore").read_text(),
            "*.tmp\nexample.old\n",
        )

    def test_rotates_existing_backups(self) -> None:
        folder = self.make_path("example", "new")
        self.make_path("example.old", "one")
        self.make_path("example.old2", "two")

        oldify_folder(folder, nogit=True, cwd=self.root)

        self.assertEqual(self.read_marker(self.root / "example.old"), "new")
        self.assertEqual(self.read_marker(self.root / "example.old2"), "one")
        self.assertEqual(self.read_marker(self.root / "example.old3"), "two")

    def test_full_chain_fails_without_changing_paths(self) -> None:
        folder = self.make_path("example", "new")
        self.make_path("example.old", "one")
        for number in range(2, 10):
            self.make_path(f"example.old{number}", str(number))

        with self.assertRaisesRegex(OldifyError, "--delete9"):
            oldify_folder(folder, nogit=True, cwd=self.root)

        self.assertEqual(self.read_marker(folder), "new")
        self.assertEqual(self.read_marker(self.root / "example.old9"), "9")

    def test_delete9_discards_oldest_and_rotates(self) -> None:
        folder = self.make_path("example", "new")
        self.make_path("example.old", "one")
        for number in range(2, 10):
            self.make_path(f"example.old{number}", str(number))

        oldify_folder(folder, delete9=True, nogit=True, cwd=self.root)

        self.assertEqual(self.read_marker(self.root / "example.old"), "new")
        self.assertEqual(self.read_marker(self.root / "example.old2"), "one")
        self.assertEqual(self.read_marker(self.root / "example.old9"), "8")

    def test_requires_git_repo_and_gitignore_by_default(self) -> None:
        folder = self.make_path("example")

        with self.assertRaisesRegex(OldifyError, "not a Git repository"):
            oldify_folder(folder, cwd=self.root)

        self.make_git_repo()
        with self.assertRaisesRegex(OldifyError, "no .gitignore"):
            oldify_folder(folder, cwd=self.root)

        self.assertTrue(folder.exists())

    def test_nogit_skips_git_checks_and_update(self) -> None:
        gitignore = self.root / ".gitignore"
        gitignore.write_text("keep-me\n", encoding="utf-8")
        folder = self.make_path("example")

        oldify_folder(folder, nogit=True, cwd=self.root)

        self.assertEqual(gitignore.read_text(), "keep-me\n")

    def test_rejects_mismatched_backup_type_without_changes(self) -> None:
        path = self.make_path("example", "new")
        backup = self.make_path("example.old", "one")
        conflicting = self.root / "example.old2"
        if path.is_dir():
            conflicting.write_text("keep-me")
        else:
            conflicting.mkdir()
            (conflicting / "marker.txt").write_text("keep-me")

        with self.assertRaisesRegex(OldifyError, "Backup path is not a"):
            oldify_path(path, nogit=True, cwd=self.root)

        self.assertEqual(self.read_marker(path), "new")
        self.assertEqual(self.read_marker(backup), "one")
        marker = conflicting / "marker.txt" if conflicting.is_dir() else conflicting
        self.assertEqual(marker.read_text(), "keep-me")

    def test_cli_renames_path_and_reports_missing_path(self) -> None:
        path = self.make_path("example")
        runner = CliRunner()

        result = runner.invoke(app, ["--nogit", str(path)])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Oldified", result.output)
        self.assertEqual(self.read_marker(self.root / "example.old"), "original")

        result = runner.invoke(app, ["--nogit", str(path)])

        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn("Path does not exist", result.output)

    def test_dangling_backup_symlink_is_not_overwritten(self) -> None:
        path = self.make_path("example", "new")
        backup = self.root / "example.old"
        missing = self.root / "missing"
        backup.symlink_to(missing)

        with self.assertRaisesRegex(OldifyError, "Backup path is not a"):
            oldify_path(path, nogit=True, cwd=self.root)

        self.assertEqual(self.read_marker(path), "new")
        self.assertTrue(backup.is_symlink())
        self.assertEqual(backup.readlink(), missing)

    def test_delete9_unlinks_backup_symlink_without_deleting_its_target(self) -> None:
        path = self.make_path("example", "new")
        for number in range(1, 9):
            suffix = ".old" if number == 1 else f".old{number}"
            self.make_path(f"example{suffix}", str(number))
        target = self.make_path("keep-me", "keep-me")
        oldest = self.root / "example.old9"
        oldest.symlink_to(target, target_is_directory=target.is_dir())

        oldify_path(path, delete9=True, nogit=True, cwd=self.root)

        self.assertEqual(self.read_marker(target), "keep-me")
        self.assertFalse(oldest.is_symlink())
        self.assertEqual(self.read_marker(oldest), "8")

    def test_new_api_rotates_path_and_updates_all_gitignore_entries(self) -> None:
        self.make_git_repo()
        gitignore = self.root / ".gitignore"
        gitignore.write_text("example.old\n")
        self.make_path("example", "new")
        self.make_path("example.old", "one")
        self.make_path("example.old2", "two")

        result = oldify_path(Path("example"), cwd=self.root)

        self.assertEqual(result, self.root.resolve() / "example.old")
        self.assertEqual(self.read_marker(result), "new")
        self.assertEqual(self.read_marker(self.root / "example.old2"), "one")
        self.assertEqual(self.read_marker(self.root / "example.old3"), "two")
        self.assertEqual(
            gitignore.read_text(), "example.old\nexample.old2\nexample.old3\n"
        )


class FileOldifyTests(OldifyTests):
    """Run the same rotation and Git behavior checks against regular files."""

    def make_path(self, name: str, marker: str = "original") -> Path:
        path = self.root / name
        path.write_text(marker, encoding="utf-8")
        return path

    def read_marker(self, path: Path) -> str:
        return path.read_text()

    def test_suffix_is_appended_after_file_extension(self) -> None:
        self.make_path("report.txt", "new")
        self.make_path("report.txt.old", "previous")

        result = oldify_path(Path("report.txt"), nogit=True, cwd=self.root)

        self.assertEqual(result, self.root.resolve() / "report.txt.old")
        self.assertEqual(result.read_text(), "new")
        self.assertEqual((self.root / "report.txt.old2").read_text(), "previous")


if __name__ == "__main__":
    unittest.main()
