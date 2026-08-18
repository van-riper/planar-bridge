"""Unit test for the CLI runner's interrupt handling."""

import runpy
from typing import Any

import pytest

from planar_bridge.cli import main


def test_run_exits_cleanly_on_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Ctrl-C is caught, reported as Interrupted, and exits with code 130."""

    def fake_run(coro: Any) -> None:
        coro.close()  # the pull_all coroutine is never awaited here
        raise KeyboardInterrupt

    monkeypatch.setattr(main.asyncio, "run", fake_run)

    with pytest.raises(SystemExit) as exit_info:
        main.run([])

    assert exit_info.value.code == main.INTERRUPT_EXIT_CODE
    assert "Interrupted" in capsys.readouterr().out


def test_module_entry_invokes_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Running python -m planar_bridge delegates to cli.main.run."""
    calls: list[bool] = []
    monkeypatch.setattr(main, "run", lambda: calls.append(True))

    runpy.run_module("planar_bridge.__main__", run_name="__main__")

    assert calls == [True]
