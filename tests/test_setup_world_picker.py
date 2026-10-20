"""开场区「先选世界 → 再列该世界角色」的接口与开局校验测试（v0.18.7）。

起因：开场界面原先把**所有世界的角色混在一张勾选列表**里（loadCharacters 取
/api/characters 全量），世界归属只能靠引擎取「首个在场角色的 world」反推——
多世界并存时会把不同世界的角色放进同一局。改为显式选世界后，需要：
  1. 按世界过滤角色的接口（/api/characters/by-world + store 两个新函数）；
  2. 开局时世界显式传入并做一致性校验（跨世界混场、世界不存在均须拦截）；
  3. 未传 world 的旧调用方仍能开局（向后兼容）。

全部用内存 mock，不碰磁盘真实 data/、不调 LLM。
"""

import sys
from pathlib import Path

import pytest

ENGINE = Path(__file__).resolve().parent.parent / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

import app as engine_app  # noqa: E402
import store  # noqa: E402


# ---------------------------------------------------------------------------
# 桩数据：三张卡分属两个世界，另有两张「未归属」的卡（一张 world 指向已删世界、
# 一张干脆没写 world）——这两类在任何世界下都不会出现在角色列表里。
# ---------------------------------------------------------------------------

CARDS = {
    "甲": {"name": "甲", "world": "世界一"},
    "乙": {"name": "乙", "world": "世界一"},
    "丙": {"name": "丙", "world": "世界二"},
    "丁": {"name": "丁", "world": "已删世界"},   # 指向不存在的世界书
    "戊": {"name": "戊"},                        # 干脆没写 world
}
WORLDS = ["世界一", "世界二"]


@pytest.fixture
def client(monkeypatch):
    """test_client + 全内存 store桩：不读磁盘、不调任何 LLM。"""
    monkeypatch.setattr(engine_app.store, "list_characters", lambda: list(CARDS))
    monkeypatch.setattr(engine_app.store, "list_worlds", lambda: list(WORLDS))
    monkeypatch.setattr(engine_app.store, "load_card",
                        lambda n: dict(CARDS.get(n) or {}))
    monkeypatch.setattr(engine_app.store, "list_characters_by_world",
                        lambda w: [n for n, c in CARDS.items() if (c.get("world") or "") == w])
    monkeypatch.setattr(engine_app.store, "unassigned_characters",
                        lambda: [n for n, c in CARDS.items()
                                 if (c.get("world") or "") not in WORLDS])
    # memory.new / director 的 LLM 路径全部短路
    made = {}

    def fake_new(cast, scene_place="", world_name="", scene_time="", opening_demo=""):
        made["cast"], made["world"] = list(cast), world_name
        made["opening_demo"] = opening_demo
        return "sid_test"

    monkeypatch.setattr(engine_app.memory, "new", fake_new)
    monkeypatch.setattr(engine_app.memory, "load",
                        lambda sid: {"present": list(made.get("cast") or []), "scene": {},
                                     "states": {}, "secrets": [], "relations": {},
                                     "world_name": made.get("world", "")})
    monkeypatch.setattr(engine_app.memory, "save", lambda sid, s: None)
    monkeypatch.setattr(engine_app.director, "fill_relation_gaps", lambda s: [])
    monkeypatch.setattr(engine_app.director, "init_address", lambda s: {})
    return engine_app.app.test_client(), made


# ---------------------------------------------------------------------------
# 1. store 层：按世界过滤
# ---------------------------------------------------------------------------

def test_list_characters_by_world_filters(tmp_path, monkeypatch):
    data = tmp_path / "data"
    (data / "characters").mkdir(parents=True)
    (data / "worlds").mkdir(parents=True)
    monkeypatch.setattr(store, "DATA_DIR", data)
    monkeypatch.setattr(store, "EXAMPLES_DIR", data / "examples")
    store._cache.clear()
    # 必须真实存在这两本世界书：unassigned_characters 判定「world 指向已存在的
    # 世界书」，没建的话所有卡都会算未归属，测的就不是本来要测的东西了。
    store.save_world("世界一", [])
    store.save_world("世界二", [])
    for name, w in [("甲", "世界一"), ("乙", "世界一"), ("丙", "世界二"), ("丁", "")]:
        store.save_card(name, {"world": w} if w else {})
    assert set(store.list_characters_by_world("世界一")) == {"甲", "乙"}
    assert store.list_characters_by_world("世界二") == ["丙"]
    assert store.list_characters_by_world("不存在") == []
    # 未归属 = world 为空 + world 指向不存在的世界书
    assert set(store.unassigned_characters()) == {"丁"}


# ---------------------------------------------------------------------------
# 2. HTTP 层：/api/characters/by-world
# ---------------------------------------------------------------------------

def test_by_world_endpoint_returns_names_and_unassigned(client):
    c, _ = client
    r = c.get("/api/characters/by-world?world=%E4%B8%96%E7%95%8C%E4%B8%80")
    assert r.status_code == 200
    d = r.get_json()
    assert set(d["names"]) == {"甲", "乙"}
    # 未归属清单与所选世界无关，一并返回供前端提示
    assert set(d["unassigned"]) == {"丁", "戊"}


def test_by_world_endpoint_unknown_world_returns_empty(client):
    c, _ = client
    d = c.get("/api/characters/by-world?world=%E4%B8%8D%E5%AD%98%E5%9C%A8").get_json()
    assert d["names"] == []


# ---------------------------------------------------------------------------
# 3. 开局：世界显式传入 + 两条校验
# ---------------------------------------------------------------------------

def test_session_new_uses_explicit_world(client):
    c, made = client
    r = c.post("/api/session/new", json={"cast": ["甲", "乙"], "scene": "客厅", "world": "世界一"})
    assert r.status_code == 200, r.get_json()
    assert made["world"] == "世界一"
    assert made["cast"] == ["甲", "乙"]


def test_session_new_opening_demo_always_system_default(client):
    """v1.2.3：写法示范不再让玩家自定义，恒用引擎中性默认（即便请求体传了也忽略）。"""
    c, made = client
    r = c.post("/api/session/new", json={
        "cast": ["甲", "乙"], "scene": "客厅", "world": "世界一",
        "opening_demo": "*我恐惧地张望*"})
    assert r.status_code == 200, r.get_json()
    assert made["opening_demo"] == store._FIRST_ROUND_DEMO


def test_session_new_rejects_cross_world_cast(client):
    """选了世界却混入别世界的卡 → 400 并点名混入者（静默纠正会让玩家以为角色在局里）。"""
    c, _ = client
    r = c.post("/api/session/new", json={"cast": ["甲", "丙"], "world": "世界一"})
    assert r.status_code == 400
    err = r.get_json()["error"]
    assert "不属于该世界" in err and "丙" in err, err


def test_session_new_rejects_unknown_world(client):
    c, _ = client
    r = c.post("/api/session/new", json={"cast": ["甲"], "world": "不存在"})
    assert r.status_code == 400
    assert "世界不存在" in r.get_json()["error"]


def test_session_new_falls_back_to_first_card_world(client):
    """未传 world 的旧调用方仍能开局：回退到首个角色的 world（向后兼容）。"""
    c, made = client
    r = c.post("/api/session/new", json={"cast": ["甲", "乙"], "scene": "客厅"})
    assert r.status_code == 200, r.get_json()
    assert made["world"] == "世界一"


def test_session_new_empty_cast_rejected(client):
    c, _ = client
    # cast 全是不存在的名字 → 去重过滤后为空
    r = c.post("/api/session/new", json={"cast": ["不存在"], "world": "世界一"})
    assert r.status_code == 400
    assert "没有可登场" in r.get_json()["error"]


def test_session_new_rejects_partial_cast(client):
    """名册必须完整：传子集直接 400 并点名缺谁（v2.1.1）。

    起因：开场区的角色勾选已改为只读名册。引擎以「剧本全部角色」为簿记定义域——
    关系基线、秘密归属、亲缘、短期目标都按名册建账，少一个人就会在快照里留下指向
    无卡角色的悬空引用（世界书点名他、关系里有他，prompt 里却没有他的卡）。
    故 cast 只作兼容入参，必须等于该世界的全部角色；不静默补齐，因为补齐会让调用方
    以为自己的选择生效了，而实际登场的是别人。
    """
    c, made = client
    r = c.post("/api/session/new", json={"cast": ["甲"], "world": "世界一"})
    assert r.status_code == 400, r.get_json()
    err = r.get_json()["error"]
    assert "全部角色" in err and "乙" in err, err
    assert "cast" not in made, "名册不完整的请求不该建局"


def test_session_new_default_cast_is_world_members(client):
    """不传 cast：默认该世界的全部角色登场，不含跨世界/未归属角色。"""
    c, made = client
    r = c.post("/api/session/new", json={"world": "世界一", "scene": "集市"})
    assert r.status_code == 200, r.get_json()
    assert set(made["cast"]) == {"甲", "乙"}
