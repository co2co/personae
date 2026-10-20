"""久未登场提醒段守护（v2.1.2）。

背景：`silent_rounds` 原本只有前端 chip 一个消费方，面板写「引擎已在关注」，
提示词里却一个字都没有——数字涨到 5，叙事也没有任何回流（会话 8823e5f7：
13 轮里后 6 轮只写一条线，另一条线的角色全程零出场）。

本段把它接回提示词，但只作「可选提醒」：整数阈值触发、最多点名两人、
必须留在各自位置、不给整段对白、不打断主镜头。**不做任何语义判断**——
语义检测终成穷举，谁该有戏由导演指令决定，引擎只负责让「被冷落」可见。

这里只测渲染规则（纯函数），不调 LLM、不碰真实数据目录。
角色名一律用中性占位（普适性红线）。
"""

import prompter

A, B, C, D = "角色甲", "角色乙", "角色丙", "角色丁"


def _snap(place="某处甲", round_no=8, locations=None, silent=None, focus=None):
    return {
        "present": [A, B, C, D],
        "scene": {"place": place, "time": "深夜", "weather": "",
                  "round": round_no, "same_scene": 0},
        "locations": locations if locations is not None else {},
        "goals": {}, "relations": {}, "ledger": [], "secrets": [],
        "states": {}, "actions": {}, "silent_rounds": silent or {},
        "address": {}, "focus": focus,
    }


def _cards(*names):
    return {n: {} for n in names}


def test_empty_when_nobody_is_stale():
    """连续 1 轮无行为不触发：那是正常节奏，提醒太勤会变成噪音。"""
    snap = _snap(silent={A: 1, B: 0, C: 1, D: 0})
    assert prompter.stale_cast_block(snap, _cards(A, B, C, D)) == ""


def test_empty_when_field_missing():
    """旧会话快照可能没有 silent_rounds，不得抛错。"""
    snap = _snap()
    snap.pop("silent_rounds")
    assert prompter.stale_cast_block(snap, _cards(A, B)) == ""


def test_threshold_is_two_rounds():
    snap = _snap(silent={A: 2, B: 0, C: 0, D: 0})
    out = prompter.stale_cast_block(snap, _cards(A, B, C, D))
    assert "[可选提醒·久未登场]" in out
    assert A + "：连续 2 轮没有戏" in out
    assert B not in out


def test_caps_at_two_names_longest_first():
    """静默最久的先被点名，且最多两人——否则又是「人人有份」式过场。"""
    snap = _snap(place="某处甲", locations={
        B: {"place": "某处乙", "round": 8},
        C: {"place": "某处丙", "round": 8},
        D: {"place": "某处丁", "round": 8},
    }, silent={B: 3, C: 6, D: 4})
    out = prompter.stale_cast_block(snap, _cards(A, B, C, D))
    assert C in out and D in out
    assert B not in out
    assert out.count("连续 ") == 2


def test_away_keeps_position_and_forbids_moving():
    snap = _snap(place="某处甲", locations={B: {"place": "某处乙", "round": 8}},
                 silent={B: 3})
    out = prompter.stale_cast_block(snap, _cards(A, B))
    assert "（在 某处乙）" in out
    assert "不搬进当前场景" in out
    assert "一轮最多一处" in out


def test_present_but_silent_uses_different_wording():
    """人就在当前这一场却没动作，是另一类问题：不是「不在场」，是被写成背景。"""
    snap = _snap(place="某处甲", locations={A: {"place": "某处甲", "round": 8}},
                 silent={A: 4})
    out = prompter.stale_cast_block(snap, _cards(A, B))
    assert "就在当前这一场里" in out
    assert "不要只让他站在那儿" in out
    assert "不搬进当前场景" not in out


def test_stale_location_is_marked_as_unreliable():
    """位置多轮未更新时只说「原先在」并给出落位自由，不能断言他还在那儿。

    写「位置已多轮未更新」会降低模型确定性——实测被点名的两人连续三轮一个字都没写，
    因为它不知道该把人放在哪。给授权（可自行落定一处，写清在哪）才可执行。
    """
    snap = _snap(place="某处甲", round_no=10,
                 locations={B: {"place": "某处乙", "round": 2}}, silent={B: 5})
    out = prompter.stale_cast_block(snap, _cards(A, B))
    assert "原先在 某处乙，可按他的身份与处境自行落定一处" in out


def test_unrecorded_location_does_not_invent_one():
    snap = _snap(place="某处甲", locations={}, silent={B: 3})
    out = prompter.stale_cast_block(snap, _cards(A, B))
    assert "位置未记录" in out


def test_focus_round_limits_quota_to_one_narration_line():
    """有【镜头跟随】时，镜头外额度只有一句旁白，提醒不得越过它。"""
    snap = _snap(place="某处甲", locations={B: {"place": "某处乙", "round": 8}},
                 silent={B: 3}, focus={"subjects": [A]})
    out = prompter.stale_cast_block(snap, _cards(A, B), focus={"subjects": [A]})
    assert "一句无说话人的旁白" in out
    assert "一两句话交代即可" not in out


def test_without_focus_allows_a_sentence_or_two():
    snap = _snap(place="某处甲", locations={B: {"place": "某处乙", "round": 8}},
                 silent={B: 3})
    out = prompter.stale_cast_block(snap, _cards(A, B))
    assert "一两句话交代即可" in out


def test_only_names_in_roster_are_mentioned():
    """名册外（不在 cards_present）的名字即使有静默数字也不得出现。"""
    snap = _snap(silent={A: 5, "名册外角色": 9})
    out = prompter.stale_cast_block(snap, _cards(A))
    assert "名册外角色" not in out


def test_advisory_is_subordinate_to_directive():
    snap = _snap(silent={A: 3})
    out = prompter.stale_cast_block(snap, _cards(A))
    assert "优先级仍低于导演指令" in out
    assert "听导演的" in out


def test_asks_for_one_place_but_keeps_escape_hatch():
    """措辞实证（v2.1.2 首轮实机）：写成「若叙事允许，从中挑一处」时 R8 整轮无视。

    改为「请给出至少一处」提升执行力，但仍留「腾不出篇幅」的豁免，
    且不提供「可以完全略过」的台阶——那等于把提醒写成摆设。
    """
    snap = _snap(place="某处甲", locations={B: {"place": "某处乙", "round": 8}},
                 silent={B: 3})
    out = prompter.stale_cast_block(snap, _cards(A, B))
    assert "本轮请给出其中至少一处的交代" in out
    assert "一轮最多一处" in out
    assert "完全略过" not in out


def test_silent_rounds_reach_the_built_prompt():
    """端到端：数字不丢——build_session 必须把它渲染进系统块。"""
    snap = _snap(place="某处甲", locations={A: {"place": "某处甲", "round": 8}},
                 silent={A: 3})
    msgs = prompter.build_session(_cards(A, B), "随便写点", [], snap, history=[])
    text = "\n".join(m["content"] for m in msgs)
    assert "[可选提醒·久未登场]" in text
    assert A + "：连续 3 轮没有任何动作" in text


def test_stale_location_same_name_is_not_treated_as_present():
    """位置陈旧且恰好与当前场景同名，也不能断言「他就在这一场」——陈旧位置本身不可信。"""
    snap = _snap(place="某处甲", round_no=10,
                 locations={A: {"place": "某处甲", "round": 1}}, silent={A: 4})
    out = prompter.stale_cast_block(snap, _cards(A, B))
    assert "就在当前这一场里" not in out
    assert "原先在 某处甲，可按他的身份与处境自行落定一处" in out


def test_stale_block_is_last_system_block():
    """顺序守护：必须压在全块最末（近因最强），重构时最容易被排到中间去。

    v2.1.2 首轮实机：R7 只有模型在段尾读到这一处才给出「北境」切场，
    因此它必须排在秘密发酵段之后。
    """
    snap = _snap(silent={A: 3})
    snap["secrets"] = []
    msgs = prompter.build_session(_cards(A, B), "随便写点", [], snap, history=[])
    text = msgs[0]["content"]
    assert "[可选提醒·久未登场]" in text
    assert text.rstrip().endswith("听导演的。")


def test_stale_block_is_last_system_block():
    """顺序守护：必须压在全块最末（近因最强），重构时最容易被排到中间去。

    v2.1.2 首轮实机：R7 只有模型在段尾读到这一处才给出「北境」切场，
    因此它必须排在秘密发酵段之后。
    """
    snap = _snap(silent={A: 3})
    snap["secrets"] = []
    msgs = prompter.build_session(_cards(A, B), "随便写点", [], snap, history=[])
    text = msgs[0]["content"]
    assert "[可选提醒·久未登场]" in text
    assert text.rstrip().endswith("听导演的。")
