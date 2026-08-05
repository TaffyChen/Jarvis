from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.infra.market.service import market
from app.infra.storage import reset_storage_state


@pytest.fixture()
def isolated_data_dir(tmp_path):
    """将读写重定向到临时目录，避免单测污染真实 data/。"""
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
