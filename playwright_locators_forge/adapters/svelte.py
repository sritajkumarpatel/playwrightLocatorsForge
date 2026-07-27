"""Svelte support.

Unlike Vue, a Svelte component has no wrapping `<template>` -- markup
sits at the top level alongside `<script>`/`<style>` blocks. So instead
of extracting one named block (`extract_top_level_block`), this strips
the `<script>`/`<style>` blocks out (`strip_top_level_blocks`) and parses
whatever's left as HTML. Svelte control-flow blocks (`{#if}`, `{#each}`,
`{:else}`, ...) and bindings (`bind:value`, `on:click`, `class:active`)
tokenize fine as HTML text/attribute syntax -- they don't need special
handling for locator extraction, the same way Angular's `[x]`/`(x)`
syntax doesn't.
"""

from __future__ import annotations

from pathlib import Path

from playwright_locators_forge.adapters.base import FrameworkAdapter, element_name, glob_files
from playwright_locators_forge.models import Element, PageResult
from playwright_locators_forge.scanner.hashing import element_hash
from playwright_locators_forge.scanner.locator_types import build_candidates
from playwright_locators_forge.scanner.markup_parser import parse_html, strip_top_level_blocks


class SvelteAdapter(FrameworkAdapter):
    name = "svelte"

    def discover_files(self, root: Path, include: list[str], exclude: list[str]) -> list[Path]:
        files = glob_files(root, include, exclude)
        return [f for f in files if f.suffix == ".svelte"]

    def extract(self, root: Path, file_path: Path, test_id_attrs: list[str]) -> PageResult:
        source = file_path.read_text(encoding="utf-8", errors="replace")
        rel_path = file_path.relative_to(root).as_posix()

        markup = strip_top_level_blocks(source, {"script", "style"})
        raw_nodes = parse_html(markup)

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
                    line=node.line,
                    attrs=node.attrs,
                    text=node.text,
                    candidates=candidates,
                    content_hash=content_hash,
                )
            )

        return PageResult(source_file=rel_path, route_hint=file_path.stem, framework=self.name, elements=elements)
