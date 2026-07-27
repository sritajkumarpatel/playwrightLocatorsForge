from __future__ import annotations

from pathlib import Path

from playwright_locators_forge.adapters.base import FrameworkAdapter, glob_files
from playwright_locators_forge.models import Element, PageResult
from playwright_locators_forge.scanner.hashing import element_hash
from playwright_locators_forge.scanner.locator_types import build_candidates
from playwright_locators_forge.scanner.markup_parser import parse_jsx


class ReactAdapter(FrameworkAdapter):
    name = "react"

    def discover_files(self, root: Path, include: list[str], exclude: list[str]) -> list[Path]:
        files = glob_files(root, include, exclude)
        return [f for f in files if f.suffix in (".tsx", ".jsx")]

    def extract(self, root: Path, file_path: Path, test_id_attrs: list[str]) -> PageResult:
        source = file_path.read_text(encoding="utf-8", errors="replace")
        raw_nodes = parse_jsx(source)
        rel_path = file_path.relative_to(root).as_posix()

        elements: list[Element] = []
        for idx, node in enumerate(raw_nodes):
            candidates = build_candidates(node, test_id_attrs)
            name = (
                node.attrs.get("data-testid")
                or node.attrs.get("id")
                or f"{node.tag}_{idx}"
            )
            elements.append(
                Element(
                    name=name,
                    tag=node.tag,
                    file=rel_path,
                    line=node.line,
                    attrs=node.attrs,
                    text=node.text,
                    candidates=candidates,
                    content_hash=element_hash(node),
                )
            )

        route_hint = file_path.stem
        return PageResult(source_file=rel_path, route_hint=route_hint, framework=self.name, elements=elements)
