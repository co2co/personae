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
    entries = [{"keys": ["物资"], "content": "稀缺，需争夺。", "enabled": True}]
    hits = world_mod.scan(entries, history=["物资"], directive="", default_depth=4, character=None)
    assert len(hits) == 1


def test_disabled_entry_skipped():
    entries = [{"keys": ["物资"], "content": "x", "enabled": False}]
    assert world_mod.scan(entries, history=["物资"], directive="", default_depth=4, character=None) == []


def test_character_filter():
    entries = [{"keys": ["k"], "content": "角色甲的秘密条目", "character": "角色甲", "enabled": True}]
    assert len(world_mod.scan(entries, history=["k"], character=None)) == 1
    assert world_mod.scan(entries, history=["k"], character="角色丙") == []


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


# --- 秘密条目不占 max_entries 配额（v0.15.x 修复）---

def test_secret_does_not_consume_injection_quota():
    """秘密不进 prompt，就不该挤掉真正要注入的设定。

    回归：秘密此前参与 max_entries=8 竞争，命中后又在 app.py 被剔除，
    实测 8 条里秘密占 3，把优先级更低的设定（如逼近的尸潮）静默挤掉。
    """
    entries = [{"keys": ["常驻"], "content": "常驻设定", "constant": True, "enabled": True}]
    entries += [{"keys": [f"密{i}"], "content": f"秘密{i}", "secret": True,
                 "character": f"角色{i}", "priority": 90 - i, "enabled": True}
                for i in range(3)]
    entries += [{"keys": ["关键"], "content": "关键设定", "priority": 10, "enabled": True}]

    hits = world_mod.scan(entries, ["常驻 密0 密1 密2 关键"], directive="",
                          default_depth=4, character=None)
    injected = [e for e in hits if not e.get("secret")]
    assert any(e["content"] == "关键设定" for e in injected), \
        "低优先级的关键设定被秘密挤掉了：%s" % [e["content"] for e in injected]


def test_secret_still_returned_for_meta():
    """秘密不占配额，但命中信息仍须返回（编辑器预览与 wb_meta「排除秘密」清单要用）。"""
    entries = [{"keys": ["密"], "content": "秘密内容", "secret": True,
                "character": "角色甲", "enabled": True}]
    assert len(world_mod.scan(entries, ["密"], directive="", default_depth=4,
                              character=None, include_secret=True)) == 1
    # 常量秘密无条件纳入（不受关键词限制），两条路径都该看到
    const_secret = [{"keys": [], "content": "常驻秘密", "secret": True, "constant": True,
                     "character": "角色甲", "enabled": True}]
    assert len(world_mod.scan(const_secret, [], directive="", default_depth=4,
                              character=None, include_secret=True)) == 1


def test_recursive_pulled_secret_does_not_consume_quota():
    """被引用的秘密同样不进注入列表。"""
    entries = [
        {"name": "设定", "keys": ["触"], "content": "见 #密条#", "enabled": True},
        {"name": "密条", "keys": ["不命中"], "content": "秘密内容", "secret": True,
         "character": "角色甲", "enabled": True},
    ]
    hits = world_mod.scan(entries, ["触"], directive="", default_depth=4,
                          character=None, include_secret=True)
    injected = [e for e in hits if not e.get("secret")]
    assert [e["content"] for e in injected] == ["见 #密条#"], injected
    assert any(e.get("secret") for e in hits)


def test_recursive_pulled_entry_ranked_after_referrer():
    """被引条目排在引用方之后：依赖项的优先级由引用方决定，不该凭自身 priority 抢位。"""
    entries = [
        {"name": "引用方", "keys": ["触"], "content": "见 #被引#", "priority": 50, "enabled": True},
        {"name": "被引", "keys": ["不命中"], "content": "被引内容", "priority": 999, "enabled": True},
    ]
    hits = world_mod.scan(entries, ["触"], directive="", default_depth=4, character=None)
    assert [e.get("name") for e in hits] == ["引用方", "被引"], \
        "被引条目应排在引用方之后，实际 %s" % [e.get("name") for e in hits]


def test_three_step_reference_chain_is_directional():
    """三段链：A → B → C，沿引用方向逐级拉入，不反向。

    随包 demo 用它展示递归引用：提到「落脚点」就该知道唯一撤离通道是地下通道，
    而那条通道正对着尸潮来的方向（结构性两难）。链尾「尸潮」不被反向拉回上游——
    引用是依赖关系（下游需要知道上游），不是双向绑定。
    """
    entries = [
        {"name": "落脚点", "keys": ["落脚点"], "priority": 60,
         "content": "撤离走 #地下通道#。", "enabled": True},
        {"name": "地下通道", "keys": ["地下通道"], "priority": 59,
         "content": "唯一的撤离出口方向。那条路不安全，详见 #威胁逼近#。", "enabled": True},
        {"name": "威胁逼近", "keys": ["威胁逼近"], "priority": 56,
         "content": "威胁正朝这个方向移动，撑不了太久。", "enabled": True},
    ]
    cases = {
        "落脚点": ["落脚点", "地下通道", "威胁逼近"],      # 上游触发 -> 整链
        "地下通道": ["地下通道", "威胁逼近"],               # 中游触发 -> 本游+下游
        "威胁逼近": ["威胁逼近"],                            # 链尾 -> 只有自己
    }
    for trigger, expect in cases.items():
        hits = world_mod.scan(entries, [trigger], directive="", default_depth=4, character=None)
        names = [e.get("name") for e in hits]
        assert names == expect, "触发词 %r 期望 %s，实际 %s" % (trigger, expect, names)
        assert len(names) == len(set(names)), "链式展开出现重复条目：%s" % names


# --- 写法示范条目（demo，分开场示范 / 常驻示范两档）---

def test_demo_first_round_only_injected_on_round_one():
    """first_round 示范：仅首轮（round<=1）注入，之后不再出现——开场示范。"""
    entry = {"name": "开局示范", "keys": [], "content": "*动作* \"对白\"",
             "demo": True, "first_round": True, "enabled": True}
    # round=0（调用方未传，默认 0）：视为首轮，注入
    assert len(world_mod.scan([entry], [], round=0)) == 1
    assert len(world_mod.scan([entry], [], round=1)) == 1
    # round>1：不再注入
    assert world_mod.scan([entry], [], round=2) == []
    assert world_mod.scan([entry], [], round=5) == []


def test_demo_persistent_injected_every_round():
    """持续示范（无 first_round）：每轮注入——常驻示范。"""
    entry = {"name": "常驻示范", "keys": [], "content": "*动作* \"对白\"",
             "demo": True, "enabled": True}
    for r in [0, 1, 2, 10]:
        hits = world_mod.scan([entry], [], round=r)
        assert len(hits) == 1, "round=%d 常驻示范应注入" % r
        assert hits[0].get("demo") is True


def test_demo_marked_distinct_from_world_setting():
    """demo 条目带 demo 标志，供 app.py 从 world_hits 拆出走示范注入通道。"""
    entries = [
        {"name": "示范", "keys": [], "content": "写法示范", "demo": True, "enabled": True},
        {"name": "设定", "keys": ["x"], "content": "世界设定", "enabled": True},
    ]
    hits = world_mod.scan(entries, ["x"], directive="", default_depth=4, character=None)
    demo = [e for e in hits if e.get("demo")]
    setting = [e for e in hits if not e.get("demo")]
    assert [e["name"] for e in demo] == ["示范"]
    assert [e["name"] for e in setting] == ["设定"]


def test_demo_does_not_consume_injection_quota():
    """demo 条目不占 max_entries 配额、不混入普通命中截断。"""
    entries = [{"keys": [f"关{i}"], "content": f"关键设定{i}", "priority": 10 - i,
                "enabled": True} for i in range(3)]
    entries.append({"name": "示范", "keys": [], "content": "写法示范",
                    "demo": True, "enabled": True})
    hits = world_mod.scan(entries, ["关0 关1 关2"], directive="", default_depth=4,
                          character=None, max_entries=2)
    setting = [e for e in hits if not e.get("demo")]
    demo = [e for e in hits if e.get("demo")]
    assert len(setting) == 2, "max_entries=2 只截断普通设定，实际 %s" % setting
    assert len(demo) == 1, "demo 条目恒保留，不占配额"
