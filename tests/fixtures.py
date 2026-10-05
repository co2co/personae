"""测试层中性占位数据（引擎普适性红线）。

红线：引擎面向任意剧本/角色，测试层不得绑定任何具体剧本、具体角色名或题材词，
否则「换剧本即全红」。本模块提供统一的中性占位（角色甲/乙/丙/丁）与通用卡构造器，
供各测试文件 import，不依赖磁盘上的 data/characters、data/worlds。

约定：
  - 人名一律用「角色甲/角色乙/角色丙/角色丁」；
  - 场景/物件用中性词（安全屋、仓库、卷帘门…），不用题材专有名词；
  - 卡片由 make_card / make_cards 构造，最小字段齐全即可满足 build_session。
"""

NAMES = ["角色甲", "角色乙", "角色丙", "角色丁"]
A, B, C, D = NAMES


def make_card(name, relations=None, **fields):
    """构造一张通用角色卡。缺省字段留空，够 build_session 组装人设块用。"""
    card = {
        "name": name,
        "description": "",
        "personality": "",
        "core_desire": "",
        "core_fear": "",
        "short_goal": "",
        "relations": dict(relations or {}),
    }
    card.update(fields)
    return card


def make_cards(names=None, relations_by_name=None):
    """批量构造角色卡。relations_by_name: {角色名: {对象名: 关系}}。"""
    relations_by_name = relations_by_name or {}
    return {n: make_card(n, relations_by_name.get(n)) for n in (names or NAMES)}


def card_loader(cards):
    """返回一个 load_card(name) 替身，供 monkeypatch store.load_card。

    对不在 cards 里的名字按需现场生成空卡，避免测试因少写一个名字而 KeyError。
    """
    def _load(name):
        if name not in cards:
            cards[name] = make_card(name)
        return cards[name]
    return _load


def fake_list_characters(names=None):
    """返回一个 list_characters() 替身，供 monkeypatch store.list_characters。"""
    return lambda: list(names or NAMES)
