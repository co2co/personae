"""事实保全：常量层（不可逆）与状态层（可刷新）测试（确定性，不依赖真实 LLM / 网络）。

起因：历史超过窗口后被压成「指令前 80 字 + 叙事首 90 字」的骨架，早期确立的世界事实
（谁死了、谁残了、什么毁了、谁当众说过什么）随压缩蒸发，后续出现死人开口、伤口痊愈、
毁掉的东西又出现这类硬伤。关系/旧账只覆盖「人与人」，覆盖不了「世界状态」。

分类口径（用户裁定）：常量 ≠ 看起来难改的事，而是**后续任何一个动作都改不回来**的事。
门被封死可爆破、人离开会回来 —— 都不是常量，属于状态层；人死了才是常量。

覆盖：
  1. add_facts：逐字举证才写入（防凭空造事实）、去重、kind 归一化。
  2. 分类上限折叠：超限把最老的同类压成一行，体积恒定、对象不丢。
  3. update_states：一键一当前值（后写覆盖）、超限淘汰最久未更新的键 —— 故不随回合膨胀。
  4. invalidate_fact：只作标记不删除（留痕防下轮重抽），作废后不再注入提示词。
  5. check_fact_conflicts：已故者开口才告警（被提及不算），且**只报不改**。
  6. prompter：注入 [既定事实（不可违背）] 与 [当前状态（可被改写）] 两块。
"""

import sys
from pathlib import Path

import json

import pytest

ENGINE = Path(__file__).resolve().parent.parent / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

import director  # noqa: E402
import prompter  # noqa: E402


REPLY = "甲：我撑不住了。\n乙伸手去扶，甲已经没了气息，胸口不再起伏。\n卷帘门被焊死，谁也出不去。"


def _snap():
    return {"facts": [], "states": {}, "present": ["甲", "乙"],
            "scene": {"round": 1}, "secrets": [], "relations": {}, "ledger": [],
            "goals": {}, "actions": {}, "silent_rounds": {}, "address": {}}


def _fact(subject, text, kind="death", evidence=None):
    return {"kind": kind, "subject": subject, "text": text,
            "evidence": evidence if evidence is not None else "甲已经没了气息，胸口不再起伏"}


# --- 1. 写入：举证 / 去重 / 归一化 ---

def test_add_facts_requires_evidence():
    snap = _snap()
    # 证据非正文原文 -> 丢弃（与秘密归档同一套纪律）
    assert director.add_facts(snap, [_fact("甲", "甲死亡", evidence="乙说甲还活着")],
                              1, REPLY) == 0
    assert snap["facts"] == []


def test_add_facts_ok_and_dedup():
    snap = _snap()
    assert director.add_facts(snap, [_fact("甲", "甲死亡")], 3, REPLY) == 1
    assert director.add_facts(snap, [_fact("甲", "甲死亡")], 4, REPLY) == 0   # 重复不记
    assert len(snap["facts"]) == 1
    assert snap["facts"][0]["round"] == 3


def test_add_facts_normalizes_unknown_kind():
    snap = _snap()
    director.add_facts(snap, [_fact("甲", "甲当众承认", kind="瞎写的")], 1, REPLY)
    assert snap["facts"][0]["kind"] == "other"


# --- 2. 分类上限折叠 ---

def test_compact_folds_oldest_when_over_cap():
    snap = _snap()
    for i in range(35):
        snap["facts"].append({"kind": "death", "subject": "角色%d" % i,
                              "text": "角色%d 死亡" % i, "round": i + 1,
                              "quote": "", "invalid": False, "reason": ""})
    director._compact_facts(snap)
    assert len(snap["facts"]) == director.FACT_CAPS["core"]
    folded = [f for f in snap["facts"] if f.get("folded")]
    assert len(folded) == 1
    assert "角色0" in folded[0]["subject"]      # 最老的仍保留对象名
    assert "角色34" in "".join(f["text"] for f in snap["facts"] if not f.get("folded"))


def test_compact_keeps_event_group_separately():
    snap = _snap()
    for i in range(18):     # 事件类上限 15
        snap["facts"].append({"kind": "deed", "subject": "甲", "text": "事件%d" % i,
                              "round": i + 1, "quote": "", "invalid": False, "reason": ""})
    director._compact_facts(snap)
    assert len(snap["facts"]) == director.FACT_CAPS["event"]


# --- 3. 状态层：覆盖式、不膨胀 ---

def test_states_overwrite_by_subject():
    snap = _snap()
    director.update_states(snap, [{"subject": "卷帘门", "value": "被焊死，无法通行"}], 2)
    director.update_states(snap, [{"subject": "卷帘门", "value": "被炸开，可通行"}], 7)
    assert snap["states"]["卷帘门"] == {"value": "被炸开，可通行", "round": 7}
    assert len(snap["states"]) == 1        # 同一个键，覆盖而非追加


def test_states_cap_evicts_stalest():
    snap = _snap()
    for i in range(director.STATE_CAP + 5):
        director.update_states(snap, [{"subject": "对象%d" % i, "value": "值%d" % i}], i + 1)
    assert len(snap["states"]) == director.STATE_CAP
    assert "对象0" not in snap["states"]     # 最久未更新的被淘汰
    assert "对象%d" % (director.STATE_CAP + 4) in snap["states"]


# --- 4. 作废：只标记、不删除 ---

def test_invalidate_marks_and_stops_injection():
    snap = _snap()
    director.add_facts(snap, [_fact("甲", "甲死亡")], 2, REPLY)
    assert director.invalidate_fact(snap, "甲死亡", "其实只是昏迷")
    assert snap["facts"][0]["invalid"] is True
    assert len(snap["facts"]) == 1          # 留痕，不删除（防下轮被重新抽回）
    cards = {"甲": {"description": ""}, "乙": {"description": ""}}
    system = prompter.build_session(cards, "继续", [], snap)[0]["content"]
    assert "甲死亡" not in system


# --- 5. 矛盾只告警、不改写 ---

def test_conflict_warns_only_when_dead_speaks():
    snap = _snap()
    snap["facts"] = [{"kind": "death", "subject": "甲", "text": "甲死亡", "invalid": False}]
    assert director.check_fact_conflicts(snap, "甲：我没事，别管我。") == ["甲"]
    # 被提及/回忆不算矛盾（只按「开口」判，不按「名字出现」判）
    assert director.check_fact_conflicts(snap, "乙想起了甲说过的话。") == []
    # 只告警不改写：快照原样
    assert snap["facts"][0]["invalid"] is False


def test_no_conflict_after_invalidate():
    snap = _snap()
    snap["facts"] = [{"kind": "death", "subject": "甲", "text": "甲死亡", "invalid": True}]
    assert director.check_fact_conflicts(snap, "甲：我又活了。") == []


# --- 6. 提示词注入 ---

def test_prompt_injects_both_layers():
    snap = _snap()
    snap["facts"] = [{"kind": "death", "subject": "甲", "text": "甲死亡", "invalid": False}]
    snap["states"] = {"卷帘门": {"value": "被焊死，无法通行", "round": 2}}
    cards = {"甲": {"description": ""}, "乙": {"description": ""}}
    system = prompter.build_session(cards, "继续", [], snap)[0]["content"]
    assert "[既定事实（不可违背）]" in system and "甲死亡" in system
    assert "[当前状态（可被改写）]" in system and "被焊死" in system
    # 常量不可违背、状态可被改写：两块措辞必须区分开，否则模型会一视同仁
    assert "不可逆转" in system and "可被后续剧情改变" in system


def test_prompt_skips_empty_layers():
    snap = _snap()
    cards = {"甲": {"description": ""}, "乙": {"description": ""}}
    system = prompter.build_session(cards, "继续", [], snap)[0]["content"]
    assert "[既定事实（不可违背）]" not in system
    assert "[当前状态（可被改写）]" not in system


if __name__ == "__main__":
    pytest.main([__file__, "-q"])


# --- 7. 端到端接线：mock 纪官，走真实 reflect 解析链路 ---

def test_reflect_writes_facts_and_states(monkeypatch):
    """纪官输出 new_facts / state_updates，reflect 须写入两层（常量须逐字举证）。"""
    reply = "甲：我撑不住了。\n乙伸手去扶，甲已经没了气息，胸口不再起伏。\n卷帘门被焊死，谁也出不去。"
    payload = {
        "relations": {}, "actions": {}, "goals": {},
        "new_facts": [
            {"kind": "death", "subject": "甲", "text": "甲已死亡",
             "evidence": "甲已经没了气息，胸口不再起伏"},
            {"kind": "disable", "subject": "乙", "text": "乙右手骨折",
             "evidence": "这段原文根本没出现过"},          # 举证不过 -> 丢弃
        ],
        "state_updates": [{"subject": "卷帘门", "value": "被焊死，无法通行"}],
    }
    snap = _snap()
    monkeypatch.setattr(director.llm, "complete", lambda *a, **k: json.dumps(payload, ensure_ascii=False))
    monkeypatch.setattr(director.memory, "load", lambda sid: snap)
    monkeypatch.setattr(director.memory, "save", lambda sid, s: None)
    director.reflect("sid", reply)

    texts = [f["text"] for f in snap["facts"]]
    assert "甲已死亡" in texts
    assert "乙右手骨折" not in texts                  # 无举证 -> 不入表
    assert snap["states"]["卷帘门"]["value"] == "被焊死，无法通行"


def test_dead_speaker_triggers_warning_not_rewrite(monkeypatch, caplog):
    """已故者开口：只告警，快照不得被自动改写（纠错权归作者）。"""
    snap = _snap()
    snap["facts"] = [{"kind": "death", "subject": "甲", "text": "甲已死亡",
                      "invalid": False, "round": 2}]
    monkeypatch.setattr(director.memory, "load", lambda sid: snap)
    monkeypatch.setattr(director.memory, "save", lambda sid, s: None)
    hits = director.check_fact_conflicts(snap, "甲：你们别管我，我还能走。")
    assert hits == ["甲"]
    assert snap["facts"][0]["invalid"] is False        # 不改写


# --- 8. 状态键归一化：泛称后缀与助词变体必须并回既有键 ---

def test_state_key_merges_emotion_variants():
    """压测实证：纪官为同一角色造出「陆衡/陆衡情绪/陆衡状态/陆衡的情绪状态」四键。"""
    snap = _snap()
    snap["states"] = {"陆衡": {"value": "高度紧张", "round": 1}}
    assert director.state_key(snap, "陆衡情绪") == "陆衡"
    assert director.state_key(snap, "陆衡状态") == "陆衡"
    assert director.state_key(snap, "陆衡的情绪状态") == "陆衡"


def test_state_key_merges_wound_variants():
    """「王晨手臂伤口 / 王晨手臂咬伤 / 王晨的手臂伤口」三键须并为一个。"""
    snap = _snap()
    snap["states"] = {"王晨手臂伤口": {"value": "渗血", "round": 1}}
    assert director.state_key(snap, "王晨的手臂伤口") == "王晨手臂伤口"
    assert director.state_key(snap, "王晨手臂咬伤") == "王晨手臂伤口"


def test_state_key_keeps_distinct_objects_apart():
    """只剥泛称后缀，不得把语义不同的对象并成一个键。"""
    snap = _snap()
    snap["states"] = {"王晨": {"value": "昏迷", "round": 1}}
    assert director.state_key(snap, "王晨手臂伤口") == "王晨手臂伤口"   # 新键，不并
    assert director.state_key(snap, "陆衡的刀") == "陆衡的刀"
    assert director.state_key(snap, "安全通道铁门") == "安全通道铁门"


# --- 9. 折叠不得套娃：摘要行每组唯一 ---

def test_compact_does_not_refold_the_summary():
    """压测实证：旧实现每轮新建摘要行，且不排除已折叠条目，下一轮它又是最老的一条
    被再折一次 —— 出现「早期已确立（R1–R3）：早期已确立（R1–R1）：…」套娃，
    且每轮白占一个新条目，上限形同虚设。"""
    snap = _snap()
    for i in range(20):
        snap["facts"].append({"kind": "deed", "subject": "角色%d" % i,
                              "text": "事件%d" % i, "round": i + 1,
                              "quote": "", "invalid": False, "reason": ""})
    director._compact_facts(snap)
    assert len([f for f in snap["facts"] if f.get("folded")]) == 1
    first_len = len(snap["facts"])

    # 再塞新的、再折一次：摘要行仍是唯一的一条，不得出现嵌套前缀
    for i in range(20, 26):
        snap["facts"].append({"kind": "deed", "subject": "角色%d" % i,
                              "text": "事件%d" % i, "round": i + 1,
                              "quote": "", "invalid": False, "reason": ""})
    director._compact_facts(snap)
    folded = [f for f in snap["facts"] if f.get("folded")]
    assert len(folded) == 1
    assert "早期已确立" not in folded[0]["subject"]
    assert not any("早期已确立" in (f.get("subject") or "")
                   for f in snap["facts"] if not f.get("folded"))
    # 体积恒定：总条目数不再随追加轮次无限增长
    assert len(snap["facts"]) <= first_len + director.FACT_CAPS["event"]


def test_compact_summary_tracks_round_range():
    snap = _snap()
    for i in range(20):
        snap["facts"].append({"kind": "deed", "subject": "甲", "text": "事件%d" % i,
                              "round": i + 1, "quote": "", "invalid": False, "reason": ""})
    director._compact_facts(snap)
    folded = [f for f in snap["facts"] if f.get("folded")][0]
    assert folded["fold_lo"] == 1
    assert "R1–" in folded["text"]


def test_update_states_drops_placeholder_values():
    """「未明确提及，维持现状」这类占位值不占键位（压测实证 8 键里有 2 键是这种空值）。"""
    snap = _snap()
    director.update_states(snap, [
        {"subject": "街道通行", "value": "未明确提及，维持现状"},
        {"subject": "公寓大门", "value": "关闭，隔绝外部噪音"},
    ], 3)
    assert list(snap["states"]) == ["公寓大门"]
