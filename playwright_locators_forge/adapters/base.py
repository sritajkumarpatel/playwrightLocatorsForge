"""Every framework adapter implements this interface. Adding support for a
new framework (Blazor, plain Jinja templates, ...) means writing one
adapter, not touching the scanner, renderer, or CLI.
"""

from __future__ import annotations

import fnmatch
from abc import ABC, abstractmethod
from pathlib import Path

from playwright_locators_forge.models import PageResult
from playwright_locators_forge.scanner.markup_parser import RawNode


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


def element_name(node: RawNode, content_hash: str, seen: set[str]) -> str:
    """Pick a stable element name, mutating `seen` to register it.

    Falls back to `{tag}_{content_hash[:6]}` rather than a positional
    index: an index-based name (`button_3`) shifts for every element
    whose *neighbors* change, breaking `forge resolve` lookups and
    producing noisy diffs for edits that didn't touch that element at
    all. A hash of the element's own tag/attrs/text only changes when
    the element itself does. Collisions (two genuinely identical
    elements in one file) are disambiguated with a numeric suffix.
    """
    base = node.attrs.get("data-testid") or node.attrs.get("id") or f"{node.tag}_{content_hash[:6]}"
    name = base
    suffix = 2
    while name in seen:
        name = f"{base}_{suffix}"
        suffix += 1
    seen.add(name)
    return name
