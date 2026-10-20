"""玩家角色卡机制已移除的守护测试。

v2.0.0 起引擎恢复「环境推手作为外部导演、不登场」的设计：不再创建、识别或注入
任何玩家角色卡。本文件保留原文件名以延续测试收集路径，但断言的是机制确实已移除。
"""

import sys
from pathlib import Path

import pytest

ENGINE = Path(__file__).resolve().parent.parent / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

import store  # noqa: E402


@pytest.fixture
def data(tmp_path, monkeypatch):
    d = tmp_path / "data"
    (d / "characters").mkdir(parents=True)
    (d / "worlds").mkdir(parents=True)
    monkeypatch.setattr(store, "DATA_DIR", d)
    monkeypatch.setattr(store, "EXAMPLES_DIR", d / "examples")
    store._cache.clear()
    yield d
    store._cache.clear()


def test_store_has_no_player_card_api():
    for name in (
        "PLAYER_NAME",
        "empty_player_card",
        "_all_player_cards",
        "ensure_player_card",
        "ensure_player_card_if_absent",
        "player_card_name",
    ):
        assert not hasattr(store, name), name


def test_save_world_does_not_create_player_card(data):
    store.save_world("王朝", [])
    assert store.list_characters() == []


def test_import_drama_does_not_create_player_card(data):
    tpl = {
        "world": {"name": "甲", "entries": [{"name": "设定", "keys": [], "content": "c"}]},
        "characters": [],
    }
    store.import_drama("甲", tpl)
    assert store.list_characters() == []
