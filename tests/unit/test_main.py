"""Unit test for the CLI runner's interrupt handling."""

import runpy
from collections.abc import Coroutine

import pytest

from planar_bridge.cli import main


def test_run_exits_cleanly_on_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Ctrl-C is caught, reported as Interrupted, and exits with code 130."""

    def fake_run(coro: Coroutine[object, object, object]) -> None:
        """Discard the coroutine and simulate a Ctrl-C during the run.

        Raises:
            KeyboardInterrupt: Always, in place of running the coroutine.
        """
        coro.close()  # the pull_all coroutine is never awaited here
        raise KeyboardInterrupt

    monkeypatch.setattr(main.asyncio, "run", fake_run)

    with pytest.raises(SystemExit) as exit_info:
        main.run([])

    assert exit_info.value.code == main.INTERRUPT_EXIT_CODE
    assert "Interrupted" in capsys.readouterr().out


def test_run_exits_with_message_on_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An unreachable source is reported and exits with a failure code."""

    def fake_run(coro: Coroutine[object, object, object]) -> None:
        """Discard the coroutine and simulate an unreachable source.

        Raises:
            RuntimeError: Always, in place of running the coroutine.
        """
        coro.close()  # an unawaited coroutine here would raise a warning
        message = "failed to fetch MTGJSON metadata"
        raise RuntimeError(message)

    monkeypatch.setattr(main.asyncio, "run", fake_run)

    with pytest.raises(SystemExit) as exit_info:
        main.run([])

    assert exit_info.value.code == main.RUN_FAILED_EXIT_CODE
    assert "failed to fetch MTGJSON metadata" in capsys.readouterr().out


def test_run_exits_with_message_on_value_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A bad config value is reported and exits with a failure code."""

    def fake_run(coro: Coroutine[object, object, object]) -> None:
        """Discard the coroutine and simulate a bad configured language.

        Raises:
            ValueError: Always, in place of running the coroutine.
        """
        coro.close()  # an unawaited coroutine here would raise a warning
        message = "language code 'xx' not supported"
        raise ValueError(message)

    monkeypatch.setattr(main.asyncio, "run", fake_run)

    with pytest.raises(SystemExit) as exit_info:
        main.run([])

    assert exit_info.value.code == main.RUN_FAILED_EXIT_CODE
    assert "language code 'xx' not supported" in capsys.readouterr().out


def test_run_exits_with_message_on_type_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A malformed config value is reported and exits with a failure code."""

    def fake_run(coro: Coroutine[object, object, object]) -> None:
        """Discard the coroutine and simulate a malformed filter list.

        Raises:
            TypeError: Always, in place of running the coroutine.
        """
        coro.close()  # an unawaited coroutine here would raise a warning
        message = "exempt_sets must be a list of strings, got str"
        raise TypeError(message)

    monkeypatch.setattr(main.asyncio, "run", fake_run)

    with pytest.raises(SystemExit) as exit_info:
        main.run([])

    assert exit_info.value.code == main.RUN_FAILED_EXIT_CODE
    assert "exempt_sets must be a list" in capsys.readouterr().out


def test_module_entry_invokes_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Running python -m planar_bridge delegates to cli.main.run."""
    calls: list[bool] = []
    monkeypatch.setattr(main, "run", lambda: calls.append(True))

    runpy.run_module("planar_bridge.__main__", run_name="__main__")

    assert calls == [True]
