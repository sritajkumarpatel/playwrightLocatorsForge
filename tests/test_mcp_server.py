"""Tests the MCP tool functions directly as plain Python callables.

FastMCP's @mcp.tool() decorator registers the function for the server's
tool registry but doesn't wrap/replace it, so these can be exercised
without spinning up a real MCP client/stdio round-trip (that's covered
manually against a real client -- see the module docstring in
mcp_server.py for how). This keeps the test suite fast and dependency-light
while still verifying the actual logic these tools run.
"""

from playwright_locators_forge import mcp_server
from playwright_locators_forge.config import DEFAULT_PRIORITY, DEFAULT_TEST_ID_ATTRS
from playwright_locators_forge.models import Element, PageResult
from playwright_locators_forge.render.markdown import write_pages
from playwright_locators_forge.scanner.hashing import element_hash
from playwright_locators_forge.scanner.locator_types import build_candidates
from playwright_locators_forge.scanner.markup_parser import RawNode


def _seed_locator_map(tmp_path):
    node = RawNode(tag="button", attrs={"data-testid": "submit-btn"}, text="Go", line=10)
    element = Element(
        name="submit-btn",
        tag="button",
        file="src/about.tsx",
        line=10,
        attrs=node.attrs,
        text="Go",
        candidates=build_candidates(node, DEFAULT_TEST_ID_ATTRS),
        content_hash=element_hash(node),
    )
    page = PageResult(source_file="src/about.tsx", route_hint="about", framework="react", elements=[element])
    write_pages(tmp_path / "locators", [page], DEFAULT_PRIORITY)


def test_list_scanned_pages(tmp_path, monkeypatch):
    _seed_locator_map(tmp_path)
    monkeypatch.setattr(mcp_server, "_ROOT", tmp_path)
    pages = mcp_server.list_scanned_pages()
    assert len(pages) == 1
    assert pages[0]["route_hint"] == "about"
    assert pages[0]["element_count"] == 1


def test_list_scanned_pages_before_any_scan(tmp_path, monkeypatch):
    monkeypatch.setattr(mcp_server, "_ROOT", tmp_path)
    assert mcp_server.list_scanned_pages() == []


def test_get_page_locators_found(tmp_path, monkeypatch):
    _seed_locator_map(tmp_path)
    monkeypatch.setattr(mcp_server, "_ROOT", tmp_path)
    result = mcp_server.get_page_locators("about")
    assert result["found"] is True
    element = result["elements"][0]
    assert element["name"] == "submit-btn"
    assert element["locator"] == 'getByTestId("submit-btn")'
    assert element["dynamic_only"] is False


def test_get_page_locators_not_found(tmp_path, monkeypatch):
    _seed_locator_map(tmp_path)
    monkeypatch.setattr(mcp_server, "_ROOT", tmp_path)
    result = mcp_server.get_page_locators("does-not-exist")
    assert result["found"] is False
    assert result["elements"] == []


def test_resolve_locator_found(tmp_path, monkeypatch):
    _seed_locator_map(tmp_path)
    monkeypatch.setattr(mcp_server, "_ROOT", tmp_path)
    result = mcp_server.resolve_locator("about", "submit-btn")
    assert result == {"found": True, "locator": 'getByTestId("submit-btn")', "locator_type": "testId", "stale": False}


def test_resolve_locator_missing_page(tmp_path, monkeypatch):
    monkeypatch.setattr(mcp_server, "_ROOT", tmp_path)
    result = mcp_server.resolve_locator("nope", "nope")
    assert result["found"] is False
    assert result["locator"] is None


def test_resolve_locator_missing_element(tmp_path, monkeypatch):
    _seed_locator_map(tmp_path)
    monkeypatch.setattr(mcp_server, "_ROOT", tmp_path)
    result = mcp_server.resolve_locator("about", "does-not-exist")
    assert result["found"] is False


def test_check_freshness_clean(tmp_path, monkeypatch):
    _seed_locator_map(tmp_path)
    monkeypatch.setattr(mcp_server, "_ROOT", tmp_path)
    result = mcp_server.check_freshness()
    assert result == {"scanned": True, "stale_elements": []}


def test_check_freshness_before_any_scan(tmp_path, monkeypatch):
    monkeypatch.setattr(mcp_server, "_ROOT", tmp_path)
    result = mcp_server.check_freshness()
    assert result == {"scanned": False, "stale_elements": []}


def test_check_freshness_detects_stale(tmp_path, monkeypatch):
    _seed_locator_map(tmp_path)
    monkeypatch.setattr(mcp_server, "_ROOT", tmp_path)

    # re-scan with the element's underlying content changed -> stale
    changed_node = RawNode(tag="button", attrs={"data-testid": "submit-btn"}, text="Go now", line=10)
    changed_element = Element(
        name="submit-btn",
        tag="button",
        file="src/about.tsx",
        line=10,
        attrs=changed_node.attrs,
        text="Go now",
        candidates=build_candidates(changed_node, DEFAULT_TEST_ID_ATTRS),
        content_hash=element_hash(changed_node),
    )
    changed_page = PageResult(
        source_file="src/about.tsx", route_hint="about", framework="react", elements=[changed_element]
    )
    write_pages(tmp_path / "locators", [changed_page], DEFAULT_PRIORITY)

    result = mcp_server.check_freshness()
    assert result["scanned"] is True
    assert len(result["stale_elements"]) == 1
    assert result["stale_elements"][0]["element"] == "submit-btn"
