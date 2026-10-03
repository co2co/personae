"""纪官输出健壮性：截断抢救与失败留痕。

背景：纪官要吐关系/行动/目标/秘密三类/事实两层，输出超 max_tokens 会在半句话上被切断。
旧实现里 _extract_json 解析失败即返回 None，reflect 静默 return —— 整轮回写（含事实保全）
全部丢失，且日志无痕。这里锁死三条：完整照常解析 / 截断抢救已完整成员 / 失败必须留痕。
"""

import json

import pytest

import director


def test_complete_json_parsed_normally():
    raw = '{"relations": {"甲 → 乙": "同伴"}, "actions": {"甲": "清点物资"}}'
    assert director._extract_json(raw)["actions"]["甲"] == "清点物资"
    assert director._is_complete_json(raw) is True


def test_truncated_json_salvages_complete_members():
    """尾部被切断在字符串中间：前面的完整成员必须抢救回来，不得整轮丢弃。"""
    good = {
        "relations": {"甲 → 乙": "母子"},
        "actions": {"甲": "扶起乙"},
    }
    # 模拟截断：第三个成员只写了一半就断掉
    raw = json.dumps(good, ensure_ascii=False)[:-1] + ', "new_facts": [{"kind": "death"'
    data = director._extract_json(raw)
    assert data is not None, "截断输出必须抢救，不得返回 None"
    assert data["actions"]["甲"] == "扶起乙"
    assert "new_facts" not in data          # 半截成员丢弃
    assert director._is_complete_json(raw) is False


def test_truncated_inside_string_is_detected():
    raw = '{"actions": {"甲": "扶起乙，乙已经没了'
    assert director._is_complete_json(raw) is False
    # 一个完整成员都没有时放弃抢救（避免造出空壳对象）
    assert director._extract_json(raw) is None


def test_nested_brackets_not_mistaken_for_top_level():
    """深度跟踪：数组/子对象内部的逗号与花括号不得被当成顶层成员边界。"""
    raw = ('{"state_updates": [{"subject": "铁门", "value": "焊死"},'
           '{"subject": "无线电", "value": "已'
           '砸碎"}], "actions": {"甲"')
    data = director._extract_json(raw)
    assert data is not None
    assert len(data["state_updates"]) == 2      # 数组内两项都完整，必须保住


def test_reflect_logs_when_output_unparsable(monkeypatch):
    """解析彻底失败时必须留痕——静默丢轮是最难定位的失败模式。

    注：引擎用自研日志总线（logger.bus，非 stdlib logging），故此处直接挂载探针断言。
    """
    called = []

    def spy_warn(category, msg, meta=None):
        called.append((category, msg))

    snap = {"present": ["甲"], "relations": {}, "goals": {}, "secrets": [],
            "scene": {"round": 1, "place": "某处"}}
    monkeypatch.setattr(director.logger, "warn", spy_warn)
    monkeypatch.setattr(director.llm, "complete", lambda *a, **k: "抱歉，我无法输出 JSON")
    monkeypatch.setattr(director.memory, "load", lambda sid: snap)
    monkeypatch.setattr(director.memory, "save", lambda sid, s: None)
    director.reflect("sid", "甲：我清点物资。")
    assert any("无法解析" in m for _, m in called)


def test_reflect_allows_generous_token_budget(monkeypatch):
    """额度必须够长：写死 900 会被事实保全后的输出顶爆。"""
    seen = {}

    def fake_complete(prompt, **kw):
        seen.update(kw)
        return json.dumps({"relations": {}, "actions": {}}, ensure_ascii=False)

    snap = {"present": ["甲"], "relations": {}, "goals": {}, "secrets": [],
            "scene": {"round": 1, "place": "某处"}}
    monkeypatch.setattr(director.llm, "complete", fake_complete)
    monkeypatch.setattr(director.memory, "load", lambda sid: snap)
    monkeypatch.setattr(director.memory, "save", lambda sid, s: None)
    director.reflect("sid", "甲：我清点物资。")
    assert seen.get("max_tokens", 0) >= 1500
