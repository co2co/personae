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


def new(cast, scene_place="", world_name="", scene_time="", opening_demo=""):
    """开启一个沙盘世界。cast 为在场的 NPC 角色卡列表。

    环境推手（导演）不登场、不说话，只通过本轮指令扰动世界，因此不进入 present。

    scene_place / scene_time：开场地点的纯地点名与时间锚，已由 session_new 经
    scene.parse_initial_scene 拆分（混写「傍晚，客厅」时，时间词进 time、地点进 place）。
    时间锚缺失会让模型只能靠世界书反向脑补时间（一次真实事故），故单独保留 time。
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
                # 秘密是否已成公开事实（归属者当众自述/承认，或把柄尽失后世人皆知）。
                # 置位后 _secret_state 判为「已公开」，不可逆。
                "public": False,
                "known_by": [],
                "exposures": [],
                # 起疑（线索逼近）记录：介于「潜伏」与「曝光」之间的中间态。
                # 只存疑点与举证，不存秘密真相——起疑者尚未证实，引擎不得剧透。
                "suspicions": [],
            })

    # 短期目标（goals）已随纪官瘦身撤除（2026-11-08）：旧版先拿角色卡 short_goal 或
    # core_desire 当种子，再让纪官每轮改写——「引擎替角色想下一步」。角色卡里的
    # short_goal 现在由 prompter 直接作为「开局意图」注入，恒定不变，不再进快照。

    snap = {
        "present": present,
        # 剧本归属：会话开在世界名之下，随快照固化。前端「剧本库/会话管理」
        # 据此把运行时会话挂回所属剧本。存量会话无此字段，前端回退从角色卡读 world。
        "world": world_name,
        # same_scene 已删（2026-11-08）：它只为旧版「停够三轮就强制推进时间」服务，
        # 那条强制规则已撤——引擎不再伪造时间流逝。
        "scene": {"place": scene_place, "time": scene_time, "weather": "", "round": 0},
        # 开局写法示范：由引擎静默注入的中性格式范例。首轮 act 时注入一次，之后不再出现。
        "opening_demo": (opening_demo or "").strip(),
        "relations": relations,
        # 权威关系基线：与 relations 一同固化自角色卡 relations 字段，作作者口径的备份
        # （玩家视图不外发，?debug=1 可见）。纪官瘦身（2026-11-08）后引擎不再改写关系，
        # 原先以它为可信源的两道冻结闸已一并删除，因此它当前无消费方：保留是为了兼容
        # 旧快照与作者工具，不构成引擎行为。删关系回写这条因果见 director.reflect 注释。
        "relations_base": dict(relations),
        # 作者显式声明的亲属身份（来自角色卡可选字段 relations_kinship）：
        # { "源 → 目标": "母亲" }。血缘是作者定义的固定事实，不该靠从描述句里猜词——
        # 句中的身份词常指第三方，据此冻结会把正确关系改坏。
        # 缺省为空 dict。纪官瘦身后此字段同样只落盘、不被消费（冻结闸已随关系回写一起删）；
        # 角色卡的 relations_kinship 因此暂无实际效果，若要恢复保护须回到关系改写那条链路上。
        "kinship_base": dict(kinship),
        "secrets": secrets,
        "ledger": [],
        # 称呼速查：{ "源 → 目标": "称呼" }，新建会话时由纪官从角色卡与关系表一次性推导。
        # 关系定性只说明「是什么关系」，称呼才决定正文里怎么叫——缺了它，人设里的
        # 「讨好领队」「顶撞权威」这类设定无处落地（压测实证：应出现的称呼 0 次）。
        "address": {},
        "recent": {},
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
    # 秘密状态字面量迁移（v0.26.0 四态）：历史「全曝光」归一为「已公开」；
    # 补 public 标志位（旧快照无此字段，缺省 False）。状态本身在本轮 reflect
    # 归档时由 _secret_state 重算，故此处只做字面量归一，不重算（避免 memory
    # 反向依赖 director 造成循环导入）。
    for s in snap.get("secrets", []):
        kb = s.get("known_by")
        if isinstance(kb, list) and "玩家" in kb:
            s["known_by"] = ["环境推手" if k == "玩家" else k for k in kb]
        s.setdefault("public", s.get("state") == "全曝光")
        if s.get("state") == "全曝光":
            s["state"] = "已公开"
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
            # 剧本归属（快照 world 字段）；存量会话无此字段则为空串，前端回退处理。
            "world": snap.get("world", "") or "",
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


# 会话保留上限：只保留最近 MAX_KEPT_SESSIONS 条会话，超出部分自动删除。
# 由路由层 session_new 在新建会话后触发（见 app.py）——不放进 memory.new，
# 因为测试直接调 memory.new 且操作真实 data/sessions，放进 new 会让跑测试
# 误删存量真实会话。
MAX_KEPT_SESSIONS = 10


def prune_sessions(max_keep=MAX_KEPT_SESSIONS):
    """会话保留策略：只保留最近 max_keep 条有效会话，其余整目录删除。

    「有效会话」口径与 list_sessions 一致——须含 snapshot.json（光有 chat.jsonl
    的半成品目录不算会话，不参与计数、不被保留位占用，但会被一并清掉以免堆积）。
    排序键用目录 mtime（最近一次写入时间），与 list_sessions 的「最近更新在前」一致：
    新建会话后，新会话的目录 mtime 最新，自然占据保留位之首。
    返回实际删除的会话目录数（供路由层记录日志）。
    """
    if not SESS_DIR.exists():
        return 0
    entries = []
    for folder in SESS_DIR.iterdir():
        if not folder.is_dir():
            continue
        # 与 list_sessions 同口径：无 snapshot.json 的不计入保留名额，直接归入待删。
        valid = (folder / "snapshot.json").exists()
        entries.append((folder, valid, folder.stat().st_mtime))
    if not entries:
        return 0
    # 有效会话按 mtime 降序排，保留前 max_keep 个；其余（含无效目录）全部删除。
    valid_sorted = sorted([e for e in entries if e[1]], key=lambda x: x[2], reverse=True)
    keep = {e[0] for e in valid_sorted[:max_keep]}
    removed = 0
    for folder, _valid, _mtime in entries:
        if folder in keep:
            continue
        try:
            shutil.rmtree(folder)
            removed += 1
        except OSError:
            # 单个目录删除失败（占用/权限）不阻断其余清理；下次新建会话会再试。
            continue
    return removed
