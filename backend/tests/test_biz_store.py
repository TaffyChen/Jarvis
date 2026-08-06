from __future__ import annotations

from app.infrastructure.persistence.analyses_store import load_analyses, save_analyses
from app.infrastructure.persistence.positions_store import load_positions, save_positions


def test_positions_roundtrip(isolated_data_dir):
    save_positions({"sz000333": {"buyPrice": 10, "shares": 100, "name": "美的"}})
    data = load_positions()
    assert data["sz000333"]["buyPrice"] == 10
    assert data["sz000333"]["shares"] == 100


def test_analyses_roundtrip(isolated_data_dir):
    save_analyses({"sz000333": {"code": "sz000333", "name": "美的", "notes": "ok"}})
    data = load_analyses()
    assert data["sz000333"]["name"] == "美的"
    assert data["sz000333"]["notes"] == "ok"
