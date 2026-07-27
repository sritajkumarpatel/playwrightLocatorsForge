from playwright_locators_forge.adapters.angular import AngularAdapter
from playwright_locators_forge.adapters.base import FrameworkAdapter
from playwright_locators_forge.adapters.html import HtmlAdapter
from playwright_locators_forge.adapters.react import ReactAdapter
from playwright_locators_forge.adapters.svelte import SvelteAdapter
from playwright_locators_forge.adapters.vue import VueAdapter

ADAPTERS: dict[str, type[FrameworkAdapter]] = {
    "react": ReactAdapter,
    "angular": AngularAdapter,
    "vue": VueAdapter,
    "svelte": SvelteAdapter,
    "html": HtmlAdapter,
}


def get_adapter(framework: str) -> FrameworkAdapter:
    try:
        return ADAPTERS[framework]()
    except KeyError as exc:
        raise ValueError(
            f"Unknown framework '{framework}'. Supported: {', '.join(ADAPTERS)}"
        ) from exc
