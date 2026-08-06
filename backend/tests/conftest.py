from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.infrastructure.market.service import market
from app.infrastructure.persistence.storage import reset_storage_state


@pytest.fixture()
def isolated_data_dir(tmp_path):
    """关掉 MySQL、走内存库；tmp_path 仅占位 data_dir，避免误写仓库。"""
    old_data_dir = settings.data_dir
    old_mysql_host = settings.mysql_host
    old_stock_codes = copy.deepcopy(market.stock_codes)
    try:
        object.__setattr__(settings, "data_dir", tmp_path)
        object.__setattr__(settings, "mysql_host", "")
        reset_storage_state()
        market.stock_codes = []
        yield tmp_path
    finally:
        object.__setattr__(settings, "data_dir", old_data_dir)
        object.__setattr__(settings, "mysql_host", old_mysql_host)
        reset_storage_state()
        market.stock_codes = old_stock_codes
