"""forge scan | rank | resolve | check | init

See README.md for the full workflow. Quick reference:

  forge init                      drop config templates + AGENTS.md snippet into the current repo
  forge scan                      scan the repo, write locators/*.md + a JSON cache
  forge rank                      re-sort existing results against locator-priority.yaml (no re-scan)
  forge resolve --page X --el Y   print the top-ranked locator for one element
  forge check                     exit non-zero if any element drifted from source since last scan
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from playwright_locators_forge.adapters import get_adapter
from playwright_locators_forge.config import load_config, load_priority
from playwright_locators_forge.models import PageResult, page_from_dict, page_to_dict
from playwright_locators_forge.render.markdown import write_pages
from playwright_locators_forge.resolver import find_stale_elements, resolve_locator

CACHE_FILENAME = ".forge-cache.json"


def _scan(root: Path, framework_override: str | None) -> list[PageResult]:
    cfg = load_config(root)
    framework = framework_override or cfg.framework
    adapter = get_adapter(framework)
    files = adapter.discover_files(root, cfg.include, cfg.exclude)

    pages: list[PageResult] = []
    for file_path in files:
        page = adapter.extract(root, file_path, cfg.test_id_attrs)
        if page.elements:
            pages.append(page)
    return pages


def cmd_scan(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    cfg = load_config(root)
    priority = load_priority(root)
    pages = _scan(root, args.framework)

    written = write_pages(cfg.output_dir, pages, priority)
    cache_path = cfg.output_dir / CACHE_FILENAME
    cache_path.write_text(json.dumps([page_to_dict(p) for p in pages], indent=2), encoding="utf-8")

    print(f"Scanned {len(pages)} file(s), {sum(len(p.elements) for p in pages)} element(s).")
    print(f"Wrote {len(written)} file(s) to {cfg.output_dir}")
    return 0


def cmd_rank(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    cfg = load_config(root)
    priority = load_priority(root)
    cache_path = cfg.output_dir / CACHE_FILENAME

    if not cache_path.exists():
        print(f"No cache found at {cache_path}. Run `forge scan` first.", file=sys.stderr)
        return 1

    pages = [page_from_dict(d) for d in json.loads(cache_path.read_text())]
    written = write_pages(cfg.output_dir, pages, priority)
    print(f"Re-ranked {len(pages)} page(s) against locator-priority.yaml. Wrote {len(written)} file(s).")
    return 0


def cmd_resolve(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    cfg = load_config(root)
    locator = resolve_locator(cfg.output_dir, args.page, args.element)
    if locator is None:
        print(f"No locator found for page='{args.page}' element='{args.element}'.", file=sys.stderr)
        return 1
    print(locator)
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    cfg = load_config(root)
    if not cfg.output_dir.exists():
        print(f"No locators output at {cfg.output_dir}. Run `forge scan` first.", file=sys.stderr)
        return 1

    stale = find_stale_elements(cfg.output_dir)
    if stale:
        by_page: dict[str, list[str]] = {}
        for row in stale:
            by_page.setdefault(row["page"], []).append(row["element"])
        for page, names in by_page.items():
            print(f"{page}: {len(names)} stale element(s): {', '.join(names)}")
        print(f"\n{len(stale)} stale element(s) found. Run `forge scan` to refresh.")
        return 1

    print("No drift detected.")
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    # Ship templates inside the package itself (not the repo root) so
    # `forge init` works from any installed copy -- editable install,
    # regular install, or a built wheel -- not just a repo checkout.
    templates_dir = Path(__file__).resolve().parent / "templates"
    if not templates_dir.exists():
        print(
            f"Template directory not found at {templates_dir} -- the installed "
            "package is missing its templates. Reinstall with `pip install -e .` "
            "from the playwright-locators-forge repo.",
            file=sys.stderr,
        )
        return 1

    targets = {
        templates_dir / "locator-priority.yaml": root / "locator-priority.yaml",
        templates_dir / ".locatorsforge.yaml": root / ".locatorsforge.yaml",
        templates_dir / "AGENTS.snippet.md": root / "AGENTS.forge-snippet.md",
    }

    for src, dest in targets.items():
        if dest.exists() and not args.force:
            print(f"Skipping {dest} (already exists, use --force to overwrite)")
            continue
        dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Wrote {dest}")

    print(
        "\nNext: merge AGENTS.forge-snippet.md into your AGENTS.md/CLAUDE.md so "
        "agents driving Playwright MCP check the locator map first, then run `forge scan`."
    )
    return 0


def _add_root_arg(p: argparse.ArgumentParser, *, is_top_level: bool) -> None:
    """Add --root to a parser.

    Deliberately does NOT use argparse's `parents=` mechanism to share one
    action object across the top-level parser and every subparser: that
    seems convenient, but `ArgumentParser.set_defaults()` mutates
    `action.default` on every action it finds with a matching `dest` in
    `self._actions` -- so if the same Action instance is registered on
    both the main parser and a subparser, calling `set_defaults` on the
    main parser silently overwrites the subparser's default too (they're
    the same object). That corrupted `--root` back to "." even when a
    subparser instance's own args never referenced it. Giving each parser
    its own independently-constructed action sidesteps that entirely.
    """
    p.add_argument(
        "--root",
        default="." if is_top_level else argparse.SUPPRESS,
        help="Repo root to operate on (default: current directory)",
    )


def build_parser() -> argparse.ArgumentParser:
    # --root needs to work both before AND after the subcommand
    # (`forge --root X scan` and `forge scan --root X`) -- argparse hands
    # remaining argv to the subparser once it sees the subcommand token,
    # so the top-level parser alone isn't enough for the second form.
    # Subparser copies default to SUPPRESS so an *unset* --root there
    # doesn't clobber a value already parsed at the top level.
    parser = argparse.ArgumentParser(prog="forge", description="Playwright Locators Forge")
    _add_root_arg(parser, is_top_level=True)
    sub = parser.add_subparsers(dest="command", required=True)

    p_scan = sub.add_parser("scan", help="Scan the repo and (re)generate locators/*.md")
    _add_root_arg(p_scan, is_top_level=False)
    p_scan.add_argument("--framework", default=None, help="Override auto-detected framework")
    p_scan.set_defaults(func=cmd_scan)

    p_rank = sub.add_parser("rank", help="Re-rank existing results against locator-priority.yaml")
    _add_root_arg(p_rank, is_top_level=False)
    p_rank.set_defaults(func=cmd_rank)

    p_resolve = sub.add_parser("resolve", help="Print the top-ranked locator for one element")
    _add_root_arg(p_resolve, is_top_level=False)
    p_resolve.add_argument("--page", required=True, help="Route hint, source file, or output .md path")
    p_resolve.add_argument("--element", required=True, help="Element name as shown in the locators .md file")
    p_resolve.set_defaults(func=cmd_resolve)

    p_check = sub.add_parser("check", help="Fail if any element drifted from source since the last scan")
    _add_root_arg(p_check, is_top_level=False)
    p_check.set_defaults(func=cmd_check)

    p_init = sub.add_parser("init", help="Drop config templates + AGENTS.md snippet into this repo")
    _add_root_arg(p_init, is_top_level=False)
    p_init.add_argument("--force", action="store_true", help="Overwrite existing config files")
    p_init.set_defaults(func=cmd_init)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
