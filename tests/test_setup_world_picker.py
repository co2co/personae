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
    # v1.0.0：session_new 会 ensure_player_card 并把玩家并入 cast。mock 掉，
    # 既避免触碰真实磁盘（真函数写真实 data/characters），又让本组「世界一致性」
    # 测试保持聚焦（不为玩家卡的世界归属而引入额外断言）。
    ensured = []
    ensured_browse = []

    def fake_ensure(w):
        ensured.append(w)
        return "玩家"

    def fake_ensure_browse(w):
        ensured_browse.append(w)
        return "玩家"

    monkeypatch.setattr(engine_app.store, "ensure_player_card", fake_ensure)
    # 2026-10-20：by-world 改调浏览安全版补建（只读列表不得删卡重建），同样 mock。
    monkeypatch.setattr(engine_app.store, "ensure_player_card_if_absent", fake_ensure_browse)
    # memory.new / director 的 LLM 路径全部短路
    made = {}
    made["ensured"] = ensured
    made["ensured_browse"] = ensured_browse

    def fake_new(cast, scene_place="", world_name="", scene_time="", player=None, opening_demo=""):
        made["cast"], made["world"], made["player"] = list(cast), world_name, player
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
    # v1.0.0：save_world 首次创建时播种玩家卡，ensure_player_card 把其 world 重指到
    # 「最后保存的世界」——本例先世界一后世界二，故玩家卡归属世界二。
    assert set(store.list_characters_by_world("世界二")) == {"丙", "玩家"}
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


def test_by_world_endpoint_browse_ensures_player_for_real_world(client):
    """2026-10-20：浏览真实世界的角色列表 → 走浏览安全版补建（保留 v1.0.0 兜底初衷），
    且**不得**调用破坏性 ensure_player_card（玩家卡 world 不匹配时删卡重建，
    多剧本并存下页面加载会抹空玩家已填内容——重启丢档 bug 的根因）。"""
    c, made = client
    c.get("/api/characters/by-world?world=%E4%B8%96%E7%95%8C%E4%B8%80")
    assert made["ensured_browse"] == ["世界一"]
    assert made["ensured"] == []


def test_by_world_endpoint_does_not_ensure_unknown_world(client):
    """world 指向不存在的世界书时不得补建（避免把玩家卡 world 重指到幽灵世界）。"""
    c, made = client
    c.get("/api/characters/by-world?world=%E4%B8%8D%E5%AD%98%E5%9C%A8")
    assert made["ensured_browse"] == []
    assert made["ensured"] == []


# ---------------------------------------------------------------------------
# 3. 开局：世界显式传入 + 两条校验
# ---------------------------------------------------------------------------

def test_session_new_uses_explicit_world(client):
    c, made = client
    r = c.post("/api/session/new", json={"cast": ["甲", "乙"], "scene": "客厅", "world": "世界一"})
    assert r.status_code == 200, r.get_json()
    assert made["world"] == "世界一"
    # v1.0.0：玩家并入在场名单（ensure_player_card 兜底 + cast 末尾追加）
    assert made["cast"] == ["甲", "乙", "玩家"]
    assert made["player"] == "玩家"


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


def test_session_new_default_cast_is_world_members(client):
    """不传 cast：默认该世界的全部角色登场，不含跨世界/未归属角色。"""
    c, made = client
    r = c.post("/api/session/new", json={"world": "世界一", "scene": "集市"})
    assert r.status_code == 200, r.get_json()
    assert set(made["cast"]) == {"甲", "乙", "玩家"}
