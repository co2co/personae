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
    h = _hist(prompter.HISTORY_WINDOW_ROUNDS - 2)  # 窗口内
    assert prompter.compress_history(h) == h


def test_compress_over_window_summarizes_older():
    h = _hist(20)
    out = prompter.compress_history(h)
    w = prompter.HISTORY_WINDOW_ROUNDS
    n_user = sum(1 for m in out if m["role"] == "user")
    n_assist = sum(1 for m in out if m["role"] == "assistant")
    n_sys = sum(1 for m in out if m["role"] == "system")
    # 最近 w 轮原始（各 2w 条）+ 1 条摘要块
    assert n_sys == 1
    assert n_user == w
    assert n_assist == w
    summary = out[0]["content"]
    assert "历史叙事摘要" in summary
    assert "R1｜" in summary
    # older（第 0 轮）完整长正文（30 次重复体）已被压缩，不再完整出现
    assert ("这是第0轮的较长叙事正文，描述小队在废墟中的行动与对话。" * 30) not in summary
    # 摘要行不得超长：单行长度须有界（否则窗口外会重新膨胀）
    longest = max(len(line) for line in summary.splitlines()[1:])
    cap = prompter.SUMMARY_DIRECTIVE_CHARS + prompter.SUMMARY_NARRATIVE_CHARS + 20
    assert longest <= cap, "摘要行 %d 字，超出上限 %d" % (longest, cap)


def test_summary_keeps_configured_char_budget():
    """摘要块每轮提取的字数须落在配置上限内，且真的用满了预算。

    摘要质量比窗口长度更值钱（见 prompter 常量注释），故两项都要被测试钉住。
    """
    h = _hist(30)
    out = prompter.compress_history(h)
    lines = out[0]["content"].splitlines()[1:]
    assert lines, "30 轮历史应产生摘要行"
    # 未截断的轮次：指令段与叙事段都应达到预算上限（输入本身比预算长）
    full = [ln for ln in lines if "｜叙事: " in ln]
    assert full, "摘要行格式异常"
    for ln in full:
        head_u = ln.split("｜指令: ")[1].split("｜叙事: ")[0]
        head_a = ln.split("｜叙事: ")[1]
        assert len(head_u) <= prompter.SUMMARY_DIRECTIVE_CHARS
        assert len(head_a) <= prompter.SUMMARY_NARRATIVE_CHARS
    # 至少一条用满叙事预算（证明预算常量真的生效，不是被写死成小值）
    assert max(len(ln.split("｜叙事: ")[1]) for ln in full) == prompter.SUMMARY_NARRATIVE_CHARS


def test_compress_window_keeps_recent_full():
    h = _hist(20)
    out = prompter.compress_history(h)
    # 最近一轮（第 19 轮）原始长正文应完整保留
    assert any("这是第19轮的较长叙事正文" in m["content"] for m in out)


def test_build_session_long_history_stable():
    """长历史下压缩必须有效——用「相对无压缩的压缩率」断言，不写死 tok 绝对值。

    绝对阈值会随窗口/摘要预算调参而失效（v0.16.1 从 8→12 窗口时旧断言 12000
    恰好被突破）。压缩率的语义才是真正要守的不变式：窗口外无论累积多少轮，
    进入 prompt 的都只是有界的骨架摘要。
    """
    h = _hist(60)
    msgs = prompter.build_session(
        CARDS, "角色丁拦下军车", [], MIN_SNAP,
        history=h, focus={"subjects": []})
    tok = sum(prompter.count_tokens(m.get("content", "")) for m in msgs)
    raw = sum(prompter.count_tokens(m.get("content", "")) for m in h)
    assert raw > 0
    ratio = tok / raw
    assert ratio < 0.5, "压缩率 %.0f%%（%d/%d tok）过高，长历史会重新膨胀" % (
        ratio * 100, tok, raw)


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
