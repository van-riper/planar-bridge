# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Planar Bridge downloads and maintains a local library of high-quality Magic: the Gathering
card scans. Card images come from [Scryfall](https://scryfall.com/); the bulk set/card
metadata used to drive the downloads comes from [MTGJSON](https://mtgjson.com/). The
signature feature is *resolution upgrading*: if a locally stored scan is low-res and a
`highres_scan` later becomes available on Scryfall, it is re-downloaded.

## Commands

Requires Python >= 3.13 (enforced at startup in `__main__.py`). The project uses a src
layout (`src/planar_bridge/`) and is managed with [uv](https://docs.astral.sh/uv/).

```sh
# Set up the dev environment (runtime + dev deps from pyproject.toml; creates .venv)
uv sync

# Run the program (console script, or the equivalent module form)
uv run planar-bridge
uv run python -m planar_bridge

# Test, lint, format, type-check
uv run pytest
uv run ruff check src tests
uv run ruff format src tests
uv run ty check
```

181 tests cover the whole `src/` tree at 99% line coverage; `ruff check` and `ty check`
are both clean on the current tree.

## Runtime layout & environment

The data directory is resolved in `paths.py::load_paths()` and created on demand (`mkdir
-p`, via `ensure_directories_exist()`) rather than required to pre-exist. Resolution order:

1. `$PLANAR_BRIDGE_DIR`
2. `$HOME/.local/share/planar-bridge` (Linux/macOS) or `%APPDATA%/planar-bridge` (Windows) —
   note this reads `$HOME`/`$APPDATA` directly, not `$XDG_DATA_HOME`.

Inside the data dir: `.mtgjson/` holds the MTGJSON bulk database (`AllPrintings.sqlite`) and
its metadata (`Meta.json`); each set lives in `<SET_CODE>/` (tokens under
`<SET_CODE>/tokens/`); `catalog.sqlite` is the per-card resolution catalog; `config.toml` is
read from the data dir root. This differs from the `imgs/` + `json/` tree shown in older
versions of the README.

`config.toml` is optional and layered over `config.defaults.DEFAULT_*` values in
`config/loader.py::load_config()`. See `config.example.toml`.

## Architecture

The pull pipeline is a three-level loop, driven by MTGJSON's `AllPrintings.sqlite`:

- **`pipeline/run.py`** — the composition root. `pull_all()` builds the shared `httpx`
  client, rate limiter, and sources, then calls `pull_meta()` and walks every set.
- **`pipeline/metadata.py`** — `pull_meta()`: compares the local MTGJSON version against
  `constants.MTGJSON_VERSION`; on drift, emits `VersionMismatch` and consults an
  `approve_version` callback (the CLI's `--assume-yes` flag or an interactive `y/n` prompt
  from `cli/prompt.py`) before continuing. Refetches `Meta.json` only when it is missing.
- **`pipeline/download.py`** — `_pull_sets()` → `pull_set()` → `pull_card()`. Cards within a
  set download concurrently under an `asyncio.Semaphore` bounded by
  `constants.MAX_CONCURRENT_DOWNLOADS`.
- **`pipeline/context.py`** — `PullContext` (run-wide dependencies), `SetObject` (a set's
  record, image directory, and progress counter), `CardObject` (a card's derived facts,
  image path, and catalog state).
- **`domain/`** — pure, I/O-free functions reading MTGJSON dicts and the resolved
  `AppConfig`:
  - `card_model.py` — `build_card_fields()`; `card_is_bad()` (reprints, wrong language,
    funny, online-only, bad layouts, exempt promos); `card_filename()` (combined layouts —
    split/flip/adventure/aftermath — join every face UUID with `_`); `card_face()` for
    two-sided layouts.
  - `set_model.py` — `build_set_record()`; `set_is_omitted()` (exempt types/sets,
    foreign/online-only, unless pardoned).
  - `decisions.py` — `decide_download()`, the pure upgrade/skip decision from Scryfall's
    reported image status plus local state.
  - `metadata.py` — `version_matches_pin()`, `normalize_version()`.
  - `layouts.py` — the layout category sets (`LAYOUT_TWOSIDED`, `LAYOUT_COMBINED`,
    `LAYOUT_BAD`, `LAYOUT_TOKEN`).
- **`catalog/`** — the only layer that knows SQLite. `repository.py::CatalogRepository`
  persists one row per card (`filename`, `set_code`, `uuid`, `is_high_resolution`,
  `relative_path`, `updated_at`) in `catalog.sqlite`, replacing the old per-set
  `.states.json` files; `upsert_card()` commits immediately. `schema.py` holds the DDL and
  `SCHEMA_VERSION`.
- **`sources/`** — `bulk.py::BulkReader` is an anti-corruption layer over
  `AllPrintings.sqlite`, projecting cards/tokens back into the JSON-shaped dicts the domain
  expects; `mtgjson.py` and `scryfall.py` wrap the two network APIs behind the `ports.py`
  protocols (`MetadataSource`, `ImageSource`, `BulkSource`).
- **`engine/`** — `client.py::AsyncHttpClient` wraps `httpx` with retry/backoff
  (`RetryPolicy`); `limiter.py::RateLimiter` enforces the shared requests-per-second cap
  across concurrent requests.
- **`events/`** + **`reporters/console.py`** — the engine emits typed, data-only `Event`
  subclasses (`SetStarted`, `CardDownloaded`, `CardFailed`, `RunFinished`, ...) on an
  `EventBus`; `ConsoleReporter` is the only place that knows about color, timestamps, and
  message text, so a future non-console reporter can subscribe to the same stream.
- **`cli/`** — `args.py` (argparse → `RunOptions`), `main.py` (the console-script entry
  point, Python-version guard, Ctrl-C handling), `prompt.py` (the version-drift `y/n`
  prompt — the only `input()` call in the program).
- **`constants.py`** — the pinned `MTGJSON_VERSION`, `MAX_REQUESTS_PER_SECOND`,
  `MAX_CONCURRENT_DOWNLOADS`, and the Scryfall `HTTP_HEADERS`.

### State & resumability

The program is designed to be killed and resumed. Progress is persisted in
`catalog.sqlite`: `CatalogRepository.upsert_card()` commits immediately after each card, so a
card is only marked done once its scan is confirmed. On restart, `pull_card()` skips a card
without hitting the network when the catalog already records it at the current resolution
and its image file still exists on disk.

### Rate limiting — do not remove

`constants.MAX_REQUESTS_PER_SECOND` (9.0) is enforced by `engine.limiter.RateLimiter`,
shared across all in-flight requests, to hold every Scryfall request under Scryfall's
50–100ms / ~10-req-per-second limit. The README's Terms of Use explicitly forbids removing
or loosening this; doing so risks an IP ban. Treat it as load-bearing.

## Conventions

- New modules use absolute, package-rooted imports (e.g.
  `from planar_bridge.config.loader import AppConfig`) and live under
  `src/planar_bridge/`, matching the generously blank-line-spaced function bodies already in
  the codebase.
- `MTGJSON_VERSION` in `constants.py` is the version the code is validated against; bumping
  it is a deliberate act, since `domain.metadata.version_matches_pin()` warns the user on
  any mismatch.
