"""Smoke tests for the central rrational._logging utilities."""

from __future__ import annotations

import logging


def test_logger_root_name_is_rrational():
    from rrational._logging import logger

    assert logger.name == "rrational"


def test_set_log_level_accepts_string():
    from rrational._logging import logger, set_log_level

    set_log_level("DEBUG")
    try:
        assert logger.level == logging.DEBUG
    finally:
        set_log_level("WARNING")


def test_set_log_level_accepts_bool():
    from rrational._logging import logger, set_log_level

    set_log_level(True)
    try:
        assert logger.level == logging.INFO
    finally:
        set_log_level("WARNING")


def test_use_log_level_context_restores_old_level():
    from rrational._logging import logger, set_log_level, use_log_level

    set_log_level("WARNING")
    with use_log_level("DEBUG"):
        assert logger.level == logging.DEBUG
    assert logger.level == logging.WARNING


def test_use_log_level_with_none_is_noop():
    from rrational._logging import logger, set_log_level, use_log_level

    set_log_level("INFO")
    with use_log_level(None):
        assert logger.level == logging.INFO
    assert logger.level == logging.INFO


def test_verbose_decorator_scopes_log_level():
    from rrational._logging import logger, set_log_level, verbose

    set_log_level("WARNING")

    @verbose
    def noisy() -> int:
        return logger.level

    assert noisy(verbose="DEBUG") == logging.DEBUG
    assert logger.level == logging.WARNING


def test_verbose_decorator_default_keeps_level():
    from rrational._logging import logger, set_log_level, verbose

    set_log_level("WARNING")

    @verbose
    def noisy() -> int:
        return logger.level

    assert noisy() == logging.WARNING


def test_set_log_level_rejects_unknown_string():
    import pytest

    from rrational._logging import set_log_level

    with pytest.raises(ValueError, match="Unknown log level"):
        set_log_level("LOUD")
