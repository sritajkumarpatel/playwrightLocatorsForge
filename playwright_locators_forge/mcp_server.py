"""MCP server exposing the locator map as first-class tools.

Why this exists: `AGENTS.md`/`CLAUDE.md` instructions only work if the
specific agent runtime happens to load that file into context, and even
then an agent still has to choose to open a markdown file and parse it
by eye instead of reaching for whatever DOM-inspection tool (e.g.
playwright-mcp's snapshot tools) is already sitting in its toolbox.
Exposing `forge resolve`/`forge check` as MCP tools puts the locator map
at the same level of convenience as live DOM inspection, so it's the
easy/obvious choice rather than something an agent has to remember to do.

This is still not a hard guarantee an agent will call these tools first
-- an MCP server can't intercept or block other tool calls the agent has
access to. Tool descriptions below are written directively ("ALWAYS
call this before...") specifically to bias tool selection, but the only
airtight enforcement is verifying agent OUTPUT afterwards (e.g. a CI
check that generated test locators match the map).

Usage: point an MCP client's config at `forge-mcp --root /path/to/repo`
(or run it with FORGE_ROOT set / cwd already at the repo root). See
README.md's "MCP integration" section for example client config.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from playwright_locators_forge.config import load_config
from playwright_locators_forge.resolver import find_page_file, find_stale_elements, list_indexed_pages, parse_page

mcp = FastMCP("playwright-locators-forge")

_ROOT = Path(os.environ.get("FORGE_ROOT", ".")).resolve()


def _output_dir() -> Path:
    return load_config(_ROOT).output_dir


@mcp.tool()
def list_scanned_pages() -> list[dict]:
    """List every page/component already scanned into the locator map,
    with its route hint, framework, and element count.

    ALWAYS call this first when you don't already know the exact page
    identifier to pass to get_page_locators/resolve_locator -- it's
    cheaper and more reliable than guessing a route name or grepping
    source files.
    """
    output_dir = _output_dir()
    if not output_dir.exists():
        return []
    return list_indexed_pages(output_dir)


@mcp.tool()
def get_page_locators(page: str) -> dict:
    """Get every element and its ranked locator for one page/component.

    ALWAYS call this before using a live browser/DOM snapshot tool to
    find locators on a page that's already in the locator map (check
    list_scanned_pages first if unsure). Only fall back to live DOM
    inspection for elements NOT present in the result, elements where
    `locator` is null (every candidate was a runtime binding -- see
    `dynamic_only`), or elements where `stale` is true (source changed
    since the last scan; verify against the live page before trusting
    it).

    `page` accepts a route hint (e.g. "about"), a source file path, or
    an output .md path -- whatever you have on hand.
    """
    output_dir = _output_dir()
    page_path = find_page_file(output_dir, page)
    if page_path is None:
        return {"found": False, "page": page, "elements": []}

    elements = []
    for name, record in parse_page(page_path).items():
        top = record.top()
        elements.append(
            {
                "name": name,
                "tag": record.tag,
                "source": record.source,
                "stale": record.stale,
                "locator": top.value if top else None,
                "locator_type": top.type if top else None,
                "dynamic_only": top is None,
            }
        )
    return {"found": True, "page": page_path.relative_to(output_dir).as_posix(), "elements": elements}


@mcp.tool()
def resolve_locator(page: str, element: str) -> dict:
    """Get the single top-ranked, non-dynamic locator string for one
    named element on one page.

    ALWAYS call this before falling back to a live DOM snapshot tool
    when writing or running a Playwright test against an element that's
    already in the locator map. Use the returned `locator` value exactly
    as given (e.g. `getByTestId("submit-btn")`) rather than re-deriving
    a new one. If `found` is false or `locator` is null, the element
    isn't reliably in the map (unscanned, or every candidate is a
    runtime binding) -- fall back to live inspection in that case, and
    treat `stale=true` as a signal to double-check against the live page
    before trusting the value.
    """
    output_dir = _output_dir()
    page_path = find_page_file(output_dir, page)
    if page_path is None:
        return {"found": False, "locator": None, "stale": False}

    record = parse_page(page_path).get(element)
    if record is None:
        return {"found": False, "locator": None, "stale": False}

    top = record.top()
    return {
        "found": True,
        "locator": top.value if top else None,
        "locator_type": top.type if top else None,
        "stale": record.stale,
    }


@mcp.tool()
def check_freshness() -> dict:
    """Report every element across the whole locator map whose source
    has changed since the last `forge scan`.

    Call this once at the start of a session before relying heavily on
    the locator map, so a widespread stale map (e.g. after a big UI
    refactor nobody re-scanned) doesn't silently feed you wrong
    locators. An empty `stale_elements` list means the map is trustworthy
    as of the last scan.
    """
    output_dir = _output_dir()
    if not output_dir.exists():
        return {"scanned": False, "stale_elements": []}
    return {"scanned": True, "stale_elements": find_stale_elements(output_dir)}


def main() -> None:
    global _ROOT
    parser = argparse.ArgumentParser(prog="forge-mcp", description="MCP server for playwright-locators-forge")
    parser.add_argument(
        "--root", default=None, help="Repo root the locator map belongs to (default: $FORGE_ROOT or cwd)"
    )
    args = parser.parse_args()
    if args.root is not None:
        _ROOT = Path(args.root).resolve()
    mcp.run()


if __name__ == "__main__":
    main()
