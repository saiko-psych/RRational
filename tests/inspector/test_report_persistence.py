"""Tests for the HDF5 persistence stubs on ReportBuilder (Cluster C7)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from rrational.inspector.report import ReportBuilder


def test_save_raises_not_implemented_without_h5py(tmp_path):
    builder = ReportBuilder(MagicMock())
    with pytest.raises(NotImplementedError, match="h5py"):
        builder.save(tmp_path / "out.h5")


def test_load_raises_not_implemented_without_h5py(tmp_path):
    with pytest.raises(NotImplementedError, match="h5py"):
        ReportBuilder.load(tmp_path / "out.h5")
