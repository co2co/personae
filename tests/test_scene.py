"""scene.apply 的确定性测试：锁定"全员随世界转移被误填进 leave 清空 present"的回归。

不调真实 LLM：monkeypatch scene.llm.complete 返回受控 JSON。
覆盖：
- 危险响应（leave 覆盖全部在场者、arrive 为空）-> 视为随世界移动，present 不得清空
- 显式单人离场（leave 仅含部分）-> 仍应生效
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
        "leave": ["老周", "林晚", "阿杰", "苏曼", "高洋"],
        "arrive": [],
        "reason": "全员突围撤离，各自离开便利店",
    })


@pytest.fixture
def patched(monkeypatch):
    monkeypatch.setattr(scene.llm, "complete", _fake_complete)
    monkeypatch.setattr(scene.store, "list_characters",
                        lambda: ["老周", "林晚", "阿杰", "苏曼", "高洋"])
    monkeypatch.setattr(scene.store, "load_card", lambda n: {"short_goal": ""})


def _snap():
    return {
        "scene": {"place": "便利店后仓", "time": "", "weather": "", "round": 1, "same_scene": 3},
        "present": ["老周", "林晚", "阿杰", "苏曼", "高洋"],
        "secrets": [], "relations": {}, "goals": {}, "ledger": [],
    }


def test_scene_apply_keeps_present_on_move_together(patched):
    snap = _snap()
    changed, prop = scene.apply("sid", "老周带所有人从后窗突围撤离，目标城东", snap)
    assert changed is True
    # 关键回归：leave 覆盖全员且无 arrive -> 视为随世界移动，present 不得清空
    assert snap["present"] == ["老周", "林晚", "阿杰", "苏曼", "高洋"]


def test_scene_apply_explicit_single_leave_respected(patched):
    # 显式单人离场仍应生效（leave 仅含部分在场者）
    def _fake2(messages, **kw):
        return json.dumps({"changed": True, "place": "便利店后仓", "time": "",
                           "weather": "（未设定）", "leave": ["苏曼"], "arrive": [],
                           "reason": "苏曼出去找女儿"})
    scene.llm.complete = _fake2
    snap = _snap()
    changed, prop = scene.apply("sid", "苏曼出去找女儿", snap)
    assert "苏曼" not in snap["present"]
    assert len(snap["present"]) == 4
