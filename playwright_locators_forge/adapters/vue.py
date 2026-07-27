"""Vue Single File Component support.

First-draft scope: extract the `<template>...</template>` block with a
regex (SFC section boundaries are simple, line-anchored markers, not
something that needs a full Vue SFC compiler for this purpose) and parse
it with the same HTML walker used for Angular/plain HTML. `<script>` and
`<style>` blocks are ignored entirely -- locators only come from markup.
"""

from __future__ import annotations

import re
from pathlib import Path

from playwright_locators_forge.adapters.base import FrameworkAdapter, glob_files
from playwright_locators_forge.models import Element, PageResult
from playwright_locators_forge.scanner.hashing import element_hash
from playwright_locators_forge.scanner.locator_types import build_candidates
from playwright_locators_forge.scanner.markup_parser import parse_html

_TEMPLATE_BLOCK_RE = re.compile(r"<template[^>]*>(.*?)</template>", re.DOTALL)


class VueAdapter(FrameworkAdapter):
    name = "vue"

    def discover_files(self, root: Path, include: list[str], exclude: list[str]) -> list[Path]:
        files = glob_files(root, include, exclude)
        return [f for f in files if f.suffix == ".vue"]

    def extract(self, root: Path, file_path: Path, test_id_attrs: list[str]) -> PageResult:
        source = file_path.read_text(encoding="utf-8", errors="replace")
        rel_path = file_path.relative_to(root).as_posix()
        route_hint = file_path.stem

        match = _TEMPLATE_BLOCK_RE.search(source)
        if not match:
            return PageResult(source_file=rel_path, route_hint=route_hint, framework=self.name, elements=[])

        line_offset = source[: match.start(1)].count("\n")
        raw_nodes = parse_html(match.group(1))

        elements: list[Element] = []
        for idx, node in enumerate(raw_nodes):
            candidates = build_candidates(node, test_id_attrs)
            name = node.attrs.get("data-testid") or node.attrs.get("id") or f"{node.tag}_{idx}"
            elements.append(
                Element(
                    name=name,
                    tag=node.tag,
                    file=rel_path,
                    line=node.line + line_offset,
                    attrs=node.attrs,
                    text=node.text,
                    candidates=candidates,
                    content_hash=element_hash(node),
                )
            )

        return PageResult(source_file=rel_path, route_hint=route_hint, framework=self.name, elements=elements)
