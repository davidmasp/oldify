"""Rotate folders into numbered .old backups."""

from .cli import app
from .core import oldify_folder
from .errors import OldifyError

__all__ = ["OldifyError", "app", "oldify_folder"]
