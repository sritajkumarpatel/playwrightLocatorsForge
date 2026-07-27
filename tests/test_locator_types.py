from playwright_locators_forge.config import DEFAULT_PRIORITY, DEFAULT_TEST_ID_ATTRS
from playwright_locators_forge.scanner.locator_types import build_candidates, rank_candidates
from playwright_locators_forge.scanner.markup_parser import RawNode


def _node(tag, attrs=None, text="", dynamic_attrs=None):
    return RawNode(tag=tag, attrs=attrs or {}, text=text, line=1, dynamic_attrs=dynamic_attrs or set())


def test_testid_candidate_generated():
    node = _node("button", {"data-testid": "submit-btn"})
    candidates = build_candidates(node, DEFAULT_TEST_ID_ATTRS)
    testid = next(c for c in candidates if c.type == "testId")
    assert testid.value == 'getByTestId("submit-btn")'
    assert testid.dynamic is False


def test_id_and_role_and_implicit_role_for_button():
    node = _node("button", {"id": "go"}, text="Go")
    candidates = build_candidates(node, DEFAULT_TEST_ID_ATTRS)
    types = {c.type for c in candidates}
    assert {"id", "role", "text", "xpath"} <= types
    role = next(c for c in candidates if c.type == "role")
    assert role.value == 'getByRole("button", name="Go")'


def test_input_type_submit_maps_to_button_role():
    node = _node("input", {"type": "submit"})
    candidates = build_candidates(node, DEFAULT_TEST_ID_ATTRS)
    role = next(c for c in candidates if c.type == "role")
    assert 'getByRole("button"' in role.value


def test_xpath_always_present_as_fallback():
    node = _node("div")
    candidates = build_candidates(node, DEFAULT_TEST_ID_ATTRS)
    assert any(c.type == "xpath" for c in candidates)


def test_angular_dynamic_testid_binding_flagged():
    node = _node(
        "button",
        {"[attr.data-testid]": "trackingId", "id": "static-id"},
        dynamic_attrs={"[attr.data-testid]"},
    )
    candidates = build_candidates(node, DEFAULT_TEST_ID_ATTRS)
    testid = next(c for c in candidates if c.type == "testId")
    assert testid.dynamic is True
    id_candidate = next(c for c in candidates if c.type == "id")
    assert id_candidate.dynamic is False


def test_rank_static_always_beats_dynamic_regardless_of_type_priority():
    """Regression: a dynamic testId (priority 1) must never outrank a
    static id (priority 2) -- being unresolvable without a live DOM check
    matters more than the nominal type priority."""
    node = _node(
        "button",
        {"[attr.data-testid]": "trackingId", "id": "static-id"},
        text="Go",
        dynamic_attrs={"[attr.data-testid]"},
    )
    candidates = build_candidates(node, DEFAULT_TEST_ID_ATTRS)
    ranked = rank_candidates(candidates, DEFAULT_PRIORITY)
    rank_1_type, rank_1_candidate = 1, ranked[0][1]
    assert ranked[0][0] == rank_1_type
    assert rank_1_candidate.type == "id"
    assert rank_1_candidate.dynamic is False
    # every dynamic candidate ranks after every static one
    first_dynamic_rank = next(r for r, c in ranked if c.dynamic)
    last_static_rank = max(r for r, c in ranked if not c.dynamic)
    assert first_dynamic_rank > last_static_rank


def test_rank_respects_custom_priority_order():
    node = _node("button", {"data-testid": "submit-btn", "id": "go"}, text="Go")
    candidates = build_candidates(node, DEFAULT_TEST_ID_ATTRS)
    custom_priority = {**DEFAULT_PRIORITY, "id": 0}  # id now beats testId
    ranked = rank_candidates(candidates, custom_priority)
    assert ranked[0][1].type == "id"
