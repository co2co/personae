"""亲密描写尺度铁律（铁律⑧）特化测试。

验证 v0.11.0 后新增的「亲密描写尺度」约束在 build_session 里的确定性表现。
注：单元测试无法真实调用 LLM 验证「模型拒答/越线」，故聚焦在可确定性验证的层面——
约束是否存在、是否双向（放行+红线）、是否全局默认、是否守住普适性红线。

运行：tests/venv/Scripts/python.exe -m pytest tests/test_intimacy_scale.py -q
"""
import sys
sys.path.insert(0, "engine")

import prompter


MIN_SNAP = {
    "scene": {"round": 1, "place": "某处", "time": "夜", "weather": ""},
    "relations": {}, "ledger": [], "secrets": [],
    "goals": {}, "present": ["角色甲", "角色乙"],
}
CARDS = {n: {"name": n} for n in ["角色甲", "角色乙"]}


def _system_prompt(snap=None, cards=None):
    msgs = prompter.build_session(
        cards or CARDS, "", [], snap or MIN_SNAP)
    return msgs[0]["content"]


def test_scale_law_present():
    """铁律⑧「亲密描写尺度」必须存在于 system prompt。"""
    sys_p = _system_prompt()
    assert "亲密描写尺度" in sys_p


def test_scale_law_is_bidirectional():
    """约束必须双向：既有放行许可（成年人+自愿），又有硬红线（未成年/非自愿/露骨）。"""
    sys_p = _system_prompt()
    # 放行侧：成年人 + 自愿 + 关系驱动
    assert "成年人" in sys_p
    assert "自愿" in sys_p
    assert "关系自然发展" in sys_p
    # 红线侧：未成年性化 / 非自愿胁迫 / 露骨堆砌
    assert "未成年" in sys_p
    assert "非自愿" in sys_p
    assert "胁迫" in sys_p
    assert "露骨" in sys_p


def test_scale_law_is_global_default():
    """全局默认写死一条线：不依赖任何角色卡字段、任何剧本/世界书都生效。

    即：空角色卡（无 description/personality 等）、空世界书命中、空秘密，
    铁律⑧仍须出现。
    """
    empty_cards = {n: {} for n in ["甲", "乙"]}
    empty_snap = {
        "scene": {"round": 1, "place": "", "time": "", "weather": ""},
        "relations": {}, "ledger": [], "secrets": [],
        "goals": {}, "present": ["甲", "乙"],
    }
    sys_p = _system_prompt(snap=empty_snap, cards=empty_cards)
    assert "亲密描写尺度" in sys_p


def test_scale_law_neutral_wording():
    """普适性红线：措辞不得含具体角色名 / 剧本题材词。"""
    sys_p = _system_prompt()
    # 历史已删剧本 / 当前 DEMO 角色名 / 题材词均不得出现
    banned = ["王晨", "陆衡", "王秀兰", "林清", "苏晚", "顾庭深", "林见秋", "许照",
              "方哲", "陈默", "林瑶", "周凯",
              "程禹", "沈薇", "许言", "苏黎",
              "丧尸", "末日", "客服部", "庄园", "民宿"]
    for b in banned:
        assert b not in sys_p, "提示词出现禁用名/题材词：%s" % b


def test_scale_law_uses_neutral_placeholder_only():
    """铁律⑧自身必须只用中性占位（如「角色」「双方」「成年人」），不含任何专名。"""
    sys_p = _system_prompt()
    idx = sys_p.find("⑧")
    law8 = sys_p[idx:idx + 200]
    # 出现「未成年人」等词是允许的（这是红线表述，不是专名），但不得含具体姓名
    for name in ["程禹", "沈薇", "许言", "苏黎", "角色甲", "角色乙"]:
        assert name not in law8, "铁律⑧混入专名：%s" % name
