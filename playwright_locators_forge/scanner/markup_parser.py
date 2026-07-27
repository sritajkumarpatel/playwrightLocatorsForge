"""tree-sitter based markup walkers.

Two entry points, `parse_html` and `parse_jsx`, both return a flat list of
`RawNode`. Everything downstream (locator_types.py) works off that single
shape, so adapters never need to know tree-sitter node types directly --
they just pick the right parser for the markup they extracted.

Angular templates, Vue `<template>` blocks, and plain `.html` files all go
through `parse_html`; React/Preact JSX goes through `parse_jsx`. Angular's
bracket/paren attribute syntax (`[attr.data-testid]="expr"`, `*ngIf="x"`,
`(click)="x"`) tokenizes fine as ordinary HTML attribute names -- HTML5
allows any character in an attribute name except whitespace, `"`, `'`,
`>`, `/`, `=` -- so no Angular-specific grammar is needed here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import tree_sitter_html
import tree_sitter_typescript
from tree_sitter import Language, Parser

# Tags that are almost never meaningful test targets on their own; skip them
# to keep output focused on interactive/identifiable elements.
_SKIP_TAGS = {"script", "style", "html", "head", "meta", "link", "br", "hr"}


@lru_cache(maxsize=None)
def _html_parser() -> Parser:
    return Parser(Language(tree_sitter_html.language()))


@lru_cache(maxsize=None)
def _tsx_parser() -> Parser:
    return Parser(Language(tree_sitter_typescript.language_tsx()))


@dataclass
class RawNode:
    tag: str
    attrs: dict[str, str]
    text: str
    line: int  # 1-indexed
    dynamic_attrs: set[str] = field(default_factory=set)  # attribute names
    # whose value is a runtime binding/expression rather than a literal
    # string, e.g. Angular `[attr.data-testid]`, Vue `:id`, JSX `{expr}`.


def _decode(source_bytes: bytes, node) -> str:
    return source_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def parse_html(source: str) -> list[RawNode]:
    parser = _html_parser()
    source_bytes = source.encode("utf-8")
    tree = parser.parse(source_bytes)
    nodes: list[RawNode] = []

    def walk(node):
        if node.type == "element":
            start_tag = next((c for c in node.children if c.type == "start_tag"), None)
            if start_tag is not None:
                tag_name_node = next((c for c in start_tag.children if c.type == "tag_name"), None)
                tag = _decode(source_bytes, tag_name_node) if tag_name_node else ""
                attrs: dict[str, str] = {}
                dynamic_attrs: set[str] = set()
                for attr in (c for c in start_tag.children if c.type == "attribute"):
                    name_node = next((c for c in attr.children if c.type == "attribute_name"), None)
                    value_node = next(
                        (c for c in attr.children if c.type in ("quoted_attribute_value", "attribute_value")),
                        None,
                    )
                    if name_node is None:
                        continue
                    name = _decode(source_bytes, name_node)
                    value = ""
                    if value_node is not None:
                        raw = _decode(source_bytes, value_node)
                        value = raw.strip("\"'")
                    attrs[name] = value
                    # Angular `[x]`/`(x)`/`*x`, Vue `:x`/`v-bind:x`, or a
                    # mustache interpolation in the value -> not a literal.
                    if (
                        name[:1] in "[(*"
                        or name.startswith(":")
                        or name.startswith("v-bind:")
                        or "{{" in value
                    ):
                        dynamic_attrs.add(name)
                if tag and tag.lower() not in _SKIP_TAGS:
                    text_parts = [
                        _decode(source_bytes, c).strip()
                        for c in node.children
                        if c.type == "text" and _decode(source_bytes, c).strip()
                    ]
                    nodes.append(
                        RawNode(
                            tag=tag,
                            attrs=attrs,
                            text=" ".join(text_parts)[:120],
                            line=node.start_point[0] + 1,
                            dynamic_attrs=dynamic_attrs,
                        )
                    )
        for child in node.children:
            walk(child)

    walk(tree.root_node)
    return nodes


def parse_jsx(source: str) -> list[RawNode]:
    parser = _tsx_parser()
    source_bytes = source.encode("utf-8")
    tree = parser.parse(source_bytes)
    nodes: list[RawNode] = []

    def extract_opening(opening_node):
        tag_node = next(
            (c for c in opening_node.children if c.type in ("identifier", "member_expression")),
            None,
        )
        tag = _decode(source_bytes, tag_node) if tag_node else ""
        attrs: dict[str, str] = {}
        dynamic_attrs: set[str] = set()
        for attr in (c for c in opening_node.children if c.type == "jsx_attribute"):
            name_node = attr.children[0] if attr.children else None
            if name_node is None:
                continue
            name = _decode(source_bytes, name_node)
            value = ""
            value_node = next(
                (c for c in attr.children if c.type in ("string", "jsx_expression")),
                None,
            )
            if value_node is not None:
                raw = _decode(source_bytes, value_node)
                value = raw.strip("\"'{}").strip()
                if value_node.type == "jsx_expression":
                    dynamic_attrs.add(name)
            attrs[name] = value
        return tag, attrs, dynamic_attrs

    def collect_text(node) -> str:
        parts = []
        for c in node.children:
            if c.type == "jsx_text":
                t = _decode(source_bytes, c).strip()
                if t:
                    parts.append(t)
        return " ".join(parts)[:120]

    def walk(node):
        if node.type == "jsx_element":
            opening = next((c for c in node.children if c.type == "jsx_opening_element"), None)
            if opening is not None:
                tag, attrs, dynamic_attrs = extract_opening(opening)
                if tag and tag[0].islower() and tag.lower() not in _SKIP_TAGS:
                    nodes.append(
                        RawNode(
                            tag=tag,
                            attrs=attrs,
                            text=collect_text(node),
                            line=node.start_point[0] + 1,
                            dynamic_attrs=dynamic_attrs,
                        )
                    )
        elif node.type == "jsx_self_closing_element":
            tag, attrs, dynamic_attrs = extract_opening(node)
            if tag and tag[0].islower() and tag.lower() not in _SKIP_TAGS:
                nodes.append(
                    RawNode(
                        tag=tag,
                        attrs=attrs,
                        text="",
                        line=node.start_point[0] + 1,
                        dynamic_attrs=dynamic_attrs,
                    )
                )
        for child in node.children:
            walk(child)

    walk(tree.root_node)
    return nodes
