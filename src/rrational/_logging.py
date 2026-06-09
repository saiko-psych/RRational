"""Central logging for the RRational package — MNE-style.

Single point of configuration so the toolkit's diagnostics don't drown
in third-party noise (NeuroKit2's DeprecationWarning blast, NumPy's
internal trace) and so a user can crank verbosity up or down without
chasing logger names through 30 modules.

Public API
----------
``logger``
    The root :class:`logging.Logger` shared by every RRational module.
    Use ``from rrational._logging import logger`` then ``logger.info(...)``.
``set_log_level(level)``
    Adjust the package logger's level at runtime. Accepts the standard
    strings ("DEBUG", "INFO", "WARNING", "ERROR") or integer levels.
``use_log_level(level)``
    Context manager / decorator that swaps the level for the duration
    of a block and restores it afterwards — mirrors
    ``mne.utils.use_log_level``.
``verbose``
    Decorator that wires ``verbose=True / False / "DEBUG"`` into any
    function so the caller can scope the noise without touching global
    state. Mirrors ``mne.utils.verbose``.

The configuration is opt-in — the inspector / streamlit apps decide
whether to add a handler. Library code only emits records; if the
host hasn't configured a handler, Python's lastResort handler logs
warnings to stderr and silently drops everything quieter. That's the
same etiquette MNE follows.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, TypeVar

# ---------------------------------------------------------------------------
# Root package logger
# ---------------------------------------------------------------------------
logger = logging.getLogger("rrational")
logger.addHandler(logging.NullHandler())  # silence "no handler" warnings
logger.setLevel(logging.WARNING)


F = TypeVar("F", bound=Callable[..., Any])

# Levels the public API accepts as strings — kept identical to MNE's
# (no custom levels) so users coming from MNE-land find the same words.
_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "WARN": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def _resolve_level(level: int | str | bool | None) -> int | None:
    """Normalise the assorted ways a caller can spell a log level.

    ``True`` / ``False`` are sugar for INFO / WARNING (matches MNE).
    ``None`` means "leave the current level alone" and returns ``None``
    so the caller can short-circuit.
    """
    if level is None:
        return None
    if isinstance(level, bool):
        return logging.INFO if level else logging.WARNING
    if isinstance(level, int):
        return level
    if isinstance(level, str):
        upper = level.upper()
        if upper not in _LEVELS:
            raise ValueError(
                f"Unknown log level {level!r}; expected one of "
                f"{sorted(_LEVELS)} or True / False."
            )
        return _LEVELS[upper]
    raise TypeError(
        f"Log level must be str | int | bool | None, got {type(level).__name__}"
    )


def set_log_level(level: int | str | bool | None) -> None:
    """Set the rrational logger level."""
    new_level = _resolve_level(level)
    if new_level is not None:
        logger.setLevel(new_level)


@contextmanager
def use_log_level(level: int | str | bool | None):
    """Swap the package log level for the duration of a ``with`` block.

    Pass ``None`` to leave the level alone (useful inside helpers that
    receive ``verbose`` from the caller).
    """
    new_level = _resolve_level(level)
    if new_level is None:
        yield
        return
    old_level = logger.level
    logger.setLevel(new_level)
    try:
        yield
    finally:
        logger.setLevel(old_level)


def verbose(func: F) -> F:
    """Decorate ``func`` so its ``verbose`` keyword controls log noise.

    The decorated function gets a free ``verbose`` keyword (defaulting
    to ``None`` = "use the current level"). Pass ``True`` / ``False`` /
    a level string to scope a single call without mutating the global
    logger. Lifted from MNE's pattern but kept minimal — no parameter
    introspection or signature mangling, just a simple wrapper.
    """

    @wraps(func)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        v = kwargs.pop("verbose", None)
        with use_log_level(v):
            return func(*args, **kwargs)

    return wrapped  # type: ignore[return-value]
