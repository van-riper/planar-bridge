"""Unit test for the console entry point's interrupt handling."""

from typing import Any

import pytest

from planar_bridge import __main__


def test_main_exits_cleanly_on_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Ctrl-C is caught, reported as Interrupted, and exits with code 130."""

    def fake_run(coro: Any) -> None:
        coro.close()  # the pull_all coroutine is never awaited here
        raise KeyboardInterrupt

    monkeypatch.setattr(__main__.asyncio, "run", fake_run)

    with pytest.raises(SystemExit) as exit_info:
        __main__.main()

    assert exit_info.value.code == __main__.INTERRUPT_EXIT_CODE
    assert "Interrupted" in capsys.readouterr().out
