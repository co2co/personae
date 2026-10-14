"""快照的玩家视图投影测试（防剧透 + 内部字段不外发）。

背景：引擎内部快照含大量「不该给用户看」的东西——秘密的完整真相与暴露后果、
发酵压力数字、命中词表、关系冻结基准、称呼速查表。/api/snapshot 与
/api/session/new 原本把整个快照发给前端，打开 DevTools 即可见全部真相，
与引擎对 LLM 的信息分级标准不一致（prompter 明确写「pressure 只存在于快照，
模型永远看不到」）。v0.16.1 起对外出口一律走 app.player_view 投影。

普适性红线：全部用 tests/fixtures.py 的中性占位，不含具体剧本名或题材词。
不读磁盘剧本数据，纯内存快照。
"""

import json
import os
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

# 路由层依赖本地 LLM 端点，测试期间清掉代理变量避免误走代理
for _k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY",
           "ALL_PROXY", "all_proxy"):
    os.environ.pop(_k, None)

import app as app_module  # noqa: E402
from fixtures import A, B  # noqa: E402

# 秘密的内部字段：这些都不该出现在玩家视图里
SECRET_INTERNAL = ("content", "bottom_line", "keys", "pressure", "exposures")
# 快照顶层内部字段：同上。
# 注意 aux 不在此列——临时群演是「谁在这局出现过」的事实，用户需要知道，
# 前端把它挂在在场角色面板末尾以蓝色底色区分。
SNAP_INTERNAL = ("relations_base", "kinship_base", "address", "recent")


def _snap():
    """构造一份含全部内部字段的快照，模拟真实会话状态。"""
    return {
        "present": [A, B],
        "scene": {"place": "某处", "time": "夜", "weather": "", "round": 3},
        "relations": {f"{A} → {B}": "母亲，独占欲"},
        "actions": {A: "翻看物资"},
        "goals": {A: "守住入口"},
        "secrets": [{
            "owner": A, "content": "秘密真相", "bottom_line": "暴露后果",
            "keys": ["触发词"], "state": "潜伏",
            "known_by": [], "suspicions": [], "exposures": [],
            "pressure": 3,
        }],
        "ledger": [{"account": f"{A} 的秘密已被 {B} 知晓（R2）：x", "round": 2}],
        "states": {"某物": {"value": "已封死", "round": 2}},
        "silent_rounds": {A: 1, B: 0},
        "relations_base": {f"{A} → {B}": "母亲"},
        "kinship_base": {f"{A} → {B}": "母亲"},
        "address": {f"{A} → {B}": "妈妈"},
        "aux": [{"name": "路人", "role": "摊主",
                 "intro_round": 2, "status": "活跃"}],
        "recent": {},
    }


def test_player_view_keeps_playable_fields():
    """玩家视图须保留「导演判断局势」所需的全部字段。"""
    v = app_module.player_view(_snap())
    for k in ("present", "scene", "relations", "states", "ledger",
              "actions", "goals", "secrets", "silent_rounds"):
        assert k in v, "玩家视图缺字段 %s" % k


def test_player_view_strips_secret_truth():
    """秘密只给「谁藏着什么、露到哪一步」，不给内容与后果——导演全知就没戏。"""
    v = app_module.player_view(_snap())
    assert v["secrets"], "秘密条目本身应保留"
    for s in v["secrets"]:
        for k in SECRET_INTERNAL:
            assert k not in s, "秘密条目泄露内部字段 %s" % k
        assert s["owner"] == A and s["state"] == "潜伏"


def test_player_view_strips_internal_top_fields():
    """冻结基准 / 称呼速查等纯内部字段不得外发。"""
    v = app_module.player_view(_snap())
    for k in SNAP_INTERNAL:
        assert k not in v, "快照泄露内部字段 %s" % k


def test_player_view_serialized_has_no_truth_leak():
    """序列化后全文检索：真相与后果一个字都不该出现。

    防的是「新增字段时忘记加白名单」——逐字段断言会漏，字符串检索不会。
    """
    raw = json.dumps(app_module.player_view(_snap()), ensure_ascii=False)
    for needle in ("秘密真相", "暴露后果", "触发词", "妈妈"):
        assert needle not in raw, "玩家视图泄露内容：%s" % needle


def test_player_view_debug_returns_full():
    """?debug=1 保留完整快照，供开发排障（与右栏日志的调试定位一致）。"""
    d = app_module.player_view(_snap(), debug=True)
    assert "content" in d["secrets"][0]
    assert "address" in d and "kinship_base" in d


def test_player_view_empty_snapshot():
    """空快照返回空 dict，不抛异常。"""
    assert app_module.player_view(None) == {}
    assert app_module.player_view({}) == {}


def test_snapshot_route_uses_player_view(monkeypatch):
    """/api/snapshot 走玩家视图；?debug=1 走完整视图。"""
    snap = _snap()
    monkeypatch.setattr(app_module.memory, "load", lambda sid: snap)
    c = app_module.app.test_client()
    got = c.get("/api/snapshot?session=x").get_json()
    assert "content" not in got["secrets"][0]
    assert got["relations"], "关系须对外可见"

    full = c.get("/api/snapshot?session=x&debug=1").get_json()
    assert "content" in full["secrets"][0]


def test_session_new_returns_player_view(monkeypatch):
    """新建会话的返回体同样不得带秘密真相。

    不读磁盘卡组（普适性红线）：store 层与 memory 层都 mock 掉，
    只验证「返回体经 player_view 投影」这一条契约。
    """
    from fixtures import make_cards
    cards = make_cards([A, B])
    monkeypatch.setattr(app_module.store, "list_characters", lambda: [A, B])
    monkeypatch.setattr(app_module.store, "load_card", lambda n: cards[n])
    monkeypatch.setattr(app_module.memory, "new",
                        lambda cast, scene_place="", world_name="", scene_time="": "sid-test")
    snap = _snap()
    monkeypatch.setattr(app_module.memory, "load", lambda sid: snap)
    monkeypatch.setattr(app_module.memory, "save", lambda sid, s: None)
    monkeypatch.setattr(app_module.director, "fill_relation_gaps", lambda s: False)
    monkeypatch.setattr(app_module.director, "derive_address_terms",
                        lambda s, c: False, raising=False)
    c = app_module.app.test_client()
    r = c.post("/api/session/new", json={"cast": [A, B], "scene": "某处"})
    assert r.status_code == 200, r.get_data(as_text=True)
    got = r.get_json()["snapshot"]
    assert "content" not in got["secrets"][0]
    assert "address" not in got


def test_player_view_exposes_aux():
    """临时群演须外发：用户需要知道谁在这局里出现过。

    前端把它挂到「在场角色」面板末尾并用蓝色底色区分——在场但不属于剧本卡组。
    """
    v = app_module.player_view(_snap())
    assert "aux" in v, "临时群演未外发，半路加入的配角会从用户视野里消失"
    assert v["aux"][0]["name"] == "路人"
    # 群演详情可用（tooltip 显示身份与加入回合），但不含引擎内部标记
    assert v["aux"][0]["role"] == "摊主"
    assert "note" not in v["aux"][0]


def test_player_view_aux_is_generic_flag():
    """aux 投影须注入 is_generic 标记（前端据此把身份/职业泛称 chip 从在场面板过滤）。

    判据与登记拒收同源（director._is_aux_reject_register），不在前端复刻词表。
    「路人」是身份泛称 → True；具名「角色丙」→ False。
    """
    snap = _snap()
    snap["aux"] = [
        {"name": "路人", "role": "摊主", "intro_round": 2, "status": "活跃"},
        {"name": "角色丙", "role": "会话群演", "intro_round": 3, "status": "活跃"},
    ]
    v = app_module.player_view(snap)
    by_name = {a["name"]: a for a in v["aux"]}
    assert by_name["路人"]["is_generic"] is True, "身份泛称应被标记"
    assert by_name["角色丙"]["is_generic"] is False, "具名群演不得被标记"
    # 注入是展示层信号，不写回内部快照落盘
    assert "is_generic" not in snap["aux"][0], "is_generic 是投影字段，不得污染内部快照"


def test_player_view_no_relation_lock_marker():
    """关系锁标记已随「关系」面板下架而移除。

    v0.16.1 起左栏不展示关系定性（那是引擎的中间产物，摆出来会让玩家照着
    面板核对而不是读故事），锁标记因此没有消费者，连带派生字段一并删除——
    避免留下「有字段没消费者」的死代码。冻结机制本身在引擎侧照常工作。
    """
    v = app_module.player_view(_snap())
    assert "relation_locked" not in v
    # 内部冻结基准照样不外发
    assert "kinship_base" not in v
