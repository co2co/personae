"""引擎默认条目的来源标记（origin=engine）与恢复机制。

2026-10-21 下架亲密尺度（对齐 v0.29.0）后，引擎出厂条目只剩「写法示范·常驻」一条
（「亲密描写标准」不再由引擎播种，见 test_standard_entry.py）。本文件守护：
  1. 出厂条目（写法示范·常驻）带 origin=engine；save_world 首次创建播种即带标记。
  2. restore_default_entries：只补缺失、不覆盖已有内容、世界不存在返回 None；
     只补示范条，不补亲密条（下架后）。
  3. import_drama 补种示范条对称（下架后不再补亲密条）。
  4. HTTP：/api/world/<name>/restore-defaults 正常路径与 404。
  5. UI 往返：按前端 collectWorldEntries 的形状提交后，origin/demo/first_round 保留
     （前端是否真的回传这三者由 test_frontend_binding.py 的静态探针守护）。

全部走隔离的 store.DATA_DIR（临时目录），不碰真实 data/、不调 LLM。

普适性红线：全文件只用中性占位，不绑定任何具体剧本角色名或题材词；
「亲密描写标准」在此仅作「下架后不再播种的旧条名」常量出现（引擎内部条名，非题材词）。
"""
import sys
from pathlib import Path

import pytest

ENGINE = Path(__file__).resolve().parent.parent / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

import store  # noqa: E402
import app as engine_app  # noqa: E402

# 下架后引擎不再播种的旧条名（仅作常量引用，不来自 store 符号）。
STD_NAME = "亲密描写标准"


@pytest.fixture
def data(tmp_path, monkeypatch):
    """把 store.DATA_DIR 指到临时目录并清缓存，磁盘读写自洽。"""
    d = tmp_path / "data"
    (d / "characters").mkdir(parents=True)
    (d / "worlds").mkdir(parents=True)
    monkeypatch.setattr(store, "DATA_DIR", d)
    monkeypatch.setattr(store, "EXAMPLES_DIR", d / "examples")
    store._cache.clear()
    yield d
    store._cache.clear()


@pytest.fixture
def client(data):
    return engine_app.app.test_client()


def _by_name(entries):
    return {(e or {}).get("name"): e for e in (entries or [])}


def _strip_engine(entries):
    return [e for e in entries if (e or {}).get("origin") != store.ORIGIN_ENGINE]


# ---- 1. 出厂条目带来源标记 -------------------------------------------------

def test_factory_entry_carries_origin():
    assert store._standard_example_entry()["origin"] == store.ORIGIN_ENGINE


def test_save_world_seeds_example_with_origin(data):
    store.save_world("甲剧本", [{"name": "自定设定", "content": "甲剧本的世界设定。"}])
    entries = store.load_world("甲剧本")
    by = _by_name(entries)

    assert store.STANDARD_EXAMPLE_NAME in by
    assert STD_NAME not in by, "下架后引擎不得再播种「亲密描写标准」"
    assert by[store.STANDARD_EXAMPLE_NAME]["origin"] == store.ORIGIN_ENGINE
    # 示范条目必须仍走 few-shot 通道
    assert by[store.STANDARD_EXAMPLE_NAME]["demo"] is True
    assert by[store.STANDARD_EXAMPLE_NAME]["first_round"] is False
    # 作者自写条目不带来源标记
    assert "origin" not in by["自定设定"]


def test_save_world_does_not_reseed_existing(data):
    """已存在的剧本再保存不播种（用户删掉的默认条目不会自己回来）。"""
    store.save_world("甲剧本", [{"name": "自定设定", "content": "x"}])
    store.save_world("甲剧本", [{"name": "自定设定", "content": "y"}])
    names = [e.get("name") for e in store.load_world("甲剧本")]
    assert store.STANDARD_EXAMPLE_NAME not in names


# ---- 2. restore 语义：只补缺失、不覆盖 -------------------------------------

def test_restore_adds_example_when_deleted(data):
    store.save_world("甲剧本", [])
    store.save_world("甲剧本", [{"name": "自定设定", "content": "x"}])  # 已存在 → 不再播种

    result = store.restore_default_entries("甲剧本")

    assert result["added"] == [store.STANDARD_EXAMPLE_NAME]
    assert STD_NAME not in result["added"], "下架后 restore 不得再补「亲密描写标准」"
    by = _by_name(store.load_world("甲剧本"))
    assert by[store.STANDARD_EXAMPLE_NAME]["demo"] is True


def test_restore_keeps_author_edits(data):
    """已有条目一律不覆盖——作者改过的内容与字段原样保留。"""
    store.save_world("甲剧本", [])
    entries = store.load_world("甲剧本")
    for e in entries:
        if e.get("name") == store.STANDARD_EXAMPLE_NAME:
            e["content"] = "作者换成本剧角色的示范。"
    store.save_world("甲剧本", entries)

    result = store.restore_default_entries("甲剧本")

    assert result["added"] == []
    assert result["present"] == [store.STANDARD_EXAMPLE_NAME]
    by = _by_name(store.load_world("甲剧本"))
    assert by[store.STANDARD_EXAMPLE_NAME]["content"] == "作者换成本剧角色的示范。"


def test_restore_does_not_add_standard(data):
    """下架后 restore 永不补亲密条（即便剧本里原本没有它）。"""
    store.save_world("甲剧本", [{"name": "自定设定", "content": "x"}])
    result = store.restore_default_entries("甲剧本")
    by = _by_name(store.load_world("甲剧本"))
    assert STD_NAME not in by
    assert STD_NAME not in result["added"]


def test_restore_missing_world_returns_none(data):
    assert store.restore_default_entries("不存在的剧本") is None


def test_restore_empty_name_raises(data):
    with pytest.raises(ValueError):
        store.restore_default_entries("   ")


# ---- 3. import 补种对称 ----------------------------------------------------

def test_import_seeds_example_entry(data):
    template = {
        "world": {"name": "乙剧本", "entries": [{"name": "自定设定", "content": "乙剧本的设定。"}]},
        "characters": [],
    }
    store.import_drama("乙剧本", template)

    by = _by_name(store.load_world("乙剧本"))
    assert store.STANDARD_EXAMPLE_NAME in by
    assert STD_NAME not in by, "下架后导入的剧本包不得被补种「亲密描写标准」"
    assert by[store.STANDARD_EXAMPLE_NAME]["origin"] == store.ORIGIN_ENGINE


def test_import_preserves_template_own_standard(data):
    """模板自带旧版亲密条时，import 原样保留、不重复、不覆盖。"""
    template = {
        "world": {
            "name": "乙剧本",
            "entries": [
                {"name": STD_NAME, "content": "模板自带旧版标准。"},
                {"name": store.STANDARD_EXAMPLE_NAME, "content": "模板自带示范。", "demo": True},
            ],
        },
        "characters": [],
    }
    store.import_drama("乙剧本", template)

    entries = store.load_world("乙剧本")
    names = [e.get("name") for e in entries]
    assert names.count(STD_NAME) == 1
    assert names.count(store.STANDARD_EXAMPLE_NAME) == 1
    assert _by_name(entries)[STD_NAME]["content"] == "模板自带旧版标准。"


# ---- 4. HTTP 路由 ---------------------------------------------------------

def test_restore_route_ok(client, data):
    store.save_world("甲剧本", [])
    store.save_world("甲剧本", [{"name": "自定设定", "content": "x"}])

    r = client.post("/api/world/甲剧本/restore-defaults")
    payload = r.get_json()

    assert r.status_code == 200
    assert payload["ok"] is True
    assert store.STANDARD_EXAMPLE_NAME in payload["added"]
    assert STD_NAME not in payload["added"]


def test_restore_route_404(client, data):
    r = client.post("/api/world/不存在的剧本/restore-defaults")
    assert r.status_code == 404
    assert "error" in r.get_json()


# ---- 5. UI 往返：字段不被剥掉 ---------------------------------------------

def test_ui_roundtrip_preserves_flags(data):
    """按前端 collectWorldEntries 的形状提交，保存后 origin/demo/first_round 保留。

    这是「UI 点一次保存就把 demo 抹掉」那个缺陷的后端侧回归：前端已经改为回传三者，
    此处确认后端不会在保存链路上丢弃或改写它们。
    """
    store.save_world("甲剧本", [])
    before = store.load_world("甲剧本")

    payload = []
    for i, e in enumerate(before):
        payload.append({
            "keys": e.get("keys") or [],
            "content": e.get("content", ""),
            "priority": 100 - i * 5,
            "enabled": e.get("enabled", True),
            "constant": e.get("constant", False),
            "position": e.get("position", "before"),
            "depth": e.get("depth"),
            "name": e.get("name"),
            "secret": bool(e.get("secret")),
            "demo": bool(e.get("demo")),
            "first_round": bool(e.get("first_round")),
            "origin": e.get("origin"),
        })
    store.save_world("甲剧本", payload)

    by = _by_name(store.load_world("甲剧本"))
    example = by[store.STANDARD_EXAMPLE_NAME]
    assert example["demo"] is True
    assert example["first_round"] is False
    assert example["origin"] == store.ORIGIN_ENGINE
