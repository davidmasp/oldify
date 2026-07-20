from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from oldify import OldifyError, oldify_folder


class OldifyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def make_folder(self, name: str, marker: str = "original") -> Path:
        folder = self.root / name
        folder.mkdir()
        (folder / "marker.txt").write_text(marker, encoding="utf-8")
        return folder

    def test_renames_folder_and_appends_gitignore_at_end(self) -> None:
        (self.root / ".git").mkdir()
        (self.root / ".gitignore").write_text("*.pyc", encoding="utf-8")
        folder = self.make_folder("example")

        result = oldify_folder(folder, cwd=self.root)

        self.assertEqual(result, self.root / "example.old")
        self.assertFalse(folder.exists())
        self.assertEqual((result / "marker.txt").read_text(), "original")
        self.assertEqual((self.root / ".gitignore").read_text(), "*.pyc\nexample.old\n")

    def test_rotates_existing_backups(self) -> None:
        folder = self.make_folder("example", "new")
        self.make_folder("example.old", "one")
        self.make_folder("example.old2", "two")

        oldify_folder(folder, nogit=True, cwd=self.root)

        self.assertEqual((self.root / "example.old/marker.txt").read_text(), "new")
        self.assertEqual((self.root / "example.old2/marker.txt").read_text(), "one")
        self.assertEqual((self.root / "example.old3/marker.txt").read_text(), "two")

    def test_full_chain_fails_without_changing_folders(self) -> None:
        folder = self.make_folder("example", "new")
        self.make_folder("example.old", "one")
        for number in range(2, 10):
            self.make_folder(f"example.old{number}", str(number))

        with self.assertRaisesRegex(OldifyError, "--delete9"):
            oldify_folder(folder, nogit=True, cwd=self.root)

        self.assertEqual((folder / "marker.txt").read_text(), "new")
        self.assertEqual((self.root / "example.old9/marker.txt").read_text(), "9")

    def test_delete9_discards_oldest_and_rotates(self) -> None:
        folder = self.make_folder("example", "new")
        self.make_folder("example.old", "one")
        for number in range(2, 10):
            self.make_folder(f"example.old{number}", str(number))

        oldify_folder(folder, delete9=True, nogit=True, cwd=self.root)

        self.assertEqual((self.root / "example.old/marker.txt").read_text(), "new")
        self.assertEqual((self.root / "example.old2/marker.txt").read_text(), "one")
        self.assertEqual((self.root / "example.old9/marker.txt").read_text(), "8")

    def test_requires_git_repo_and_gitignore_by_default(self) -> None:
        folder = self.make_folder("example")

        with self.assertRaisesRegex(OldifyError, "not a Git repository"):
            oldify_folder(folder, cwd=self.root)

        (self.root / ".git").mkdir()
        with self.assertRaisesRegex(OldifyError, "no .gitignore"):
            oldify_folder(folder, cwd=self.root)

        self.assertTrue(folder.exists())

    def test_nogit_skips_git_checks_and_update(self) -> None:
        gitignore = self.root / ".gitignore"
        gitignore.write_text("keep-me\n", encoding="utf-8")
        folder = self.make_folder("example")

        oldify_folder(folder, nogit=True, cwd=self.root)

        self.assertEqual(gitignore.read_text(), "keep-me\n")


if __name__ == "__main__":
    unittest.main()
