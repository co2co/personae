"""辅助群演（aux）自动登记测试：自称消解 + 描述性泛称过滤 + 历史脏数据自愈。

背景（v0.16.1）：真实会话 3e19589c 出现左栏两个 chip 指同一人——模型先用
描述性称呼起段（「年轻女子：……我叫角色丙……」），自我介绍后改用本名
（「角色丙：……」），discover_aux_speakers 把两个称呼都当成新角色登记。

根因有两层：
  ① 登记前没有「自称消解」——「我叫X」是模型亲口给出的同一性依据，最可靠；
  ② 描述性泛称（年轻女子/中年男人）本质不是人名，却能通过「2~6 字 + 行首冒号」过滤。

普适性红线：全部用中性占位与虚构人名，不含任何具体剧本名或题材词。
"""

import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

import director  # noqa: E402
from fixtures import A, B  # noqa: E402

CAST = {A, B}

# 复现真实场景：先以描述性称呼起段并自报姓名，之后改用本名
REPLY_ALIAS = (
    "门缝拉开，门外一个年轻女人踉跄扑进门内。\n"
    "年轻女子：（声音嘶哑）别关……我叫角色丙……我是护士……\n"
    f"{A}：（按住刀柄）站在原地别动。\n"
    f"{B}：她腿上有伤。\n"
    "角色丙：（突然闷哼）我……我叫角色丙……不是咬伤，是抓伤……\n"
)


def test_discover_resolves_selfname_alias():
    """自称消解：描述性称呼与本名只算一个人，保留本名。"""
    got = director.discover_aux_speakers(REPLY_ALIAS, CAST)
    assert got == ["角色丙"], "自称消解失败，候选=%s" % got
    # 泛称不该出现在结果里
    assert "年轻女子" not in got


def test_discover_filters_generic_nouns():
    """描述性泛称不作为群演名登记——它们不是人名。"""
    reply = (
        "年轻女子：（哭喊）救我。\n"
        "中年男人：（冷漠）自己进来。\n"
        "路人：（犹豫）我也在这。\n"
    )
    got = director.discover_aux_speakers(reply, CAST)
    assert got == [], "泛称未被过滤：%s" % got


def test_discover_keeps_distinct_real_names():
    """同轮引入两个真角色时不得误消解。"""
    reply = (
        "角色丙：（喘息）我是护士。\n"
        f"{A}：记录一下。\n"
        "李医生：（推门进来）我姓李。\n"
    )
    got = director.discover_aux_speakers(reply, CAST)
    assert "角色丙" in got and "李医生" in got, "误消解真角色：%s" % got


def test_discover_keeps_same_generic_in_different_rounds():
    """跨轮出现的两个描述性称呼可能真是两人，各自单轮出现时应保留。"""
    snap = {"aux": [{"name": "年轻女子", "intro_round": 3},
                    {"name": "中年男人", "intro_round": 7}]}
    director.register_aux(snap, ["路人甲"], 8, None)
    names = [a["name"] for a in snap["aux"]]
    assert "年轻女子" in names and "中年男人" in names, "跨轮被误删：%s" % names


def test_register_prunes_legacy_alias_duplicate():
    """历史脏数据在下次登记时自愈：同轮的「泛称 + 本名」只留本名。"""
    snap = {"aux": [{"name": "年轻女子", "intro_round": 4, "role": "会话群演",
                     "note": "", "status": "活跃"},
                    {"name": "角色丙", "intro_round": 4, "role": "会话群演",
                     "note": "", "status": "活跃"}]}
    added = director.register_aux(snap, ["新角色甲"], 12, None)
    names = [a["name"] for a in snap["aux"]]
    assert "年轻女子" not in names, "泛称未被清理：%s" % names
    assert "角色丙" in names, "本名被误删：%s" % names
    assert added == ["新角色甲"]


def test_register_keeps_two_real_names_same_round():
    """同轮两个真角色（均非描述词）不得被清理。"""
    snap = {"aux": [{"name": "角色丙", "intro_round": 4, "role": "会话群演",
                     "note": "", "status": "活跃"},
                    {"name": "李医生", "intro_round": 4, "role": "会话群演",
                     "note": "", "status": "活跃"}]}
    director.register_aux(snap, [], 5, None)
    names = [a["name"] for a in snap["aux"]]
    assert names == ["角色丙", "李医生"], "真角色被误删：%s" % names


def test_register_is_idempotent_on_existing_name():
    """已登记的名字不重复入表。"""
    snap = {"aux": [{"name": "角色丙", "intro_round": 4, "role": "会话群演",
                     "note": "", "status": "活跃"}]}
    added = director.register_aux(snap, ["角色丙"], 6, None)
    assert added == []
    assert len(snap["aux"]) == 1


# ---- 散文形态支持（v0.17.0 移除「角色名：」分段契约后，模型回归散文主体）----
# 移除分段格式契约后，依赖「行首 名字：」的机制必须在散文体下仍可用，
# 否则它们会静默失效：discover_aux_speakers（群演登记）与 detect_offscreen_activity
# （背景人物失责检测）。
#
# ★ 已知取舍：群演登记的散文判据是「人名 + 说话动词 + 引号」，覆盖率有限——
#   模型若写成「那个陌生人咳了一声。“水够吗？”」，该群演本轮不登记、下一轮才发现。
#   接受该漏检：漏检只是群演晚一轮进左栏，误检会让左栏出现「从今天起」这种
#   根本不存在的角色。旁路是导演的【引入角色】指令（parse_aux_introductions，
#   不依赖任何正文形态），散文剧本下最可靠的入口。


def test_discover_aux_speaker_in_prose_said_form():
    """散文体：「角色丙说：“…”」应被识别为群演候选。"""
    assert director.discover_aux_speakers("角色丙说：“水够吗？”", CAST) == ["角色丙"]


def test_discover_aux_strips_verb_and_adverb_tail():
    """贪婪匹配吃进的说话动词与状语要从名字尾部切掉。"""
    assert director.discover_aux_speakers("角色丙低声说：“水够吗？”", CAST) == ["角色丙"]
    assert director.discover_aux_speakers("角色丙喊道：“快跑！”", CAST) == ["角色丙"]


def test_discover_aux_strips_prefix_pollution():
    """候选前缀被叙述词污染时要从头部切掉（「他转向角色丙」→ 角色丙）。"""
    assert director.discover_aux_speakers(
        "他转向角色丙说：“水够吗？”", CAST) == ["角色丙"]


def test_discover_aux_rejects_quoted_sentence_content():
    """引号内的台词内容不得被当成人名——这是散文判据的最大误判源。"""
    assert director.discover_aux_speakers("“从今天起，”他的声音不高。", CAST) == []
    assert director.discover_aux_speakers("“我腿软。”她咬着嘴唇。", CAST) == []
    assert director.discover_aux_speakers("“救命……”有人喊道。", CAST) == []


def test_discover_aux_still_supports_segmented_form():
    """分段形态仍要认（模型偶尔仍会这么写，不能只押散文一种）。"""
    assert director.discover_aux_speakers("角色丙：（喘息）我是护士。", CAST) == ["角色丙"]


def test_offscreen_detects_quoted_dialogue():
    """散文体：背景人物被写成对白（「“角色戊。”他转身」）应判失责。"""
    hit, _ = director.detect_offscreen_activity("“角色戊。”他转身看向门。", ["角色戊"])
    assert hit is True


def test_offscreen_mention_alone_is_not_violation():
    """仅被提及不算失责（老机制，不能因新增引号判据而误报）。"""
    hit, _ = director.detect_offscreen_activity("他们说起角色戊最近的事。", ["角色戊"])
    assert hit is False
