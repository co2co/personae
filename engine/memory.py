"""快照层：每个会话一份持久化状态（沙盘的核心记忆）。

存 data/sessions/<id>/snapshot.json + chat.jsonl。
快照包含：场景、关系图、秘密表、后果账本、各角色短期目标、好感度、最近事件。
每轮整体覆盖写（沙盘规则：禁止多次 patch，避免上下文膨胀）。
"""

import json
import shutil
import uuid
from pathlib import Path

import store
import world as world_mod

DATA = Path(__file__).parent / "data"
SESS_DIR = DATA / "sessions"


def _new_id():
    return uuid.uuid4().hex[:8]


def new(cast, scene_place="", world_name="home"):
    """开启一个沙盘世界。cast 为在场角色卡列表（全部为 NPC，环境推手不作为角色入场）。

    环境推手在原生机制里是外部导演/观察者：不登场、不说话，只注入环境扰动（切换场景、
    改变天气、指令某角色行动等），观察迷你世界如何运转。
    """
    sid = _new_id()
    folder = SESS_DIR / sid
    folder.mkdir(parents=True, exist_ok=True)
    present = list(cast)
    cards = {c: store.load_card(c) for c in present}

    relations = {}
    for c in present:
        for other, desc in (cards[c].get("relations") or {}).items():
            relations[f"{c} → {other}"] = desc

    secrets = []
    for e in store.load_world(world_name):
        if e.get("secret") and e.get("character"):
            secrets.append({
                "owner": e["character"],
                "content": e["content"],
                "bottom_line": e.get("bottom_line", ""),
                "keys": e.get("keys", []),
                "state": "潜伏",
                "known_by": [],
                "exposures": [],
            })

    # 短期目标：优先用角色卡手填的 short_goal；未填则退回核心渴望作为初始意图
    # （两者皆无则留空，由推演引擎在首轮后自动补写）
    goals = {c: (cards[c].get("short_goal") or cards[c].get("core_desire") or "")
             for c in present}
    # 行动状态：铁律里的“主动/防御/无行动”，由每轮谁在正文里出现来廉价判定
    action_state = {c: "主动" for c in present}

    snap = {
        "present": present,
        "scene": {"place": scene_place, "time": "", "weather": "", "round": 0, "same_scene": 0},
        "relations": relations,
        "actions": {},
        "secrets": secrets,
        "ledger": [],
        "goals": goals,
        "action_state": action_state,
        "recent": {},
        "intimacy_phase": "normal",
        "phase_rounds": 0,
    }
    save(sid, snap)
    return sid


def path(sid):
    return SESS_DIR / sid / "snapshot.json"


def load(sid):
    p = path(sid)
    if not p.exists():
        return None
    snap = json.loads(p.read_text(encoding="utf-8"))
    # 非破坏式迁移：旧快照把环境推手记为“玩家”，统一归一为“环境推手”
    for s in snap.get("secrets", []):
        kb = s.get("known_by")
        if isinstance(kb, list) and "玩家" in kb:
            s["known_by"] = ["环境推手" if k == "玩家" else k for k in kb]
    snap.setdefault("intimacy_phase", "normal")
    snap.setdefault("phase_rounds", 0)
    return snap


def save(sid, snap):
    path(sid).write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
    return snap


def chat_path(sid):
    folder = SESS_DIR / sid
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "chat.jsonl"


def load_chat(sid):
    p = chat_path(sid)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def append_chat(sid, message):
    p = chat_path(sid)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(message, ensure_ascii=False) + "\n")


def set_action_state(sid, name, state):
    """更新某角色本轮的行动状态（主动/防御/无行动），供侧栏观察世界运转。"""
    snap = load(sid)
    if name in snap.get("action_state", {}):
        snap["action_state"][name] = state
        save(sid, snap)
    return snap.get("action_state", {})


def list_sessions():
    """列举全部会话，返回精简摘要（不加载完整快照内容）。"""
    out = []
    if not SESS_DIR.exists():
        return out
    for folder in SESS_DIR.iterdir():
        if not folder.is_dir():
            continue
        if not (folder / "snapshot.json").exists():
            continue
        sid = folder.name
        snap = load(sid)
        if not snap:
            continue
        sc = snap.get("scene", {})
        out.append({
            "session": sid,
            "present": snap.get("present", []),
            "scene": sc.get("place", ""),
            "round": sc.get("round", 0),
            "intimacy_phase": snap.get("intimacy_phase", "normal"),
            "updated": int(folder.stat().st_mtime),
        })
    # 最近更新的排在最前
    out.sort(key=lambda x: x["updated"], reverse=True)
    return out


def delete_session(sid):
    """删除整局会话（snapshot.json + chat.jsonl + 目录）。不存在返回 False。"""
    folder = SESS_DIR / sid
    if not folder.exists() or not folder.is_dir():
        return False
    shutil.rmtree(folder)
    return True
