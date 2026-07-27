"""Angular support.

Two template shapes are handled:

1. External template (`templateUrl: './about.component.html'`) -- by far
   the common case. We resolve the path relative to the .ts file and parse
   the .html file directly, so line numbers point at the real template.
2. Inline template (a backtick-delimited `template:` string inside
   @Component({...})) -- we
   pull the backtick/string literal out of the .ts source and parse it as
   HTML, offsetting line numbers back to their position in the .ts file so
   `file:line` in the output still points somewhere useful.

This uses regex over the decorator, not a full TypeScript AST, which is a
deliberate first-draft tradeoff: `@Component({...})` metadata is simple,
regular, boilerplate-y syntax, and a full TS parser is a lot of machinery
for marginal accuracy gain here. Revisit if decorator metadata gets
programmatically generated in a target repo.
"""

from __future__ import annotations

import re
from pathlib import Path

from playwright_locators_forge.adapters.base import FrameworkAdapter, glob_files
from playwright_locators_forge.models import Element, PageResult
from playwright_locators_forge.scanner.hashing import element_hash
from playwright_locators_forge.scanner.locator_types import build_candidates
from playwright_locators_forge.scanner.markup_parser import parse_html

_TEMPLATE_URL_RE = re.compile(r"templateUrl\s*:\s*['\"]([^'\"]+)['\"]")
_INLINE_TEMPLATE_RE = re.compile(r"template\s*:\s*`(.*?)`", re.DOTALL)
_SELECTOR_RE = re.compile(r"selector\s*:\s*['\"]([^'\"]+)['\"]")


class AngularAdapter(FrameworkAdapter):
    name = "angular"

    def discover_files(self, root: Path, include: list[str], exclude: list[str]) -> list[Path]:
        candidates = glob_files(root, [p for p in include if p.endswith(".ts")] or ["**/*.ts"], exclude)
        return [f for f in candidates if "@Component" in f.read_text(encoding="utf-8", errors="replace")]

    def extract(self, root: Path, file_path: Path, test_id_attrs: list[str]) -> PageResult:
        source = file_path.read_text(encoding="utf-8", errors="replace")
        selector_match = _SELECTOR_RE.search(source)
        route_hint = selector_match.group(1) if selector_match else file_path.stem

        template_url_match = _TEMPLATE_URL_RE.search(source)
        if template_url_match:
            html_path = (file_path.parent / template_url_match.group(1)).resolve()
            if not html_path.exists():
                return PageResult(
                    source_file=file_path.relative_to(root).as_posix(),
                    route_hint=route_hint,
                    framework=self.name,
                    elements=[],
                )
            html_source = html_path.read_text(encoding="utf-8", errors="replace")
            rel_path = html_path.relative_to(root).as_posix()
            line_offset = 0
        else:
            inline_match = _INLINE_TEMPLATE_RE.search(source)
            if not inline_match:
                return PageResult(
                    source_file=file_path.relative_to(root).as_posix(),
                    route_hint=route_hint,
                    framework=self.name,
                    elements=[],
                )
            html_source = inline_match.group(1)
            rel_path = file_path.relative_to(root).as_posix()
            line_offset = source[: inline_match.start(1)].count("\n")

        raw_nodes = parse_html(html_source)
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
                    line=node.line + line_offset,
                    attrs=node.attrs,
                    text=node.text,
                    candidates=candidates,
                    content_hash=element_hash(node),
                )
            )

        return PageResult(source_file=rel_path, route_hint=route_hint, framework=self.name, elements=elements)
