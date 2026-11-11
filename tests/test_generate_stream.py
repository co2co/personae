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
