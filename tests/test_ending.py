"""结局判定（软指引）测试：确定性逻辑 + Flask /api/end、/api/ending/dismiss 端点。

不调真实 LLM：/api/end 用 monkeypatch 替换 llm.complete 验证总结提示词组装与存档；
逻辑分支用最小快照 dict 直接验证 evaluate 与抑制行为。

普适性红线：cast 由 tests/fixtures.py 的中性占位提供，不读磁盘 data/characters，
换剧本（磁盘上是完全不同的卡组）时本文件依然可跑。
"""

import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

import store
import pytest
import ending
import llm
import memory
import app as app_module
from fixtures import NAMES, make_card, fake_list_characters

# 中性占位卡组：不依赖磁盘剧本
_CARDS = {n: make_card(n) for n in NAMES}

client = app_module.app.test_client()


@pytest.fixture(autouse=True)
def _neutral_cast(monkeypatch):
    """把 store 的角色来源换成本文件自建的中性卡组。"""
    monkeypatch.setattr(store, "list_characters", fake_list_characters(NAMES))
    monkeypatch.setattr(store, "load_card", lambda name: _CARDS.setdefault(name, make_card(name)))


def _make_session():
    chars = store.list_characters()
    cast = chars[:2] if len(chars) >= 2 else chars
    assert cast, "测试需要先有角色卡"
    return memory.new(cast, scene_place="测试场景")


@pytest.fixture
def session():
    sid = _make_session()
    yield sid
    try:
        memory.delete_session(sid)
    except Exception:
        pass


def test_evaluate_secrets_resolved():
    snap = {"present": ["A", "B"], "secrets": [{"state": "暴露"}, {"state": "全曝光"}],
            "scene": {"round": 3}}
    c = ending.evaluate(snap)
    assert c and "secrets_resolved" in c["reasons"]
    # 2026-11-08 引擎瘦身：present 是永不收缩的名册，「全员离场」与
    # 「剧本 ending_flag」两条死分支已删，终局条件只剩秘密全曝光一条。
    assert c["reasons"] == ["secrets_resolved"]
    assert set(ending.ENDING_TRIGGERS) == {"secrets_resolved"}


def test_evaluate_present_empty_no_longer_triggers():
    """空 present 不再命中任何终局条件（旧 all_left 分支已删）。"""
    snap = {"present": [], "secrets": [{"state": "潜伏"}], "scene": {"round": 5}}
    assert ending.evaluate(snap) is None


def test_evaluate_none():
    snap = {"present": ["A"], "secrets": [{"state": "潜伏"}], "scene": {"round": 1}}
    assert ending.evaluate(snap) is None


def test_evaluate_dismissed_suppressed():
    snap = {"present": ["A"], "secrets": [{"state": "暴露"}], "scene": {"round": 5},
            "ending_dismissed_reasons": ["secrets_resolved"]}
    assert ending.evaluate(snap, snap["ending_dismissed_reasons"]) is None


def test_evaluate_new_reason_after_dismiss():
    snap = {"present": ["A"], "secrets": [{"state": "暴露"}], "scene": {"round": 5},
            "ending_dismissed_reasons": ["别的条件"]}
    c = ending.evaluate(snap, snap["ending_dismissed_reasons"])
    assert c and c["reasons"] == ["secrets_resolved"]
    assert c["new_reasons"] == ["secrets_resolved"]


def test_mark_dismissed():
    snap = {}
    ending.mark_dismissed(snap, ["secrets_resolved"])
    assert snap["ending_dismissed_reasons"] == ["secrets_resolved"]


def test_end_endpoint_generates_summary(session, monkeypatch):
    captured = {}

    def fake_complete(messages, **kw):
        captured["messages"] = messages
        return "【综合收束】本剧本以所有人离开收束……"

    monkeypatch.setattr(llm, "complete", fake_complete)
    memory.append_chat(session, {"role": "user", "content": "【导演指令】散场"})
    memory.append_chat(session, {"role": "assistant", "content": "众人离去。"})

    r = client.post("/api/end", json={"session": session})
    assert r.status_code == 200
    data = r.get_json()
    assert "summary" in data and data["summary"]
    assert data["exported"] is True
    assert (memory.SESS_DIR / session / "summary.md").exists()

    # 总结提示词应包含世界最终状态与完整对话
    blob = "\n".join(m["content"] for m in captured["messages"])
    assert "世界最终状态" in blob and "完整对话" in blob


def test_ending_dismiss_endpoint(session, monkeypatch):
    def fake_complete(messages, **kw):
        return "x"

    monkeypatch.setattr(llm, "complete", fake_complete)
    snap = memory.load(session)
    snap["ending_last_reasons"] = ["secrets_resolved"]
    memory.save(session, snap)

    r = client.post("/api/ending/dismiss", json={"session": session})
    assert r.status_code == 200 and r.get_json().get("ok") is True

    snap2 = memory.load(session)
    assert snap2["ending_dismissed_reasons"] == ["secrets_resolved"]
    # 抑制验证：dismiss 后 evaluate 不再弹出该条件
    snap2["secrets"] = [{"state": "暴露"}]
    assert ending.evaluate(snap2, snap2.get("ending_dismissed_reasons")) is None
