"""Vue Single File Component support.

Extracts the root-level `<template>...</template>` block by walking the
actual parse tree (see `extract_top_level_block`), not a regex, so a
nested `<template #slotName>` used for a named slot doesn't get mistaken
for the end of the outer template. The extracted markup is parsed with
the same HTML walker used for Angular/plain HTML. `<script>`/`<style>`
blocks are ignored entirely -- locators only come from markup.
"""

from __future__ import annotations

from pathlib import Path

from playwright_locators_forge.adapters.base import FrameworkAdapter, element_name, glob_files
from playwright_locators_forge.models import Element, PageResult
from playwright_locators_forge.scanner.hashing import element_hash
from playwright_locators_forge.scanner.locator_types import build_candidates
from playwright_locators_forge.scanner.markup_parser import extract_top_level_block, parse_html


class VueAdapter(FrameworkAdapter):
    name = "vue"

    def discover_files(self, root: Path, include: list[str], exclude: list[str]) -> list[Path]:
        files = glob_files(root, include, exclude)
        return [f for f in files if f.suffix == ".vue"]

    def extract(self, root: Path, file_path: Path, test_id_attrs: list[str]) -> PageResult:
        source = file_path.read_text(encoding="utf-8", errors="replace")
        rel_path = file_path.relative_to(root).as_posix()
        route_hint = file_path.stem

        block = extract_top_level_block(source, "template")
        if block is None:
            return PageResult(source_file=rel_path, route_hint=route_hint, framework=self.name, elements=[])

        template_source, line_offset = block
        raw_nodes = parse_html(template_source)

        elements: list[Element] = []
        seen_names: set[str] = set()
        for node in raw_nodes:
            candidates = build_candidates(node, test_id_attrs)
            content_hash = element_hash(node)
            name = element_name(node, content_hash, seen_names)
            elements.append(
                Element(
                    name=name,
                    tag=node.tag,
                    file=rel_path,
                    line=node.line + line_offset,
                    attrs=node.attrs,
                    text=node.text,
                    candidates=candidates,
                    content_hash=content_hash,
                )
            )

        return PageResult(source_file=rel_path, route_hint=route_hint, framework=self.name, elements=elements)
