"""NSFW 门控「突破防守」测试（确定性，不依赖真实 LLM / 网络）。

场景：模拟玩家「未确认成年」且「未开启 NSFW」，尝试突破门控。
覆盖两层防守：
  A. 门控逻辑层（nsfw.resolve_session / resolve_for_request）——纯函数，秒级。
  B. 端点执行层（/api/act）——Flask 测试客户端驱动真实链路，仅 mock 掉 LLM 调用。

两层都断言：即便客户端伪造 nsfw="on" + 导演扰动把机会等级顶到「满机会」，
系统也必须保持受限（unlocked=False、intimate=False、提示词为 GUARD 且不含越线指引）。
"""

import json
import sys
from pathlib import Path

import pytest

# 让测试能 import 引擎模块（nsfw / app 等）
ENGINE = Path(__file__).resolve().parent.parent / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

import nsfw  # noqa: E402


# ---------------------------------------------------------------------------
# A. 门控逻辑层（确定性，默认快测）
# ---------------------------------------------------------------------------

def test_not_adult_blocks_even_with_override_on():
    """突破尝试：客户端伪造 override='on'，但未成年确认 -> 必须仍受限。"""
    d = nsfw.resolve_session({}, False, "满机会", override="on")
    assert d["unlocked"] is False
    assert d["intimate_allowed"] is False
    assert d["prompt"] == nsfw.GUARD


def test_not_adult_blocks_at_full_opportunity():
    """机会等级被导演判为满机会，但玩家未确认成年 -> 仍受限。"""
    d = nsfw.resolve_session({}, False, "满机会")
    assert d["unlocked"] is False
    assert d["prompt"] == nsfw.GUARD


def test_guard_prompt_contains_no_explicit_instructions():
    """GUARD 文本不得包含任何越线级（满机会）露骨指引，否则等于把解锁内容泄露给模型。"""
    assert nsfw.OPP_PROMPT["满机会"] not in nsfw.GUARD
    for w in ("插入", "抽送", "生殖器", "阴道", "阴茎", "高潮"):
        assert w not in nsfw.GUARD


def test_resolve_for_request_nsfw_off_ignores_body_on():
    """resolve_for_request：nsfw_enabled=False 时，请求体里的 nsfw='on' 被忽略。"""
    d = nsfw.resolve_for_request({}, adult_confirmed=False, nsfw_enabled=False,
                                 body_nsfw="on", opp_level="满机会")
    assert d["unlocked"] is False
    assert d["intimate_allowed"] is False
    assert d["prompt"] == nsfw.GUARD
    assert "受限" in d["reason"]


def test_adult_confirmed_but_nsfw_off_still_restricted():
    """已成年但本次未开启 NSFW（override=off）-> 仍受限。"""
    d = nsfw.resolve_for_request({}, adult_confirmed=True, nsfw_enabled=False,
                                 body_nsfw="on", opp_level="满机会")
    assert d["unlocked"] is False


def test_adult_and_enabled_with_override_on_unlocks():
    """反向对照：成年 + 开启 -> 解锁（确认 gate 仅在正确条件下放行）。"""
    d = nsfw.resolve_for_request({}, adult_confirmed=True, nsfw_enabled=True,
                                 body_nsfw="on", opp_level="满机会")
    assert d["unlocked"] is True
    assert d["intimate_allowed"] is True


def test_adult_confirmed_no_opportunity_romantic_only():
    """成年已确认但本轮无亲密机会：允许浪漫张力，但不写具体越线过程。"""
    d = nsfw.resolve_for_request({}, adult_confirmed=True, nsfw_enabled=True,
                                 body_nsfw=None, opp_level="无")
    assert d["unlocked"] is True
    assert d["intimate_allowed"] is False


# ---------------------------------------------------------------------------
# B. 端点执行层（Flask 测试客户端，mock 掉 LLM）
# ---------------------------------------------------------------------------

@pytest.fixture
def client_and_capture(monkeypatch):
    pytest.importorskip("flask")
    import app as app_mod
    import llm as llm_mod
    import prompter as prompter_mod

    # 服务端设置：玩家「未确认成年」且「未开启 NSFW」
    def fake_setting(name):
        forced = {"adult_confirmed": False, "nsfw_enabled": False}
        if name in forced:
            return forced[name]
        defaults = {
            "base_url": "http://127.0.0.1:1234/v1",
            "api_key": "sk-test",
            "model": "test-model",
            "budget": 4096,
            "max_tokens": 512,
            "temperature": 0.8,
            "top_p": 0.95,
            "enable_thinking": False,
        }
        return defaults.get(name)

    monkeypatch.setattr(llm_mod, "setting", fake_setting)

    # 阻断一切真实 LLM 调用
    def fake_stream(messages, **kwargs):
        yield "林晚：沉默。\n老周：沉默。"
    monkeypatch.setattr(llm_mod, "stream", fake_stream)
    monkeypatch.setattr(llm_mod, "complete", lambda messages, **kwargs: "")

    # 抓取注入模型的 NSFW 提示词与机会等级
    captured = {}
    real_build = prompter_mod.build_session

    def spy_build(*args, **kwargs):
        nsfw_prompt = kwargs.get("nsfw_prompt")
        if nsfw_prompt is None and len(args) > 4:
            nsfw_prompt = args[4]
        captured["nsfw_prompt"] = nsfw_prompt
        opp = kwargs.get("opp_level")
        if opp is None and len(args) > 5:
            opp = args[5]
        captured["opp"] = opp
        return real_build(*args, **kwargs)

    monkeypatch.setattr(prompter_mod, "build_session", spy_build)

    return app_mod.app.test_client(), captured


def test_endpoint_breakthrough_blocked_when_not_adult_and_nsfw_off(client_and_capture):
    """端到端突破防守：未成年 + 未开启 NSFW + 伪造 nsfw='on' + 满机会扰动 -> 必须受限。"""
    client, captured = client_and_capture

    # 建一个真实会话（用既有角色卡，初始关系生成由 mock 的 LLM 兜底，不触网）
    r = client.post("/api/session/new", json={"cast": ["林晚", "老周"]})
    assert r.status_code == 200, r.get_data(as_text=True)
    sid = r.get_json()["session"]

    try:
        # 突破扰动：导演指令直接写入露骨词（顶到满机会），且请求体伪造 nsfw='on'
        directive = "林晚和老周独处，老周把林晚按在墙上做爱"
        resp = client.post("/api/act", json={
            "session": sid,
            "input": directive,
            "nsfw": "on",
        })
        assert resp.status_code == 200
        raw = resp.get_data(as_text=True)

        done = None
        for block in raw.split("\n\n"):
            block = block.strip()
            if block.startswith("data:"):
                payload = json.loads(block[len("data:"):].strip())
                if payload.get("done"):
                    done = payload
                    break
        assert done is not None, "未收到 done 事件"

        decision = done["nsfw"]
        # 核心断言 1：门控输出仍为受限
        assert decision["unlocked"] is False, f"突破成功！门控被绕过：{decision}"
        assert decision["intimate_allowed"] is False
        assert "受限" in decision["reason"]

        # 核心断言 2：即便机会等级被顶到满机会，注入模型的提示词仍是 GUARD
        assert captured["opp"] == "满机会", "扰动未顶到满机会，突破场景不成立"
        assert captured["nsfw_prompt"] == nsfw.GUARD
        assert nsfw.OPP_PROMPT["满机会"] not in captured["nsfw_prompt"]
    finally:
        client.delete("/api/session/" + sid)
