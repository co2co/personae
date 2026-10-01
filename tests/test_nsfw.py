"""NSFW 门控确定性测试（不调 LLM，纯逻辑）。

锁死 engine/nsfw.resolve_session 的「成年确认 + 机会等级」驱动逻辑，
确保 NSFW 支持度在引擎层面被正确解锁/受限，不受模型随机性影响。

另锁定「许可 vs 事实」语义分离：机会等级只是许可上限，本轮实际写到了哪一步
由 director.detect_intimacy 判定，二者不可混用。
"""

import director
import nsfw


def test_unconfirmed_adult_is_locked():
    d = nsfw.resolve_session({}, False, "满机会")
    assert d["unlocked"] is False
    assert d["intimate_allowed"] is False
    assert "克制" in d["prompt"]          # 受限基调 GUARD


def test_adult_no_opportunity_romantic_tension():
    d = nsfw.resolve_session({}, True, "无")
    assert d["unlocked"] is True
    assert d["intimate_allowed"] is False
    assert "浪漫" in d["prompt"]          # 允许浪漫张力但不越线


def test_adult_half_step_intimate():
    d = nsfw.resolve_session({}, True, "半步")
    assert d["intimate_allowed"] is True


def test_adult_full_opportunity_must_cross_line():
    d = nsfw.resolve_session({}, True, "满机会")
    assert d["intimate_allowed"] is True
    # 满机会提示词必须强令越线，而非停在门口/克制收尾
    assert "越线" in d["prompt"]


def test_adult_full_opportunity_explicit_language():
    # B 方向强化：满机会提示词必须给出露骨的生理描写引导，不容回避
    d = nsfw.resolve_session({}, True, "满机会")
    p = d["prompt"]
    assert any(k in p for k in ("插入", "抽送", "体液", "生殖器", "胸部"))
    # 同时明确禁止糊弄式收尾
    assert "门口" in p and "糊弄" in p


def test_override_off_suppresses_full():
    d = nsfw.resolve_session({}, True, "满机会", override="off")
    assert d["unlocked"] is False
    assert d["intimate_allowed"] is False
    assert "克制" in d["prompt"]


def test_override_on_forces_unlock():
    # 优先级：未确认成年 > 当次 override。成年已确认时，override="on" 强制解锁。
    d = nsfw.resolve_session({}, True, "无", override="on")
    assert d["unlocked"] is True
    assert d["intimate_allowed"] is True


def test_adult_gate_beats_override_on():
    # 未确认成年时，override="on" 也不能绕过年龄硬门禁（符合 docstring 优先级）
    d = nsfw.resolve_session({}, False, "满机会", override="on")
    assert d["unlocked"] is False
    assert d["intimate_allowed"] is False


# ---- 许可 vs 事实：机会等级只发许可，实际发生与否看正文 ----

def test_detect_intimacy_three_tiers():
    assert director.detect_intimacy("他进入了她，抽送起来") == "越线"
    assert director.detect_intimacy("他把她按在墙上，吻了下去") == "接触"
    assert director.detect_intimacy("两人沉默地走过长街") == "无"
    assert director.detect_intimacy("") == "无"


def test_permission_is_not_fact():
    """满机会只代表"允许写到越线"，不代表本轮真的写了。

    30 轮压测实测：满机会 28 轮，而正文露骨级 0/30 —— 许可发了但剧情没走到，
    二者必须分开度量，否则门控数据会虚报。
    """
    d = nsfw.resolve_session({}, True, "满机会")
    assert d["intimate_allowed"] is True           # 许可：顶格
    # 事实：正文只到接触级
    assert director.detect_intimacy("他把她压在身下，隔着衣服抱紧") == "接触"


def _after_reply_with(reply, monkeypatch):
    """用受控快照跑 after_reply，返回记账后的 ledger。"""
    snap = {}
    monkeypatch.setattr(director.memory, "load", lambda sid: snap)
    monkeypatch.setattr(director.memory, "save", lambda sid, s: None)
    director.after_reply("sid", reply)
    return snap.get("ledger", [])


def test_after_reply_no_ledger_when_permission_unused(monkeypatch):
    """回归锁定：满机会许可未兑现时不得记账。

    原实现 after_reply(..., decision["intimate"]) 把派生的许可值当事实用，
    等价条件退化为「满机会就记」——30 轮压测会凭空记下 28 条"发生了亲密越线"，
    与 docstring「确有亲密内容时」的意图不符。
    """
    led = _after_reply_with("他把她压在身下，隔着衣服抱紧，喘息着", monkeypatch)
    assert led == [], f"许可未兑现却记了旧账：{led}"


def test_after_reply_logs_only_on_actual_crossing(monkeypatch):
    led = _after_reply_with("他插入了她，抽送的节奏越来越快", monkeypatch)
    assert len(led) == 1
    assert "亲密越线" in led[0]["account"]


def test_after_reply_no_ledger_on_plain_narration(monkeypatch):
    led = _after_reply_with("老周握紧螺丝刀，盯着卷帘门", monkeypatch)
    assert led == []
