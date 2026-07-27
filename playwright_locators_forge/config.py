"""Loads the two config files a consuming repo owns:

  .locatorsforge.yaml   -- what to scan, which framework, where to write output
  locator-priority.yaml -- the ranking order, edited by whoever owns test quality

Both are plain YAML so anyone on the team can edit them without touching
Python. Framework auto-detection only runs when `.locatorsforge.yaml`
doesn't pin a framework, so a monorepo with mixed stacks can still force
the right adapter per scan.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_TEST_ID_ATTRS = ["data-testid", "data-test", "data-cy", "data-qa"]
DEFAULT_INCLUDE = ["**/*.tsx", "**/*.jsx", "**/*.html", "**/*.vue"]
DEFAULT_EXCLUDE = ["**/node_modules/**", "**/dist/**", "**/build/**", "**/*.spec.*", "**/*.test.*"]

DEFAULT_PRIORITY = {
    "testId": 1,
    "id": 2,
    "role": 3,
    "label": 4,
    "name": 5,
    "text": 6,
    "css": 7,
    "xpath": 8,
}


@dataclass
class ForgeConfig:
    root: Path
    framework: str = "auto"
    include: list[str] = field(default_factory=lambda: list(DEFAULT_INCLUDE))
    exclude: list[str] = field(default_factory=lambda: list(DEFAULT_EXCLUDE))
    output: str = "locators"
    test_id_attrs: list[str] = field(default_factory=lambda: list(DEFAULT_TEST_ID_ATTRS))

    @property
    def output_dir(self) -> Path:
        return self.root / self.output


def load_config(root: Path) -> ForgeConfig:
    path = root / ".locatorsforge.yaml"
    if not path.exists():
        return ForgeConfig(root=root, framework=detect_framework(root))

    raw = yaml.safe_load(path.read_text()) or {}
    cfg = ForgeConfig(
        root=root,
        framework=raw.get("framework", "auto"),
        include=raw.get("include") or list(DEFAULT_INCLUDE),
        exclude=raw.get("exclude") or list(DEFAULT_EXCLUDE),
        output=raw.get("output", "locators"),
        test_id_attrs=raw.get("testIdAttributes") or list(DEFAULT_TEST_ID_ATTRS),
    )
    if cfg.framework == "auto":
        cfg.framework = detect_framework(root)
    return cfg


def load_priority(root: Path) -> dict[str, int]:
    path = root / "locator-priority.yaml"
    if not path.exists():
        return dict(DEFAULT_PRIORITY)
    raw = yaml.safe_load(path.read_text()) or {}
    priority_map = raw.get("priority") or {}
    # yaml numeric keys load as int already; normalize just in case.
    return {v: int(k) for k, v in priority_map.items()}


def detect_framework(root: Path) -> str:
    package_json = root / "package.json"
    if (root / "angular.json").exists():
        return "angular"
    if package_json.exists():
        try:
            data = json.loads(package_json.read_text())
        except (json.JSONDecodeError, OSError):
            data = {}
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        if "@angular/core" in deps:
            return "angular"
        if "vue" in deps:
            return "vue"
        if "svelte" in deps:
            return "svelte"
        if "react" in deps:
            return "react"
    if list(root.rglob("*.vue")):
        return "vue"
    if list(root.rglob("*.tsx")) or list(root.rglob("*.jsx")):
        return "react"
    return "html"
