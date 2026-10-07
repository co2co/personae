"""store 只读缓存测试（v0.17.4，确定性，不碰磁盘真实 data/）。

覆盖：
  1. 带 mtime 校验的缓存：文件不变时重复 load 命中内存（省 IO）；文件变了重读。
  2. save_card / delete_card / save_world / delete_world 会失效文件缓存与目录签名缓存。
  3. list_characters / list_worlds 目录签名缓存：文件集合变化才重扫。
"""

import json
import sys
from pathlib import Path

import pytest

ENGINE = Path(__file__).resolve().parent.parent / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

import store  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_store(tmp_path, monkeypatch):
    """把 store.DATA_DIR 指向临时目录，并清空进程级缓存，避免污染真实 data/。"""
    data = tmp_path / "data"
    (data / "characters").mkdir(parents=True)
    (data / "worlds").mkdir(parents=True)
    monkeypatch.setattr(store, "DATA_DIR", data)
    monkeypatch.setattr(store, "EXAMPLES_DIR", data / "examples")
    store._cache.clear()
    yield data
    store._cache.clear()


def test_load_card_caches_and_invalidates_on_save(_isolated_store):
    store.save_card("甲", {"name": "甲", "desc": "v1"})
    assert store.load_card("甲")["desc"] == "v1"
    # 同文件未变，第二次读命中缓存（数据一致即可，这里验证语义正确性）
    assert store.load_card("甲")["desc"] == "v1"
    # 覆盖写后缓存失效，读到新值
    store.save_card("甲", {"name": "甲", "desc": "v2"})
    assert store.load_card("甲")["desc"] == "v2"


def test_load_world_caches_and_invalidates(_isolated_store):
    # 注意：新建世界时 store.save_world 会在首位播种一条「亲密描写标准」标准条目
    # （见 store._STANDARD_ENTRY_CONTENT）。这里验证的是「缓存随覆盖写失效」，
    # 故断言用户那条内容在列表里被更新，而非固定在下标 0。
    def user_entry(text):
        return next(e for e in store.load_world("世界甲") if e["content"].startswith("c"))

    store.save_world("世界甲", [{"keys": ["x"], "content": "c1"}])
    assert user_entry("c1")["content"] == "c1"
    store.save_world("世界甲", [{"keys": ["x"], "content": "c2"}])
    assert user_entry("c2")["content"] == "c2"


def test_list_characters_refreshes_on_new_card(_isolated_store):
    store.save_card("甲", {"name": "甲"})
    assert store.list_characters() == ["甲"]
    store.save_card("乙", {"name": "乙"})
    assert store.list_characters() == ["乙", "甲"]  # sorted：Unicode 乙<甲
    store.delete_card("甲")
    assert store.list_characters() == ["乙"]


def test_list_worlds_refreshes_on_delete(_isolated_store):
    store.save_world("世界甲", [])
    store.save_world("世界乙", [])
    assert store.list_worlds() == ["世界乙", "世界甲"]
    store.delete_world("世界甲")
    assert store.list_worlds() == ["世界乙"]


def test_load_card_missing_still_raises(_isolated_store):
    with pytest.raises(FileNotFoundError):
        store.load_card("不存在")
