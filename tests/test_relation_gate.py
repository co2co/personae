"""关系表来源测试。

覆盖：
  1. 角色卡 relations 字段可确定性地构建权威关系基线（seed_relations_from_cards），
     并由 memory.new 播种进 snap["relations"]。
  2. 纪官不得改写关系定性（2026-11-08 引擎瘦身）：关系是作者的设定，
     旧的「未在场冻结 / 亲属身份冻结」两道闸随之撤除——源头不再让模型写关系，
     闸就没有存在的必要（审计 P3：作者手写的关系细部此前只活一轮）。
  3. 关系缺口补全只补缺：卡片手填的关系优先，LLM 不得覆盖。

亲属身份冻结层（relations_kinship / kinship_base / _KINSHIP_TOKENS）已于
2026-11-09 整体删除——关系回写撤除后它只剩落盘、没有消费方，词表与用例一并清理。
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
# 0. 关系基线必须由 memory.new 播种
# ---------------------------------------------------------------------------

def test_memory_new_seeds_relations(monkeypatch):
    """真实会话（卡片自带 relations）必须把关系播种进 snap["relations"]。

    回归护城河：v0.7.7 的修复点——memory.new 只播种 relations 而漏播种的旧缺陷会让
    真实会话的关系网恒空，作者手写的关系一个字都进不了提示词。

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
        assert rel, "relations 不应为空"
        # 关系按作者口径原样落地（不从描述句里推断身份词）
        assert rel.get("角色甲 → 角色乙", "") == "妻子"
        # 已退役的冻结基线不得回来（2026-11-09 清理）
        assert "relations_base" not in snap and "kinship_base" not in snap
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


# ---------------------------------------------------------------------------
# 5. 关系缺口自动推断（漏网 bug 修复）
# ---------------------------------------------------------------------------

def test_fill_relation_gaps_infers_for_uncovered(monkeypatch):
    """缺口补全：在场角色在关系网里完全无关系边时，应触发纪官推断并写回 snap["relations"]。

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
    }
    gap = director.fill_relation_gaps(snap)
    assert gap == ["子"], gap
    # 推断关系写回 relations
    assert snap["relations"].get("子 → 父") == "父亲", snap["relations"]
    assert snap["relations"].get("子 → 母") == "母亲", snap["relations"]
    assert "relations_base" not in snap, "已退役的冻结基线不得回来"
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
    }
    gap = director.fill_relation_gaps(snap)
    assert gap == [], gap
    assert called["n"] == 0, "齐全卡不应调用推断"
    assert snap["relations"] == {"角色乙 → 角色甲": "妻子", "角色甲 → 角色乙": "丈夫"}


# ---------------------------------------------------------------------------
# 5b. 缺口推断的额度口径（回归：NameError 曾让 LLM 补全从未生效）
# ---------------------------------------------------------------------------

def test_init_relations_actually_calls_llm(monkeypatch):
    """init_relations 必须真的调用模型补全，而不是在 except 里静默退回手填基线。

    回归缺陷：额度按人数放宽那行写成 len(present)，而本函数没有 present 这个局部名，
    NameError 被外层 except Exception 吞掉，缺口推断因此永远只返回卡片手填的部分，
    模型一次都没被叫到——fill_relation_gaps 的用例都 mock 掉了 init_relations，
    所以这条失效在测试里完全看不见。
    """
    calls = {"n": 0}

    def fake_complete(prompt, **kw):
        calls["n"] += 1
        assert kw.get("max_tokens", 0) >= 700, "输出额度应随人数放宽，避免截断丢整块"
        return '{"relations": {"\\u89d2\\u8272\\u7532 \\u2192 \\u89d2\\u8272\\u4e59": "\\u90bb\\u5c45"}}'

    monkeypatch.setattr(director.llm, "complete", fake_complete)
    cards = {"角色甲": {"relations": {}}, "角色乙": {"relations": {}}}
    got = director.init_relations(cards)
    assert calls["n"] == 1, "init_relations 没有调用模型：NameError 之类的异常被静默吞掉了"
    assert got.get("角色甲 → 角色乙") == "邻居", got


def test_init_relations_card_relations_win_over_llm(monkeypatch):
    """模型只补缺：卡片手填的关系不得被模型输出覆盖。"""
    def fake_complete(prompt, **kw):
        return '{"relations": {"\\u89d2\\u8272\\u7532 \\u2192 \\u89d2\\u8272\\u4e59": "\\u964c\\u751f\\u4eba"}}'

    monkeypatch.setattr(director.llm, "complete", fake_complete)
    cards = {"角色甲": {"relations": {"角色乙": "十年邻居"}}, "角色乙": {"relations": {}}}
    got = director.init_relations(cards)
    assert got.get("角色甲 → 角色乙") == "十年邻居", got


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
        "secrets": [], "states": {}, "locations": {}, "ledger": [],
    }
    payload = {"relations": {"角色甲 → 角色乙": "妻子，关系破裂"}}
    monkeypatch.setattr(director.llm, "complete",
                        lambda *a, **k: json.dumps(payload, ensure_ascii=False))
    monkeypatch.setattr(director.memory, "load", lambda sid: snap)
    monkeypatch.setattr(director.memory, "save", lambda sid, s: None)
    out = director.reflect("sid", "角色甲把茶杯放下，没接话。")
    assert out["relations"]["角色甲 → 角色乙"] == author, out["relations"]



