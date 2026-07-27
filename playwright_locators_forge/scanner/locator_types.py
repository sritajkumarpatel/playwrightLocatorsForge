"""Turns a RawNode (tag/attrs/text) into candidate locators, and ranks
candidates according to the project's locator-priority.yaml.

Ranking is intentionally a separate, cheap step from extraction: `forge
rank` re-sorts already-extracted candidates using the current priority
file without re-parsing any source, so editing priority is instant and
safe to do often.
"""

from __future__ import annotations

from playwright_locators_forge.models import LocatorCandidate
from playwright_locators_forge.scanner.markup_parser import RawNode

# Implicit ARIA roles for common HTML tags, used when there's no explicit
# `role` attribute. Not exhaustive -- covers what actually shows up in
# Playwright's getByRole() day to day.
_IMPLICIT_ROLES: dict[str, str] = {
    "button": "button",
    "a": "link",
    "input": "textbox",
    "textarea": "textbox",
    "select": "combobox",
    "h1": "heading",
    "h2": "heading",
    "h3": "heading",
    "h4": "heading",
    "h5": "heading",
    "h6": "heading",
    "img": "img",
    "table": "table",
    "ul": "list",
    "ol": "list",
    "li": "listitem",
    "nav": "navigation",
    "form": "form",
    "dialog": "dialog",
}

_INPUT_ROLE_BY_TYPE = {
    "button": "button",
    "submit": "button",
    "reset": "button",
    "checkbox": "checkbox",
    "radio": "radio",
    "range": "slider",
}


def _resolve_attr(node: RawNode, base_name: str) -> tuple[str, bool] | None:
    """Find `base_name` under its static form or any bound-attribute form
    (Angular `[base_name]`/`[attr.base_name]`, Vue `:base_name`/
    `v-bind:base_name`), returning (value, is_dynamic) or None if absent.
    """
    attrs = node.attrs
    if base_name in attrs and attrs[base_name]:
        return attrs[base_name], base_name in node.dynamic_attrs

    bound_forms = (
        f"[{base_name}]",
        f"[attr.{base_name}]",
        f":{base_name}",
        f"v-bind:{base_name}",
    )
    for form in bound_forms:
        if form in attrs and attrs[form]:
            return attrs[form], True
    return None


def _role_for(tag: str, attrs: dict[str, str]) -> str | None:
    if "role" in attrs and attrs["role"]:
        return attrs["role"]
    if tag == "input":
        input_type = attrs.get("type", "text").lower()
        return _INPUT_ROLE_BY_TYPE.get(input_type, "textbox")
    return _IMPLICIT_ROLES.get(tag)


def build_candidates(node: RawNode, test_id_attrs: list[str]) -> list[LocatorCandidate]:
    """Generate every locator candidate we can support for one element."""
    candidates: list[LocatorCandidate] = []
    attrs = node.attrs

    for test_attr in test_id_attrs:
        found = _resolve_attr(node, test_attr)
        if found is None:
            continue
        value, dynamic = found
        candidates.append(
            LocatorCandidate(
                type="testId",
                value=f'getByTestId("{value}")' if not dynamic else f"expr: {value}",
                dynamic=dynamic,
                note="" if not dynamic else f"{test_attr} is a runtime binding, not a literal value",
            )
        )

    id_found = _resolve_attr(node, "id")
    if id_found is not None:
        value, dynamic = id_found
        candidates.append(
            LocatorCandidate(
                type="id",
                value=f'locator("#{value}")' if not dynamic else f"expr: {value}",
                dynamic=dynamic,
                note="" if not dynamic else "id is a runtime binding, not a literal value",
            )
        )

    aria_label_found = _resolve_attr(node, "aria-label")
    role = _role_for(node.tag, attrs)
    if role:
        accessible_name = (aria_label_found[0] if aria_label_found else None) or node.text or None
        if accessible_name:
            candidates.append(
                LocatorCandidate(
                    type="role",
                    value=f'getByRole("{role}", name="{accessible_name}")',
                )
            )
        else:
            candidates.append(LocatorCandidate(type="role", value=f'getByRole("{role}")'))

    if aria_label_found is not None:
        value, dynamic = aria_label_found
        candidates.append(
            LocatorCandidate(
                type="label",
                value=f'getByLabel("{value}")' if not dynamic else f"expr: {value}",
                dynamic=dynamic,
                note="" if not dynamic else "aria-label is a runtime binding, not a literal value",
            )
        )

    name_found = _resolve_attr(node, "name")
    if name_found is not None:
        value, dynamic = name_found
        candidates.append(
            LocatorCandidate(
                type="name",
                value=f'locator("[name=\\"{value}\\"]")' if not dynamic else f"expr: {value}",
                dynamic=dynamic,
                note="" if not dynamic else "name is a runtime binding, not a literal value",
            )
        )

    if node.text and node.tag in {"button", "a", "h1", "h2", "h3", "h4", "h5", "h6", "label", "span"}:
        candidates.append(LocatorCandidate(type="text", value=f'getByText("{node.text}")'))

    class_attr = attrs.get("class") or attrs.get("className")
    if class_attr:
        css_classes = ".".join(c for c in class_attr.split() if c)
        if css_classes:
            candidates.append(LocatorCandidate(type="css", value=f'locator("{node.tag}.{css_classes}")'))

    # xpath is the guaranteed-available fallback -- always emitted last so
    # there's never a "no candidates" element, even for anonymous nodes.
    xpath_predicate = ""
    if node.text:
        xpath_predicate = f"[contains(normalize-space(.), \"{node.text[:40]}\")]"
    elif attrs:
        first_attr, first_val = next(iter(attrs.items()))
        if first_val and first_attr not in node.dynamic_attrs:
            xpath_predicate = f'[@{first_attr}="{first_val}"]'
    candidates.append(LocatorCandidate(type="xpath", value=f"//{node.tag}{xpath_predicate}"))

    return candidates


def rank_candidates(
    candidates: list[LocatorCandidate], priority: dict[str, int]
) -> list[tuple[int, LocatorCandidate]]:
    """Sort candidates by the project's priority.yaml.

    Static candidates always sort ahead of dynamic ones, regardless of
    type priority -- a dynamic testId is less trustworthy than a static
    id, since it can't be resolved without a live DOM check. Within each
    of those two groups, ordering follows the configured type priority.
    """
    default_rank = max(priority.values(), default=99) + 1

    def sort_key(c: LocatorCandidate):
        return (c.dynamic, priority.get(c.type, default_rank))

    ordered = sorted(candidates, key=sort_key)
    return [(i + 1, c) for i, c in enumerate(ordered)]
