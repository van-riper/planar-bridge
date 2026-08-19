# Planar Bridge

Planar Bridge is a cross-platform tool for downloading and maintaining locally
stored high-quality card scans from Magic: the Gathering.

All scans are obtained from [Scryfall](https://scryfall.com/) via their online
card database. Bulk datasets used to drive the downloads come from
[MTGJSON](https://mtgjson.com/).

Planar Bridge also upgrades the resolution on cards when a higher resolution
becomes available. If a low-resolution scan exists locally, Planar Bridge
replaces it with a higher-resolution scan once Scryfall has one. This helps
with cards from a newly spoiled set that have not been scanned at a crisp
high resolution yet.

Planar Bridge is currently unstable, so expect the config format and CLI to
change before v1 is released.

## Installation

Planar Bridge is supported on Linux and macOS. It is expected (not yet tested)
to function on Windows. It requires at least Python 3.13.0, so check your
installed Python version if you are unsure:

```sh
$ python3 -V
Python 3.13.0
```

(note that lines in code blocks beginning with `$` mean this line is used as
a user-executed command)

To install Planar Bridge, start by cloning this repository.

```sh
$ git clone --depth=1 https://github.com/van-riper/planar-bridge.git
```

Then set up the environment with [uv](https://docs.astral.sh/uv/), which
installs the runtime and development dependencies into a local virtual
environment:

```sh
$ uv sync
```

## Usage

To run Planar Bridge, use the `planar-bridge` console script (or the
equivalent module form, `uv run python -m planar_bridge`):

```sh
$ uv run planar-bridge
[12:34:56] INFO: Comparing local & source files...
...
```

Planar Bridge will then begin the download process. Keep in mind that with over
600 categorized sets, downloading all card scans will take several hours even
with the fastest internet connection. However, you can kill the program and
start it later, and it will resume where it left off.

Useful flags:

```sh
$ uv run planar-bridge --set LEA --set LEB   # restrict the run to these sets
$ uv run planar-bridge --dry-run             # report what would download, write nothing
$ uv run planar-bridge --language de         # override the configured card language
$ uv run planar-bridge -y                    # skip the MTGJSON version-drift prompt
```

### Data directory

Planar Bridge stores all card scans, bulk data, and its catalog database
outside the repo, in a data directory it creates on first run. Resolution
order:

1. `$PLANAR_BRIDGE_DIR`, if set
2. `$HOME/.local/share/planar-bridge` (Linux/macOS) or
   `%APPDATA%/planar-bridge` (Windows)

Here is an example layout of that directory with some example set codes and
phony UUIDs:

```txt
planar-bridge/                 (the data directory)
├─ .mtgjson/
│  ├─ AllPrintings.sqlite
│  └─ Meta.json
├─ catalog.sqlite
├─ config.toml
├─ LEA/
│  ├─ tokens/
│  │  ├─ 01234567-89ab-cdef-0123-456789abcdef.jpg
│  │  └─ ...
│  ├─ 01234567-89ab-cdef-fedc-ba9876543210.jpg
│  ├─ fedcba98-7654-3210-0123-456789abcdef.jpg
│  └─ ...
├─ LEB/
│  └─ ...
└─ ...
```

Planar Bridge names card image files according to that card's UUID from
MTGJSON's database. Cards that share a single image across two faces (split,
flip, adventure, aftermath layouts) are named by joining both UUIDs with `_`.
At this time, there is no way to name a card file according to that card's
name.

`.mtgjson/` holds the MTGJSON bulk database (`AllPrintings.sqlite`) and its
metadata (`Meta.json`), fetched once and reused on later runs.
`catalog.sqlite` is a small SQLite database recording each downloaded card's
resolution; it replaces what used to be a `.states.json` file per set, and is
what lets a killed run resume from exactly where it left off. Do not modify or
delete it, since it drives both resuming and resolution upgrades.

## Development

Planar Bridge is developed with [uv](https://docs.astral.sh/uv/). After
`uv sync`, the dev tooling runs through `uv run`:

```sh
$ uv run pytest                    # run the test suite
$ uv run ruff check src tests      # lint
$ uv run ruff format src tests     # format
$ uv run ty check                  # type-check
```

## Configuration

If you want to configure Planar Bridge, copy `config.example.toml` from this
repo to `config.toml` inside your data directory (see
[Data directory](#data-directory) above).

Configuration options let you enable reprints, set a preferred card language,
and choose which sets, set types, and promo types to exclude from the
download process. For more information on set and promo types, visit
[MTGJSON](https://mtgjson.com/).

For now, the configuration of Planar Bridge is limited, so if you have a
suggestion for more options to configure, feel free to
[open an issue](https://github.com/van-riper/planar-bridge/issues/new/).

## Terms of Use

By downloading and running this program, you agree to Wizards of the Coast's
[Fan Content Policy](https://company.wizards.com/en/legal/fancontentpolicy/) as
well as Scryfall's [Terms of Service](https://scryfall.com/docs/terms/).
If you have any questions about what you can/cannot do regarding these
policies, carefully read each article and FAQ on the links to WotC's and
Scryfall's terms and conditions.

This program has been made with the intent of respecting the 50 - 100
millisecond request rate limit that Scryfall denotes on its website:

> We kindly ask that you insert 50 – 100 milliseconds of delay between the
> requests you send to the server at api.scryfall.com. (i.e., 10 requests per
> second on average).
>
> Submitting excessive requests to the server may result in a HTTP 429 Too Many
> Requests status code. Overloading the API after this point may result in a
> temporary or permanent ban of your IP address. Applications that continously
> recieve rate limit warnings over a longer period may also be blocked.
>
> \- [Scryfall's API homepage](https://scryfall.com/docs/api/) (Sep 2024)

Do not modify or remove this program's built-in rate limiter, which keeps
every request to Scryfall under that limit. If you remove it, your IP address
will likely get blocked, either temporarily or permanently.

With that being said, Planar Bridge and its developers accept zero
responsibility regarding incidents that breach WotC's, Scryfall's, and/or
Planar Bridge's terms and conditions.

## Credits

Logo based on 'Portal' design made by [Lorc](https://lorcblog.blogspot.com/).

## License

This project is developed under an MIT License. For more information, see
[LICENSE](https://github.com/van-riper/planar-bridge/blob/main/LICENSE).
