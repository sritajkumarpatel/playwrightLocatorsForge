"""Content hashing used to detect drift between the source code and a
manually-maintained locators/*.md file.

The hash covers only what would actually change a locator (tag + attrs +
text), not line numbers -- reformatting/moving an element shouldn't mark
it stale, but changing its testid/id/text should.
"""

from __future__ import annotations

import hashlib

from playwright_locators_forge.scanner.markup_parser import RawNode


def element_hash(node: RawNode) -> str:
    attr_part = "&".join(f"{k}={v}" for k, v in sorted(node.attrs.items()))
    payload = f"{node.tag}|{attr_part}|{node.text}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
