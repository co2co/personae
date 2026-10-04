"""world.scan 的确定性单元测试（不调 LLM，快速）。

覆盖：constant 必中 / depth 远距命中 vs 默认丢失 / position 属性保留 /
recursive 拉入 + 防环 + 禁用目标不拉 / 向后兼容（无 name）/ 禁用跳过 / character 过滤 /
depth 触发回合数（设计机制）/ 关键词在中段时窗口取「最近 d 条」。
"""

import pytest

import world as world_mod


def test_constant_always_hits():
    entries = [{"keys": ["x"], "content": "常量", "constant": True, "enabled": True}]
    hits = world_mod.scan(entries, history=[], directive="", default_depth=4, character=None)
    assert len(hits) == 1
    assert hits[0]["content"] == "常量"


def test_depth_far_hit_vs_default_miss():
    base = {"keys": ["城东"], "content": "城东庇护所", "enabled": True}
    history = ["城东", "b", "c", "d", "e"]  # 城东在第 0 条，最近 4 条（b~e）全无关
    # 默认 depth=4：只回看最后 4 条 -> 城东丢失
    miss = world_mod.scan([{**base, "depth": None}], history,
                          directive="", default_depth=4, character=None)
    assert miss == []
    # 条目级 depth=10：能命中第 0 条
    hit = world_mod.scan([{**base, "depth": 10}], history,
                         directive="", default_depth=4, character=None)
    assert len(hit) == 1


def test_position_attr_preserved():
    entries = [{"keys": ["门"], "content": "after 段", "position": "after", "enabled": True}]
    hits = world_mod.scan(entries, history=["门"], directive="", default_depth=4, character=None)
    assert hits[0].get("position") == "after"


def test_recursive_pull_in():
    entries = [
        {"name": "学院", "keys": ["魔法"], "content": "古老学院。详见 #校规#。",
         "priority": 100, "enabled": True},
        {"name": "校规", "keys": ["不命中"], "content": "禁魔法。", "priority": 50, "enabled": True},
        {"name": "独立", "keys": ["天气"], "content": "晴天。", "enabled": True},
    ]
    hits = world_mod.scan(entries, history=["魔法出现了"], directive="", default_depth=4, character=None)
    names = [e.get("name") for e in hits]
    assert "学院" in names and "校规" in names and "独立" not in names


def test_recursive_cycle_safe():
    entries = [
        {"name": "X", "keys": ["触发"], "content": "见 #Y#", "priority": 100, "enabled": True},
        {"name": "Y", "keys": ["不命中"], "content": "见 #X#", "priority": 50, "enabled": True},
    ]
    hits = world_mod.scan(entries, history=["触发"], directive="", default_depth=4, character=None)
    assert len(hits) == 2  # 互相引用不致死循环，各自出现一次


def test_recursive_disabled_target_not_pulled():
    entries = [
        {"name": "A", "keys": ["k"], "content": "见 #B#。", "enabled": True},
        {"name": "B", "keys": ["x"], "content": "B 内容", "enabled": False},
    ]
    hits = world_mod.scan(entries, history=["k"], directive="", default_depth=4, character=None)
    assert all(e.get("name") != "B" for e in hits)


def test_backward_compat_no_name_field():
    entries = [{"keys": ["病毒"], "content": "感染致命。", "enabled": True}]
    hits = world_mod.scan(entries, history=["病毒"], directive="", default_depth=4, character=None)
    assert len(hits) == 1


def test_disabled_entry_skipped():
    entries = [{"keys": ["病毒"], "content": "x", "enabled": False}]
    assert world_mod.scan(entries, history=["病毒"], directive="", default_depth=4, character=None) == []


def test_character_filter():
    entries = [{"keys": ["k"], "content": "老周的秘密条目", "character": "老周", "enabled": True}]
    assert len(world_mod.scan(entries, history=["k"], character=None)) == 1
    assert world_mod.scan(entries, history=["k"], character="林晚") == []


@pytest.mark.parametrize("depth", [1, 2, 4, 8, 10])
def test_depth_trigger_rounds_match_design(depth):
    """设计机制：depth=d 的条目只回看最近 d 条聊天，关键词在最近 d 条内才触发。

    把关键词放在 history[0]，逐轮追加无关废话（模拟对话推进），验证：
      - 触发区：history 长度 L <= depth 时命中（关键词仍在最近 d 条内）
      - 失触发区：L 超过 depth 后落空（关键词已滑出最近 d 条窗口）
    """
    key = "城东"
    entry = {"keys": [key], "content": "城东庇护所", "enabled": True, "depth": depth}
    for L in range(1, depth + 6):  # 覆盖触发区(L<=d)与失触发区(L>d)
        history = [key] + [f"废话轮{i}" for i in range(L - 1)]
        assert len(history) == L
        hits = world_mod.scan([entry], history, directive="", default_depth=4, character=None)
        triggered = any(key in h["content"] for h in hits)
        assert triggered == (L <= depth), \
            f"depth={depth} L={L} 触发={triggered}，不符合「最近 {depth} 轮」设计"


def test_depth_window_offsets_middle_keyword():
    """关键词不在开头，验证窗口是「最近 d 条」而非「最前 d 条」。

    关键词放在 index 3（第 4 条），depth=5：触发当且仅当关键词在最近 5 条内，
    即 L<=8 触发、L=9 起落（此时关键词滑到第 6 条之前，被排除）。
    """
    key = "地铁"
    entry = {"keys": [key], "content": "地铁通道静谧", "enabled": True, "depth": 5}
    for L, expect in [(4, True), (5, True), (8, True), (9, False), (12, False)]:
        # 构造长度恰为 L：3 条前缀 + 关键词 + (L-4) 条后缀
        history = [f"前{i}" for i in range(3)] + [key] + [f"后{j}" for j in range(L - 4)]
        assert len(history) == L
        hits = world_mod.scan([entry], history, directive="", default_depth=4, character=None)
        triggered = any(key in h["content"] for h in hits)
        assert triggered == expect, f"L={L} 触发={triggered} 期望={expect}"
