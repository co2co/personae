"""结局判定（软指引）测试：确定性逻辑 + Flask /api/end、/api/ending/dismiss 端点。

不调真实 LLM：/api/end 用 monkeypatch 替换 llm.complete 验证总结提示词组装与存档；
逻辑分支用最小快照 dict 直接验证 evaluate 与抑制行为。
"""

import store
import pytest
import ending
import llm
import memory
import app as app_module

client = app_module.app.test_client()


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


def test_evaluate_all_left():
    snap = {"present": [], "secrets": [{"state": "潜伏"}], "scene": {"round": 5}}
    c = ending.evaluate(snap)
    assert c and "all_left" in c["reasons"]
    assert c["severity"] == "high"


def test_evaluate_secrets_resolved():
    snap = {"present": ["A", "B"], "secrets": [{"state": "暴露"}, {"state": "全曝光"}],
            "scene": {"round": 3}}
    c = ending.evaluate(snap)
    assert c and "secrets_resolved" in c["reasons"]
    assert "all_left" not in c["reasons"]


def test_evaluate_none():
    snap = {"present": ["A"], "secrets": [{"state": "潜伏"}], "scene": {"round": 1}}
    assert ending.evaluate(snap) is None


def test_evaluate_dismissed_suppressed():
    snap = {"present": [], "secrets": [{"state": "潜伏"}], "scene": {"round": 5},
            "ending_dismissed_reasons": ["all_left"]}
    assert ending.evaluate(snap, snap["ending_dismissed_reasons"]) is None


def test_evaluate_new_reason_after_dismiss():
    snap = {"present": [], "secrets": [{"state": "暴露"}], "scene": {"round": 5},
            "ending_dismissed_reasons": ["all_left"]}
    c = ending.evaluate(snap, snap["ending_dismissed_reasons"])
    assert c and "all_left" in c["reasons"]
    assert "secrets_resolved" in c["new_reasons"]


def test_mark_dismissed():
    snap = {}
    ending.mark_dismissed(snap, ["all_left", "secrets_resolved"])
    assert snap["ending_dismissed_reasons"] == ["all_left", "secrets_resolved"]


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
    snap["ending_last_reasons"] = ["all_left"]
    memory.save(session, snap)

    r = client.post("/api/ending/dismiss", json={"session": session})
    assert r.status_code == 200 and r.get_json().get("ok") is True

    snap2 = memory.load(session)
    assert snap2["ending_dismissed_reasons"] == ["all_left"]
    # 抑制验证：dismiss 后 evaluate 不再弹出该条件
    snap2["present"] = []
    assert ending.evaluate(snap2, snap2.get("ending_dismissed_reasons")) is None
