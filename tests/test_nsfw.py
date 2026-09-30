"""NSFW 门控确定性测试（不调 LLM，纯逻辑）。

锁死 engine/nsfw.resolve_session 的「成年确认 + 机会等级」驱动逻辑，
确保 NSFW 支持度在引擎层面被正确解锁/受限，不受模型随机性影响。
"""

import nsfw


def test_unconfirmed_adult_is_locked():
    d = nsfw.resolve_session({}, False, "满机会")
    assert d["unlocked"] is False
    assert d["intimate"] is False
    assert "克制" in d["prompt"]          # 受限基调 GUARD


def test_adult_no_opportunity_romantic_tension():
    d = nsfw.resolve_session({}, True, "无")
    assert d["unlocked"] is True
    assert d["intimate"] is False
    assert "浪漫" in d["prompt"]          # 允许浪漫张力但不越线


def test_adult_half_step_intimate():
    d = nsfw.resolve_session({}, True, "半步")
    assert d["intimate"] is True


def test_adult_full_opportunity_must_cross_line():
    d = nsfw.resolve_session({}, True, "满机会")
    assert d["intimate"] is True
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
    assert d["intimate"] is False
    assert "克制" in d["prompt"]


def test_override_on_forces_unlock():
    # 优先级：未确认成年 > 当次 override。成年已确认时，override="on" 强制解锁。
    d = nsfw.resolve_session({}, True, "无", override="on")
    assert d["unlocked"] is True
    assert d["intimate"] is True


def test_adult_gate_beats_override_on():
    # 未确认成年时，override="on" 也不能绕过年龄硬门禁（符合 docstring 优先级）
    d = nsfw.resolve_session({}, False, "满机会", override="on")
    assert d["unlocked"] is False
    assert d["intimate"] is False
