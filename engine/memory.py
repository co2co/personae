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


def new(cast, scene_place="", world_name=""):
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

    # 作者显式声明的亲属身份（角色卡可选字段 relations_kinship）。血缘是固定事实，
    # 不从 relations 描述句里猜词——那里的身份词常指第三方，猜错会把正确关系改坏。
    kinship = {}
    for c in present:
        for other, kin in (cards[c].get("relations_kinship") or {}).items():
            if other and kin:
                kinship[f"{c} → {other}"] = str(kin).strip()

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
                # 起疑（线索逼近）记录：介于「潜伏」与「曝光」之间的中间态。
                # 只存疑点与举证，不存秘密真相——起疑者尚未证实，引擎不得剧透。
                "suspicions": [],
                # 发酵压力：连续多少轮这条秘密在叙事里完全没被触及（提及/暗示/回避/物证/追问
                # 任一都算触及）。由代码累加、触及即归零；模型永远看不到这个数字，只看到
                # prompter 按档位生成的文案。用于替代原技能「LLM 自写简报自我提醒」的推进压力。
                "pressure": 0,
            })

    # 短期目标：优先用角色卡手填的 short_goal；未填则退回核心渴望作为初始意图
    # （两者皆无则留空，由推演引擎在首轮后自动补写）
    goals = {c: (cards[c].get("short_goal") or cards[c].get("core_desire") or "")
             for c in present}

    snap = {
        "present": present,
        "scene": {"place": scene_place, "time": "", "weather": "", "round": 0, "same_scene": 0},
        "relations": relations,
        # 权威关系基线：与 relations 一同固化自角色卡 relations 字段。
        # reflect 的「未在场冻结」与「亲属身份冻结」都以它为唯一可信源；
        # 若此处不固化，真实会话（卡片自带 relations）会跳过 app.py 的固化分支，
        # 导致 relations_base 为空、两道冻结闸静默失效（见 v0.7.7 修复说明）。
        "relations_base": dict(relations),
        # 作者显式声明的亲属身份（来自角色卡可选字段 relations_kinship）：
        # { "源 → 目标": "母亲" }。血缘是作者定义的固定事实，不该靠从描述句里猜词——
        # 句中的身份词常指第三方，据此冻结会把正确关系改坏（见 director._preserve_kinship）。
        # 缺省为空 dict：未声明的边退回「句首显式身份词」这条弱规则。
        "kinship_base": dict(kinship),
        "actions": {},
        "secrets": secrets,
        "ledger": [],
        "goals": goals,
        # 连续静默轮数：由纪官输出的 actions 判定（某角色本轮无任何行为摘要则 +1）。
        # 用于「在场即须留痕」——连续沉默到阈值即注入硬性焦点，避免角色在长弧里被遗忘。
        "silent_rounds": {c: 0 for c in present},
        # 称呼速查：{ "源 → 目标": "称呼" }，新建会话时由纪官从角色卡与关系表一次性推导。
        # 关系定性只说明「是什么关系」，称呼才决定正文里怎么叫——缺了它，人设里的
        # 「讨好领队」「顶撞权威」这类设定无处落地（压测实证：应出现的称呼 0 次）。
        "address": {},
        "recent": {},
        # 会话级辅助群演注册表：导演/叙事在推演中刻意引入的临时角色（如半路加入的配角）。
        # 随会话存续，不进角色卡库、不进世界书、不进分发 zip；仅用于让引擎识别其为
        # 合法叙事参与者、保障跨回合连续性，并在快照里留存便于复盘（见 v0.9.0）。
        "aux": [],
        # 状态层：**可刷新**的当前状态（门是否封死、物品在谁手上、伤情等）。
        # 一键一当前值、后写覆盖前写，因此条目数只取决于「世界里有几个对象」，与回合数无关。
        "states": {},
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
    snap.setdefault("states", {})
    for s in snap.get("secrets", []):
        kb = s.get("known_by")
        if isinstance(kb, list) and "玩家" in kb:
            s["known_by"] = ["环境推手" if k == "玩家" else k for k in kb]
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
