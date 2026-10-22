"""叙事纪律块守护测试。

对齐 2026-10-18 铁律瘦身架构：把「管手段/管镜头/管说话」三条叙事纪律收敛为
只保留「镜头轮换」这一条与题材无关的通用内核；【手段】（禁黑箱手段清单）与
【说话】（职业腔调/套话禁用词）属题材特异设定，一律下沉到各剧本世界书——
世界书里已有更详细、更贴合题材的版本，引擎不再重复堆料。

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


def test_discipline_keeps_generic_lens_only():
    """叙事纪律收敛为纯通用「镜头轮换」内核，不再含【手段】【说话】题材轴。"""
    disc = prompter._NARRATIVE_DISCIPLINE
    assert "【手段】" not in disc
    assert "【说话】" not in disc


def test_discipline_anti_single_spotlight():
    """镜头轴：无主角，主镜头多线轮换、防单点吸死。"""
    disc = prompter._NARRATIVE_DISCIPLINE
    assert "没有唯一主角" in disc
    assert "轮换" in disc


def test_discipline_anti_full_cast_every_round():
    """镜头轴：多线并进≠每轮全员出场，只落最相关那条线。"""
    disc = prompter._NARRATIVE_DISCIPLINE
    assert "无关" in disc


def test_discipline_is_generic_no_proper_nouns():
    """普适性红线：叙事纪律块不得含任何具体剧本/题材专有名词。

    收敛后引擎侧只保留「镜头轮换」纯通用内核；具体冲突手段/剧情线名/职业腔调、
    套话禁用词全部留在世界书。黑名单只放「题材类别词」，不放具体角色名。
    """
    disc = prompter._NARRATIVE_DISCIPLINE
    banned = ["宫", "朝堂", "后宫", "边将", "文官", "宗室", "禁军",
              "名分", "礼制", "账簿", "兵权", "虎符", "勤王", "下毒", "巫蛊"]
    for w in banned:
        assert w not in disc, "叙事纪律块混入题材类别词：%s" % w


def test_build_laws_appends_discipline_after_laws():
    """架构顺序：铁律在前，叙事纪律接在其后（平级但独立成段）。"""
    laws = prompter._build_laws()
    idx_laws = laws.find("写作基调")
    idx_disc = laws.find("叙事纪律")
    assert idx_laws != -1 and idx_disc != -1
    assert idx_disc > idx_laws


def test_law8_intimacy_restored_in_engine():
    """铁律⑧（亲密描写）已恢复引擎级恒定注入（2026-10-20）。"""
    laws = prompter._build_laws()
    # 尺度措辞（怎么写亲密戏）与时机层回到引擎层；「未成年」是引擎级法律红线，
    # 由「己、法律底线」承载，必须保留。
    assert "亲密与性描写" in laws and "身临其境" in laws
    assert "未成年" in laws and "法律底线" in laws


def test_laws_positive_tone_not_negative():
    """铁律改为正向基调：讲「该怎么做」，不再堆「禁止/必须/不得」负向硬约束。"""
    laws = prompter._build_laws()
    assert "写作基调" in laws
    # 机制投影铁律用「甲/乙/丙/丁/戊」而非「①②③」，且保留信息边界这一灵魂
    assert "信息有边界" in laws

