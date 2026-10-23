"""亲密尺度「不播种」回归测试（2026-10-21 下架，对齐 v0.29.0，不碰磁盘真实 data/）。

契约（下架后，simon 裁决）：
  1. 新建世界**不再播种**「亲密描写标准」——save_world([]) → 只剩「写法示范·常驻」。
  2. 传入用户条目时，**不前置**亲密条；「写法示范·常驻」置于首位，用户条目保持原顺序。
  3. 既有磁盘世界（旧版引擎播种过）的「亲密描写标准」条**原样保留**——save/load
     只做覆盖式读写，不主动清理、不重复（引擎改动只影响今后的播种，不回填旧条）。
  4. 引擎不预设亲密尺度：store 不再暴露 _standard_entry / _has_standard_entry /
     STANDARD_ENTRY_NAME 符号。

回滚蓝本（唯一权威）：git tag `nsfw-on-v2.1.7`（→ 提交 a6e1280）里的
NSFW 播种版（六分层 + 器官词正反示例），含本文件的上架态。
重新上架：git checkout nsfw-on-v2.1.7 -- <13文件>。
注：早期目录快照 _backup_offshelf_nsfw_* 已于 2026-10-23 晚手工清理。

普适性红线：全文件只用中性占位，不绑定任何具体剧本角色名或题材词。
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


def test_new_world_does_not_seed_standard_entry():
    """新建世界 save_world("W", []) → 不再含「亲密描写标准」，只剩写法示范。"""
    store.save_world("新世界", [])
    names = [e["name"] for e in store.load_world("新世界")]
    assert STD_NAME not in names, "下架后引擎不得再播种「亲密描写标准」"
    assert "写法示范·常驻" in names


def test_user_entries_not_prepended_by_standard():
    """传入用户条目时不前置亲密条；写法示范首位，用户条目保持原顺序。"""
    entries = [
        {"name": "自定义", "keys": ["x"], "content": "内容A"},
        {"name": "其它", "keys": ["y"], "content": "内容B"},
    ]
    store.save_world("新世界", entries)
    names = [e["name"] for e in store.load_world("新世界")]
    assert STD_NAME not in names
    assert names[0] == "写法示范·常驻"
    assert names[1] == "自定义"
    assert names[2] == "其它"


def test_existing_world_legacy_entry_preserved():
    """既有世界（旧版引擎播种过）的亲密条原样保留，不被清理或重复。"""
    legacy = {
        "name": STD_NAME, "keys": [], "content": "【本剧亲密与性行为描写标准……（旧版出厂条内容）",
        "priority": 100, "enabled": True, "constant": True,
        "position": "after", "depth": None, "secret": False,
    }
    user_entry = {"name": "本剧设定", "keys": ["x"], "content": "自定义内容"}
    store.save_world("旧世界", [legacy, user_entry])
    loaded = store.load_world("旧世界")
    names = [e["name"] for e in loaded]
    # 首建时引擎不再补亲密条，但玩家传入的旧条（覆盖式写入）原样保留
    assert STD_NAME in names
    assert loaded[names.index(STD_NAME)]["content"] == legacy["content"]
    assert "本剧设定" in names
    # 再次保存（如玩家只改了另一条）不会删除或重复旧条
    store.save_world("旧世界", loaded)
    assert "本剧设定" in [e["name"] for e in store.load_world("旧世界")]


def test_store_exposes_no_standard_entry_symbols():
    """下架后 store 不再暴露亲密条播种符号（引擎不预设尺度）。"""
    assert not hasattr(store, "STANDARD_ENTRY_NAME")
    assert not hasattr(store, "_STANDARD_ENTRY_CONTENT")
    assert not hasattr(store, "_standard_entry")
    assert not hasattr(store, "_has_standard_entry")
