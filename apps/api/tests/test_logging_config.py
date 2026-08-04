"""App logs must actually reach the container output.

This is not a style preference. Uvicorn installs handlers only for its own
`uvicorn*` loggers and never calls `basicConfig`, so the root logger keeps its
WARNING default and every `logger.info()` under `app.*` is dropped before it
reaches a handler. The chat latency line shipped to staging exactly that way
and emitted nothing at all — which looks identical to code that never ran, and
cost a deploy cycle to notice.

The tests reset the root logger to uvicorn's effective default first, because
pytest attaches its own handlers and would otherwise make them pass vacuously.
"""

import io
import logging

from app.main import configure_logging


def _as_uvicorn_leaves_it():
    """Logging as it is under `uvicorn app.main:app`: root has no handlers of
    its own and keeps its default level.

    The `app` logger is reset too. Logger levels are process-global and
    `conftest` builds the app — and so calls `configure_logging()` — before
    these tests run, which would otherwise leave the very state under test
    already applied and every assertion here vacuous.
    """
    root = logging.getLogger()
    app_logger = logging.getLogger("app")
    saved = (root.level, root.handlers[:], app_logger.level)
    root.handlers.clear()
    root.setLevel(logging.WARNING)
    app_logger.setLevel(logging.NOTSET)
    return root, saved


def _restore(root, saved) -> None:
    level, handlers, app_level = saved
    root.setLevel(level)
    root.handlers[:] = handlers
    logging.getLogger("app").setLevel(app_level)


def test_info_records_are_enabled_for_app_loggers() -> None:
    root, saved = _as_uvicorn_leaves_it()
    try:
        assert not logging.getLogger("app.chat.latency").isEnabledFor(logging.INFO)
        configure_logging()
        assert logging.getLogger("app.chat.latency").isEnabledFor(logging.INFO)
    finally:
        _restore(root, saved)


def test_an_info_record_actually_reaches_a_handler() -> None:
    """`isEnabledFor` alone would still pass with no handler attached, and a
    record that reaches no handler is as lost as one filtered by level."""
    root, saved = _as_uvicorn_leaves_it()
    try:
        configure_logging()
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        root.addHandler(handler)
        logging.getLogger("app.chat.latency").info("chat outcome=ok ttft_ms=123")
        handler.flush()
        assert "ttft_ms=123" in stream.getvalue()
    finally:
        _restore(root, saved)


def test_does_not_fight_a_host_that_configured_logging_itself() -> None:
    """`basicConfig` is a no-op when the root logger already has handlers, so
    a deployment with its own logging setup keeps it."""
    root, saved = _as_uvicorn_leaves_it()
    try:
        existing = logging.StreamHandler(io.StringIO())
        root.addHandler(existing)
        configure_logging()
        assert root.handlers == [existing]
    finally:
        _restore(root, saved)
