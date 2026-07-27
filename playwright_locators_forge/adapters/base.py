"""Every framework adapter implements this interface. Adding support for a
new framework (Svelte, Blazor, plain Jinja templates, ...) means writing
one adapter, not touching the scanner, renderer, or CLI.
"""

from __future__ import annotations

import fnmatch
from abc import ABC, abstractmethod
from pathlib import Path

from playwright_locators_forge.models import PageResult


class FrameworkAdapter(ABC):
    name: str

    @abstractmethod
    def discover_files(self, root: Path, include: list[str], exclude: list[str]) -> list[Path]:
        """Return every source file this adapter knows how to read."""

    @abstractmethod
    def extract(self, root: Path, file_path: Path, test_id_attrs: list[str]) -> PageResult:
        """Parse one file into a PageResult with ranked-later candidates."""


def glob_files(root: Path, include: list[str], exclude: list[str]) -> list[Path]:
    """Shared glob helper: union of include patterns, minus exclude patterns."""
    matched: set[Path] = set()
    for pattern in include:
        matched.update(root.glob(pattern))

    def is_excluded(p: Path) -> bool:
        rel = p.relative_to(root).as_posix()
        return any(fnmatch.fnmatch(rel, pattern) for pattern in exclude)

    return sorted(p for p in matched if p.is_file() and not is_excluded(p))
