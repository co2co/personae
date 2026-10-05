"""scene.apply 的确定性测试。

不调真实 LLM：monkeypatch scene.llm.complete 返回受控 JSON。
覆盖：
- 危险响应（leave 覆盖全部在场者、arrive 为空）-> 视为随世界移动，present 不得清空
- 显式单人离场（leave 仅含部分）-> 仍应生效
- 场景防僵死：指令含触发词但 LLM 判定无变化时，停留计数必须累加（不得清零）
- 停留超时触发时必须带"强制推进"提示，且失败后进入冷却而非每轮调 LLM
"""

import json

import pytest

import scene


def _fake_complete(messages, **kw):
    # 危险响应：LLM 把"全员突围撤离"误填成 leave=全员、arrive=空
    return json.dumps({
        "changed": True,
        "place": "城东",
        "time": "",
        "weather": "（未设定）",
        "leave": ["角色甲", "角色丙", "角色戊", "角色丁", "角色乙"],
        "arrive": [],
        "reason": "全员突围撤离，各自离开便利店",
    })


@pytest.fixture
def patched(monkeypatch):
    monkeypatch.setattr(scene.llm, "complete", _fake_complete)
    monkeypatch.setattr(scene.store, "list_characters",
                        lambda: ["角色甲", "角色丙", "角色戊", "角色丁", "角色乙"])
    monkeypatch.setattr(scene.store, "load_card", lambda n: {"short_goal": ""})


def _snap():
    return {
        "scene": {"place": "便利店后仓", "time": "", "weather": "", "round": 1, "same_scene": 3},
        "present": ["角色甲", "角色丙", "角色戊", "角色丁", "角色乙"],
        "secrets": [], "relations": {}, "goals": {}, "ledger": [],
    }


def test_scene_apply_keeps_present_on_move_together(patched):
    snap = _snap()
    changed, prop = scene.apply("sid", "角色甲带所有人从后窗突围撤离，目标城东", snap)
    assert changed is True
    # 关键回归：leave 覆盖全员且无 arrive -> 视为随世界移动，present 不得清空
    assert snap["present"] == ["角色甲", "角色丙", "角色戊", "角色丁", "角色乙"]


def test_scene_apply_explicit_single_leave_respected(patched):
    # 显式单人离场仍应生效（leave 仅含部分在场者）
    def _fake2(messages, **kw):
        return json.dumps({"changed": True, "place": "便利店后仓", "time": "",
                           "weather": "（未设定）", "leave": ["角色丁"], "arrive": [],
                           "reason": "角色丁出去找女儿"})
    scene.llm.complete = _fake2
    snap = _snap()
    changed, prop = scene.apply("sid", "角色丁出去找女儿", snap)
    assert "角色丁" not in snap["present"]
    assert len(snap["present"]) == 4


def _no_change_complete(messages, **kw):
    """场景导演判定"无变化"的响应。"""
    return json.dumps({"changed": False, "place": "便利店后仓", "time": "",
                       "weather": "", "leave": [], "arrive": [], "reason": "无变化"})


def test_same_scene_accumulates_when_llm_reports_no_change(patched):
    """回归锁定：指令含触发词但 LLM 判定无变化时，停留计数必须累加而非清零。

    原实现在 `changed=false` 分支把 same_scene 清零，导致指令常含"去/天亮"等
    触发词时每轮触发、每轮清零，same_scene 永远达不到 AUTO_TIME_THRESHOLD，
    防僵死保护彻底失效（30 轮压测实测：场景连续 23 轮不变，与叙事脱节）。
    """
    scene.llm.complete = _no_change_complete
    snap = _snap()
    snap["scene"]["same_scene"] = 0
    seen = []
    for _ in range(4):
        # "去" 命中 MOVE_KEYS：每轮都会触发一次场景判定
        scene.apply("sid", "角色甲带人去城东", snap)
        seen.append(snap["scene"]["same_scene"])
    # 前三轮累加到阈值；第四轮因超时触发强制推进，失败后冷却归零
    assert seen[:3] == [1, 2, 3], f"停留计数未累加（防僵死保护失效）：{seen}"
    assert seen[3] == 0, f"强制推进失败后应冷却归零，实际：{seen}"


def test_force_hint_used_on_timeout_and_cooldown_after_failure(patched):
    """停留超时触发时（无触发词也须触发），提示须要求强制推进。"""
    captured = {}

    def _capture(messages, **kw):
        captured["prompt"] = messages[0]["content"]
        return _no_change_complete(messages, **kw)

    scene.llm.complete = _capture
    snap = _snap()          # same_scene=3，已达 AUTO_TIME_THRESHOLD
    # 指令不含任何触发词，仅靠停留超时触发
    changed, _ = scene.apply("sid", "角色甲沉默地握紧螺丝刀", snap)
    assert captured.get("prompt"), "已超时却未调用场景导演"
    assert "强制推进" in captured["prompt"], "超时触发未追加强制推进提示"
    assert changed is False
    assert snap["scene"]["same_scene"] == 0, "强制推进失败后应冷却归零，避免每轮调 LLM"


def test_triggered_on_spatial_door_split():
    """T2 根因修复：空间分隔指令（门内/门外/分开）应触发场景判定，而非静默跳过。

    原 R16「角色丁挤进门内找家人，角色甲被挡在门外，两边分开」不命中任一触发词，
    _triggered 返回 (False, False) -> scene LLM 不调 -> present 恒为全员。
    """
    snap = _snap()
    snap["scene"]["same_scene"] = 0
    triggered, force = scene._triggered(
        "角色丁挤进门内找家人，角色甲被挡在门外，两边分开", snap)
    assert triggered is True
    assert force is False


def test_leave_respected_on_door_split(patched):
    """T2 根因修复：指令含「门外/挡在门外」时，scene LLM 返回的 leave 不被清空，
    被挡在门外的角色应从在场名单移除（其余人随场景移动）。
    """
    def _fake_door(messages, **kw):
        return json.dumps({"changed": True, "place": "门内", "time": "",
                           "weather": "（未设定）", "leave": ["角色甲"], "arrive": [],
                           "reason": "角色甲被挡在门外，与角色丁分开"})
    scene.llm.complete = _fake_door
    snap = _snap()
    changed, prop = scene.apply(
        "sid", "角色丁挤进门内找家人，角色甲被挡在门外，两边分开", snap)
    assert changed is True
    assert "角色甲" not in snap["present"]
    assert len(snap["present"]) == 4
