"""关系表与「插入」语境判定测试（会话 0ac57abf 审计驱动的修复）。

覆盖：
  1. 「插入」极通用，需性语境才判事实越线（插入空间/话题/U盘 => 无；插入她/体内 => 越线）。
  2. 角色卡 relations 字段可确定性地构建权威关系基线（seed_relations_from_cards）。
  3. reflect 冻结未在场/无卡关联人物的关系，禁止模型改写或升级（小姨子->妻子类漂移拦截）。
"""

import json
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

import director  # noqa: E402
import memory  # noqa: E402


# ---------------------------------------------------------------------------
# 0. relations_base 必须由 memory.new 一并固化（v0.7.7 修复）
# ---------------------------------------------------------------------------

def test_memory_new_seeds_relations_base():
    """真实会话（卡片自带 relations）必须固化 relations_base。

    回归护城河：v0.7.4/v0.7.6 的「未在场冻结」「亲属身份冻结」都以 relations_base
    为唯一可信源；若 memory.new 不固化，真实会话（卡片有 relations 时跳过 app.py
    固化分支）会让 relations_base 为空，两道闸静默失效。
    """
    sid = memory.new(["陈锋", "夏雨"], scene_place="安全屋", world_name="丧尸末日")
    try:
        snap = memory.load(sid)
        rel = snap.get("relations", {})
        base = snap.get("relations_base", {})
        assert rel, "relations 不应为空"
        assert base, "relations_base 不应为空（v0.7.7 修复点）"
        assert base == rel, "relations_base 应与 seeded relations 一致"
        # 亲属身份键应在基线中
        assert director._first_kinship(base.get("陈锋 → 夏雨", "")) == "妻子"
    finally:
        import shutil
        from pathlib import Path
        d = Path(memory.SESS_DIR) / sid if not str(memory.SESS_DIR).endswith(sid) else None
        # 直接按 sid 定位会话目录并清理
        root = Path(memory.SESS_DIR)
        target = root / sid
        if target.exists():
            shutil.rmtree(target)


# ---------------------------------------------------------------------------
# 1. 「插入」需性语境
# ---------------------------------------------------------------------------

def test_insert_metaphor_space_not_crossing():
    """会话 0ac57abf 第 2 轮「强行插入他们之间的空间」——空间隐喻，不得判越线。"""
    assert director.detect_intimacy("林泽宇强行插入他们之间的空间") == "无"


def test_insert_topic_not_crossing():
    assert director.detect_intimacy("他在讨论里插入一个话题") == "无"


def test_insert_usb_not_crossing():
    assert director.detect_intimacy("把U盘插入接口") == "无"


def test_insert_her_still_crossing():
    """插入 + 她：仍判越线（真实性行为）。"""
    assert director.detect_intimacy("他插入了她，抽送起来") == "越线"


def test_insert_body_still_crossing():
    assert director.detect_intimacy("手指插入体内，她颤了一下") == "越线"


# ---------------------------------------------------------------------------
# 2. 卡片 relations -> 权威基线
# ---------------------------------------------------------------------------

def test_seed_relations_from_cards():
    cards = {
        "林梦雅": {"relations": {"周牧野": "丈夫", "林梦琪": "妹妹", "林泽宇": "侄子"}},
        "周牧野": {"relations": {"林梦雅": "妻子", "林梦琪": "小姨子"}},
    }
    base = director.seed_relations_from_cards(cards)
    assert base.get("林梦雅 → 林梦琪") == "妹妹"
    assert base.get("周牧野 → 林梦琪") == "小姨子"
    assert base.get("林梦雅 → 周牧野") == "丈夫"


# ---------------------------------------------------------------------------
# 3. reflect 冻结未在场关联人物关系
# ---------------------------------------------------------------------------

def test_reflect_freezes_offscreen_relation(monkeypatch):
    """模型试图把未在场/无卡的林梦琪升为「妻子」，必须被冻结为基线小姨子；
    镜头内（周牧野/林梦雅 都在场）的关系允许演化。"""
    def fake_complete(messages, **kwargs):
        return json.dumps({
            "relations": {
                "周牧野 → 林梦琪": "妻子，占有欲强烈",
                "周牧野 → 林梦雅": "妻子，关系紧张（镜头内演化）",
            },
            "actions": {}, "goals": {},
        }, ensure_ascii=False)
    monkeypatch.setattr(director.llm, "complete", fake_complete)

    snap = {
        "present": ["周牧野", "林梦雅"],
        "relations": {"周牧野 → 林梦琪": "小姨子", "周牧野 → 林梦雅": "妻子"},
        "relations_base": {"周牧野 → 林梦琪": "小姨子", "周牧野 → 林梦雅": "妻子"},
        "secrets": [], "goals": {}, "actions": {}, "ledger": [],
    }
    monkeypatch.setattr(director.memory, "load", lambda sid: snap)
    monkeypatch.setattr(director.memory, "save", lambda sid, s: None)

    director.reflect("sid-x", "周牧野握了握林梦雅的手")

    # 未在场关联人物：冻结为基线，不得升级为妻子
    assert snap["relations"]["周牧野 → 林梦琪"] == "小姨子", snap["relations"]
    # 镜头内角色：关系允许随剧情演化
    assert snap["relations"]["周牧野 → 林梦雅"] == "妻子，关系紧张（镜头内演化）"


# ---------------------------------------------------------------------------
# 4. 背景人物活动化自检（simon 验收：引擎把背景人物写成活动角色即失责）
# ---------------------------------------------------------------------------

def test_background_names_excludes_present():
    """relations 里出现但不在在场名单的角色 = 背景人物（如林梦琪）。"""
    snap = {"present": ["周牧野", "林梦雅"],
            "relations": {"周牧野 → 林梦琪": "小姨子",
                          "林梦雅 → 林梦琪": "妹妹",
                          "周牧野 → 林梦雅": "妻子"}}
    offs = director.background_names_from_relations(snap, snap["present"])
    assert offs == ["林梦琪"]


def test_offscreen_dialogue_flagged():
    """背景人物获得独立台词块（对白/独白）-> 失责。"""
    offs = ["林梦琪"]
    reply = "周牧野看着窗外。\n林梦琪：其实我早就知道了，姐夫。\n林梦雅叹了口气。"
    viol, hits = director.detect_offscreen_activity(reply, offs)
    assert viol is True
    assert any("林梦琪" in h for h in hits)


def test_offscreen_action_subject_flagged():
    """第三人称里背景人物作主语且有动作 -> 失责（如「林梦琪从门后走出」）。"""
    offs = ["林梦琪"]
    reply = "周牧野沉默不语。林梦琪从门后走出，静静望着二人。林梦雅握紧了手。"
    viol, hits = director.detect_offscreen_activity(reply, offs)
    assert viol is True
    assert any(h.startswith("林梦琪") for h in hits)


def test_offscreen_mentioned_by_present_ok():
    """在场角色以谈论方式带过背景人物 -> 不失责（允许的背景提及）。"""
    offs = ["林梦琪"]
    reply = "林梦雅低声说：我妹妹梦琪最近总一个人待着，怪让人担心的。周牧野点点头。"
    viol, hits = director.detect_offscreen_activity(reply, offs)
    assert viol is False, hits


def test_offscreen_no_background_clean():
    """无背景人物时自检直接通过。"""
    viol, hits = director.detect_offscreen_activity("周牧野走了出去。", [])
    assert viol is False and hits == []


def test_preserve_kinship_blocks_identity_flip():
    """亲属身份冻结：父亲被模型改写成姐夫时，应回退为父亲、保留情感修饰。"""
    corrected = director._preserve_kinship("父亲", "姐夫，挑衅者/主动方")
    assert corrected.startswith("父亲"), corrected
    assert "挑衅者" in corrected, corrected


def test_preserve_kinship_allows_emotional_evolution():
    """亲属身份一致时，允许情感/状态修饰演化（父亲 -> 父亲，关系紧张）。"""
    corrected = director._preserve_kinship("父亲，关系紧张", "父亲，关系彻底破裂")
    assert corrected == "父亲，关系彻底破裂", corrected


def test_preserve_kinship_no_baseline_free():
    """基线无亲属身份词时（如同事），模型可自由定义关系身份。"""
    corrected = director._preserve_kinship("同事", "恋人，暗通款曲")
    assert corrected == "恋人，暗通款曲", corrected


def test_preserve_kinship_mother_sister_in_law_blocked():
    """母亲被改写成嫂子时，应回退为母亲。"""
    corrected = director._preserve_kinship("母亲", "嫂子，复杂情感萌芽")
    assert corrected.startswith("母亲"), corrected
    assert "复杂情感" in corrected, corrected


def test_married_couple_affection_full():
    """v0.7.7 修复：关系值写「妻子/丈夫」的已婚组合应触发满机会。

    回归点：STRONG_AFFECTION 原先只含「夫妻」状态词，不含「妻子/丈夫」亲属词，
    导致角色卡以「妻子/丈夫」描述夫妻时永远触发不了满机会，NSFW 机制形同虚设。
    """
    snap = {
        "present": ["陈锋", "夏雨"],
        "relations": {
            "陈锋 → 夏雨": "妻子，彼此深爱，末日里唯一的柔软。",
            "夏雨 → 陈锋": "丈夫，深爱的男人。",
        },
    }
    # scope=None 且两端都在场 -> 应命中满机会
    assert director._opp_from_affection(snap, None) == "满机会"
    # scope 指向该夫妻子集 -> 仍命中
    assert director._opp_from_affection(snap, ["陈锋", "夏雨"]) == "满机会"


def test_offscreen_flashback_action_detected():
    """背景人物在闪回里成为主动主语（老高笑/老高塞糖）应被判失责。

    复现跨剧本对照验证中丧尸末日 R2/R4 的真实失责样本。
    """
    offs = ["老高"]
    reply = ("李想望着墙角的旧照片。老高笑的样子浮上心头。"
             "老高每次出完任务回来，都从兜里摸出一颗水果糖，塞进她手心里。")
    viol, hits = director.detect_offscreen_activity(reply, offs)
    assert viol is True, hits
    assert any(h.startswith("老高") for h in hits)

