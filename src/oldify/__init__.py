"""Rotate files and folders into numbered .old backups."""

from .cli import app
from .core import oldify_folder, oldify_path
from .errors import OldifyError

__all__ = ["OldifyError", "app", "oldify_folder", "oldify_path"]
