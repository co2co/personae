"""叙事纪律块（手段/镜头/说话）守护测试。

对齐 2026-10-16 架构归位：把「管手段/管镜头/管说话」三条跨题材通用叙事约束
从各剧本世界书「升格」为引擎内置的「叙事纪律」块（与创作铁律平级），
避免作者每个剧本手动复制一套泛用常量。剧本特异部分（具体冲突手段清单、
具体剧情线名、具体职业腔调）仍留在世界书。

本文件断言绑定该架构，改叙事纪律文案须同步本文件。

普适性红线：全文件只用中性占位，不绑定任何具体剧本角色名或题材词。
叙事纪律块自身也必须纯通用、不含任何具体剧本/题材专有名词。
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


def test_discipline_block_present():
    """叙事纪律块必须注入 system prompt（与铁律平级）。"""
    sys_p = _system_prompt()
    assert "叙事纪律" in sys_p


def test_discipline_covers_three_axes():
    """叙事纪律须覆盖手段/镜头/说话三轴。"""
    disc = prompter._NARRATIVE_DISCIPLINE
    assert "【手段】" in disc
    assert "【镜头】" in disc
    assert "【说话】" in disc


def test_discipline_forbids_blackbox_means():
    """手段轴：禁用黑箱手段，博弈落在明面规则与台面算计之间。"""
    disc = prompter._NARRATIVE_DISCIPLINE
    assert "禁用" in disc and "黑箱手段" in disc


def test_discipline_anti_single_spotlight():
    """镜头轴：无主角，主镜头多线轮换、防单点吸死。"""
    disc = prompter._NARRATIVE_DISCIPLINE
    assert "没有主角" in disc
    assert "轮换" in disc


def test_discipline_anti_full_cast_every_round():
    """镜头轴：多线并进≠每轮全员出场，只落最相关那条线。"""
    disc = prompter._NARRATIVE_DISCIPLINE
    assert "不等于" in disc or "不要求" in disc
    assert "无关" in disc


def test_discipline_anti_cliche():
    """说话轴：禁用套话与空洞敬语。"""
    disc = prompter._NARRATIVE_DISCIPLINE
    assert "套话" in disc


def test_discipline_is_generic_no_proper_nouns():
    """普适性红线：叙事纪律块不得含任何具体剧本/题材专有名词。

    升格进引擎的必须是纯通用内核；具体冲突手段/剧情线名/职业腔调留在世界书。
    黑名单只放「题材类别词」，不放具体角色名（角色名本身会触发通用性红线检测，
    测试层一律不得出现，故用类别词守护「不混入题材」这一边界即可）。
    """
    disc = prompter._NARRATIVE_DISCIPLINE
    # 题材类别词（这些只该出现在世界书，绝不能出现在引擎内置叙事纪律里）
    banned = ["宫", "朝堂", "后宫", "边将", "文官", "宗室", "禁军",
              "名分", "礼制", "账簿", "兵权", "虎符", "勤王"]
    for w in banned:
        assert w not in disc, "叙事纪律块混入题材类别词：%s" % w


def test_build_laws_appends_discipline_after_laws():
    """架构顺序：铁律在前，叙事纪律接在其后（平级但独立成段）。"""
    laws = prompter._build_laws()
    idx_law8 = laws.find("⑨ 避免机械重复")
    idx_disc = laws.find("叙事纪律")
    assert idx_law8 != -1 and idx_disc != -1
    assert idx_disc > idx_law8
