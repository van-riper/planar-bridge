<p align="center">
  <img
    width="256"
    src="https://user-images.githubusercontent.com/64651989/159095590-39a9c3ce-4a44-46b1-a597-515a3b282015.png"
    alt="Planar Bridge logo"
  />
</p>

# Planar Bridge

Planar Bridge downloads and maintains a local library of high-quality card
scans from Magic: the Gathering.

Scans come from [Scryfall](https://scryfall.com/), and the bulk set and card
metadata that drives the downloads comes from [MTGJSON](https://mtgjson.com/).

Planar Bridge also upgrades resolution over time. If a scan stored locally is
low-res and Scryfall later publishes a high-res version, for instance once a
newly spoiled set gets rescanned, Planar Bridge replaces the old file.

## Installation

Planar Bridge runs on Linux and macOS. Windows should work too, though it
hasn't been tested there yet. It requires Python 3.13 or later, so check your
installed version if you're unsure:

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

Planar Bridge then begins the download process. Downloading every card scan
can take several hours, even on a fast connection, but you can kill the
program at any point and start it later. It resumes exactly where it left off.

MTGJSON's bulk database is pinned to a specific version. If your locally
cached copy has drifted from that version, Planar Bridge asks you to confirm
before continuing; pass `-y` to skip that prompt.

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

This reads `$HOME` and `%APPDATA%` directly; it does not check
`$XDG_DATA_HOME`.

Here is an example layout of that directory with some example set codes and
phony UUIDs:

```txt
planar-bridge/                 (the data directory)
├─ .mtgjson/
│  ├─ AllPrintings.sqlite
│  └─ Meta.json
├─ catalog.sqlite
├─ planar-bridge.toml
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

Planar Bridge names card image files after that card's UUID from MTGJSON's
database. Cards that share a single image across two faces (split, flip,
adventure, aftermath layouts) are named by joining both UUIDs with `_`. At
this time, there is no way to name a card file according to that card's name.

`.mtgjson/` holds the MTGJSON bulk database (`AllPrintings.sqlite`) and its
metadata (`Meta.json`), fetched once and reused on later runs.
`catalog.sqlite` is a small SQLite database recording each downloaded card's
resolution; it's what lets a killed run resume from exactly where it left off.
Do not modify or delete it, since it drives both resuming and resolution
upgrades.

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

If you want to configure Planar Bridge, copy `planar-bridge.example.toml`
from this repo to `planar-bridge.toml` inside your data directory (see
[Data directory](#data-directory) above).

Configuration options let you enable reprints, set a preferred card language,
and choose which sets, set types, and promo types to exclude from the
download process. For more information on set and promo types, visit
[MTGJSON](https://mtgjson.com/).

Configuration is limited for now. If you have a suggestion for more options,
feel free to
[open an issue](https://github.com/van-riper/planar-bridge/issues/new/).

## Terms of Use

By downloading and running this program, you agree to Wizards of the Coast's
[Fan Content Policy](https://company.wizards.com/en/legal/fancontentpolicy/) as
well as Scryfall's [Terms of Service](https://scryfall.com/docs/terms/). If
you have any questions about what you can or cannot do under these policies,
read the linked terms and FAQs carefully.

This program respects the 50 - 100 millisecond request rate limit that
Scryfall states on its website:

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

With that said, Planar Bridge and its developers accept no responsibility for
incidents that breach WotC's, Scryfall's, and/or Planar Bridge's terms and
conditions.

## Credits

Logo based on the 'Portal' design by [Lorc](https://lorcblog.blogspot.com/).

## License

This project is under the MIT License. See
[LICENSE](https://github.com/van-riper/planar-bridge/blob/main/LICENSE) for
details.
