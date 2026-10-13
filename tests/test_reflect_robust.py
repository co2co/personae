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
    assert seen.get("max_tokens", 0) >= 2500


def _reflect_user_prompt(monkeypatch):
    """捕获 reflect 实际发出的 user 提示词正文（用于断言输出字段顺序）。"""
    captured = {}

    def fake_complete(prompt, **kw):
        # user 消息是含输出 schema 的那条；按内容定位，不依赖消息顺序
        for m in prompt:
            if isinstance(m, dict) and "secret_exposures" in m.get("content", ""):
                captured["user"] = m["content"]
                break
        return json.dumps({"secret_exposures": []}, ensure_ascii=False)

    snap = {"present": ["甲"], "relations": {}, "goals": {}, "secrets": [],
            "scene": {"round": 1, "place": "某处"}}
    monkeypatch.setattr(director.llm, "complete", fake_complete)
    monkeypatch.setattr(director.memory, "load", lambda sid: snap)
    monkeypatch.setattr(director.memory, "save", lambda sid, s: None)
    director.reflect("sid", "甲：我清点物资。")
    return captured["user"]


def test_reflect_schema_orders_secret_bookkeeping_first(monkeypatch):
    """治截断的字段重排：秘密簿记四字段必须排在冗长的 relations/actions/goals 之前。

    背景（v0.28.4）：旧顺序 relations/actions/goals 在前、secret_exposures 排第 4 位，
    输出被 max_tokens 截断时恰先把秘密簿记砍掉，导致 4/6 暗牌全程潜伏。
    此用例锁定「秘密簿记前置」这一顺序契约，防回归到旧顺序。
    """
    prompt = _reflect_user_prompt(monkeypatch)
    i_exp = prompt.index('"secret_exposures"')
    i_sus = prompt.index('"secret_suspicions"')
    i_hrd = prompt.index('"handle_releases"')
    i_toc = prompt.index('"secret_touches"')
    i_relations = prompt.index('"relations"')
    i_actions = prompt.index('"actions"')
    i_goals = prompt.index('"goals"')
    # 四个秘密簿记字段彼此相邻且整体前置
    assert i_exp < i_sus < i_hrd < i_toc
    # 全部秘密簿记字段都排在冗长的关系/行动/目标之前
    assert i_toc < i_relations
    assert i_relations < i_actions < i_goals


def test_truncated_output_preserves_leading_secret_bookkeeping():
    """截断兜底（字段重排的直接收益）：新顺序下尾部被截时，前置的秘密簿记必须被抢救。

    构造一段「secret_exposures 在前且完整、其后 relations/actions 写到一半被切断」的输出，
    模拟 REFLECT_MAX_TOKENS 截断。断言 _extract_json 抢救出 secret_exposures——
    即旧 bug「截断=整轮秘密簿记丢失」不再发生。
    """
    full = {
        "secret_exposures": [
            {"owner": "甲", "by": "乙", "via": "看见", "evidence": "乙看见了甲藏起的旧物"}
        ],
        "secret_suspicions": [],
        "handle_releases": [],
        "secret_touches": [{"owner": "甲", "touched": True}],
        "relations": {"甲 → 乙": "旧识，彼此戒备，这回合乙在暗中"},
        "actions": {"甲": "把旧物重新藏回袖中", "乙": "装作没看见却"},
    }
    # 模拟 max_tokens 截断：砍掉尾部一段，落在 actions 字符串中间
    raw = json.dumps(full, ensure_ascii=False)
    cut = raw[: int(len(raw) * 0.8)]
    data = director._extract_json(cut)
    assert data is not None, "截断输出必须抢救，不得返回 None"
    # 前置的秘密簿记完整保住（旧 bug：截断时整轮 secret_exposures 丢失）
    assert data["secret_exposures"][0]["owner"] == "甲"
    assert data["secret_exposures"][0]["by"] == "乙"
    assert data["secret_exposures"][0]["evidence"] == "乙看见了甲藏起的旧物"
    assert data["secret_touches"] == [{"owner": "甲", "touched": True}]
    # 被截断的尾部半截成员（actions 写到一半）必须丢弃，不得造出残缺条目
    assert "actions" not in data
    assert director._is_complete_json(cut) is False


def test_malformed_tail_singlequote_keys_salvages_head():
    """尾部畸形①（v0.28.4 第二层）：模型在尾部把双引号键漂成单引号键。

    实测（Hy4-preview）：完整 JSON 有首尾括号、整体 json.loads 失败，坏区恒在尾部
    （如 'location_updates': / 'who' 这类单引号键），而头部的秘密簿记保持合法。
    旧 _salvage_json 只取「最后一个完整边界」，该边界落在坏区 → 整轮返回 None、
    秘密簿记全丢。回退式 salvage 须回退到坏区之前的边界，保住头部 secret_exposures。
    """
    head = ('{"secret_exposures": [{"owner": "甲", "by": "乙", "via": "自述", '
            '"evidence": "乙听见甲亲口说了那桩旧事"}], '
            '"secret_suspicions": [], "handle_releases": [], '
            '"secret_touches": [{"owner": "甲", "touched": true}], '
            '"relations": {"甲 → 乙": "旧识，彼此戒备"}, '
            '"actions": {"甲": "把那桩旧事说漏了口", "乙": "装作没听见"}, ')
    # 尾部畸形：后续键用单引号（Python repr 风格），整体非法
    bad_tail = "'location_updates': [{'who':'乙','place':'某处'}], 'scene_shift': {'changed': false}}"
    raw = head + bad_tail
    assert director._is_complete_json(raw) is False, "前提：尾部畸形导致整体不可解析"
    data = director._extract_json(raw)
    assert data is not None, "尾部畸形不得导致整轮返回 None"
    # 头部合法簿记被回退式 salvage 保住（旧实现：取最后边界落在坏区 → None → 全丢）
    assert data["secret_exposures"][0]["owner"] == "甲"
    assert data["secret_exposures"][0]["by"] == "乙"
    assert data["secret_exposures"][0]["evidence"] == "乙听见甲亲口说了那桩旧事"
    assert data["secret_touches"] == [{"owner": "甲", "touched": True}]
    # 坏区（单引号键）之后的内容必须丢弃，不得造出畸形条目
    assert "location_updates" not in data


def test_malformed_tail_bare_control_char_salvages_head():
    """尾部畸形②（v0.28.4 第二层）：模型在尾部字符串值里塞裸控制符/裸键。

    实测：尾部出现 `"value": "\n由甲交给乙……"`（裸换行未转义）与 `"who ": "\n乙 "`
    这类结构性坏 JSON，整体 json.loads 失败；坏区恒在尾部，头部秘密簿记合法。
    回退式 salvage 须回退到坏区之前，保住头部簿记而非整轮丢弃。
    """
    head = ('{"secret_exposures": [{"owner": "甲", "by": "乙", "via": "看见", '
            '"evidence": "乙撞见甲把物件递了出去"}], '
            '"secret_suspicions": [], "handle_releases": [], '
            '"secret_touches": [{"owner": "甲", "touched": true}], ')
    # 尾部畸形：字符串值内含未转义的裸换行（非法控制符）
    bad_tail = '"state_updates": [{"subject": "物件", "value": "\n由甲交给乙带走"}], }'
    raw = head + bad_tail
    assert director._is_complete_json(raw) is False, "前提：尾部裸控制符导致整体不可解析"
    data = director._extract_json(raw)
    assert data is not None, "尾部裸控制符不得导致整轮返回 None"
    # 头部秘密簿记保住
    assert len(data["secret_exposures"]) == 1
    assert data["secret_exposures"][0]["owner"] == "甲"
    assert data["secret_exposures"][0]["via"] == "看见"
    assert data["secret_touches"] == [{"owner": "甲", "touched": True}]
    # 含裸控制符的坏成员（state_updates）必须丢弃
    assert "state_updates" not in data


def test_pure_truncation_behaviour_unchanged():
    """回退式 salvage 不得破坏既有纯截断语义：最后一个可解析边界本就能解析，
    回退第一步即命中，结果与旧实现一致（完整成员全保住、半截成员丢弃）。"""
    good = {
        "secret_exposures": [{"owner": "甲", "by": "乙", "via": "听见", "evidence": "乙听见甲说了"}],
        "relations": {"甲 → 乙": "旧识"},
        "actions": {"甲": "说漏了口", "乙": "装作没听见"},
        "goals": {"甲": "把旧事压下去"},
    }
    raw = json.dumps(good, ensure_ascii=False)[:-1] + ', "state_updates": [{"subject": "门"'
    data = director._extract_json(raw)
    assert data is not None
    assert data["secret_exposures"][0]["owner"] == "甲"
    assert data["relations"]["甲 → 乙"] == "旧识"
    assert data["actions"]["乙"] == "装作没听见"
    assert data["goals"]["甲"] == "把旧事压下去"
    assert "state_updates" not in data
