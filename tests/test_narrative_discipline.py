"""镜头与尺度措辞「引擎不再立法」回归测试（2026-11-09 引擎瘦身）。

架构口径（与 nsfw 分支 7284909 同源，两处按 master 口径校正，见下）：
引擎只保留与题材无关的机制投影铁律（信息边界 / 秘密代价 / 后果留痕 / 导演不登场 /
不写重复），镜头与尺度措辞一律归作者世界书。
- 「叙事纪律（镜头轮换）」已从引擎层删除；随包范例剧本把它写成世界书条目
  「叙事纪律·镜头轮换」（engine/data/examples/worlds/），作者可改写、停用、删除。
- 铁律⑧（亲密与性描写尺度）在 master 上早已下架（2026-10-21，对齐 v0.29.0），
  引擎从不承载；尺度断言见 test_intimacy_scale.py。
- 校正一（master 专属）：「己、法律底线」未成年红线仍由引擎层恒定注入、不可由世界书
  覆盖，本文件锁住它——nsfw 分支删掉了这一条，master 不跟。
- 校正二（master 专属）：随包范例剧本必须真的带着那条镜头纪律，否则「下沉到世界书」
  只是把约束扔掉。

普适性红线：全文件只用中性占位，不绑任何具体剧本角色名或题材词。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "engine"
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

LENS_RULE = "主镜头要在多条剧情线之间轮换"


def _system_prompt(snap=None, cards=None):
    msgs = prompter.build_session(
        cards or CARDS, "", [], snap or MIN_SNAP)
    return msgs[0]["content"]


def test_lens_discipline_no_longer_in_engine():
    """镜头纪律不再由引擎恒定注入（归作者世界书）。"""
    sys_p = _system_prompt()
    assert "叙事纪律" not in sys_p
    assert LENS_RULE not in sys_p
    assert not hasattr(prompter, "_NARRATIVE_DISCIPLINE")


def test_lens_block_only_describes_where_people_are():
    """引擎只陈述「谁在哪」这一物理事实，不规定镜头该怎么切。

    [本轮场面] 段保留分场事实与「不得凭空出现」这类物理一致性约束，
    但不得再出现「主镜头要轮换」「不要被单一角色吸住」这种镜头审美指令。
    """
    snap = dict(MIN_SNAP)
    snap["locations"] = {A: {"place": "东屋", "round": 1},
                         B: {"place": "西屋", "round": 1}}
    sys_p = _system_prompt(snap=snap)
    assert "东屋" in sys_p and "西屋" in sys_p
    for w in (LENS_RULE, "不要被单一强势角色一直吸住"):
        assert w not in sys_p, "镜头审美指令回流引擎层：%s" % w


def test_laws_are_mechanism_projection_plus_minor_redline():
    """laws 恰为机制投影前缀：无铁律⑧、无叙事纪律；未成年红线仍在。"""
    laws = prompter._build_laws()
    assert laws == prompter._LAWS_PREFIX
    for gone in ("亲密与性描写", "身临其境", "正面写实", "叙事纪律"):
        assert gone not in laws, "引擎层不应再承载：%s" % gone
    assert "法律底线" in laws and "未成年" in laws, "未成年红线必须留在引擎层"


def test_laws_are_generic_no_proper_nouns():
    """普适性红线：引擎层措辞不得含任何具体剧本/题材专有名词。

    黑名单只放「题材类别词」，不放具体角色名。镜头与手段题材词已归世界书，
    引擎侧出现任何一个都说明题材内容被重新搬回了引擎层。
    """
    laws = prompter._build_laws()
    banned = ["宫", "朝堂", "后宫", "边将", "文官", "宗室", "禁军",
              "名分", "礼制", "账簿", "兵权", "虎符", "勤王", "下毒", "巫蛊"]
    for w in banned:
        assert w not in laws, "引擎层混入题材类别词：%s" % w


def test_laws_positive_tone_not_negative():
    """铁律保持正向基调：讲「该怎么做」，不再堆「禁止/必须/不得」负向硬约束。"""
    laws = prompter._build_laws()
    assert "写作基调" in laws
    # 机制投影铁律用「甲/乙/丙/丁/戊/己」而非「①②③」，且保留信息边界这一灵魂
    assert "信息有边界" in laws


def test_example_drama_carries_lens_discipline():
    """下沉的落地检查：随包范例世界书确实带着镜头轮换纪律条。

    引擎删掉一段措辞时最坏的情况是「引擎不再说、也没人接」——本用例锁住接盘方。
    该条归作者：2026-11-14 撤净「引擎默认条目」层后，引擎既不播种也不补任何条目，
    这条只能由剧本自己带着——所以「没人接」的风险全在世界书里，不在引擎里。
    """
    worlds = ENGINE / "data" / "examples" / "worlds"
    files = sorted(worlds.glob("*.json"))
    assert files, "随包范例世界书缺失"
    hits = 0
    for path in files:
        entries = json.loads(path.read_text(encoding="utf-8")).get("entries", [])
        for e in entries:
            if LENS_RULE in (e.get("content") or ""):
                assert e.get("constant") is True, "该条应恒定注入，否则等于没沉下去"
                assert e.get("origin") != "engine", "范例剧本里它是作者条目，不是引擎播种"
                hits += 1
    assert hits, "随包范例世界书没有承接镜头轮换纪律"
