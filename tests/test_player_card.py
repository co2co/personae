"""玩家角色卡「身份锚 is_player 标志、名字自由可改」的 store 层测试（v1.0.0）。

背景（A 方案）：引擎识别玩家不再靠硬编码文件名「玩家」，而靠卡内 is_player 标志——
玩家可在角色编辑器里自由给玩家卡改名（如把人设命名成「苏定城」），引擎仍认得，不产生
孤儿卡。覆盖四个核心不变量：
  1. player_card_name 认标志不认名：玩家卡改名后仍命中同一张卡。
  2. save_card 单例约束：保存一张新 is_player 卡时，同世界其它 is_player 卡（改名前旧卡 /
     误建的第二张）被删去，恒保唯一玩家卡。
  3. ensure_player_card 幂等收敛：同世界「空白默认卡 + 已填人设卡」并存时，保留内容最
     丰富者、删掉空卡。
  4. ensure_player_card 全局单例收敛：玩家卡挂在旧世界名下时，操作新世界把它重指过去，
     不新建空卡、不产生孤儿（切换/导入剧本场景）。

全部走隔离的 store.DATA_DIR（临时目录），不碰真实 data/、不调任何 LLM。
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


def test_ensure_converges_empty_and_filled(data):
    """3) 同世界「空白默认卡 + 已填人设卡」并存时，ensure 保留有内容者、删空卡。"""
    store.save_world("王朝", [])
    store.save_card("玩家", {"world": "王朝", "is_player": True})                      # 空卡
    store.save_card("苏定城", {"world": "王朝", "is_player": True,
                               "description": "精瘦男子，未来修仙穿越者。",
                               "core_desire": "与心仪女性同房修炼。",
                               "core_fear": "只在意修为提升。"})                          # 有内容
    name = store.ensure_player_card("王朝")
    assert name == "苏定城"
    # 空卡被删，有内容者保留且内容不丢
    assert not (data / "characters" / "玩家.json").exists()
    kept = store.load_card("苏定城")
    assert kept["description"] and kept["core_desire"] and kept["is_player"]
    assert store.player_card_name("王朝") == "苏定城"


def test_ensure_global_singleton_repoints_old_world(data):
    """4) 玩家卡挂在旧世界名下，操作新世界时 ensure 把它重指过去（不新建、不孤儿）。"""
    store.save_world("旧朝", [])
    store.save_world("新朝", [])
    store.save_card("苏定城", {"world": "旧朝", "is_player": True, "description": "穿越者"})
    # 操作新世界：玩家卡（认标志）应被重指到新朝，而不是新建一张默认名空卡
    name = store.ensure_player_card("新朝")
    assert name == "苏定城"
    assert (data / "characters" / "苏定城.json").exists()
    # 未新建默认名「玩家」空卡
    assert not (data / "characters" / "玩家.json").exists()
    assert store.load_card("苏定城")["world"] == "新朝"
    # 旧世界不再持有玩家卡
    assert store.player_card_name("旧朝") is None


def test_ensure_creates_empty_when_no_player(data):
    """基线：无任何玩家卡时 ensure 新建一张默认名空卡并归属当前世界。"""
    store.save_world("王朝", [])
    name = store.ensure_player_card("王朝")
    assert name == store.PLAYER_NAME
    card = store.load_card(name)
    assert card["world"] == "王朝" and card["is_player"] is True
