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


# --- 分段格式：v0.17.0 已移除该契约（simon 定：损害叙事观感）---

def test_focus_out_of_shot_goal_suppressed():
    """方案 B：有镜头焦点时，镜头外角色的残留目标不注入，避免其被旧目标拽回抢戏。

    对应会话 9f2e16e9 R14：焦点锁定某角色，镜头外角色的旧目标「贴身照看某人伤口」
    却仍作为「当前意图」注入，导致其无视镜头约束、追到电梯口救治。
    """
    snap = dict(MIN_SNAP)
    snap["goals"] = {
        "角色甲": "照看角色丁的伤口",
        "角色丁": "寻找物资",
    }
    msgs = prompter.build_session(
        CARDS, "继续", [], snap,
        focus={"subjects": ["角色丁"], "place": "地库"})
    sysmsg = "\n".join(m["content"] for m in msgs)
    # 镜头外角色（角色甲）的残留目标不得作为「当前意图」出现
    assert "照看角色丁的伤口" not in sysmsg
    # 镜头内角色（角色丁）的目标仍应注入
    assert "寻找物资" in sysmsg


def test_no_focus_keeps_all_goals():
    """方案 B 反例：无焦点（自然推演）时所有角色目标照常注入，不误伤。"""
    snap = dict(MIN_SNAP)
    snap["goals"] = {"角色甲": "照看角色丁的伤口", "角色丁": "寻找物资"}
    msgs = prompter.build_session(CARDS, "继续", [], snap, focus=None)
    sysmsg = "\n".join(m["content"] for m in msgs)
    assert "照看角色丁的伤口" in sysmsg
    assert "寻找物资" in sysmsg


def test_build_session_has_no_speaker_block_contract():
    """不得再强制「角色名：」分段格式。

    v0.16.1 曾加 [分段格式] 块修 5 处机制，但 simon 亲测发现**叙事正文观感明显下降**：
    原本以散文为主体的正文（大段环境/动作/心理描写 + 引号对白）被压成
    「角色甲：（动作）台词」的流水账。叙事质量优先于机制完整度，故 v0.17.0 整体移除。

    依赖该格式的机制均已随版本演进移除或改用不依赖格式的判据。
    """
    sysmsg = "\n".join(m["content"] for m in prompter.build_session(
        CARDS, "继续", [], MIN_SNAP))
    assert "[分段格式]" not in sysmsg, "分段格式契约已移除，不得重新引入"
    # 输出格式块本身应保留（它承载的是叙事要求，不是格式强制）
    assert "[输出格式]" in sysmsg


def test_output_discipline_forbids_craft_standard_echo():
    """输出纪律须含「禁止把世界书技法/描写标准复述进正文」一条（v0.28.5 减损）。

    对应会话 9a7cb89f：模型把世界书「亲密描写标准」条目的技法标签原文
    （「心理通过身体写出」「把外部压力重新压回来」等）当成正文内容吐出来，
    污染叙事。根因是线上模型指令回声（非引擎机制 bug），此条从源头压住：
    明确「技法标准是执行约束、只按其方式写、不得复述标签」。
    断言措辞锚点（「技法」「描写标准」「复述」「正文」）而非整句，给将来微调留余地。
    """
    sysmsg = "\n".join(m["content"] for m in prompter.build_session(
        CARDS, "继续", [], MIN_SNAP))
    assert "[输出纪律]" in sysmsg, "输出纪律块缺失"
    for kw in ("技法", "描写标准", "复述", "正文"):
        assert kw in sysmsg, "输出纪律缺少技法标准回声抑制的关键锚点：%s" % kw


def test_offscreen_note_injected_for_cardless_relation_name(monkeypatch):
    """背景人物防活动化软约束：关系表里出现、但无独立角色卡的名字必须触发提示。

    对应 v0.31.2 恢复：offscreen 提示词层曾在 v0.31.0 随检测层被连带误删（检测层
    命中率趋零+曾误删正文确该删，但此处只做 prompt 约束、从不删正文）。本用例固化
    「无卡背景人物 → 注入[背景人物·非在场]约束」这一不变式，防再次被当死代码删掉。
    用中性占位（角色甲/丁有卡、角色戊无卡），不绑任何剧本名（普适性红线）。
    """
    import store
    monkeypatch.setattr(store, "list_characters",
                        lambda: ["角色甲", "角色丁"])
    snap = dict(MIN_SNAP)
    snap["relations"] = {"角色甲 → 角色戊": "某位仅被提及的旧识"}
    sysmsg = "\n".join(m["content"] for m in prompter.build_session(
        CARDS, "继续", [], snap))
    assert "[背景人物·非在场]" in sysmsg, "无卡背景人物未触发活动化约束"
    assert "角色戊" in sysmsg, "背景人物名未写入约束"
    # 关系升级漂移约束是防「小姨子→妻子」的核心，必须保留
    assert "不得改写为在场/夫妻/恋人" in sysmsg


def test_offscreen_note_absent_when_all_relations_are_cards(monkeypatch):
    """反例：关系表里全是已有角色卡的人名时，不得注入背景人物约束（零开销）。

    防止「把有卡但本轮不在场名单的角色」误划成背景——这正是 v0.28.x 早期
    的真实会话事故（提示词要求「不得出场」却正在演，自相矛盾）。
    """
    import store
    monkeypatch.setattr(store, "list_characters",
                        lambda: ["角色甲", "角色丁"])
    snap = dict(MIN_SNAP)
    snap["relations"] = {"角色甲 → 角色丁": "同队"}
    sysmsg = "\n".join(m["content"] for m in prompter.build_session(
        CARDS, "继续", [], snap))
    assert "[背景人物·非在场]" not in sysmsg


def test_demo_hits_render_example_block():
    """demo_hits（写法示范条目）须渲染成[写法示范]块，示范正文进入 prompt。"""
    demo = [{"name": "示范", "content": "*动作* \"对白\" 散文", "demo": True}]
    sysmsg = "\n".join(m["content"] for m in prompter.build_session(
        CARDS, "继续", [], MIN_SNAP, demo_hits=demo))
    assert "[写法示范]" in sysmsg
    assert "*动作* \"对白\" 散文" in sysmsg


def test_no_demo_hits_no_example_block():
    """未传 demo_hits 时，不渲染[写法示范]块（零开销，向后兼容）。"""
    sysmsg = "\n".join(m["content"] for m in prompter.build_session(
        CARDS, "继续", [], MIN_SNAP))
    assert "[写法示范]" not in sysmsg
