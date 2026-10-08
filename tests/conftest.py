import sys
from pathlib import Path

# 让 tests/ 下的测试能直接 import 引擎模块（world / director 等）。
# 引擎本体位于项目根的 engine/ 目录，加入 sys.path 即可。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))

import pytest  # noqa: E402

import memory  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_session_dir(tmp_path, monkeypatch):
    """把会话存储目录重定向到每个测试独立的临时目录，测试永不触碰真实 data/sessions。

    背景（v0.22.1 事故）：此前测试直接调 memory.new 或走 /api/session/new 路由，
    SESS_DIR 始终指向真实 engine/data/sessions/——测试既往真实目录写会话，
    路由层新增的「会话保留策略（prune_sessions）」又会在测试运行中对真实目录
    执行删除，误删了 124 个真实历史会话（sessions 被 gitignore，无法恢复）。

    本 fixture 把 memory.SESS_DIR 指到 tmp_path 下的独立目录：memory.new、
    prune_sessions、以及走 /api/session/new 路由的测试全部在隔离目录内自洽，
    真实 data/sessions 不再受任何测试影响。依赖 memory.SESS_DIR 做断言的测试
    （test_ending / test_relation_gate）引用的是同一全局，重定向后仍一致。
    """
    isolated = tmp_path / "sessions"
    isolated.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(memory, "SESS_DIR", isolated)
    yield
