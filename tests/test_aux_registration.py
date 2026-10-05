"""辅助群演（aux）自动登记测试：自称消解 + 描述性泛称过滤 + 历史脏数据自愈。

背景（v0.16.1）：真实会话 3e19589c 出现左栏两个 chip 指同一人——模型先用
描述性称呼起段（「年轻女子：……我叫苏青……」），自我介绍后改用本名
（「苏青：……」），discover_aux_speakers 把两个称呼都当成新角色登记。

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
    "年轻女子：（声音嘶哑）别关……我叫苏青……我是护士……\n"
    f"{A}：（按住刀柄）站在原地别动。\n"
    f"{B}：她腿上有伤。\n"
    "苏青：（突然闷哼）我……我叫苏青……不是咬伤，是抓伤……\n"
)


def test_discover_resolves_selfname_alias():
    """自称消解：描述性称呼与本名只算一个人，保留本名。"""
    got = director.discover_aux_speakers(REPLY_ALIAS, CAST)
    assert got == ["苏青"], "自称消解失败，候选=%s" % got
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
        "苏青：（喘息）我是护士。\n"
        f"{A}：记录一下。\n"
        "李医生：（推门进来）我姓李。\n"
    )
    got = director.discover_aux_speakers(reply, CAST)
    assert "苏青" in got and "李医生" in got, "误消解真角色：%s" % got


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
                    {"name": "苏青", "intro_round": 4, "role": "会话群演",
                     "note": "", "status": "活跃"}]}
    added = director.register_aux(snap, ["新角色甲"], 12, None)
    names = [a["name"] for a in snap["aux"]]
    assert "年轻女子" not in names, "泛称未被清理：%s" % names
    assert "苏青" in names, "本名被误删：%s" % names
    assert added == ["新角色甲"]


def test_register_keeps_two_real_names_same_round():
    """同轮两个真角色（均非描述词）不得被清理。"""
    snap = {"aux": [{"name": "苏青", "intro_round": 4, "role": "会话群演",
                     "note": "", "status": "活跃"},
                    {"name": "李医生", "intro_round": 4, "role": "会话群演",
                     "note": "", "status": "活跃"}]}
    director.register_aux(snap, [], 5, None)
    names = [a["name"] for a in snap["aux"]]
    assert names == ["苏青", "李医生"], "真角色被误删：%s" % names


def test_register_is_idempotent_on_existing_name():
    """已登记的名字不重复入表。"""
    snap = {"aux": [{"name": "苏青", "intro_round": 4, "role": "会话群演",
                     "note": "", "status": "活跃"}]}
    added = director.register_aux(snap, ["苏青"], 6, None)
    assert added == []
    assert len(snap["aux"]) == 1
