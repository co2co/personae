"""亲密与性内容铁律（铁律⑧）特化测试（NSFW 支持版）。

对齐 v0.28.8 出厂措辞：当叙事推进到亲密场景时，要求身临其境、正面写实、
禁止隐喻/文学化一带而过；尺度与颗粒度由场景与人物关系自然决定，不预设上限、
也不强制克制。
保留的约束：
  - 时机层：叙事尚未推进到亲密时刻前不得提前/硬写。
  - 法律红线：未成年角色的性化描写一律禁止。
本文件断言与该措辞绑定，改铁律文案须同步本文件。

普适性红线：全文件只用中性占位，不绑定任何具体剧本角色名或题材词。
"""
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

import prompter  # noqa: E402
from fixtures import A, B  # noqa: E402

MIN_SNAP = {
    "scene": {"round": 1, "place": "某处", "time": "夜", "weather": ""},
    "relations": {}, "ledger": [], "secrets": [],
    "goals": {}, "present": [A, B],
}
CARDS = {n: {"name": n} for n in [A, B]}


def _system_prompt(snap=None, cards=None):
    msgs = prompter.build_session(
        cards or CARDS, "", [], snap or MIN_SNAP)
    return msgs[0]["content"]


def test_law_present():
    """铁律⑧「亲密与性描写」必须存在于 system prompt。"""
    sys_p = _system_prompt()
    assert "亲密与性描写" in sys_p


def test_law_requires_immersive_when_intimate():
    """推进到亲密场景时要求身临其境、正面写实、禁止隐喻/文学化一带而过。"""
    sys_p = _system_prompt()
    assert "身临其境" in sys_p
    assert "正面写实" in sys_p
    assert "禁止用隐喻" in sys_p


def test_law_no_scale_presets():
    """尺度与颗粒度自然决定，不预设上限、不强制克制。"""
    sys_p = _system_prompt()
    assert "不预设上限" in sys_p
    assert "不强制克制" in sys_p
    assert "自然决定" in sys_p


def test_law_is_driven_by_narrative():
    """亲密及性内容由剧情与角色关系自然驱动。"""
    sys_p = _system_prompt()
    assert "剧情与角色关系自然驱动" in sys_p


def test_law_has_timing_constraint():
    """时机层：叙事未推进到亲密时刻前不得提前/硬写。"""
    sys_p = _system_prompt()
    assert "尚未推进到亲密时刻" in sys_p
    assert "提前引入或硬写" in sys_p


def test_law_hard_redline_is_minor_only():
    """法律红线仅保留未成年一条。"""
    sys_p = _system_prompt()
    assert "硬红线" in sys_p
    assert "未成年" in sys_p


def test_law_is_global_default():
    """全局默认：不依赖任何角色卡/世界书/秘密，空配置仍须出现。"""
    empty_cards = {n: {} for n in [A, B]}
    empty_snap = {
        "scene": {"round": 1, "place": "", "time": "", "weather": ""},
        "relations": {}, "ledger": [], "secrets": [],
        "goals": {}, "present": [A, B],
    }
    sys_p = _system_prompt(snap=empty_snap, cards=empty_cards)
    assert "亲密与性描写" in sys_p


def test_law_neutral_wording():
    """普适性红线：措辞不得含具体角色名 / 剧本题材词。"""
    sys_p = _system_prompt()
    banned = ["苏晚", "顾庭深", "林见秋", "许照", "方哲", "陈默", "林瑶", "周凯",
              "丧尸", "末日", "庄园", "民宿", "避难所"]
    for b in banned:
        assert b not in sys_p, "提示词出现禁用名/题材词：%s" % b


def test_law_uses_neutral_placeholder_only():
    """铁律⑧ 自身必须只用中性表述，不含任何专名。"""
    sys_p = _system_prompt()
    idx = sys_p.find("⑧")
    law8 = sys_p[idx:idx + 160]
    for name in [A, B]:
        assert name not in law8, "铁律⑧混入专名：%s" % name
