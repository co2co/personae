"""v0.29.0：引擎不再出厂播种任何尺度条目（确定性，不碰磁盘真实 data/）。

契约（simon 2026-10-14 拍板）：
  1. 新建世界不再自动插入任何尺度条目——save_world 对传入 entries 原样保存。
  2. 引擎不内置亲密尺度设定——系统提示词无正面写实/不预设上限等放大倾向
     （由 test_intimacy_scale.py 守护铁律⑧ 中性措辞）。
  3. 玩家主权：玩家可自行在世界书里新建任意条目（含「亲密叙事标准」），
     引擎对既有/自建条目不增不删不覆盖。
  4. 既有世界（旧版引擎播种过的）中的标准条目原样保留——引擎不主动清理，
     save_world/load_world 只做覆盖式读写。
"""
import sys
from pathlib import Path

import pytest

ENGINE = Path(__file__).resolve().parent.parent / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

import store  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_store(tmp_path, monkeypatch):
    data = tmp_path / "data"
    (data / "characters").mkdir(parents=True)
    (data / "worlds").mkdir(parents=True)
    monkeypatch.setattr(store, "DATA_DIR", data)
    monkeypatch.setattr(store, "EXAMPLES_DIR", data / "examples")
    store._cache.clear()
    yield data
    store._cache.clear()


def test_new_world_does_not_seed_any_entry():
    """新建世界 save_world("W", []) → load 返回空列表，无自动播种。"""
    store.save_world("新世界", [])
    ents = store.load_world("新世界")
    assert ents == []


def test_save_world_preserves_entries_verbatim():
    """save_world 原样保存：传入 N 条 → load 返回同样的 N 条（不增不减）。"""
    entries = [
        {"keys": ["a"], "content": "条目一"},
        {"keys": ["b"], "content": "条目二"},
    ]
    store.save_world("新世界", entries)
    loaded = store.load_world("新世界")
    assert len(loaded) == 2
    assert [e["content"] for e in loaded] == ["条目一", "条目二"]


def test_user_can_add_own_intimacy_standard_entry():
    """玩家可自行新建「亲密叙事标准」条目，save/load 原样保留。"""
    custom = {
        "name": "亲密叙事标准",
        "keys": [],
        "content": "本剧亲密戏的自定义写法要求……",
        "constant": True,
        "position": "after",
        "enabled": True,
        "depth": None,
        "secret": False,
    }
    store.save_world("新世界", [custom])
    loaded = store.load_world("新世界")
    assert len(loaded) == 1
    assert loaded[0]["name"] == "亲密叙事标准"
    assert loaded[0]["content"] == custom["content"]


def test_user_can_delete_own_entry():
    """玩家可整条删除自己的条目，再次保存不会复活。"""
    store.save_world("新世界", [
        {"name": "亲密叙事标准", "content": "自定义", "enabled": True},
        {"name": "其它设定", "content": "保留", "enabled": True},
    ])
    kept = [e for e in store.load_world("新世界") if e.get("name") != "亲密叙事标准"]
    store.save_world("新世界", kept)
    loaded = store.load_world("新世界")
    assert [e.get("name") for e in loaded] == ["其它设定"]


def test_user_can_disable_own_entry():
    """enabled=false 停用（不删除），load 原样尊重。"""
    store.save_world("新世界", [
        {"name": "亲密叙事标准", "content": "自定义", "enabled": True},
    ])
    ents = store.load_world("新世界")
    ents[0]["enabled"] = False
    store.save_world("新世界", ents)
    assert store.load_world("新世界")[0]["enabled"] is False


def test_existing_world_legacy_entry_preserved():
    """既有世界（旧版引擎播种过的）中已有的「亲密描写标准」条目原样保留。

    引擎不主动清理——save/load 只做覆盖式读写，不删除玩家（或旧版引擎）
    已存入的条目。
    """
    legacy_entry = {
        "name": "亲密描写标准",
        "keys": [],
        "content": "【本剧亲密与性行为描写标准……（旧版出厂条内容）",
        "priority": 100,
        "enabled": True,
        "constant": True,
        "position": "after",
        "depth": None,
        "secret": False,
    }
    user_entry = {"name": "本剧设定", "keys": ["x"], "content": "自定义内容"}
    store.save_world("旧世界", [legacy_entry, user_entry])
    loaded = store.load_world("旧世界")
    assert len(loaded) == 2
    assert loaded[0]["name"] == "亲密描写标准"
    assert loaded[1]["name"] == "本剧设定"
    # 再次保存（如玩家只改了另一条）不会删除旧条
    store.save_world("旧世界", loaded)
    assert len(store.load_world("旧世界")) == 2
