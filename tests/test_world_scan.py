"""world.scan 的确定性单元测试（不调 LLM，快速）。

覆盖：constant 必中 / depth 远距命中 vs 默认丢失 / position 属性保留 /
recursive 拉入 + 防环 + 禁用目标不拉 / 向后兼容（无 name）/ 禁用跳过 / character 过滤。
"""

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
