"""出厂「亲密描写标准」播种测试（NSFW 支持版，不碰磁盘真实 data/）。

契约（NSFW 支持恢复，对齐 v0.28.8 出厂单元）：
  1. 新建世界自动前置插入「亲密描写标准」——save_world([]) → load 返回 1 条标准。
  2. 标准恒定 constant=True / position=after / priority=100，置于 entries 首位。
  3. 不重复播种：传入 entries 已含「亲密描写标准」时不再额外插入。
  4. 玩家主权：玩家可对标准条停用/删除，引擎尊重（不复活、不强制回填）。
  5. 既有世界旧版标准条原样保留——save/load 只做覆盖式读写，不主动清理。
"""
import sys
from pathlib import Path

import pytest

ENGINE = Path(__file__).resolve().parent.parent / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

import store  # noqa: E402

STD_NAME = "亲密描写标准"


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


def test_new_world_seeds_standard_entry():
    """新建世界 save_world("W", []) → load 首条为「亲密描写标准」（另有常驻示范条）。"""
    store.save_world("新世界", [])
    ents = store.load_world("新世界")
    names = [e["name"] for e in ents]
    assert names[0] == STD_NAME
    # 常驻写法示范（引擎通用默认）也一并播种，见 test_standard_example.py
    assert "写法示范·常驻" in names


def test_seeded_entry_attributes():
    """播种的标准条恒定 constant=True / position=after / priority=100。"""
    store.save_world("新世界", [])
    std = next(e for e in store.load_world("新世界") if e["name"] == STD_NAME)
    assert std["constant"] is True
    assert std["position"] == "after"
    assert std["priority"] == 100


def test_standard_prepended_at_front():
    """传入用户条目时，标准条被前置到首位，用户条目保持原顺序。"""
    entries = [
        {"name": "自定义", "keys": ["x"], "content": "内容A"},
        {"name": "其它", "keys": ["y"], "content": "内容B"},
    ]
    store.save_world("新世界", entries)
    loaded = store.load_world("新世界")
    names = [e["name"] for e in loaded]
    assert names[0] == STD_NAME
    # 常驻示范条在标准条之后、用户条目之前
    assert names[1] == "写法示范·常驻"
    assert names[2] == "自定义"
    assert names[3] == "其它"


def test_no_double_seed_when_standard_present():
    """传入 entries 已含标准条时，不再额外插入（不重复播种）。"""
    existing_std = {
        "name": STD_NAME, "keys": [], "content": "旧内容",
        "constant": True, "position": "after", "priority": 100,
        "enabled": True, "depth": None, "secret": False,
    }
    store.save_world("新世界", [existing_std, {"name": "u", "keys": [], "content": "c"}])
    loaded = store.load_world("新世界")
    names = [e["name"] for e in loaded]
    assert names[0] == STD_NAME
    assert loaded[0]["content"] == "旧内容"
    assert "u" in names


def test_user_can_disable_seeded_entry():
    """玩家可对播种的标准条停用（enabled=False），引擎尊重。"""
    store.save_world("新世界", [])
    ents = store.load_world("新世界")
    std = next(e for e in ents if e["name"] == STD_NAME)
    std["enabled"] = False
    store.save_world("新世界", ents)
    loaded = store.load_world("新世界")
    assert next(e for e in loaded if e["name"] == STD_NAME)["enabled"] is False


def test_user_can_delete_seeded_entry():
    """玩家可整条删除标准条，再次保存不会复活（仅首建播种）。"""
    store.save_world("新世界", [])
    # 删除标准条后再次保存（首建已过，不会回填）
    store.save_world("新世界", [e for e in store.load_world("新世界") if e["name"] != STD_NAME])
    assert all(e["name"] != STD_NAME for e in store.load_world("新世界"))


def test_existing_world_legacy_entry_preserved():
    """既有世界（旧版引擎播种过的）标准条原样保留，不被清理或重复。"""
    legacy = {
        "name": STD_NAME, "keys": [], "content": "【本剧亲密与性行为描写标准……（旧版出厂条内容）",
        "priority": 100, "enabled": True, "constant": True,
        "position": "after", "depth": None, "secret": False,
    }
    user_entry = {"name": "本剧设定", "keys": ["x"], "content": "自定义内容"}
    store.save_world("旧世界", [legacy, user_entry])
    loaded = store.load_world("旧世界")
    names = [e["name"] for e in loaded]
    assert names[0] == STD_NAME
    assert loaded[0]["content"] == legacy["content"]
    assert "本剧设定" in names
    # 再次保存（如玩家只改了另一条）不会删除或重复旧条
    store.save_world("旧世界", loaded)
    assert "本剧设定" in [e["name"] for e in store.load_world("旧世界")]
