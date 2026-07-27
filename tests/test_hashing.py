from playwright_locators_forge.scanner.hashing import element_hash
from playwright_locators_forge.scanner.markup_parser import RawNode


def _node(tag="button", attrs=None, text="", line=1):
    return RawNode(tag=tag, attrs=attrs or {}, text=text, line=line)


def test_hash_stable_for_identical_content():
    a = _node(attrs={"id": "go"}, text="Go", line=5)
    b = _node(attrs={"id": "go"}, text="Go", line=42)  # different line, same content
    assert element_hash(a) == element_hash(b)


def test_hash_changes_when_attrs_change():
    a = _node(attrs={"id": "go"})
    b = _node(attrs={"id": "stop"})
    assert element_hash(a) != element_hash(b)


def test_hash_changes_when_text_changes():
    a = _node(text="Go")
    b = _node(text="Stop")
    assert element_hash(a) != element_hash(b)


def test_hash_independent_of_attr_insertion_order():
    a = RawNode(tag="input", attrs={"name": "email", "type": "text"}, text="", line=1)
    b = RawNode(tag="input", attrs={"type": "text", "name": "email"}, text="", line=1)
    assert element_hash(a) == element_hash(b)
