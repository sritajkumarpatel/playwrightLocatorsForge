import json

from playwright_locators_forge.config import detect_framework, load_config, load_priority


def test_detect_framework_react(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"dependencies": {"react": "^18"}}))
    assert detect_framework(tmp_path) == "react"


def test_detect_framework_angular_json_present(tmp_path):
    (tmp_path / "angular.json").write_text("{}")
    assert detect_framework(tmp_path) == "angular"


def test_detect_framework_angular_via_deps(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"dependencies": {"@angular/core": "^17"}}))
    assert detect_framework(tmp_path) == "angular"


def test_detect_framework_vue(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"dependencies": {"vue": "^3"}}))
    assert detect_framework(tmp_path) == "vue"


def test_detect_framework_svelte(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"dependencies": {"svelte": "^4"}}))
    assert detect_framework(tmp_path) == "svelte"


def test_detect_framework_falls_back_to_html(tmp_path):
    assert detect_framework(tmp_path) == "html"


def test_detect_framework_falls_back_to_file_extension_scan(tmp_path):
    (tmp_path / "index.tsx").write_text("export default function App() { return null; }")
    assert detect_framework(tmp_path) == "react"


def test_load_priority_defaults_without_file(tmp_path):
    priority = load_priority(tmp_path)
    assert priority["testId"] == 1
    assert priority["xpath"] == max(priority.values())


def test_load_priority_reads_custom_yaml(tmp_path):
    (tmp_path / "locator-priority.yaml").write_text("priority:\n  1: id\n  2: testId\n")
    priority = load_priority(tmp_path)
    assert priority == {"id": 1, "testId": 2}


def test_load_config_defaults_without_file(tmp_path):
    cfg = load_config(tmp_path)
    assert cfg.output == "locators"
    assert "data-testid" in cfg.test_id_attrs


def test_load_config_reads_custom_yaml(tmp_path):
    (tmp_path / ".locatorsforge.yaml").write_text(
        "framework: vue\noutput: my-locators\ntestIdAttributes:\n  - data-qa-id\n"
    )
    cfg = load_config(tmp_path)
    assert cfg.framework == "vue"
    assert cfg.output == "my-locators"
    assert cfg.test_id_attrs == ["data-qa-id"]
    assert cfg.output_dir == tmp_path / "my-locators"
