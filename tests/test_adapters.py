import re

from playwright_locators_forge.adapters.angular import AngularAdapter
from playwright_locators_forge.adapters.base import element_name
from playwright_locators_forge.adapters.html import HtmlAdapter
from playwright_locators_forge.adapters.react import ReactAdapter
from playwright_locators_forge.adapters.svelte import SvelteAdapter
from playwright_locators_forge.adapters.vue import VueAdapter
from playwright_locators_forge.config import DEFAULT_TEST_ID_ATTRS
from playwright_locators_forge.scanner.markup_parser import RawNode


def test_react_adapter_extracts_and_includes_identity_uppercase_component(tmp_path):
    (tmp_path / "about.tsx").write_text(
        """
        export function About() {
          return (
            <div>
              <Card>
                <Button data-testid="submit-btn">Go</Button>
              </Card>
            </div>
          );
        }
        """
    )
    adapter = ReactAdapter()
    files = adapter.discover_files(tmp_path, ["**/*.tsx"], [])
    assert len(files) == 1
    page = adapter.extract(tmp_path, files[0], DEFAULT_TEST_ID_ATTRS)
    tags = [e.tag for e in page.elements]
    assert "Card" not in tags  # noise wrapper excluded
    assert "Button" in tags
    assert page.route_hint == "about"


def test_react_adapter_stable_names_survive_sibling_insertion(tmp_path):
    f1 = tmp_path / "a.tsx"
    f1.write_text('const x = <div><button id="a">A</button><input name="e" /></div>;')
    adapter = ReactAdapter()
    page1 = adapter.extract(tmp_path, f1, DEFAULT_TEST_ID_ATTRS)
    button_name_before = next(e.name for e in page1.elements if e.tag == "button")

    f1.write_text('const x = <div><span>new</span><button id="a">A</button><input name="e" /></div>;')
    page2 = adapter.extract(tmp_path, f1, DEFAULT_TEST_ID_ATTRS)
    button_name_after = next(e.name for e in page2.elements if e.tag == "button")

    assert button_name_before == button_name_after == "a"  # id wins over hash fallback anyway


def test_react_adapter_hash_based_name_stable_across_insertion(tmp_path):
    f1 = tmp_path / "a.tsx"
    f1.write_text('const x = <div><button>Go</button><input name="e" /></div>;')
    adapter = ReactAdapter()
    page1 = adapter.extract(tmp_path, f1, DEFAULT_TEST_ID_ATTRS)
    button_name_before = next(e.name for e in page1.elements if e.tag == "button")

    f1.write_text('const x = <div><span>new</span><button>Go</button><input name="e" /></div>;')
    page2 = adapter.extract(tmp_path, f1, DEFAULT_TEST_ID_ATTRS)
    button_name_after = next(e.name for e in page2.elements if e.tag == "button")

    assert button_name_before == button_name_after
    assert re.fullmatch(r"button_[0-9a-f]{6}", button_name_before)


def test_angular_adapter_external_template(tmp_path):
    (tmp_path / "about.component.ts").write_text(
            """
            import { Component } from '@angular/core';
            @Component({
              selector: 'app-about',
              templateUrl: './about.component.html',
            })
            export class AboutComponent {}
            """
    )
    (tmp_path / "about.component.html").write_text('<button data-testid="submit-btn">Go</button>')
    adapter = AngularAdapter()
    files = adapter.discover_files(tmp_path, ["**/*.ts"], [])
    assert len(files) == 1
    page = adapter.extract(tmp_path, files[0], DEFAULT_TEST_ID_ATTRS)
    assert page.route_hint == "app-about"
    assert page.source_file == "about.component.html"
    assert page.elements[0].name == "submit-btn"


def test_angular_adapter_inline_template_line_offset(tmp_path):
    ts_file = tmp_path / "about.component.ts"
    ts_file.write_text(
        "import { Component } from '@angular/core';\n"
        "@Component({\n"
        "  selector: 'app-about',\n"
        "  template: `\n"
        '    <button data-testid="submit-btn">Go</button>\n'
        "  `,\n"
        "})\n"
        "export class AboutComponent {}\n"
    )
    adapter = AngularAdapter()
    page = adapter.extract(tmp_path, ts_file, DEFAULT_TEST_ID_ATTRS)
    assert page.source_file == "about.component.ts"
    assert page.elements[0].line == 5  # points at the real line in the .ts file


def test_angular_adapter_dynamic_attr_binding(tmp_path):
    (tmp_path / "about.component.ts").write_text(
        "@Component({ selector: 'app-about', templateUrl: './about.component.html' })\n"
        "export class AboutComponent {}\n"
    )
    (tmp_path / "about.component.html").write_text(
        '<button [attr.data-testid]="trackingId" id="static-id">Go</button>'
    )
    adapter = AngularAdapter()
    ts_file = tmp_path / "about.component.ts"
    page = adapter.extract(tmp_path, ts_file, DEFAULT_TEST_ID_ATTRS)
    element = page.elements[0]
    testid_candidate = next(c for c in element.candidates if c.type == "testId")
    assert testid_candidate.dynamic is True


def test_vue_adapter_nested_slot_template(tmp_path):
    f = tmp_path / "About.vue"
    f.write_text(
        "<template>\n"
        "  <div>\n"
        '    <template #header><span>Head</span></template>\n'
        '    <button data-testid="submit-btn">Go</button>\n'
        "  </div>\n"
        "</template>\n"
        "<script setup>\nconst x = 1 < 2;\n</script>\n"
    )
    adapter = VueAdapter()
    page = adapter.extract(tmp_path, f, DEFAULT_TEST_ID_ATTRS)
    tags = [e.tag for e in page.elements]
    assert "span" in tags
    assert "button" in tags
    assert "script" not in tags


def test_svelte_adapter_ignores_script_comparisons(tmp_path):
    f = tmp_path / "About.svelte"
    f.write_text(
        "<script>\n"
        "  let count = 0;\n"
        "  if (count < 10) { count += 1; }\n"
        "</script>\n"
        "<div>\n"
        '  <button data-testid="submit-btn">Go</button>\n'
        "</div>\n"
    )
    adapter = SvelteAdapter()
    page = adapter.extract(tmp_path, f, DEFAULT_TEST_ID_ATTRS)
    assert [e.tag for e in page.elements] == ["div", "button"]
    button = next(e for e in page.elements if e.tag == "button")
    assert button.line == 6


def test_html_adapter_basic(tmp_path):
    f = tmp_path / "index.html"
    f.write_text('<html><body><a href="/x" id="link1">Click</a></body></html>')
    adapter = HtmlAdapter()
    page = adapter.extract(tmp_path, f, DEFAULT_TEST_ID_ATTRS)
    assert [e.tag for e in page.elements] == ["a"]
    assert page.elements[0].name == "link1"


def test_element_name_dedup_on_collision():
    node = RawNode(tag="button", attrs={}, text="Go", line=1)
    seen: set[str] = set()
    first = element_name(node, "abcdef", seen)
    second = element_name(node, "abcdef", seen)  # identical element elsewhere in file
    assert first != second
    assert second == f"{first}_2"


def test_element_name_prefers_testid_then_id_then_hash():
    testid_node = RawNode(tag="button", attrs={"data-testid": "go", "id": "ignored"}, text="", line=1)
    id_node = RawNode(tag="button", attrs={"id": "go2"}, text="", line=1)
    bare_node = RawNode(tag="button", attrs={}, text="", line=1)
    assert element_name(testid_node, "hash1", set()) == "go"
    assert element_name(id_node, "hash2", set()) == "go2"
    assert element_name(bare_node, "abcdef", set()) == "button_abcdef"
