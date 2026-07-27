from playwright_locators_forge.config import DEFAULT_PRIORITY, DEFAULT_TEST_ID_ATTRS
from playwright_locators_forge.models import Element, PageResult
from playwright_locators_forge.render.markdown import render_page, write_pages
from playwright_locators_forge.resolver import find_page_file, parse_page, parse_page_hashes, resolve_locator
from playwright_locators_forge.scanner.hashing import element_hash
from playwright_locators_forge.scanner.locator_types import build_candidates
from playwright_locators_forge.scanner.markup_parser import RawNode


def _page_from_source(name="submit-btn"):
    node = RawNode(tag="button", attrs={"data-testid": name}, text="Go", line=10)
    candidates = build_candidates(node, DEFAULT_TEST_ID_ATTRS)
    element = Element(
        name=name,
        tag="button",
        file="src/about.tsx",
        line=10,
        attrs=node.attrs,
        text="Go",
        candidates=candidates,
        content_hash=element_hash(node),
    )
    return PageResult(source_file="src/about.tsx", route_hint="about", framework="react", elements=[element])


def test_render_page_contains_ranked_locator_table():
    page = _page_from_source()
    md = render_page(page, DEFAULT_PRIORITY)
    assert "### submit-btn" in md
    assert "getByTestId" in md
    assert "| rank | type | locator | dynamic | note |" in md


def test_write_pages_and_resolve(tmp_path):
    page = _page_from_source()
    write_pages(tmp_path, [page], DEFAULT_PRIORITY)

    locator = resolve_locator(tmp_path, "about", "submit-btn")
    assert locator == 'getByTestId("submit-btn")'

    # also resolvable by source-file-derived route
    page_path = find_page_file(tmp_path, "about")
    assert page_path is not None
    assert page_path.exists()


def test_stale_flag_appears_when_source_changes(tmp_path):
    page = _page_from_source()
    write_pages(tmp_path, [page], DEFAULT_PRIORITY)

    # simulate the source changing: same element name, different hash
    changed_node = RawNode(tag="button", attrs={"data-testid": "submit-btn"}, text="Go now", line=10)
    changed_candidates = build_candidates(changed_node, DEFAULT_TEST_ID_ATTRS)
    changed_element = Element(
        name="submit-btn",
        tag="button",
        file="src/about.tsx",
        line=10,
        attrs=changed_node.attrs,
        text="Go now",
        candidates=changed_candidates,
        content_hash=element_hash(changed_node),
    )
    changed_page = PageResult(
        source_file="src/about.tsx", route_hint="about", framework="react", elements=[changed_element]
    )
    write_pages(tmp_path, [changed_page], DEFAULT_PRIORITY)

    page_path = find_page_file(tmp_path, "about")
    records = parse_page(page_path)
    assert records["submit-btn"].stale is True


def test_no_stale_flag_when_hash_unchanged(tmp_path):
    page = _page_from_source()
    write_pages(tmp_path, [page], DEFAULT_PRIORITY)
    write_pages(tmp_path, [page], DEFAULT_PRIORITY)  # re-scan with identical content

    page_path = find_page_file(tmp_path, "about")
    records = parse_page(page_path)
    assert records["submit-btn"].stale is False


def test_resolve_locator_missing_element_returns_none(tmp_path):
    page = _page_from_source()
    write_pages(tmp_path, [page], DEFAULT_PRIORITY)
    assert resolve_locator(tmp_path, "about", "does-not-exist") is None


def test_parse_page_hashes(tmp_path):
    page = _page_from_source()
    write_pages(tmp_path, [page], DEFAULT_PRIORITY)
    page_path = find_page_file(tmp_path, "about")
    hashes = parse_page_hashes(page_path)
    assert hashes["submit-btn"] == element_hash(
        RawNode(tag="button", attrs={"data-testid": "submit-btn"}, text="Go", line=10)
    )
