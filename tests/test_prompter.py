"""prompter 单元测试：历史滑动窗口压缩 + build_session 长上下文稳定性。

运行：tests/venv/Scripts/python.exe -m pytest tests/test_prompter.py -q
"""
import sys
sys.path.insert(0, "engine")

import prompter


def _hist(rounds):
    """构造 rounds 轮假历史：每轮 = [user 指令, assistant 长叙事]。"""
    h = []
    for i in range(rounds):
        h.append({"role": "user", "content": "【导演指令】第%d轮：小队沿地点%d前进，遭遇冲突" % (i, i)})
        h.append({"role": "assistant", "content": ("这是第%d轮的较长叙事正文，描述小队在废墟中的行动与对话。" % i) * 30})
    return h


MIN_SNAP = {
    "scene": {"round": 1, "place": "城东道路", "time": "夜", "weather": ""},
    "relations": {}, "ledger": [], "secrets": [],
    "goals": {}, "present": ["角色甲", "角色丁"],
}
CARDS = {n: {"name": n} for n in ["角色甲", "角色丁"]}


def test_compress_empty():
    assert prompter.compress_history([]) == []
    assert prompter.compress_history(None) == []


def test_compress_under_window_returns_original():
    h = _hist(6)  # 6 轮 < 窗口 8
    assert prompter.compress_history(h) == h


def test_compress_over_window_summarizes_older():
    h = _hist(20)
    out = prompter.compress_history(h)
    n_user = sum(1 for m in out if m["role"] == "user")
    n_assist = sum(1 for m in out if m["role"] == "assistant")
    n_sys = sum(1 for m in out if m["role"] == "system")
    # 最近 8 轮原始（16 条）+ 1 条摘要块
    assert n_sys == 1
    assert n_user == 8
    assert n_assist == 8
    summary = out[0]["content"]
    assert "历史叙事摘要" in summary
    assert "R1｜" in summary
    # older（第 0 轮）完整长正文（30 次重复体）已被压缩，不再完整出现
    assert ("这是第0轮的较长叙事正文，描述小队在废墟中的行动与对话。" * 30) not in summary
    # 摘要行截断到 90 字内（指令80+叙事90），单条不含超长原文
    for line in summary.splitlines()[1:]:
        assert len(line) < 200


def test_compress_window_keeps_recent_full():
    h = _hist(20)
    out = prompter.compress_history(h)
    # 最近一轮（第 19 轮）原始长正文应完整保留
    assert any("这是第19轮的较长叙事正文" in m["content"] for m in out)


def test_build_session_long_history_stable():
    """60 轮历史下，压缩后 prompt tok 应显著低于无窗口（探针无窗口≈18425）。"""
    h = _hist(60)
    msgs = prompter.build_session(
        CARDS, "角色丁拦下军车", [], MIN_SNAP,
        history=h, focus={"subjects": []})
    tok = sum(prompter.count_tokens(m.get("content", "")) for m in msgs)
    # 压缩后窗口外仅在摘要块，应远低于无窗口的线性膨胀
    assert tok < 12000, "长历史 prompt tok=%d 未有效压缩" % tok


# --- 分段格式契约（v0.16.0 压测发现：模型改用散文引号致 5 处机制静默失效）---

def test_build_session_declares_speaker_block_format():
    """build_session 必须显式声明「角色名：」分段格式。

    引擎有 5 处机制靠行首「角色名：」匹配台词块（validate_present 剥离、
    detect_offscreen_activity、已故者开口检测、_AUX_SPEAKER_RE、镜头裁剪）。
    压测实测：未声明时模型 30/30 轮改用散文引号，这 5 处全部静默失效。
    """
    sysmsg = "\n".join(m["content"] for m in prompter.build_session(
        CARDS, "继续", [], MIN_SNAP))
    assert "[分段格式]" in sysmsg
    assert "角色名" in sysmsg
    # 必须明确禁用引号替代分段——那正是压测观察到的失败模式
    assert "引号" in sysmsg


def test_speaker_block_uses_neutral_placeholders():
    """形式示例只能用中性占位，不得写入任何具体剧本角色名（引擎普适性红线）。"""
    sysmsg = "\n".join(m["content"] for m in prompter.build_session(
        CARDS, "继续", [], MIN_SNAP))
    i = sysmsg.find("[分段格式]")
    block = sysmsg[i:i + 500]
    assert "角色甲" in block or "角色乙" in block, "分段格式示例应给出行首样例"
    # 复用 test_universality 的黑名单，不在本文件重复列出（护栏自身豁免）
    from test_universality import BANNED
    for b in BANNED:
        assert b not in block, "分段格式示例混入具体剧本名/题材词：%s" % b
