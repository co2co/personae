# -*- coding: utf-8 -*-
"""引擎不再提供任何写法示范：世界书不播种条目、会话快照不带开局示范（2026-11-14 撤净）。

契约：
  1. store 不再暴露引擎条目播种符号（ORIGIN_ENGINE / STANDARD_EXAMPLE_* /
     _standard_example_entry / _has_standard_example / restore_default_entries），
     也不再暴露开局示范符号（FIRST_ROUND_DEMO_NAME / _FIRST_ROUND_DEMO）。引擎侧
     两份示范档（世界书常驻档 + 会话快照开局档）全部撤除，正文形式改用小说体散文。
  2. save_world 是纯覆盖：首次创建传空列表存出来就是空；传作者条目则原顺序原字段，
     引擎不前置任何东西，也不在后续保存时补种。
  3. import_drama 同样不补种：模板里有什么就存什么，包括旧版遗留条（旧亲密条、
     旧 origin="engine" 条目）——原样保留，不清理、不重复。
  4. 作者自建 demo 条目仍是本剧资产：保存往返不丢标志，world.scan 仍走示范通道
     且不占 max_entries 配额；first_round 条目只在 round=1 纳入、round>1 不纳入。
  5. memory.new 不收 opening_demo 形参，新建的快照里没有 opening_demo 键。
  6. HTTP：/api/world/<name>/restore-defaults 已撤（404），世界书正常读写不受影响。

全部走隔离的 store.DATA_DIR / memory.SESS_DIR（临时目录），不碰真实 data/、不调 LLM。
普适性红线：全文件只用中性占位，不绑定任何具体剧本角色名或题材词。
"""
import inspect
import sys
from pathlib import Path

import pytest

ENGINE = Path(__file__).resolve().parent.parent / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

import store  # noqa: E402
import memory  # noqa: E402
import world  # noqa: E402
import app as engine_app  # noqa: E402

DEMO_NAME = "本剧写法示范"
# 历史上由引擎播种过的旧条名：引擎已不再供给，磁盘上可能仍躺着，故只作字面量出现。
LEGACY_EXAMPLE = "写法示范·常驻"
LEGACY_STANDARD = "亲密描写标准"


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


@pytest.fixture
def client(data):
    return engine_app.app.test_client()


def _names(entries):
    return [(e or {}).get("name") for e in (entries or [])]


# ---- 1. 播种符号全部撤除 ---------------------------------------------------

def test_store_exposes_no_engine_entry_symbols():
    for sym in ("ORIGIN_ENGINE", "STANDARD_EXAMPLE_NAME", "_STANDARD_EXAMPLE_CONTENT",
                "_standard_example_entry", "_has_standard_example",
                "restore_default_entries"):
        assert not hasattr(store, sym), "引擎层不应再持有播种符号：%s" % sym


# ---- 1b. 开局示范（会话快照档）同样已撤 -------------------------------------

def test_store_exposes_no_opening_demo_symbols():
    """引擎侧最后一份示范也撤了：store 不再持有开局示范的名字与正文。"""
    for sym in ("FIRST_ROUND_DEMO_NAME", "_FIRST_ROUND_DEMO"):
        assert not hasattr(store, sym), "引擎层不应再持有开局示范符号：%s" % sym


def test_memory_new_takes_no_opening_demo():
    """快照层不再收示范：形参与快照字段一并撤除。"""
    assert "opening_demo" not in inspect.signature(memory.new).parameters


def test_new_snapshot_has_no_opening_demo_key(data, tmp_path, monkeypatch):
    monkeypatch.setattr(memory, "SESS_DIR", tmp_path / "sessions")
    store.save_card("角色甲", {"world": "测试世界"})
    sid = memory.new(["角色甲"], scene_place="客厅", world_name="测试世界")
    try:
        snap = memory.load(sid)
        assert snap is not None
        assert "opening_demo" not in snap, "新建快照不应再带开局示范字段"
    finally:
        memory.delete_session(sid)


# ---- 2. save_world 是纯覆盖 -------------------------------------------------

def test_save_world_seeds_nothing(data):
    store.save_world("新世界", [])
    assert store.load_world("新世界") == []


def test_save_world_keeps_author_order_verbatim(data):
    entries = [
        {"name": "自定设定", "keys": ["x"], "content": "内容A"},
        {"name": "其它设定", "keys": ["y"], "content": "内容B"},
    ]
    store.save_world("新世界", entries)
    assert _names(store.load_world("新世界")) == ["自定设定", "其它设定"]


def test_repeat_save_never_reintroduces_entries(data):
    """旧契约保留：作者删掉的条目（含历史遗留的引擎条）不会自己回来。"""
    store.save_world("新世界", [{"name": LEGACY_EXAMPLE, "demo": True, "content": "旧"}])
    store.save_world("新世界", [{"name": "自定设定", "content": "新"}])
    assert _names(store.load_world("新世界")) == ["自定设定"]


# ---- 3. 导入不补种、旧条目原样 ----------------------------------------------

def test_import_drama_seeds_nothing(data):
    template = {
        "world": {"name": "甲剧本", "entries": [{"name": "自定设定", "content": "甲剧本的设定。"}]},
        "characters": [],
    }
    store.import_drama("甲剧本", template)
    assert _names(store.load_world("甲剧本")) == ["自定设定"]


def test_import_drama_preserves_legacy_entries_verbatim(data):
    """旧版引擎播种过的剧本包再导入：旧条原样留着，不清洗、不重复。

    引擎改动只影响今后的播种，不回填、不清理既有数据——这条边界沿用不变。
    """
    template = {
        "world": {"name": "乙剧本", "entries": [
            {"name": LEGACY_EXAMPLE, "content": "旧版常驻示范。",
             "demo": True, "origin": "engine"},
            {"name": LEGACY_STANDARD, "content": "旧版标准。", "constant": True},
            {"name": "自定设定", "content": "作者设定。"},
        ]},
        "characters": [],
    }
    store.import_drama("乙剧本", template)
    loaded = store.load_world("乙剧本")
    assert _names(loaded) == [LEGACY_EXAMPLE, LEGACY_STANDARD, "自定设定"]
    by = {e["name"]: e for e in loaded}
    assert by[LEGACY_EXAMPLE]["origin"] == "engine"   # 残留标记无害，引擎读写不看它
    assert by[LEGACY_STANDARD]["constant"] is True


# ---- 4. 作者自建 demo 条目仍是本剧资产 --------------------------------------

def test_author_demo_roundtrips_and_uses_demo_channel(data):
    demo = {"name": DEMO_NAME, "keys": [], "content": "本剧写法范例正文。",
            "priority": 60, "enabled": True, "constant": False,
            "position": "before", "depth": None, "secret": False,
            "demo": True, "first_round": False}
    store.save_world("丙剧本", [demo])
    saved = store.load_world("丙剧本")[0]
    assert saved.get("demo") is True
    assert saved.get("first_round") is False

    hits = world.scan(store.load_world("丙剧本"), [], directive="*扰动*",
                      default_depth=4, max_entries=0, include_secret=False, round=6)
    assert [e["name"] for e in hits] == [DEMO_NAME], "示范条目应经独立通道纳入，且不占配额"


def test_author_first_round_demo_only_on_round_one(data):
    """first_round 分流通道仍活着：作者自建开局示范只在首轮注入。"""
    demo = {"name": DEMO_NAME, "keys": [], "content": "本剧开局写法范例。",
            "priority": 60, "enabled": True, "constant": False,
            "position": "before", "depth": None, "secret": False,
            "demo": True, "first_round": True}
    store.save_world("丙剧本", [demo])
    entries = store.load_world("丙剧本")

    def names(round_no):
        hits = world.scan(entries, [], directive="*扰动*", default_depth=4,
                          max_entries=0, include_secret=False, round=round_no)
        return [e["name"] for e in hits]

    assert names(1) == [DEMO_NAME], "first_round 条目应在首轮经示范通道纳入"
    assert names(2) == [], "first_round 条目自 R2 起不再注入"
    assert names(7) == [], "首轮之后任意轮次都不再注入"


# ---- 5. 恢复端点已撤 --------------------------------------------------------

def test_restore_defaults_endpoint_gone(client):
    r = client.post("/api/world/甲剧本/restore-defaults")
    assert r.status_code == 404


def test_world_write_read_still_works(client):
    r = client.post("/api/world/甲剧本", json={"entries": [{"name": "自定设定", "content": "x"}]})
    assert r.status_code == 200 and r.get_json()["ok"] is True
    got = client.get("/api/world/甲剧本").get_json()
    assert _names(got.get("entries")) == ["自定设定"]
