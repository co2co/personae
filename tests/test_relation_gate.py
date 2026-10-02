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
