"""玩家角色卡「身份锚 is_player 标志、名字自由可改」的 store 层测试（v1.0.0）。

背景（A 方案 + 普适性）：引擎识别玩家靠卡内 is_player 标志而非硬编码文件名「玩家」——
玩家可在角色编辑器里自由给玩家卡改名（如把人设命名成「苏定城」），引擎仍认得，不产生
孤儿卡。玩家卡是运行时单例（不进剧本模板 / 随包 demo），身份判据与名字无关。核心不变量：
  1. player_card_name 认标志不认名：玩家卡改名后仍命中同一张卡。
  2. save_card 单例约束：保存一张新 is_player 卡时，同世界其它 is_player 卡（改名前旧卡 /
     误建的第二张）被删去，恒保唯一玩家卡。
  3. 同剧本内填写 / 改名持久：本剧本里玩家填的内容、改的名字在后续 ensure 中保留，
     不被重置为空白。
  4. 普适性（核心）：新建 / 导入 / 切换剧本（world 变化）时，上个剧本残留的玩家卡
     不被携带过来，新剧本拿到一张**空白**玩家卡——上个剧本的填写不污染新剧本。
  5. 浏览安全（2026-10-20 修复）：只读列表路径（by-world）用 ensure_player_card_if_absent，
     多剧本并存时页面加载 / 引擎重启不得抹空玩家已填内容；删卡重建只留给
     建局 / 导入 / 新建世界等有意切换路径（ensure_player_card）。

全部走隔离的 store.DATA_DIR（临时目录），不碰真实 data/、不调任何 LLM。
"""
import json
import urllib.parse
import sys
from pathlib import Path

import pytest

ENGINE = Path(__file__).resolve().parent.parent / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

import store  # noqa: E402


@pytest.fixture
def data(tmp_path, monkeypatch):
    """把 store.DATA_DIR 指到临时目录并清缓存，磁盘读写自洽、不污染真实 data/。"""
    d = tmp_path / "data"
    (d / "characters").mkdir(parents=True)
    (d / "worlds").mkdir(parents=True)
    monkeypatch.setattr(store, "DATA_DIR", d)
    monkeypatch.setattr(store, "EXAMPLES_DIR", d / "examples")
    store._cache.clear()
    yield d
    store._cache.clear()


def test_player_card_name_ignores_renamed_card(data):
    """1) 玩家卡改名后，player_card_name 仍按 is_player 标志命中同一张卡。"""
    store.save_world("王朝", [])
    # ensure 播种一张默认名「玩家」的空卡
    assert store.ensure_player_card("王朝") == "玩家"
    # 玩家在编辑器里把它改名成「苏定城」并填入人设（is_player 保留、world 不变）
    card = store.load_card("玩家")
    card["description"] = "来自未来的修仙穿越者。"
    store.save_card("苏定城", card)
    # 单例约束应已删掉旧「玩家」卡
    assert not (data / "characters" / "玩家.json").exists()
    assert (data / "characters" / "苏定城.json").exists()
    # player_card_name 认标志：命中改名后的卡，而非固定名
    assert store.player_card_name("王朝") == "苏定城"
    # ensure 幂等：再 ensure 仍返回同一张（不新建第二张）
    assert store.ensure_player_card("王朝") == "苏定城"


def test_save_card_player_singleton_deletes_same_world_other(data):
    """2) 保存新 is_player 卡时，同世界其它 is_player 卡被删（改名/误建第二张的去重）。"""
    store.save_world("王朝", [])
    # 误建：同世界两张 is_player 卡
    store.save_card("玩家", {"world": "王朝", "is_player": True})
    store.save_card("苏定城", {"world": "王朝", "is_player": True,
                               "description": "穿越者", "core_desire": "修炼"})
    # 第二张保存触发去重 → 只剩苏定城
    remaining = [n for n in store.list_characters() if store.load_card(n).get("is_player")]
    assert remaining == ["苏定城"]


def test_save_card_player_singleton_keeps_cross_world(data):
    """2b) 去重只针对同世界 is_player 卡；其它世界的玩家卡不受影响（多世界并存不误删）。"""
    store.save_world("甲", [])
    store.save_world("乙", [])
    store.save_card("玩家A", {"world": "甲", "is_player": True})
    # 保存一张 world=乙 的玩家卡 → 只删同世界(乙)的 is_player 卡，甲的不碰
    store.save_card("玩家B", {"world": "乙", "is_player": True})
    assert (data / "characters" / "玩家A.json").exists()
    assert (data / "characters" / "玩家B.json").exists()


def test_same_world_dedup_keeps_one_is_player(data):
    """3) 同世界误建第二张 is_player 卡时（save_card 单例约束）只留一张，ensure 幂等。"""
    store.save_world("王朝", [])
    store.save_card("玩家", {"world": "王朝", "is_player": True})                       # 空卡
    # 同世界再存一张 → save_card 单例约束删掉同世界的另一张，只留后存者
    store.save_card("苏定城", {"world": "王朝", "is_player": True,
                               "description": "精瘦男子，未来修仙穿越者。",
                               "core_desire": "与心仪女性同房修炼。"})
    remaining = [n for n in store.list_characters() if store.load_card(n).get("is_player")]
    assert remaining == ["苏定城"]
    # ensure 幂等：再次 ensure 仍返回同一张（同世界命中，不新建）
    assert store.ensure_player_card("王朝") == "苏定城"
    kept = store.load_card("苏定城")
    assert kept["description"] and kept["is_player"]
    assert store.player_card_name("王朝") == "苏定城"


def test_ensure_same_world_keeps_filled_renamed(data):
    """4) 同剧本内：玩家给玩家卡改名并填入人设后，ensure 保留其全部内容（不重置为空白）。"""
    store.save_world("王朝", [])
    assert store.ensure_player_card("王朝") == "玩家"
    # 玩家在本剧本里把卡改名 + 填内容（运行时填写，属本剧本）
    card = store.load_card("玩家")
    card["description"] = "来自未来的修仙穿越者。"
    card["core_desire"] = "与心仪女性同住。"
    store.save_card("苏定城", card)
    # 再次 ensure（如每次浏览剧本触发）→ 命中同世界玩家卡，保留全部内容
    name = store.ensure_player_card("王朝")
    assert name == "苏定城"
    kept = store.load_card("苏定城")
    assert kept["description"] == "来自未来的修仙穿越者。"
    assert kept["core_desire"] == "与心仪女性同住。"
    assert kept["world"] == "王朝"


def test_ensure_new_drama_gets_blank_slot(data):
    """5) 普适性核心：换剧本（新建/导入/切换）时，旧剧本的玩家卡（哪怕已填内容）
    不携带过来，新剧本拿到一张**空白**卡——上个剧本的填写不污染新剧本。"""
    store.save_world("旧朝", [])                                  # first_create → 玩家@旧朝 空卡
    # 玩家在旧朝里把玩家卡改名并填入人设（运行时单例，归属旧朝）
    card = store.load_card("玩家")
    card["description"] = "来自未来的修仙穿越者，修为深厚。"
    store.save_card("苏定城", card)
    assert store.player_card_name("旧朝") == "苏定城"
    # 新建新剧本 → 旧朝的玩家卡（含填写内容）不应被带到新朝
    store.save_world("新朝", [])
    name = store.ensure_player_card("新朝")
    fresh = store.load_card(name)
    # 新朝拿到的是空白卡，不带旧朝内容
    assert (fresh.get("description") or "").strip() == ""
    assert (fresh.get("core_desire") or "").strip() == ""
    assert fresh["world"] == "新朝"
    assert fresh["is_player"] is True
    # 旧朝不再持有玩家卡（其残留被清掉，避免成孤儿）
    assert store.player_card_name("旧朝") is None


def test_ensure_creates_empty_when_no_player(data):
    """基线：无任何玩家卡时 ensure 新建一张默认名空卡并归属当前世界。"""
    store.save_world("王朝", [])
    name = store.ensure_player_card("王朝")
    assert name == store.PLAYER_NAME
    card = store.load_card(name)
    assert card["world"] == "王朝" and card["is_player"] is True


# ---------------------------------------------------------------------------
# 5. 浏览安全补建（ensure_player_card_if_absent）：重启丢档 bug 回归
# ---------------------------------------------------------------------------


def _two_worlds_with_filled_player(data, card_name="玩家"):
    """铺出报障时的运行态：两本世界书 + 一张已填内容、归属甲朝的玩家卡。

    第二本世界书直接落盘（模拟 sync_drama 文件拷贝铺入，不走 save_world——
    其首次创建会触发破坏性 ensure，恰好会把玩家卡抹掉，铺不出目标状态）。
    """
    store.save_world("甲朝", [])  # first_create → 玩家卡@甲朝（空卡）
    card = store.load_card("玩家")
    card["description"] = "来自未来的穿越者，修为深厚。"
    if card_name != "玩家":
        store.save_card(card_name, card)  # 玩家卡改名（is_player 保留、world 不变）
    else:
        store.save_card("玩家", card)
    (data / "worlds" / "乙朝.json").write_text(
        json.dumps({"name": "乙朝", "entries": []}, ensure_ascii=False), encoding="utf-8")
    store._cache.clear()


def test_browse_ensure_creates_empty_when_no_player(data):
    """5a) 无任何玩家卡时浏览补建：新建空白卡并归属请求的世界（保留 v1.0.0 浏览兜底）。"""
    (data / "worlds" / "甲朝.json").write_text(
        json.dumps({"name": "甲朝", "entries": []}, ensure_ascii=False), encoding="utf-8")
    store._cache.clear()
    name = store.ensure_player_card_if_absent("甲朝")
    assert name == store.PLAYER_NAME
    card = store.load_card(name)
    assert card["world"] == "甲朝" and card["is_player"] is True


def test_browse_ensure_same_world_keeps_filled(data):
    """5b) 玩家卡已归属请求的世界：命中返回、内容原样不动。"""
    _two_worlds_with_filled_player(data)
    name = store.ensure_player_card_if_absent("甲朝")
    assert name == "玩家"
    kept = store.load_card("玩家")
    assert kept["description"] == "来自未来的穿越者，修为深厚。"
    assert kept["world"] == "甲朝"


def test_browse_ensure_cross_world_keeps_filled_renamed(data):
    """5c) 核心回归：玩家卡（已改名 + 已填内容）挂在甲朝，浏览乙朝不得删卡重建。"""
    _two_worlds_with_filled_player(data, card_name="苏定城")
    # 页面加载左栏按世界列表逐个调用 by-world 的 store 侧动作（顺序任意）
    store.ensure_player_card_if_absent("乙朝")
    store.ensure_player_card_if_absent("甲朝")
    players = [n for n in store.list_characters() if store.load_card(n).get("is_player")]
    assert players == ["苏定城"]
    kept = store.load_card("苏定城")
    assert kept["description"] == "来自未来的穿越者，修为深厚。"
    assert kept["world"] == "甲朝"


def test_browse_ensure_empty_world_no_players_returns_none(data):
    """5d) 防御分支：无玩家卡且 world 为空 → 返回 None，不建无归属的卡。"""
    assert store.ensure_player_card_if_absent("") is None
    assert [n for n in store.list_characters() if store.load_card(n).get("is_player")] == []


def test_by_world_page_load_keeps_filled_player_card(data):
    """5e) 路由级复现（报障原场景）：多剧本并存，页面加载对每个剧本各调一次
    by-world——玩家已填内容不得丢失（修复前：每次重启后必现）。"""
    import app as engine_app

    _two_worlds_with_filled_player(data)
    c = engine_app.app.test_client()
    for w in ("乙朝", "甲朝"):
        r = c.get("/api/characters/by-world?world=" + urllib.parse.quote(w))
        assert r.status_code == 200
    players = [n for n in store.list_characters() if store.load_card(n).get("is_player")]
    assert players == ["玩家"]
    kept = store.load_card("玩家")
    assert kept["world"] == "甲朝"
    assert kept["description"] == "来自未来的穿越者，修为深厚。"
