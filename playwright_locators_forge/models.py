"""Shared data model used by every adapter, the scanner, and the renderer.

Kept framework-agnostic on purpose: adapters translate React/Angular/Vue/HTML
into these plain dataclasses, and nothing downstream needs to know which
framework an element came from.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LocatorCandidate:
    """One possible way to locate an element, before priority ranking."""

    type: str  # testId | id | role | label | name | text | css | xpath
    value: str
    dynamic: bool = False  # True if the underlying attribute is a runtime
    # binding (e.g. Angular `[attr.data-testid]="expr"`, Vue `:id="expr"`)
    # rather than a static string. Dynamic candidates are kept but ranked
    # last / flagged, since they can't be trusted without a live DOM check.
    note: str = ""


@dataclass
class Element:
    """A single markup element discovered in a source file."""

    name: str  # human-readable identifier, e.g. "submitButton"
    tag: str
    file: str  # path relative to the scanned repo root
    line: int
    attrs: dict[str, str] = field(default_factory=dict)
    text: str = ""
    candidates: list[LocatorCandidate] = field(default_factory=list)
    content_hash: str = ""  # for stale-detection between scans


@dataclass
class PageResult:
    """All elements discovered for one source file, i.e. one output page."""

    source_file: str  # e.g. "src/pages/about.tsx"
    route_hint: str  # best-guess route/component name, e.g. "about"
    framework: str
    elements: list[Element] = field(default_factory=list)


def page_to_dict(page: PageResult) -> dict:
    return {
        "source_file": page.source_file,
        "route_hint": page.route_hint,
        "framework": page.framework,
        "elements": [
            {
                "name": e.name,
                "tag": e.tag,
                "file": e.file,
                "line": e.line,
                "attrs": e.attrs,
                "text": e.text,
                "content_hash": e.content_hash,
                "candidates": [
                    {"type": c.type, "value": c.value, "dynamic": c.dynamic, "note": c.note}
                    for c in e.candidates
                ],
            }
            for e in page.elements
        ],
    }


def page_from_dict(data: dict) -> PageResult:
    return PageResult(
        source_file=data["source_file"],
        route_hint=data["route_hint"],
        framework=data["framework"],
        elements=[
            Element(
                name=e["name"],
                tag=e["tag"],
                file=e["file"],
                line=e["line"],
                attrs=e["attrs"],
                text=e["text"],
                content_hash=e["content_hash"],
                candidates=[
                    LocatorCandidate(type=c["type"], value=c["value"], dynamic=c["dynamic"], note=c["note"])
                    for c in e["candidates"]
                ],
            )
            for e in data["elements"]
        ],
    )
