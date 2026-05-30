<!--<img style="display:block;margin:auto;width:256px;" src="planar-bridge.png"/>-->

# Planar Bridge

Planar Bridge is a cross-platform tool for downloading and maintaining locally
stored high-quality card scans from Magic: the Gathering.

All scans are obtained from [Scryfall](https://scryfall.com/) via their online
card database. Bulk datasets used to build the image databases locally are
from [MTGJSON](https://mtgjson.com/).

One greatly advantageous feature of Planar Bridge is that it upgrades the
resolution on cards when a higher resolution is available. If a low-resolution
scan exists locally, it will replace it with higher-resolution scans if
available on Scryfall. This is especially helpful in handling cards that are
part of a spoiled set and have not been scanned at a crisp high resolution yet.

Planar Bridge is currently in pre-alpha, so everything you see now is subject
to change at any point.

This README file is incomplete at this point and will be improved upon as more
commits are made.

Please save and share this project if you want to contribute or see how Planar
Bridge progresses!

To-Do:
- Comments in source code
- Tests for debugging
- Automatic installation

## Installation

Planar Bridge is supported on Linux and macOS. It is expected (not yet tested)
to function on Windows. However, it is only confirmed to work with at least
Python 3.13.0, so check your installed Python version if you are unsure:

```sh
$ python3 -V
Python 3.13.0
```

(note that lines in code blocks beginning with `$` mean this line is used as
a user-executed command)

To install Planar Bridge, start by cloning this repository.

```sh
$ git clone --depth=1 https://github.com/maallaard/planar-bridge.git
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

By default, Planar Bridge will store all card scans and bulk files within this
repo and expects any config files to be here too. It will ignore these files
and folders when syncing changes. However, you can specify a different
directory to store card scans in, which is covered in the
[Configuration](#configuration) section.

Here is an example file tree layout of Planar Bridge's repo directory with
some example set codes and phony UUIDs:

```txt
planar-bridge/
├─ imgs/
│  ├─ LEA/
│  │  ├─ tokens/
│  │  │  ├─ 01234567-89ab-cdef-0123-456789abcdef.jpg
│  │  │  ├─ fedcba98-7654-3210-fedc-ba9876543210.jpg
│  │  │  └─ ...
│  │  ├─ 01234567-89ab-cdef-fedc-ba9876543210.jpg
│  │  ├─ fedcba98-7654-3210-0123-456789abcdef.jpg
│  │  ├─ ...
│  │  └─ .states.json
│  ├─ LEB/
│  │  ├─ 1f2e3d4c-5b6a-7089-9807-a6b5-c4d3e2f1.jpg
│  │  ├─ 9807a6b5-c4d3-e2f1-1f2e-3d4c-5b6a7089.jpg
│  │  ├─ ...
│  │  └─ .states.json
│  ├─ 2ED/
│  │  └─ ...
│  ├─ ...
├─ json/
│  ├─ AllPrintings.json
│  └─ Meta.json
├─ .gitignore
├─ config.example.toml
├─ LICENSE
├─ pyproject.toml
├─ uv.lock
├─ src/planar_bridge/
├─ tests/
└─ README.md
```

Planar Bridge stores all card scans in `imgs/` by default, which you can
change in your config file if you want. Each card is categorized by set code,
with tokens being stored in the `tokens/` subfolder of the set it belongs to.

Planar Bridge names card image files according to that card's UUID from
MTGJSON's database upon creation. At this time, there is no way to name a card
file according to that card's name.

Stored in `json/` are the bulk and meta JSON files containing card data used in
downloading card scans. You can download these files manually on MTGJSON's
[download page](https://mtgjson.com/downloads/all-files/).

In every set code folder, there will be a file named `.states.json`. This JSON
file contains the resolutions of all the card scans in that set according to
their UUIDs. This file is also found in `imgs/`, which states for each set code
whether or not every card in that set is at the highest resolution available.
Do not modify or delete these files, as they are required for proper
functionality.

## Development

Planar Bridge is developed with [uv](https://docs.astral.sh/uv/). After
`uv sync`, the dev tooling runs through `uv run`:

```sh
$ uv run pytest                    # run the test suite
$ uv run pylint src/planar_bridge  # lint
$ uv run black src tests           # format
```

## Configuration

If you want to configure Planar Bridge, copy and rename `config-example.toml`
to `config.toml` inside this repo.

Configurations you can make to Planar Bridge are specifying different `imgs/`
paths for card scans, and which sets, set types, and promo types to exclude
from the download process. For more information on set and promo types, visit
[MTGJSON](https://mtgjson.com/).

For now, the configuration of Planar Bridge is limited, so if you have a
suggestion for more options to configure, feel free to
[open an issue](https://github.com/maallaard/planar-bridge/issues/new/).

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

Do not modify or remove this program's built-in timer that regulates the
request rate itself. If you remove it, your IP address will likely get
blocked, either temporarily or permanently.

With that being said, Planar Bridge and its developers accept zero
responsibility regarding incidents that breach WotC's, Scryfall's, and/or
Planar Bridge's terms and conditions.

## Credits

Logo based on 'Portal' design made by [Lorc](https://lorcblog.blogspot.com/).

## License

This project is developed under an MIT License. For more information, see
[LICENSE](https://github.com/maallaard/planar-bridge/blob/main/LICENSE.txt).
