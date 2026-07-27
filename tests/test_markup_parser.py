from playwright_locators_forge.scanner.markup_parser import (
    extract_top_level_block,
    parse_html,
    parse_jsx,
    strip_top_level_blocks,
)


def test_parse_html_basic_attrs_and_text():
    nodes = parse_html('<button id="go" aria-label="Go now">Go</button>')
    assert len(nodes) == 1
    node = nodes[0]
    assert node.tag == "button"
    assert node.attrs == {"id": "go", "aria-label": "Go now"}
    assert node.text == "Go"
    assert node.line == 1


def test_parse_html_skips_script_and_style_content():
    # A comparison operator in embedded JS must not be mistaken for a tag.
    src = "<div><script>if (1 < 2) { x(); }</script><p>Body</p></div>"
    nodes = parse_html(src)
    tags = [n.tag for n in nodes]
    assert tags == ["div", "p"]


def test_parse_html_angular_dynamic_binding_detected():
    nodes = parse_html('<button [attr.data-testid]="expr" id="static">Go</button>')
    node = nodes[0]
    assert node.attrs["[attr.data-testid]"] == "expr"
    assert "[attr.data-testid]" in node.dynamic_attrs
    assert "id" not in node.dynamic_attrs


def test_parse_html_vue_binding_and_mustache_detected():
    nodes = parse_html('<span :id="dynId" title="{{ mustache }}">x</span>')
    node = nodes[0]
    assert ":id" in node.dynamic_attrs
    assert "title" in node.dynamic_attrs  # mustache interpolation in value


def test_parse_jsx_basic():
    nodes = parse_jsx('const x = <button data-testid="submit">Go</button>;')
    assert len(nodes) == 1
    assert nodes[0].tag == "button"
    assert nodes[0].attrs["data-testid"] == "submit"
    assert nodes[0].text == "Go"


def test_parse_jsx_expression_attr_is_dynamic():
    nodes = parse_jsx('const x = <button id={computedId}>Go</button>;')
    assert "id" in nodes[0].dynamic_attrs


def test_parse_jsx_uppercase_component_without_identity_attr_excluded():
    nodes = parse_jsx('const x = <Card><Flex onClick={f} /></Card>;')
    assert nodes == []


def test_parse_jsx_uppercase_component_with_identity_attr_included():
    src = 'const x = <Card><Button data-testid="submit">Go</Button></Card>;'
    nodes = parse_jsx(src)
    tags = [n.tag for n in nodes]
    assert "Card" not in tags
    assert "Button" in tags


def test_extract_top_level_block_handles_nested_slot_template():
    src = (
        "<template>\n"
        "  <div>\n"
        '    <template #header><span>Head</span></template>\n'
        "    <p>Body</p>\n"
        "  </div>\n"
        "</template>\n"
        "<script>let x = 1;</script>\n"
    )
    block = extract_top_level_block(src, "template")
    assert block is not None
    inner, _ = block
    nodes = parse_html(inner)
    tags_and_text = [(n.tag, n.text) for n in nodes]
    assert ("span", "Head") in tags_and_text
    assert ("p", "Body") in tags_and_text  # previously lost by the old regex


def test_extract_top_level_block_missing_tag_returns_none():
    assert extract_top_level_block("<div>no template here</div>", "template") is None


def test_strip_top_level_blocks_preserves_line_numbers():
    src = (
        "<script>\n"
        "  if (1 < 2) { doStuff(); }\n"
        "</script>\n"
        "<div>\n"
        "  <button id=\"go\">Go</button>\n"
        "</div>\n"
    )
    stripped = strip_top_level_blocks(src, {"script", "style"})
    nodes = parse_html(stripped)
    assert [n.tag for n in nodes] == ["div", "button"]
    button = next(n for n in nodes if n.tag == "button")
    assert button.line == 5  # unchanged despite script content being blanked
