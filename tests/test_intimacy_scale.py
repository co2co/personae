"""亲密与性内容铁律特化测试（NSFW 支持版，2026-10-18 架构改造后）。

对齐 2026-10-18 铁律瘦身决策：原铁律⑧「亲密与性描写」的**尺度措辞**（怎么写亲密戏）
已整体下沉到世界书的「亲密描写标准」条目（各剧本出厂自带），引擎系统层不再堆尺度词，
避免与剧本设定重复堆料。

唯一保留在引擎层的，是**未成年法律红线**——这是引擎级法律底线，永远生效，
不可由世界书覆盖（各剧本可停用/改写「亲密描写标准」条目，但红线始终在引擎）。

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


def test_scale_wording_dropped_from_engine():
    """亲密描写尺度措辞已下沉世界书，引擎层不再注入尺度词。"""
    sys_p = _system_prompt()
    assert "身临其境" not in sys_p
    assert "正面写实" not in sys_p
    assert "不预设上限" not in sys_p
    assert "不强制克制" not in sys_p


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
