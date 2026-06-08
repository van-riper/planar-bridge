"""Console entry point: guard the Python version and run the pull pipeline."""

import asyncio
from sys import version_info

from .pipeline import pull_all

if version_info.major != 3 or version_info.minor < 13:
    raise SystemExit("Python version must be at least 3.13")


def main() -> None:
    """Run the async pull pipeline to completion."""

    asyncio.run(pull_all())


if __name__ == "__main__":
    main()
