"""Module entry point: delegate to the CLI runner.

This exists so python -m planar_bridge works; the real entry logic (the
version guard, argument parsing, and the run) lives in cli.main.
"""

from .cli.main import run

if __name__ == "__main__":
    run()
