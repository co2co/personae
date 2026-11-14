# -*- coding: utf-8 -*-
"""生成回路（/api/act 的 SSE 流）回归测试。

**为什么单独有这个文件**：2026-11-11 nsfw 支线做提示词改造时，在 events() 内写了一句
`messages = _assemble(...)` 做重试再装配。这一句赋值让 `messages` 变成 `events()` 的
局部变量，遮蔽了外层 generate() 的同名变量；_generate_once 通过闭包读它时读到的是
未绑定的格子，首轮生成直接抛 `NameError: cannot access free variable 'messages'`，
整条生成回路不可用。当时的探针只调 prompter.build_session + llm.complete，完全绕过
app.py，所以没测到。

master 目前没有那句赋值（events() 只读 messages，不写），所以这个坑在 master 上是
潜伏的而不是已爆的。本文件把两件事钉住：从 HTTP 层打这条回路（探针盲区补上），以及
把「_generate_once 必须显式收提示词、events() 不得再给 messages 赋值」写成静态护栏，
让这类改动再也进不来。

不调真实 LLM：llm.stream 全部 monkeypatch。
普适性红线：cast 来自 tests/fixtures.py 的中性占位，不读磁盘剧本。
"""
import ast
import json
import re
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

import app as app_module      # noqa: E402
import director               # noqa: E402
import llm                    # noqa: E402
import memory                 # noqa: E402
import store                  # noqa: E402
import pytest                 # noqa: E402

from fixtures import NAMES, make_card, fake_list_characters  # noqa: E402

_CARDS = {n: make_card(n) for n in NAMES}

client = app_module.app.test_client()

_GOOD = "夜色沉下去，角色甲把门推开一条缝，屋里的人已经睡着了。"
_DIRECTIVE = "注入一处扰动"


@pytest.fixture(autouse=True)
def _neutral(monkeypatch):
    """中性卡组 + 记账环节短路：本文件只验生成回路，不验纪官。"""
    monkeypatch.setattr(store, "list_characters", fake_list_characters(NAMES))
    monkeypatch.setattr(store, "load_card",
                        lambda name: _CARDS.setdefault(name, make_card(name)))
    monkeypatch.setattr(director, "reflect", lambda *a, **k: {})


@pytest.fixture
def sid():
    cast = store.list_characters()[:2]
    new_id = memory.new(cast, scene_place="测试场景")
    yield new_id
    try:
        memory.delete_session(new_id)
    except Exception:
        pass


def _stub_stream(monkeypatch, outputs):
    """把 llm.stream 换成桩：每次调用吃 outputs 里的一段，并记下收到的 messages。"""
    calls = []

    def fake_stream(msgs, **_kw):
        calls.append(msgs)
        for piece in outputs[len(calls) - 1]:
            yield piece

    monkeypatch.setattr(llm, "stream", fake_stream)
    return calls


def _act(sid, directive=_DIRECTIVE):
    # master 侧 /api/act 读的字段是 body["input"]（app.py:624），不是 "directive"。
    resp = client.post("/api/act", json={"session": sid, "input": directive})
    assert resp.status_code == 200, "路由本身应 200（生成失败也在流里报错，不是 HTTP 层）"
    events = []
    for block in resp.get_data(as_text=True).split("\n\n"):
        for line in block.splitlines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    return events


def _blob(msgs):
    return "\n".join((m.get("content") or "") for m in msgs)


def test_first_attempt_receives_assembled_prompt(sid, monkeypatch):
    """核心回归：首轮生成必须拿到装配好的提示词，而不是在闭包里断掉。

    旧缺陷形态下这里会直接断流并吐 error，calls 为空。断言只取跨版本稳定的锚点
    （提示词非空、含 system 段、本轮指令真的在里面），不锁具体块名——块名是各分支
    提示词策略的事，回路通不通不是。
    """
    calls = _stub_stream(monkeypatch, [[_GOOD]])
    events = _act(sid)

    errs = [e["error"] for e in events if "error" in e]
    assert not errs, "生成回路报错：" + " ｜ ".join(errs)
    assert calls, "llm.stream 根本没被调用——生成回路在装配阶段就断了"
    assert any(m.get("role") == "system" for m in calls[0]), "提示词必须含 system 段"
    assert _DIRECTIVE in _blob(calls[0]), "本轮导演指令没进提示词"
    done = [e for e in events if e.get("done")]
    assert done and done[0]["reply"] == _GOOD


def test_events_does_not_rebind_messages():
    """静态护栏：events() 内不得给外层 messages 赋值——赋值即遮蔽，遮蔽即整轮不可用。"""
    tree = ast.parse((ENGINE / "app.py").read_text(encoding="utf-8"))

    def _walk(node, outer_names):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef):
                if child.name == "events":
                    bound = {t.id for n in ast.walk(child)
                             if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)
                             for t in [n] if isinstance(n.id, str)}
                    assert "messages" not in bound, (
                        "events() 内出现对 messages 的赋值：这会让它成为 events() 的局部变量，"
                        "遮蔽 generate() 的同名变量，_generate_once 闭包读取时直接 NameError。"
                        "要换提示词请用别的变量名并显式传参。")
                    return True
                if _walk(child, outer_names):
                    return True
        return False

    assert _walk(tree, set()), "app.py 里找不到 events()，本护栏的口径需要跟着改"


def test_generate_once_requires_explicit_messages():
    """静态护栏：_generate_once 必须显式收提示词参数，不靠闭包。"""
    src = (ENGINE / "app.py").read_text(encoding="utf-8")
    m = re.search(r"def _generate_once\(([^)]*)\)", src)
    assert m, "找不到 _generate_once"
    params = [p.strip() for p in m.group(1).split(",")]
    assert len(params) >= 3, "_generate_once 应显式接收提示词列表，实际参数 %s" % params
    assert "llm.stream(messages" not in src, "llm.stream 不得再闭包读 messages"


# ================= 拒答 / 空正文回路（移植 nsfw 线 c4537c4）=================
# 整条拒答一旦落进正式历史，就作为 assistant 轮常驻上下文，变成后续轮次的拒答范例；
# 实测一次拒绝往往演变成连锁拒绝。所以「生成 → 净身 → 有没有正文 → 重试」必须连成一体的
# 回路，且重试要带上上一版被拦下的原因（同一请求原样重打等于没重试）。

_REFUSAL_ZH = "很抱歉，我无法执行该请求。"
_REFUSAL_EN = ("I cannot fulfill this request. I am an AI assistant designed to be "
               "helpful and harmless while strictly adhering to safety guidelines.")
_META_ONLY = "**警告：根据系统安全准则，我不能生成该内容。**"


def _assistant_texts(sid):
    return [m.get("content", "") for m in memory.load_chat(sid) if m.get("role") == "assistant"]


def test_chinese_refusal_is_retried_and_never_persisted(sid, monkeypatch):
    """中文整条拒答：不落盘、自动重试一次，第二轮正文照常交付。"""
    calls = _stub_stream(monkeypatch, [[_REFUSAL_ZH], [_GOOD]])
    events = _act(sid)

    assert len(calls) == 2, "首轮是拒答，应当重试一次"
    assert not [e for e in events if "error" in e]
    done = [e for e in events if e.get("done")]
    assert done and done[0]["reply"] == _GOOD
    texts = _assistant_texts(sid)
    assert texts == [_GOOD], "拒答句不得进历史：" + repr(texts)
    assert any(e.get("status", "").startswith("模型本轮未交付正文") for e in events), \
        "重试要在前端给一条状态提示，否则用户只看到一段拒绝后又换成正文"


def test_english_refusal_is_retried(sid, monkeypatch):
    """英文整条拒答同样要拦：只配中文正则会把它整条放行落盘。"""
    calls = _stub_stream(monkeypatch, [[_REFUSAL_EN], [_GOOD]])
    events = _act(sid)
    assert len(calls) == 2
    assert _assistant_texts(sid) == [_GOOD]


def test_body_stripped_to_empty_is_retried(sid, monkeypatch):
    """只剩元标题、被净身剥成空串同样要重试——放行会在历史里留一条空 assistant 轮。"""
    calls = _stub_stream(monkeypatch, [[_META_ONLY], [_GOOD]])
    _act(sid)
    assert len(calls) == 2
    assert _assistant_texts(sid) == [_GOOD]


def test_retry_prompt_carries_previous_reason(sid, monkeypatch):
    """重试必须给模型新信息：提示词里带上上一版未通过的原因与那句拒绝的开头。"""
    calls = _stub_stream(monkeypatch, [[_REFUSAL_ZH], [_GOOD]])
    _act(sid)
    first, second = _blob(calls[0]), _blob(calls[1])
    assert "上次未通过的原因" not in first
    assert "上次未通过的原因" in second
    assert _REFUSAL_ZH in second, "要把模型自己写的那句话回喂，比只说「重试一次」有效"
    assert _DIRECTIVE in second, "重试只换提示词，本轮导演指令不得丢"


@pytest.mark.parametrize("refusal, want_reason", [
    # 单句中文拒答先被净身的行规则剥空 → 走「净身后为空」；
    # 英文拒答不在行规则里、整句留下 → 走 is_refusal 的「整条拒绝应答」。
    # 两条都拦下重试，但日志与回喂文案不同，故分开锁。
    (_META_ONLY, "经净身后为空"),
    (_REFUSAL_EN, "模型整条拒绝应答"),
])
def test_both_empty_body_reasons_are_reported(sid, monkeypatch, refusal, want_reason):
    """两条 reason 都要走通，且归类正确、正文不落盘。"""
    calls = _stub_stream(monkeypatch, [[refusal], [_GOOD]])
    _act(sid)
    assert len(calls) == 2
    assert want_reason in _blob(calls[1]), "%r 未进重试提示词" % want_reason
    assert _assistant_texts(sid) == [_GOOD]


def test_persistent_refusal_reports_error_and_writes_nothing(sid, monkeypatch):
    """连拒 REFUSAL_RETRY+1 次：报错误事件、不落盘、不写正文。"""
    calls = _stub_stream(monkeypatch, [[_REFUSAL_ZH]] * (app_module.REFUSAL_RETRY + 1))
    events = _act(sid)

    assert len(calls) == app_module.REFUSAL_RETRY + 1
    errs = [e["error"] for e in events if "error" in e]
    assert len(errs) == 1 and "已重试" in errs[0], errs
    assert not [e for e in events if e.get("done")]
    assert _assistant_texts(sid) == [], "本回合不得写入任何正文"


def test_repeat_detection_sees_cleaned_body(sid, monkeypatch):
    """复读检测的输入必须是净身后、即将落盘的正文（与历史同源），不是原始输出。"""
    seen = []

    def _capture(text, _hist):
        seen.append(text)
        return False, 0.0, ""

    monkeypatch.setattr(director, "detect_narrative_repeat", _capture)
    _stub_stream(monkeypatch, [[_META_ONLY], [_GOOD]])
    _act(sid)
    assert seen == [_GOOD], "检测输入应为最终正文，实际收到 %r" % (seen,)


# ============ 思考块兜底闸（llm 层拦截，app 层接住「空正文」）============
# 闸收在 llm.stream 取 delta.content 那一层（见 tests/test_llm_think_gate.py）。本段从
# HTTP 层验端到端：脏文不得流到前端，也不得落进 chat.jsonl 当下一轮的 assistant 示范。
# 这里走**真** llm.stream，只把 requests.post 换成按轮次吐文本的桩。

_THINK_ONLY = "<think>\n\n先想想这一幕怎么接，用户要的是一处扰动。\n</think>\n\n"
_THINK_PREFIXED = "<think>\n\n</think>\n\n" + _GOOD


class _SSEResp:
    """按片吐 SSE 的响应桩，字段齐全以走通 _stream_once 的降级判断。"""

    def __init__(self, pieces):
        self.status_code = 200
        self.encoding = "utf-8"
        self._pieces = pieces

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def close(self):
        pass

    def raise_for_status(self):
        pass

    def iter_lines(self, decode_unicode=True):
        for c in self._pieces:
            yield "data: " + json.dumps({"choices": [{"delta": {"content": c}}]})
        yield "data: [DONE]"


def _real_stream(monkeypatch, *rounds):
    """装一条真 llm.stream：第 n 次请求吐 rounds[n] 的文本（超出则重复最后一轮）。"""
    calls = []

    def fake_post(url, json=None, headers=None, stream=False, timeout=None):
        calls.append(json)
        idx = min(len(calls) - 1, len(rounds) - 1)
        return _SSEResp(list(rounds[idx]))

    monkeypatch.setattr(llm.requests, "post", fake_post)
    monkeypatch.setattr(llm, "_file_config",
                        lambda: {"base_url": "http://127.0.0.1:1/v1", "api_key": "",
                                 "model": "stub", "enable_thinking": False})
    return calls


def test_think_only_round_is_retried_and_never_persisted(sid, monkeypatch):
    """整轮只有思考块 → 正文 0 字 → 必须走空正文重试，而不是静默收场。

    这条同时守住一个易错点：闸把整轮吞掉时正文是空串，若与「流断了」共用同一个
    空串判据，生成回路会直接 return，用户看到的是一条什么也没有的回复。
    """
    calls = _real_stream(monkeypatch, [_THINK_ONLY], [_GOOD])
    events = _act(sid)

    assert len(calls) == 2, "整轮被闸吞掉应触发重试"
    deltas = [e["delta"] for e in events if e.get("delta")]
    assert all("think" not in d.lower() for d in deltas), "思考块不得流到前端：" + repr(deltas)
    assert not [e for e in events if "error" in e]
    done = [e for e in events if e.get("done")]
    assert done and done[0]["reply"] == _GOOD
    assert _assistant_texts(sid) == [_GOOD], "脏文不得进历史：" + repr(_assistant_texts(sid))


def test_template_prefix_does_not_reach_history(sid, monkeypatch):
    """模板前缀形状「<think>\\n\\n</think>\\n\\n + 正文」：只有正文该留下。"""
    _real_stream(monkeypatch, [_THINK_PREFIXED])
    events = _act(sid)

    assert _assistant_texts(sid) == [_GOOD]
    deltas = "".join(e["delta"] for e in events if e.get("delta"))
    assert "think" not in deltas.lower()
    assert deltas.strip() == _GOOD
