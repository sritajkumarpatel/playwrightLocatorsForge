"""Reads back the generated markdown files -- used by `forge resolve`/`forge
check`, and by any agent-facing integration that wants a single locator
string instead of grepping markdown itself.

Parses the exact format `render/markdown.py` produces. This intentionally
is NOT a general markdown parser: the generator format is fixed (one
`### name` heading per element, a `- hash:` bullet, a fixed-column table),
so a small line-based reader is enough and stays dependency-free.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LocatorRow:
    rank: int
    type: str
    value: str
    dynamic: bool
    note: str


@dataclass
class ElementRecord:
    name: str
    source: str = ""
    tag: str = ""
    hash: str = ""
    stale: bool = False
    locators: list[LocatorRow] = field(default_factory=list)

    def top(self, *, allow_dynamic: bool = False) -> LocatorRow | None:
        for row in sorted(self.locators, key=lambda r: r.rank):
            if allow_dynamic or not row.dynamic:
                return row
        return None


def parse_page(path: Path) -> dict[str, ElementRecord]:
    elements: dict[str, ElementRecord] = {}
    current: ElementRecord | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if line.startswith("### "):
            current = ElementRecord(name=line[4:].strip())
            elements[current.name] = current
            continue
        if current is None:
            continue
        if line.startswith("- source:"):
            current.source = line.split(":", 1)[1].strip()
        elif line.startswith("- tag:"):
            current.tag = line.split(":", 1)[1].strip().strip("`")
        elif line.startswith("- hash:"):
            current.hash = line.split(":", 1)[1].strip()
        elif line.startswith("- ⚠️ stale"):
            current.stale = True
        elif line.startswith("|") and not line.startswith("|---"):
            cols = [c.strip() for c in line.strip("|").split("|")]
            if len(cols) != 5 or cols[0] == "rank":
                continue
            rank_str, type_, value, dynamic, note = cols
            if not rank_str.isdigit():
                continue
            current.locators.append(
                LocatorRow(
                    rank=int(rank_str),
                    type=type_,
                    value=value.strip("`"),
                    dynamic=(dynamic == "yes"),
                    note=note,
                )
            )

    return elements


def parse_page_hashes(path: Path) -> dict[str, str]:
    return {name: rec.hash for name, rec in parse_page(path).items()}


def find_page_file(output_dir: Path, route_or_file: str) -> Path | None:
    """Best-effort lookup: exact relative .md path, then filename stem
    match, then a substring match against any indexed source file."""
    direct = output_dir / route_or_file
    if direct.suffix != ".md":
        direct = direct.with_suffix(".md")
    if direct.exists():
        return direct

    candidates = [p for p in output_dir.rglob("*.md") if p.name != "INDEX.md"]
    for p in candidates:
        if p.stem == route_or_file:
            return p
    for p in candidates:
        if route_or_file in p.as_posix():
            return p
    return None


def resolve_locator(output_dir: Path, route_or_file: str, element_name: str) -> str | None:
    page_path = find_page_file(output_dir, route_or_file)
    if page_path is None:
        return None
    elements = parse_page(page_path)
    record = elements.get(element_name)
    if record is None:
        return None
    top = record.top()
    return top.value if top else None


def list_indexed_pages(output_dir: Path) -> list[dict]:
    """Parse INDEX.md into structured rows. Shared by `forge` and the MCP
    server so an agent (or a human) can see what's already scanned before
    asking for a specific element.
    """
    index_path = output_dir / "INDEX.md"
    if not index_path.exists():
        return []

    pages: list[dict] = []
    for line in index_path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) != 5 or cols[0] == "Source file":
            continue
        source_file, route_hint, framework, elements, _link = cols
        pages.append(
            {
                "source_file": source_file,
                "route_hint": route_hint,
                "framework": framework,
                "element_count": int(elements) if elements.isdigit() else 0,
            }
        )
    return pages


def find_stale_elements(output_dir: Path) -> list[dict]:
    """Every element flagged stale across the whole locator map, as
    {page, element} rows. Shared by `forge check` and the MCP server's
    freshness tool.
    """
    stale: list[dict] = []
    for md_path in sorted(output_dir.rglob("*.md")):
        if md_path.name == "INDEX.md":
            continue
        for name, record in parse_page(md_path).items():
            if record.stale:
                stale.append({"page": md_path.relative_to(output_dir).as_posix(), "element": name})
    return stale
