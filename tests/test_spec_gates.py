"""通用设计规范反向对齐门禁测试（G1 / G2 / G4 / G5 / G8）。

守住以下几条跨项目硬约束：
  1. G8 重复惩罚隔离：结构化 JSON 通道（director.reflect / init_relations /
     derive_address / script_refiner.refine_script）显式传入 frequency_penalty=0.0、
     presence_penalty=0.0，不受用户全局重复惩罚配置影响，且绝不注入执笔人设。
  2. G8 单 system 首位收口：长历史触发滑动窗口压缩后，build_session 输出的
     messages 仅 messages[0] 为 system。
  3. G4 / G5 世界书透明性：world.scan_detail 完整返回 dropped（超配额整条截断）、
     unreachable（空 keys + 非常量 + 未被 #name# 引用的启用条目）与 stats 字数统计，
     且 /api/world/<name>/test 原样透出这些字段。
  4. G1 / G2 角色表消费与未知字段透传：全部核心人设字段进入 build_session，
     store.save_card / load_card 保留未识别扩展字段。
"""

import sys
from pathlib import Path

import pytest

ENGINE = Path(__file__).resolve().parent.parent / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

import app as engine_app      # noqa: E402
import director               # noqa: E402
import llm                    # noqa: E402
import memory                 # noqa: E402
import prompter               # noqa: E402
import script_refiner         # noqa: E402
import store                  # noqa: E402
import world                  # noqa: E402


# ------------------------------------------------------------------ G8: 惩罚参数隔离

def test_llm_penalty_override_blocks_global_frequency_penalty(monkeypatch):
    """全局开了高额重复惩罚时，调用方传 0.0 必须彻底剥离对应字段。"""
    monkeypatch.setattr(llm, "_file_config",
                        lambda: {"frequency_penalty": 0.8, "presence_penalty": 0.5, "min_p": 0.02})
    # 默认不传覆盖参数时，继承用户全局设置
    p_default = llm._base_payload([{"role": "user", "content": "hi"}],
                                  None, None, None, None, "m", 1.1, 256)
    assert p_default["frequency_penalty"] == 0.8
    assert p_default["presence_penalty"] == 0.5

    # 结构化 JSON 通道显式传 0.0 时，不发送惩罚字段（中性值不发）
    p_json = llm._base_payload([{"role": "user", "content": "hi"}],
                               0.3, None, 512, None, "m", 1.1, 256,
                               frequency_penalty=0.0, presence_penalty=0.0)
    assert "frequency_penalty" not in p_json
    assert "presence_penalty" not in p_json


def test_structured_json_callsites_force_zero_penalty_and_no_writer(monkeypatch, tmp_path):
    """全部结构化 JSON 调用点必须传 frequency_penalty=0.0 / presence_penalty=0.0 且不含执笔人设。"""
    monkeypatch.setattr(memory, "SESS_DIR", tmp_path / "sessions")
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    store._cache.clear()

    store.save_world("世界X", [])
    store.save_card("角色A", {
        "name": "角色A", "world": "世界X",
        "description": "沉稳寡言的守门人。",
        "core_desire": "保住钥匙", "core_fear": "大门失守",
    })
    store.save_card("角色B", {
        "name": "角色B", "world": "世界X",
        "description": "急躁的信使。",
        "core_desire": "尽快送信", "core_fear": "延误期限",
    })
    sid = memory.new(["角色A", "角色B"], scene_place="地点X", world_name="世界X")

    captured = []

    def fake_complete(messages, **kwargs):
        captured.append((messages, kwargs))
        return "{}"

    monkeypatch.setattr(llm, "complete", fake_complete)

    # 1) director.reflect
    director.reflect(sid, "角色A看了角色B一眼，没有说话。", directive="")
    # 2) director.init_relations
    cards = {"角色A": store.load_card("角色A"), "角色B": store.load_card("角色B")}
    director.init_relations(cards)
    # 3) director.init_address
    snap = memory.load(sid)
    director.init_address(snap)
    # 4) script_refiner.refine_script
    monkeypatch.setattr(script_refiner, "extract_json",
                        lambda _t: {"world": {"name": "世界X", "entries": []}, "characters": []})
    script_refiner.refine_script("这是一段测试剧本，包含角色A与角色B在地点X的相遇。" * 5,
                                 world_name="世界X")

    assert len(captured) == 4
    for messages, kwargs in captured:
        assert kwargs.get("frequency_penalty") == 0.0
        assert kwargs.get("presence_penalty") == 0.0
        joined = "\n".join(m.get("content", "") for m in messages)
        assert prompter.WRITER_GUARD not in joined
        assert "[执笔写手" not in joined


def test_build_session_single_leading_system_even_with_long_history(monkeypatch):
    """G8：历史超出滑动窗口触发压缩摘要时，messages 中仍仅 messages[0] 为 system。"""
    monkeypatch.setattr(store, "list_characters", lambda: ["角色A"])
    cards = {
        "角色A": {
            "name": "角色A",
            "description": "简介A",
            "personality": "性格A",
            "core_desire": "渴望A",
            "core_fear": "恐惧A",
            "short_goal": "意图A",
        }
    }
    snap = {
        "present": ["角色A"],
        "scene": {"place": "地点X", "time": "傍晚", "weather": "", "round": 20},
        "relations": {},
        "secrets": [],
        "ledger": [],
        "address": {},
        "states": {},
        "locations": {"角色A": {"place": "地点X", "round": 19}},
    }
    history = []
    for i in range(prompter.HISTORY_WINDOW_ROUNDS + 5):
        history.append({"role": "user", "content": f"指令{i}"})
        history.append({"role": "assistant", "content": f"叙事{i}"})

    msgs = prompter.build_session(cards, "本轮指令", [], snap, history=history)
    assert msgs[0]["role"] == "system"
    assert all(m["role"] != "system" for m in msgs[1:])
    assert "[历史叙事摘要]" in msgs[0]["content"]


# ------------------------------------------------------------------ G4 / G5: 世界书透明性

def test_world_scan_detail_dropped_unreachable_and_stats():
    """超配额关键词条目整条进 dropped；空 keys 非常量且未被引用条目进 unreachable。"""
    entries = [
        {"name": "常量条", "keys": [], "content": "1234567890", "constant": True,
         "enabled": True, "priority": 100},
        {"name": "高优命中", "keys": ["触发"], "content": "AAAAA", "constant": False,
         "enabled": True, "priority": 90},
        {"name": "中优命中", "keys": ["触发"], "content": "BBBBB", "constant": False,
         "enabled": True, "priority": 80},
        {"name": "低优截断", "keys": ["触发"], "content": "CCCCC", "constant": False,
         "enabled": True, "priority": 70},
        {"name": "被引条", "keys": [], "content": "DDDDD", "constant": False,
         "enabled": True, "priority": 60},
        {"name": "引用方", "keys": ["拉取"], "content": "见 #被引条#", "constant": False,
         "enabled": True, "priority": 50},
        {"name": "孤儿死条", "keys": [], "content": "永远不会被触发", "constant": False,
         "enabled": True, "priority": 40},
        {"name": "停用空条", "keys": [], "content": "已停用不算", "constant": False,
         "enabled": False, "priority": 30},
    ]

    detail = world.scan_detail(entries, ["触发"], max_entries=2)
    hit_names = [e["name"] for e in detail["hits"]]
    drop_names = [e["name"] for e in detail["dropped"]]
    unreach_names = [e["name"] for e in detail["unreachable"]]

    assert hit_names == ["常量条", "高优命中", "中优命中"]
    assert drop_names == ["低优截断"]
    assert detail["dropped"][0]["content"] == "CCCCC"  # 整条完整保留，不截半句
    assert unreach_names == ["孤儿死条"]  # 被引条与停用条不误报

    st = detail["stats"]
    assert st["const_chars"] == 10
    assert st["dynamic_chars"] == 10
    assert st["total_chars"] == 20
    assert st["dropped_count"] == 1


def test_world_test_api_exposes_dropped_unreachable_stats():
    """预览接口 /api/world/<name>/test 返回 dropped / unreachable / stats。"""
    client = engine_app.app.test_client()
    entries = [
        {"name": f"条目{i}", "keys": ["风"], "content": f"内容{i}", "constant": False,
         "enabled": True, "priority": 100 - i}
        for i in range(10)
    ]
    entries.append({"name": "死条", "keys": [], "content": "无触发词", "constant": False,
                    "enabled": True, "priority": 10})
    resp = client.post("/api/world/测试世界/test", json={"entries": entries, "history": ["起风了"]})
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["hits"]) == 8
    assert len(data["dropped"]) == 2
    assert [e["name"] for e in data["unreachable"]] == ["死条"]
    assert data["stats"]["dropped_count"] == 2


# ------------------------------------------------------------------ G1 / G2: 角色字段消费与透传

def test_persona_core_fields_all_consumed_and_unknown_fields_preserved(monkeypatch, tmp_path):
    """角色核心五字段全部渲染进 prompt，且未识别扩展字段保存后原样保留。"""
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    store._cache.clear()
    store.save_card("角色A", {
        "name": "角色A",
        "world": "世界X",
        "description": "DESC_TOKEN_01",
        "personality": "PERS_TOKEN_02",
        "core_desire": "DESIRE_TOKEN_03",
        "core_fear": "FEAR_TOKEN_04",
        "short_goal": "GOAL_TOKEN_05",
        "custom_ext": {"tag": "preserve_me"},
    })
    reloaded = store.load_card("角色A")
    assert reloaded["custom_ext"] == {"tag": "preserve_me"}

    snap = {
        "present": ["角色A"],
        "scene": {"place": "地点X", "time": "午后", "weather": "", "round": 1},
        "relations": {}, "secrets": [], "ledger": [], "address": {},
        "states": {}, "locations": {},
    }
    msgs = prompter.build_session({"角色A": reloaded}, "推进", [], snap)
    sys_text = msgs[0]["content"]
    for token in ("DESC_TOKEN_01", "PERS_TOKEN_02", "DESIRE_TOKEN_03", "FEAR_TOKEN_04", "GOAL_TOKEN_05"):
        assert token in sys_text
