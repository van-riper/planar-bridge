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

# Test, lint, format
uv run pytest
uv run pylint src/planar_bridge
uv run black src tests
```

The test suite currently holds only an import smoke test; real coverage arrives with the
domain-extraction work (see the rewrite plan).

## Runtime layout & environment

The data directory is resolved once at import time in `paths.py` and **must already exist**
or startup raises `FileNotFoundError`. Resolution order:

1. `$PLANAR_BRIDGE_DIR`
2. `$XDG_DATA_HOME/planar-bridge` (POSIX) or `%AppData%/planar-bridge` (Windows)

Inside the data dir: `.json/` holds `AllPrintings.json` + `Meta.json`; each set lives in
`<SET_CODE>/` (tokens under `<SET_CODE>/tokens/`); `config.toml` is read from here.
Note: this differs from the older `imgs/` + `json/` tree shown in the README.

`config.toml` is optional and layered over `constants.DEFAULT_CONFIG`. See `config.example.toml`.

## Architecture

The pull pipeline is a three-level loop, driven entirely by MTGJSON's `AllPrintings.json`:

- **`pull.py`** — orchestration. `pull_all()` → `pull_meta()` (refresh bulk files if
  outdated) → iterate sets → `pull_set()` → iterate cards → `pull_card()`. The control
  flow leans on MTGJSON's data shape and on the `.states.json` cache to decide what to skip.
- **`objects.py`** — the domain model, where almost all logic lives:
  - `MetaObject` — compares local vs. remote MTGJSON `date`/`version`. Same date →
    `SystemExit` (nothing to do). Version drift → interactive `y/N` prompt.
  - `SetObject` — wraps one set entry; computes `to_omit` (exempt types/sets, online/foreign
    only), merges `cards` + `tokens`, tracks progress, installs the SIGINT handler.
  - `CardFields` — derives per-card facts from the raw dict: `is_bad` (reprints, wrong
    language, funny, online-only, bad/blacklisted layouts, exempt promos), `filename`
    (combined layouts join all `otherFaceIds` UUIDs with `_`), and `face` for two-sided cards.
  - `CardObject` — does the network work: `parse_source_state()` queries Scryfall for
    `image_status`, decides whether a download/upgrade is needed; `download()` fetches the
    image (appending `&face=` for two-sided layouts).
  - `StatesObject` — reads/writes `.states.json`, the per-set map of `filename -> is_highres`.
    `is_all_highres()` lets a fully-upgraded set be skipped on later runs.
- **`constants.py`** — the pinned `MTGJSON_VERS`, the request `TIMEOUT` (rate limiting), layout
  category lists, language map, and `DEFAULT_CONFIG`.
- **`config.py`** — loads `config.toml`, overlays it on defaults, maps the language code to
  MTGJSON's full language name. Exposes a module-level singleton `CONFIG`.
- **`utils.py`** — colorized `status()` logger (integer levels 0–6), `handle_response()`
  (retries HTTP errors 4× with escalating backoff, returns `None` on giving up), progress
  string formatting.

### State & resumability

The program is designed to be killed and resumed. Progress is persisted entirely in each
set's `.states.json`. `write_states()` is called on normal completion, on download failure
(then `raise RuntimeError`), and from the SIGINT handler (Ctrl-C) — so a card is only marked
done once its scan is confirmed. On restart, cards already at the recorded resolution with an
existing file are skipped without hitting the network.

### Rate limiting — do not remove

`constants.TIMEOUT` (0.33s) is `sleep`'d before every Scryfall request to honor Scryfall's
50–100ms / ~10-req-per-second limit. The README's Terms of Use explicitly forbids removing
or shortening this; doing so risks an IP ban. Treat it as load-bearing.

## Conventions

- New modules use package-relative imports (e.g. `from .pull import ...`) and live under
  `src/planar_bridge/`, matching the generously blank-line-spaced function bodies already in
  the codebase.
- `MTGJSON_VERS` in `constants.py` is the version the code is validated against; bumping it is
  a deliberate act, since `MetaObject.is_outdated()` warns the user on any mismatch.
