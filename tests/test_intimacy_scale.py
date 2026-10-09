"""亲密与性描写铁律（铁律⑧）特化测试。

验证铁律⑧ 在 build_session 里的确定性表现。
注：单元测试无法真实调用 LLM 验证「模型拒答/越线」，故聚焦在可确定性验证的层面——
约束是否存在、是否双向（写实要求+硬红线）、是否全局默认、是否守住普适性红线。

v0.15.0 起铁律⑧ 改为「中性折衷标准」：不预设露骨上限也不强制克制，
只要求「剧情推进到亲密场景时须正面写实、禁止隐喻一带而过」，硬红线仅保留未成年一条。
本文件的断言与该措辞绑定，改铁律文案须同步本文件。

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


def test_law_requires_realistic_depiction():
    """写实侧：须正面写实、禁止隐喻/环境侧写/文学化一带而过。"""
    sys_p = _system_prompt()
    assert "身临其境" in sys_p
    assert "正面写实" in sys_p
    assert "禁止用隐喻" in sys_p


def test_law_is_scale_neutral():
    """尺度中性：不预设上限，也不强制克制（v0.15.0 折衷标准的核心）。"""
    sys_p = _system_prompt()
    assert "不预设上限" in sys_p
    assert "不强制克制" in sys_p


def test_law_has_timing_constraint():
    """时机层反向约束（v0.24.2 补齐）：叙事未推进到亲密时刻前不得提前/硬写。

    与「尺度中性」（不预设上限、不强制克制）正交——尺度管「到位后写多实」，
    时机管「没到位别写」。缺了时机层，铁律⑧ 单向「到位就放开」会在非临界轮
    给模型留「该往亲密放开写」的暗示，挤压处境铺陈（A/B 实测 S1/S2 处境下降
    的机制嫌疑之一）。
    """
    sys_p = _system_prompt()
    assert "尚未推进到亲密时刻" in sys_p
    assert "提前引入或硬写" in sys_p


def test_law_hard_redline_is_minor_only():
    """硬红线仅保留未成年一条；不得再出现已废弃的「非自愿/胁迫」措辞。"""
    sys_p = _system_prompt()
    assert "硬红线" in sys_p
    assert "未成年" in sys_p
    # v0.15.0 已移除的旧措辞（当时误当作红线，实为越界限制）
    assert "非自愿" not in sys_p
    assert "胁迫" not in sys_p


def test_law_is_global_default():
    """全局默认：不依赖任何角色卡字段、任何剧本/世界书都生效。

    即：空角色卡（无 description/personality 等）、空世界书命中、空秘密，
    铁律⑧ 仍须出现。
    """
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
    """铁律⑧ 自身必须只用中性表述，不含任何专名。

    窗口取 120 字：铁律⑧ 正文约 110 字，够覆盖整条；窗口再大会吃到后面的
    「本轮在场角色：角色甲」句，那是列表而非铁律内容。
    """
    sys_p = _system_prompt()
    idx = sys_p.find("⑧")
    law8 = sys_p[idx:idx + 120]
    for name in [A, B]:
        assert name not in law8, "铁律⑧混入专名：%s" % name
