"""镜头跟随（焦点）机制测试（确定性，不依赖真实 LLM / 网络）。

修复根因：引擎此前只有单一 present 名单、缺少"镜头"概念，导致玩家把扰动引向某个
在场子集（如"老周带领高洋下去下水道"）时，模型仍默认全员出场、并偏爱更戏剧的留存组，
镜头死守初始位置、不跟随被引向的角色。

覆盖：
  1. director.compute_focus 从指令识别镜头焦点（点名子集 / 指代代词延续 / 切换 / 全体或无人则无焦点）。
  2. prompter.build_session 在焦点存在时注入"镜头跟随"指令，把焦点子集设为主视角、其余在场者标为镜头外。
  3. 端点层（/api/act）：mock LLM，断言(a)注入模型的提示词含镜头跟随块且焦点=被引向子集；
     (b)后处理按焦点裁剪，镜头外角色的台词块被剥离、焦点角色保留。
"""

import json
import sys
from pathlib import Path

import pytest

ENGINE = Path(__file__).resolve().parent.parent / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

import director  # noqa: E402
import store      # noqa: E402
import prompter  # noqa: E402


@pytest.fixture(autouse=True)
def _fake_cards(monkeypatch):
    """让 store.load_card 不依赖磁盘上的具体角色卡文件（旧剧本已删）。

    本文件用例只关心「镜头焦点」机制，卡片仅需 name 字段即可构造人设块；
    用内存通用卡片替代磁盘加载，消除「换剧本即红」的既有失败。
    """
    def fake_load_card(name):
        return {"name": name, "relations": {}, "core_desire": "",
                "core_fear": "", "short_goal": "", "personality": "",
                "description": ""}
    monkeypatch.setattr(store, "load_card", fake_load_card)
    yield


def _snap(present, place="下水道", focus=None):
    """构造最小快照（compute_focus / build_session 所需的键）。"""
    return {
        "present": present,
        "scene": {"place": place, "time": "", "round": 1, "weather": ""},
        "focus": focus,
        "goals": {},
        "secrets": [],
        "relations": {},
        "ledger": [],
        "actions": {},
    }


# ---------------------------------------------------------------------------
# 1. compute_focus 焦点识别
# ---------------------------------------------------------------------------

def test_compute_focus_named_subset():
    """指令点名一个真子集 -> 镜头跟随该子集（sticky=False）。"""
    snap = _snap(["林晚", "苏曼", "阿杰", "老周", "高洋"], "下水道")
    f = director.compute_focus("老周带领高洋下去下水道查看", snap)
    assert f is not None
    assert f["subjects"] == ["老周", "高洋"]
    assert f["place"] == "下水道"
    assert f["sticky"] is False


def test_compute_focus_sticky_follow_word():
    """指令无点名但含指代代词（2人/他们/...）且上轮有焦点 -> 延续上轮焦点（sticky=True）。"""
    snap = _snap(["林晚", "苏曼", "阿杰", "老周", "高洋"], "下水道",
                 {"subjects": ["老周", "高洋"], "place": "下水道"})
    f = director.compute_focus("2人逐渐进入下水道的深处", snap)
    assert f is not None
    assert f["subjects"] == ["老周", "高洋"]
    assert f["sticky"] is True


def test_compute_focus_switch_to_other():
    """指令点名另一子集 -> 焦点切换到该子集。"""
    snap = _snap(["林晚", "苏曼", "阿杰", "老周", "高洋"], "下水道",
                 {"subjects": ["老周", "高洋"], "place": "下水道"})
    f = director.compute_focus("林晚去查看监控", snap)
    assert f is not None
    assert f["subjects"] == ["林晚"]


def test_compute_focus_all_named_is_none():
    """指令点名全体 -> 无焦点，自然推演（全员皆可写）。"""
    snap = _snap(["老周", "高洋", "林晚"], "下水道")
    f = director.compute_focus("老周、高洋、林晚一起行动", snap)
    assert f is None


def test_compute_focus_no_name_is_none():
    """指令无人名、无指代代词 -> 无焦点。"""
    snap = _snap(["老周", "高洋", "林晚"], "下水道")
    f = director.compute_focus("夜色渐深，万籁俱寂", snap)
    assert f is None


# ---------------------------------------------------------------------------
# 2. prompter 注入镜头跟随指令
# ---------------------------------------------------------------------------

def test_prompter_injects_camera_block():
    """焦点存在时，组装的提示词必须含【镜头跟随】块，且把焦点子集设为主视角、其余标为镜头外。"""
    cards = {n: store.load_card(n) for n in ["老周", "高洋", "林晚", "苏曼", "阿杰"]}
    snap = _snap(["林晚", "苏曼", "阿杰", "老周", "高洋"], "下水道")
    focus = {"subjects": ["老周", "高洋"], "place": "下水道", "sticky": False}
    msgs = prompter.build_session(
        cards, "老周带领高洋下去下水道查看", [], snap, [], [], focus=focus)
    text = "\n".join(m["content"] for m in msgs)
    assert "【镜头跟随】" in text
    assert "老周、高洋" in text
    assert "不在本回合镜头内" in text
    # 镜头外角色（留存组）应被明确列为"在别处待命"，而非本轮焦点
    assert "林晚" in text and "苏曼" in text and "阿杰" in text


def test_prompter_no_focus_keeps_all_present():
    """无焦点时提示词应保留"本轮在场角色"全覆盖句式，不注入镜头跟随块。"""
    cards = {n: store.load_card(n) for n in ["老周", "高洋", "林晚"]}
    snap = _snap(["老周", "高洋", "林晚"], "下水道")
    msgs = prompter.build_session(
        cards, "夜色渐深", [], snap, [], [], focus=None)
    text = "\n".join(m["content"] for m in msgs)
    assert "【镜头跟随】" not in text
    assert "本轮在场角色：" in text


# ---------------------------------------------------------------------------
# 3. 端点层：mock LLM，验证焦点真正驱动提示词与后处理裁剪
# ---------------------------------------------------------------------------

@pytest.fixture
def client_focus(monkeypatch):
    pytest.importorskip("flask")
    import app as app_mod
    import llm as llm_mod
    import prompter as prompter_mod
    import store as store_mod

    # 让 /api/session/new 识别本测试的角色名（磁盘上无这些旧剧本卡），
    # 避免 cast 被过滤为空导致 400。卡片由 autouse 的 _fake_cards 提供。
    cast_names = ["林晚", "苏曼", "阿杰", "老周", "高洋"]
    monkeypatch.setattr(store_mod, "list_characters", lambda: cast_names)

    def fake_setting(name):
        defaults = {
            "base_url": "http://127.0.0.1:1234/v1", "api_key": "sk-test",
            "model": "test-model", "budget": 4096, "max_tokens": 512,
            "temperature": 0.8, "top_p": 0.95, "enable_thinking": False,
        }
        return defaults.get(name)

    monkeypatch.setattr(llm_mod, "setting", fake_setting)

    # 模型产出同时含焦点角色与镜头外角色的台词块，供裁剪断言
    def fake_stream(messages, **kwargs):
        yield ("老周：我们下到下水道了，前面黑得很。\n"
               "高洋：水都到膝盖了，我手上的伤口有点疼。\n"
               "林晚：我在上面守着口子，你们俩小心点。\n")
    monkeypatch.setattr(llm_mod, "stream", fake_stream)
    monkeypatch.setattr(llm_mod, "complete", lambda messages, **kwargs: "")

    captured = {}
    real_build = prompter_mod.build_session

    def spy_build(*args, **kwargs):
        captured["messages"] = real_build(*args, **kwargs)
        captured["focus"] = kwargs.get("focus")
        return captured["messages"]

    monkeypatch.setattr(prompter_mod, "build_session", spy_build)
    return app_mod.app.test_client(), captured


def _collect_done(resp):
    for block in resp.get_data(as_text=True).split("\n\n"):
        block = block.strip()
        if block.startswith("data:"):
            try:
                payload = json.loads(block[len("data:"):].strip())
            except Exception:
                continue
            if payload.get("done"):
                return payload
    return None


def test_endpoint_focus_follows_named_subset(client_focus):
    """端到端：指令引向老周/高洋 -> 提示词含镜头跟随块且焦点=老周/高洋；
    后处理裁剪掉镜头外角色（林晚）的台词块，焦点角色保留。"""
    client, captured = client_focus
    r = client.post("/api/session/new",
                    json={"cast": ["林晚", "苏曼", "阿杰", "老周", "高洋"],
                          "scene": "下水道（晚上）"})
    assert r.status_code == 200, r.get_data(as_text=True)
    sid = r.get_json()["session"]
    try:
        directive = "老周带领高洋下去下水道查看"
        resp = client.post("/api/act", json={"session": sid, "input": directive})
        assert resp.status_code == 200, resp.get_data(as_text=True)
        done = _collect_done(resp)
        assert done is not None, "未收到 done 事件"

        # (a) 注入模型的提示词含镜头跟随块，焦点为被引向子集
        prompt_text = "\n".join(m["content"] for m in captured["messages"])
        assert "【镜头跟随】" in prompt_text, "提示词未注入镜头跟随块"
        assert "老周、高洋" in prompt_text
        assert captured["focus"]["subjects"] == ["老周", "高洋"]

        # (b) 后处理裁剪：镜头外角色（林晚）台词块被剥离，焦点角色保留
        reply = done["reply"]
        assert "老周" in reply and "高洋" in reply
        assert "林晚" not in reply, f"镜头外角色林晚未被裁剪：\n{reply}"
    finally:
        client.delete("/api/session/" + sid)
