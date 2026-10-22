"""亲密与性内容铁律特化测试（铁律⑧ 恢复版，2026-10-20）。

对齐 2026-10-20 simon 裁决：2026-10-18 把铁律⑧ 尺度措辞下沉世界书后 NSFW 支持度
不足，已按历史版本（v0.15.0 中性折衷）恢复引擎级恒定注入——「怎么写亲密戏」的
尺度措辞（身临其境/正面写实/不预设上限/不强制克制）与时机层（没到位不硬写）
回到 _LAW8_DEFAULT，系统层每回合必在。

引擎层同时保留**未成年法律红线**（_LAWS_PREFIX「己、法律底线」）——引擎级法律底线，
永远生效，不可由世界书覆盖（各剧本可停用/改写世界书「亲密描写标准」条目，
但红线始终在引擎）。铁律⑧ 内不重复该红线。

本文件断言绑定该架构，改铁律文案须同步本文件。

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


def test_scale_wording_restored_in_engine():
    """铁律⑧ 尺度措辞已恢复引擎级恒定注入（2026-10-20 恢复）。"""
    sys_p = _system_prompt()
    assert "亲密与性描写" in sys_p
    assert "身临其境" in sys_p
    assert "正面写实" in sys_p
    assert "不预设上限" in sys_p
    assert "不强制克制" in sys_p


def test_law8_timing_layer_in_engine():
    """时机层（未推进到亲密时刻前不得提前/硬写）随铁律⑧ 一并回到引擎层。"""
    sys_p = _system_prompt()
    assert "提前引入" in sys_p
    assert "硬写" in sys_p


def test_redline_not_duplicated_in_law8():
    """未成年红线由「己、法律底线」单点承载，铁律⑧ 内不重复硬红线句。"""
    law8 = prompter._LAW8_DEFAULT
    assert "未成年" not in law8, "铁律⑧ 与「己、法律底线」重复承载红线"


def test_minor_redline_kept_in_engine():
    """未成年法律红线必须始终在引擎层（不可下沉、不可由世界书覆盖）。"""
    sys_p = _system_prompt()
    assert "未成年" in sys_p
    assert "法律底线" in sys_p


def test_minor_redline_global_default():
    """未成年红线是全局默认：不依赖任何角色卡/世界书/秘密，空配置仍须出现。"""
    empty_cards = {n: {} for n in [A, B]}
    empty_snap = {
        "scene": {"round": 1, "place": "", "time": "", "weather": ""},
        "relations": {}, "ledger": [], "secrets": [],
        "goals": {}, "present": [A, B],
    }
    sys_p = _system_prompt(snap=empty_snap, cards=empty_cards)
    assert "未成年" in sys_p


def test_laws_neutral_wording():
    """普适性红线：措辞不得含具体角色名 / 剧本题材词。"""
    sys_p = _system_prompt()
    banned = ["苏晚", "顾庭深", "林见秋", "许照", "方哲", "陈默", "林瑶", "周凯",
              "丧尸", "末日", "庄园", "民宿", "避难所"]
    for b in banned:
        assert b not in sys_p, "提示词出现禁用名/题材词：%s" % b


def test_laws_use_neutral_placeholder_only():
    """铁律本身必须只用中性表述，不含任何专名。"""
    laws = prompter._build_laws()
    for name in [A, B]:
        assert name not in laws, "铁律混入专名：%s" % name
