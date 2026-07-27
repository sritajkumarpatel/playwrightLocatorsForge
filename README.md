# playwright-locators-forge

Scans a frontend repo — React, Angular, Vue, or plain HTML — and builds a
maintained, priority-ranked **locator map** (`locators/*.md`) that agents
and test authors can use instead of re-discovering locators from a live
DOM every time they drive Playwright (or Playwright MCP).

The problem this solves: picking the "right" Playwright locator (test id
vs id vs role vs label vs a brittle CSS/XPath fallback) is tedious to do
by hand, page by page, and Playwright MCP has no built-in concept of your
team's locator preferences or of dynamically-bound attributes. This tool
turns that into a one-time-per-change scan, with the ranking rule kept in
one file anyone can edit.

## Install

Requires Python 3.10+. No Node.js runtime needed — markup parsing uses
`tree-sitter` with the `tree-sitter-html` and `tree-sitter-typescript`
grammar packages, not a JS toolchain.

This is a standalone CLI tool (`forge`), not something you copy into the
repo you're scanning — install it once, in its own virtual environment,
then point it at any other project's path.

```bash
# 1. From this repo, create and activate a virtual environment
cd /path/to/playwrightLocatorsForge
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install the package (and its deps) into that venv
pip install -e .
```

`forge` is now on `PATH` for as long as this venv stays activated in your
shell. To use it again in a new terminal session, just re-run `source
.venv/bin/activate` from this repo — no need to reinstall.

If you'd rather not activate the venv every time, either:
- call it by full path: `/path/to/playwrightLocatorsForge/.venv/bin/forge`, or
- `pip install -e /path/to/playwrightLocatorsForge` into whatever Python
  environment you normally use for tooling.

## Quickstart (in the repo you want to scan)

With the venv above still activated, `cd` into the *target* repo — the
frontend project whose locators you want to map, completely separate from
this tool's own repo:

```bash
cd /path/to/your/frontend/repo
forge init          # drops .locatorsforge.yaml, locator-priority.yaml,
                     # and AGENTS.forge-snippet.md into this repo
forge scan          # scans the repo, writes locators/*.md + INDEX.md
```

Every `forge` command also accepts `--root <path>` if you'd rather stay
in this tool's directory and point at the target repo explicitly, e.g.
`forge --root /path/to/your/frontend/repo scan`.

Check the output:

```bash
cat locators/INDEX.md
cat locators/src/pages/about.md      # or whichever page you care about
forge resolve --page about --element submit-btn
```

Commit `locators/` (and the two config files) to the target repo. Re-run
`forge scan` whenever the UI changes; `forge check` in CI catches drift
that wasn't re-scanned.

## Where to use this

This is meant to live **inside the frontend repo it describes** (or as a
sibling package a monorepo pulls in), not as a one-off local script:

- **In the repo, committed.** `locators/` is checked in like a lockfile —
  changes to it show up in `git diff` / PR review, so a stale locator map
  is visible, not invisible.
- **In CI**, run `forge check` — it exits non-zero if any element's
  source (tag/attrs/text) changed since the map was last regenerated, so
  a PR that changes markup without re-running `forge scan` fails loudly
  instead of silently going stale.
- **Ahead of Playwright MCP / any agent writing or running Playwright
  tests.** Merge `AGENTS.forge-snippet.md` (written by `forge init`) into
  your `AGENTS.md`/`CLAUDE.md`. It tells the agent: check `locators/`
  first, use the rank-1 locator for each element, and only fall back to a
  live DOM inspection via Playwright MCP for unscanned UI, elements
  marked `dynamic: yes`, or elements flagged `⚠️ stale`. There's no MCP
  "pre-hook" that enforces this automatically — it works because agents
  read project instructions, so the convention has to be in your
  AGENTS.md/CLAUDE.md for it to take effect.
- **Not** a replacement for ever inspecting the live DOM — it's a fast
  path for the common case (stable, already-scanned UI) that keeps
  Playwright MCP's live inspection for genuinely new or dynamic elements.

## How it works

1. **Adapters** (`playwright_locators_forge/adapters/`) turn
   framework-specific source into plain markup:
   - React: JSX inline in `.tsx`/`.jsx`
   - Angular: external `templateUrl` files, or inline `template:` strings
     in `@Component({...})`
   - Vue: the `<template>` block of `.vue` SFCs
   - Plain HTML (also works for server-rendered templates like
     Jinja/ERB/Blade, since directives outside tag attributes are ignored)
2. A shared **tree-sitter scanner** walks that markup and extracts every
   candidate locator per element: `data-testid`/`data-test`/`data-cy`,
   `id`, ARIA role (explicit or inferred from tag), `aria-label`, `name`,
   visible text, a class-based CSS selector, and an XPath fallback.
   Attributes that are runtime bindings (Angular `[attr.x]`, Vue `:x`,
   JSX `{expr}`) are kept but flagged `dynamic: yes` — they can't be
   trusted as static locators without a live check.
3. **`locator-priority.yaml`** (the one file meant to be hand-edited)
   defines the global rank order. `forge rank` re-sorts every already-
   scanned element against it instantly, with no re-parsing of source.
4. **`render/markdown.py`** writes one `.md` file per source file, plus
   an `INDEX.md`, in a fixed table format that's both human-readable and
   reliably machine-parsable (`resolver.py` reads it back for `forge
   resolve`/`forge check`).

## CLI reference

```
forge init                                  # scaffold config + AGENTS.md snippet in target repo
forge scan [--framework react|angular|vue|html]
forge rank                                  # re-rank existing results against locator-priority.yaml
forge resolve --page <route-or-file> --element <name>
forge check                                 # non-zero exit if any element drifted since last scan
```

All commands accept `--root <path>` (default: current directory).

## Config files (live in the scanned repo, not here)

- **`.locatorsforge.yaml`** — framework, include/exclude globs, output
  dir, which attributes count as `testId`.
- **`locator-priority.yaml`** — the rank order (see above). This is the
  single knob for "prefer ids over roles" style team preferences.

## Current scope / first-draft limitations

- Angular decorator parsing uses regex over `@Component({...})`, not a
  full TypeScript AST — fine for standard boilerplate, may miss
  programmatically-constructed decorator metadata.
- Vue SFC `<template>` extraction is a regex block match; nested
  `<template>` tags inside slots are not specially handled.
- Svelte and other frameworks aren't implemented yet — add a new
  `FrameworkAdapter` in `adapters/` (see `adapters/base.py`) to extend.
- `forge check` compares against the hash stored the last time `forge
  scan` ran, not against git history directly — run it after `forge
  scan` in CI, not as a standalone git-diff check.
