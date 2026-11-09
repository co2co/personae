"""关系表来源测试。

覆盖：
  1. 角色卡 relations 字段可确定性地构建权威关系基线（seed_relations_from_cards），
     并由 memory.new 固化为 relations_base。
  2. 纪官不得改写关系定性（2026-11-08 引擎瘦身）：关系是作者的设定，
     旧的「未在场冻结 / 亲属身份冻结」两道闸随之撤除——源头不再让模型写关系，
     闸就没有存在的必要（审计 P3：作者手写的关系细部此前只活一轮）。
  3. 作者显式声明的亲属身份（relations_kinship）仍会固化进 kinship_base（数据保留）。
"""

import json
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

import director  # noqa: E402
import memory  # noqa: E402


# ---------------------------------------------------------------------------
# 0. relations_base 必须由 memory.new 一并固化（v0.7.7 修复）
# ---------------------------------------------------------------------------

def test_memory_new_seeds_relations_base(monkeypatch):
    """真实会话（卡片自带 relations）必须固化 relations_base。

    回归护城河：v0.7.4/v0.7.6 的「未在场冻结」「亲属身份冻结」都以 relations_base
    为唯一可信源；若 memory.new 不固化，真实会话（卡片有 relations 时跳过 app.py
    固化分支）会让 relations_base 为空，两道闸静默失效。

    卡片与世界书用内存 mock 提供，不依赖磁盘文件。
    """
    cards = {
        "角色甲": {"name": "角色甲", "relations": {"角色乙": "妻子"},
                "core_desire": "", "core_fear": "", "short_goal": ""},
        "角色乙": {"name": "角色乙", "relations": {"角色甲": "丈夫"},
                "core_desire": "", "core_fear": "", "short_goal": ""},
    }
    monkeypatch.setattr(memory.store, "load_card", lambda name: cards[name])
    monkeypatch.setattr(memory.store, "load_world", lambda name: [])
    sid = memory.new(["角色甲", "角色乙"], scene_place="安全屋", world_name="测试世界")
    try:
        snap = memory.load(sid)
        rel = snap.get("relations", {})
        base = snap.get("relations_base", {})
        assert rel, "relations 不应为空"
        assert base, "relations_base 不应为空（v0.7.7 修复点）"
        assert base == rel, "relations_base 应与 seeded relations 一致"
        # 亲属身份应在基线里原样落地（不再靠从描述句里推断身份词）
        assert base.get("角色甲 → 角色乙", "") == "妻子"
    finally:
        import shutil
        from pathlib import Path
        d = Path(memory.SESS_DIR) / sid if not str(memory.SESS_DIR).endswith(sid) else None
        # 直接按 sid 定位会话目录并清理
        root = Path(memory.SESS_DIR)
        target = root / sid
        if target.exists():
            shutil.rmtree(target)


# ---------------------------------------------------------------------------
# 1. 卡片 relations -> 权威基线
# ---------------------------------------------------------------------------

def test_seed_relations_from_cards():
    cards = {
        "角色甲": {"relations": {"角色乙": "丈夫", "角色丙": "妹妹", "角色丁": "侄子"}},
        "角色乙": {"relations": {"角色甲": "妻子", "角色丙": "小姨子"}},
    }
    base = director.seed_relations_from_cards(cards)
    assert base.get("角色甲 → 角色丙") == "妹妹"
    assert base.get("角色乙 → 角色丙") == "小姨子"
    assert base.get("角色甲 → 角色乙") == "丈夫"


# --- 亲属身份冻结的误判防护（v0.15.x 修复）---

def test_kinship_single_char_tokens_removed():
    """词表不得含单字身份词。

    单字（母/子/夫/弟…）在中文里几乎只作长词碎片（母子/母性/夫人/兄弟）出现，
    早期版本收录导致「以A母子的生死为筹码」被当成对 B 的身份声明「子」，
    冻结机制反过来把模型写对的「妻子」改坏成「子，关系紧张」。
    """
    assert not [t for t in director._KINSHIP_TOKENS if len(t) == 1], \
        "身份词表混入单字词：%s" % [t for t in director._KINSHIP_TOKENS if len(t) == 1]


def test_kinship_covers_common_relations():
    """词表须覆盖中国亲属称谓里的常见缺项（v0.18.6 补词守护）。

    回归事故：姨父/姑父/堂表兄弟姐妹/侄女外甥女/岳父岳母/继子女养子女等都不在表，
    作者在 relations_kinship 里显式声明了也会被 seed_kinship_from_cards 静默丢弃——
    声明形同虚设，且无任何报错（该函数对非法词静默 return），极难排查。
    """
    must = [
        # 姨父 /姑父 / 舅妈（母系亲属的配偶，原表完全缺失）
        "姨父", "姨母", "姑父", "姑母", "舅妈", "舅母",
        # 父系伯叔
        "伯父", "伯母", "叔父", "叔母", "婶婶",
        # 堂表兄弟姐妹
        "堂兄", "堂弟", "堂姐", "堂妹", "堂哥",
        "表兄", "表弟", "表姐", "表妹", "表哥",
        # 侄辈女系
        "侄女", "外甥女", "外孙", "外孙女",
        # 核心姻亲长辈
        "岳父", "岳母", "亲家", "亲家公", "亲家母",
        # 继嗣 / 收养
        "继子", "继女", "养子", "养女", "义父", "义母",
        # 高祖辈
        "曾祖父", "曾祖母", "外祖父", "外祖母",
        # 妻子的姐妹（成年向剧本高频设定）
        "小姨子", "大姨子",
    ]
    missing = [k for k in must if k not in director._KINSHIP_TOKENS]
    assert not missing, "词表缺失常见亲属词：%s" % missing


def test_kinship_excludes_social_relations():
    """社会关系词一律不得进冻结表（守护沙盘的「关系演化」核心能力）。

    本引擎的主功能就是关系演化——同事→恋人、下属上位、房东变盟友都是要演的东西。
    一旦把「同事」写进表，_preserve_kinship 会把模型写对的「恋人」拉回「同事」，
    等于从机制上关掉引擎的主要功能（守护用例见
    test_preserve_kinship_no_baseline_free）。
    职业/称谓类词另有一重风险：在中文里大量作状语与口语称呼（「领导在场」）。
    """
    forbidden = [
        "同事", "邻居", "房东", "租客", "队友", "同学", "朋友", "熟人",
        "医生", "老师", "领导", "上司", "下属", "老板", "员工", "客户",
        "恋人", "情人", "暧昧", "追求者",
        # 作量词/口语称呼，极易误判
        "大哥", "小弟", "大爷", "大妈", "师傅", "姑娘", "小姐", "先生",
    ]
    bad = [t for t in forbidden if t in director._KINSHIP_TOKENS]
    assert not bad, "社会关系/关系状态词混入冻结表：%s" % bad


def test_seed_kinship_from_cards_explicit():
    """作者用 relations_kinship 显式声明的血缘身份应被提取。"""
    cards = {
        "角色甲": {"relations": {"角色乙": "唯一的念想"},
                "relations_kinship": {"角色乙": "母亲"}},
        "角色乙": {"relations": {"角色甲": "唯一的对手"},
                "relations_kinship": {"角色甲": "儿子"}},
    }
    got = director.seed_kinship_from_cards(cards)
    assert got == {"角色甲 → 角色乙": "母亲", "角色乙 → 角色甲": "儿子"}, got


def test_seed_kinship_ignores_non_kinship_words():
    """非法身份词（同事/恋人等非亲属）不进血缘表——非亲属关系不该被冻结。"""
    cards = {"角色甲": {"relations": {"角色乙": "同事"},
                       "relations_kinship": {"角色乙": "同事"}}}
    assert director.seed_kinship_from_cards(cards) == {}


# ---------------------------------------------------------------------------
# 5. 关系缺口自动推断（漏网 bug 修复）
# ---------------------------------------------------------------------------

def test_fill_relation_gaps_infers_for_uncovered(monkeypatch):
    """缺口补全：在场角色在基线中完全无关系边时，应触发纪官推断并写回 relations/relations_base。

    复现该漏网 bug 的修复逻辑——旧版仅在「全部卡的 relations 合并为空」时才推断，
    导致「大部分有、个别缺」（子卡空且不被父母提及）漏网。
    """
    def fake_init(cards):
        return {
            "子 → 父": "父亲", "子 → 母": "母亲",
            "父 → 子": "儿子", "母 → 子": "儿子",
            "父 → 母": "妻子", "母 → 父": "丈夫",
        }
    monkeypatch.setattr(director, "init_relations", fake_init)
    monkeypatch.setattr(director.store, "load_card", lambda n: {"name": n, "relations": {}})

    snap = {
        "present": ["父", "母", "子"],
        # 基线只含父母互指，子完全无边的（= 原始漏网条件）
        "relations": {"父 → 母": "妻子", "母 → 父": "丈夫"},
        "relations_base": {"父 → 母": "妻子", "母 → 父": "丈夫"},
    }
    gap = director.fill_relation_gaps(snap)
    assert gap == ["子"], gap
    # 推断关系写回 relations 与冻结基线
    assert snap["relations"].get("子 → 父") == "父亲", snap["relations"]
    assert snap["relations_base"].get("子 → 母") == "母亲", snap["relations_base"]
    # 手填基线边保留
    assert snap["relations"].get("父 → 母") == "妻子"


def test_fill_relation_gaps_skips_when_complete(monkeypatch):
    """手填齐全（无缺口）时不触发任何 LLM 推断，零开销。"""
    called = {"n": 0}
    def fake_init(cards):
        called["n"] += 1
        return {"x → y": "z"}
    monkeypatch.setattr(director, "init_relations", fake_init)
    monkeypatch.setattr(director.store, "load_card", lambda n: {"name": n, "relations": {}})

    snap = {
        "present": ["角色乙", "角色甲"],
        "relations": {"角色乙 → 角色甲": "妻子", "角色甲 → 角色乙": "丈夫"},
        "relations_base": {"角色乙 → 角色甲": "妻子", "角色甲 → 角色乙": "丈夫"},
    }
    gap = director.fill_relation_gaps(snap)
    assert gap == [], gap
    assert called["n"] == 0, "齐全卡不应调用推断"
    assert snap["relations"] == {"角色乙 → 角色甲": "妻子", "角色甲 → 角色乙": "丈夫"}


# ---------------------------------------------------------------------------
# 4. 纪官不得改写关系定性（2026-11-08 引擎瘦身）
# ---------------------------------------------------------------------------

def test_reflect_does_not_rewrite_relations(monkeypatch):
    """纪官即便返回 relations，快照里的关系也必须是作者口径。

    旧链路：纪官每轮写「关系定性（≤30 字）」覆盖 snap["relations"]，引擎再造两道
    冻结闸去拦它的越权改写。审计 P3 实测：作者写的「她知道台阶是他递的」这类细部
    从 R2 起再也进不了提示词，只剩标签。现在关系只由作者（角色卡）决定。
    """
    author = "母亲，独占欲；她知道台阶是他递的"
    snap = {
        "scene": {"round": 4, "place": "堂屋", "time": "", "weather": ""},
        "present": ["角色甲", "角色乙"],
        "relations": {"角色甲 → 角色乙": author},
        "relations_base": {"角色甲 → 角色乙": author},
        "secrets": [], "states": {}, "locations": {}, "ledger": [],
    }
    payload = {"relations": {"角色甲 → 角色乙": "妻子，关系破裂"}}
    monkeypatch.setattr(director.llm, "complete",
                        lambda *a, **k: json.dumps(payload, ensure_ascii=False))
    monkeypatch.setattr(director.memory, "load", lambda sid: snap)
    monkeypatch.setattr(director.memory, "save", lambda sid, s: None)
    out = director.reflect("sid", "角色甲把茶杯放下，没接话。")
    assert out["relations"]["角色甲 → 角色乙"] == author, out["relations"]


