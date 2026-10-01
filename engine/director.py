"""导演简报：生成前读快照+core，跑 6 项检查，产出内部 brief 与注入指令。

规则版（不额外调 LLM），保证速度；后续可把 A5/A6 换成 LLM 判定，接口不变。
"""

import json
import re

import memory
import llm

ENV_PUSHER = "环境推手"

INFO_VERBS = ["翻", "偷看", "偷窥", "翻找", "翻查", "查看", "搜索", "监听",
             "跟踪", "打听", "问起", "查"]
# 叙事揭露的确定性校验词：回复须出现其一，才认定"某人发现了秘密"。
# 覆盖「观察者视觉/动作发现」与「持有者主动/无意泄露」两类路径。
DISCOVERY_VERBS = [
    # 视觉/感知发现
    "看见", "看到", "看清", "发现", "察觉", "注意到", "认出", "认得", "撞见", "目睹", "瞥见",
    "听见", "听出",
    # 动作揭露（掀/解/拆/拉/露/显）
    "掀开", "掀起", "解开", "拆开", "拉开", "扯开", "撕开", "翻出", "搜出", "露出", "暴露",
    "显出", "显现", "浮现", "赫然", "在目", "分明", "展露", "滑落", "现出",
    # 言语/认知获取
    "得知", "听说", "问出", "套出", "逼问出", "查到", "找到", "识破", "看穿", "揭穿", "戳穿",
    # 持有者主动/无意泄露
    "说漏", "招了", "坦白", "承认", "泄露", "说破", "抖出来", "吐露",
]
ALONE = ["独自", "只有我们", "没人", "关门", "屋里就", "没别人", "独处", "就我们"]
DEFENSE_DOWN = ["醉酒", "累了", "疲惫", "哭了", "崩溃", "靠近", "主动", "抱", "睡", "软弱"]
OBSTACLE = ["有人来", "门铃", "电话响", "被打断", "邻居", "妈妈喊", "爸喊"]

OPP_NOTE = {
    "试探": "可写指向对方的接触试探（触碰/靠近/语言挑逗），不必越线。",
    "半步": "可写对应程度的接触（持续触碰/肢体纠缠/氛围压到临界）。",
    "满机会": "尺度上限为越线（性行为或对应程度的接触）；应由剧情自然推进，亲密场景之后应有余韵/过渡回合，不要连续每回合都推进到性行为。若角色抗拒，抗拒须是可见的、指向对方的动作并留后果。",
}

# 全曝光：暂无升级规则，作为保留状态，不写入（参见 DEVLOG）
_FULL = "全曝光"


def _secret_state(known_by):
    """in-world 暴露状态：只要有在场角色知情即为「暴露」；仅环境推手/无人知情则「潜伏」。"""
    return "暴露" if any(k != ENV_PUSHER for k in known_by) else "潜伏"


def _record_exposure(s, by, via, round_no):
    """记录一次秘密曝光：写入知情者集合与曝光路径日志，并重算暴露状态。"""
    if by not in s["known_by"]:
        s["known_by"].append(by)
    s.setdefault("exposures", []).append({"by": by, "via": via, "round": round_no})
    s["state"] = _secret_state(s["known_by"])


def _reply_confirms_exposure(reply, secret, names):
    """确定性校验：LLM 报出的 secret_exposures 只有在本轮回复确实写出
    「秘密事实内容」+「明确的信息获取/发现动作」时才采信，否则视为误判丢弃。

    拦截原 reflect 的激进误判：角色仅按自身 short_goal 行事（如分配守夜、
    私下拉拢）并未真的"发现"秘密时，不应翻暴露状态。

    names：在场角色名集合，用于剔除秘密 keys 中的人名（避免"高洋"等名字本身命中）。
    """
    r = reply or ""
    # (1) 秘密内容信号：剔除人名后、长度>=2 的事实性触发词出现于回复
    fact_keys = [k for k in secret.get("keys", []) if k not in names and len(k) >= 2]
    if not any(k in r for k in fact_keys):
        return False
    # (2) 明确的信息获取/发现动作
    return any(v in r for v in DISCOVERY_VERBS)


# ---- A5 机会等级信号词与判定 ----
REL_STRONG = ["做爱", "上床", "睡过", "上过", "发生过关系", "性关系", "同床", "恋人",
              "情人", "夫妻", "占有她", "属于我", "属于他", "肉体", "偷情"]
REL_MID = ["暗恋", "喜欢", "心动", "独占欲", "占有欲", "亲密", "身体接触", "抱过",
           "吻过", "暧昧", "动情", "想要", "渴望", "贪图", "眷恋", "沉迷"]
BODY_STRONG = ["阴道", "鸡巴", "阴茎", "阳具", "穴", "插入", "进入", "高潮", "抽送",
               "射精", "交合", "做爱", "上床", "性器", "肉棒"]
BODY_MID = ["压在身下", "按在身下", "按在", "压在", "吻", "脱掉", "脱了", "脱去",
            "衣服", "胸", "腰", "抱紧", "骑", "跨坐", "贴", "湿润", "呻吟", "腿间",
            "抚摸", "舔", "含住", "顶住"]

# 同形中性词：含 BODY_STRONG 里的单字「穴」但毫无性含义，末日/野外题材高频出现。
# 判定前必须先剔除，否则「墓穴 / 洞穴 / 穴位」会被误判为性行为越线，
# 进而误记关系后果旧账、误触发事后余韵压制。
NEUTRAL_HOMONYMS = ["墓穴", "巢穴", "洞穴", "穴居", "穴位", "点穴", "太阳穴",
                    "涌泉穴", "虎穴", "匪穴", "蚁穴", "孔穴", "陵穴", "窟穴"]


def strip_neutral(text):
    """剔除同形中性词后再做尺度判定（见 NEUTRAL_HOMONYMS）。"""
    t = text or ""
    for w in NEUTRAL_HOMONYMS:
        t = t.replace(w, "")
    return t
_OPP_ORDER = {"无": 0, "试探": 1, "半步": 2, "满机会": 3}

# 性行为发生后进入"事后"阶段的回合数（余韵/对话/关系变化，不推进性行为）
AFTERMATH_ROUNDS = 2


def _opp_max(a, b):
    return b if _OPP_ORDER.get(b, 0) > _OPP_ORDER.get(a, 0) else a


# 关系文本中的强/中亲密度词：被 reflect 写回的关系若夹带这些动作词（如“偷情了一晚”），
# 会被 _opp_from_relations 永久误判为满机会/半步，造成机会等级锁死——一旦亲密，永远满机会，
# 之后任何把焦点移开的扰动指令都会被模型无视。写回时剥离这些词，保留关系定位语义。
_REL_TAINT = REL_STRONG + REL_MID


def _sanitize_relation(text):
    """reflect 写回关系时，剥离 REL_STRONG/REL_MID 动作词，避免机会等级被叙事污染后锁死。"""
    t = text or ""
    for w in _REL_TAINT:
        t = t.replace(w, "")
    return t.strip(" 、，。,.;；:：")


def _opp_from_relations(snap, present):
    """关系亲密度信号 -> 机会等级。"""
    rel_text = " ".join(snap.get("relations", {}).values())
    if any(k in rel_text for k in REL_STRONG):
        return "满机会"
    if any(k in rel_text for k in REL_MID):
        return "半步"
    return "无"


def _opp_from_secrets(snap, present):
    """在场角色持有他者已暴露秘密（把柄/胁迫）-> 满机会。"""
    for s in snap.get("secrets", []):
        if s.get("state") != "潜伏":
            holders = [k for k in s.get("known_by", []) if k != ENV_PUSHER and k in present]
            if holders:
                return "满机会"
    return "无"


def _opp_from_history(history):
    """近期叙事里的身体接触推进 -> 仅作升温连贯（半步上限），不再永久锁定满机会；满机会由关系/把柄/指令决定。"""
    if not history:
        return "无"
    recent = strip_neutral("\n".join(m.get("content", "") for m in history[-3:]
                                     if isinstance(m, dict)))
    if any(k in recent for k in BODY_STRONG):
        return "半步"
    if any(k in recent for k in BODY_MID):
        return "半步"
    return "无"


# ---- 镜头跟随（焦点）----
# 玩家把扰动引向某个在场子集时，叙事镜头应跟随该子集，其余在场角色视为"在别处待命、
# 不在本回合镜头内"，避免模型死守初始位置、只写留下的戏剧性角色（如怀孕/秘密组）。
# 这是此前"指令指向离开者但叙事不跟随"问题的根因：引擎只有单一 present 名单，
# 缺少"镜头"概念，导致模型在指令点名子集后仍默认全员出场、并偏爱更戏剧的留存组。
_FOLLOW_WORDS = ["两人", "俩人", "2人", "他们", "他俩", "这俩", "那俩", "二人",
                "双方", "两个", "他们俩", "这二人", "那二人"]


def compute_focus(directive, snap):
    """计算本轮镜头焦点（被指令点名/引用的在场子集）。

    返回 {"subjects": [...], "place": "...", "sticky": bool} 或 None。
    - 指令点名一个真子集 -> 镜头跟随该子集（sticky=False）。
    - 指令无点名但含指代代词（两人/他们/...）且上轮有焦点 -> 延续上轮焦点（sticky=True），
      避免"2人逐渐深入"这类后续指令丢失焦点、镜头跳回初始位置。
    - 指令点名全体或无人 -> None，表示自然推演、全员在场皆可写。
    place 取快照当前场景地点（scene.apply 已更新为新地点）。
    """
    present = snap.get("present", [])
    if not present or not directive:
        return None
    named = [n for n in present if n in directive]
    if 0 < len(named) < len(present):
        return {"subjects": named, "place": snap["scene"].get("place", ""), "sticky": False}
    if snap.get("focus") and any(w in directive for w in _FOLLOW_WORDS):
        prev = snap["focus"]
        subs = prev.get("subjects", [])
        if subs and all(s in present for s in subs):
            return {"subjects": subs, "place": snap["scene"].get("place", ""), "sticky": True}
    return None


def brief(sid, directive):
    """返回 (directives, snap)。会就地更新快照里的秘密状态与回合数。

    directive 是环境推手（导演）注入的扰动指令，用来判定本轮机会等级等。
    """
    snap = memory.load(sid)
    text = directive or ""

    # A1 秘密状态机：环境推手主动查（含关键词+信息获取动作）-> 记录环境推手已知。
    # 环境推手是外部观察者，不登场、不说话，其知情不翻 in-world 暴露状态。
    revealed = []
    for s in snap["secrets"]:
        if s["state"] == _FULL:
            continue
        if any(k in text for k in s["keys"]) and any(v in text for v in INFO_VERBS):
            if ENV_PUSHER not in s["known_by"]:
                _record_exposure(s, ENV_PUSHER, "环境推手主动查", snap["scene"]["round"])
                revealed.append(s["owner"])

    # A2 后果账本：命中触发词且未调用的旧账激活
    active = []
    for l in snap["ledger"]:
        if not l.get("last_called") and any(k in text for k in l.get("trigger_keys", [])):
            active.append(l["account"])

    # A4 场景计数
    snap["scene"]["round"] += 1

    # A5 机会等级 + 节奏状态机
    # 综合「关系亲密度 / 秘密把柄胁迫 / 近期叙事推进 / 扰动指令」四类信号取最高。
    # 节奏状态机：上一轮发生性行为 -> 进入"事后"阶段（余韵回合，不推进性行为）。
    present = snap.get("present", [])
    history = memory.load_chat(sid)
    last = history[-1] if history else None
    # 余韵判定基于「事实」（上一轮真的写到了越线），不基于机会等级的许可。
    if last and isinstance(last, dict) and detect_intimacy(last.get("content", "")) == "越线":
        snap["intimacy_phase"] = "aftermath"
        snap["phase_rounds"] = 1
    elif snap.get("intimacy_phase") == "aftermath":
        snap["phase_rounds"] = snap.get("phase_rounds", 0) + 1
        if snap["phase_rounds"] > AFTERMATH_ROUNDS:
            snap["intimacy_phase"] = "normal"
            snap["phase_rounds"] = 0

    opp = "无"
    opp = _opp_max(opp, _opp_from_relations(snap, present))
    opp = _opp_max(opp, _opp_from_secrets(snap, present))
    opp = _opp_max(opp, _opp_from_history(history))
    # 扰动指令：独处→半步；独处+软弱且无干扰→满机会
    if any(c in text for c in ALONE):
        opp = _opp_max(opp, "半步")
        if any(d in text for d in DEFENSE_DOWN) and not any(o in text for o in OBSTACLE):
            opp = _opp_max(opp, "满机会")
    # 扰动指令直接描述身体接触/亲密推进 -> 尊重导演意图
    # （先剔除同形中性词：导演写「躲进洞穴」不是亲密推进）
    tn = strip_neutral(text)
    if any(k in tn for k in BODY_STRONG):
        opp = _opp_max(opp, "满机会")
    elif any(k in tn for k in BODY_MID):
        opp = _opp_max(opp, "半步")
    # 事后阶段：机会等级上限为半步，本轮不推进到性行为
    if snap.get("intimacy_phase") == "aftermath":
        if _OPP_ORDER.get(opp, 0) > 2:
            opp = "半步"

    memory.save(sid, snap)
    return {
        "opportunity": opp,
        "active_consequences": active,
        "revealed_secrets": revealed,
        "goals": snap["goals"],
        "relations": snap["relations"],
        "round": snap["scene"]["round"],
    }, snap


def detect_intimacy(text):
    """检测正文中**实际**写出的亲密程度，返回 越线 / 接触 / 无。

    与机会等级的区分（关键）：机会等级（试探/半步/满机会）是「许可」——允许写到
    该尺度，写不写由剧情定；本函数返回的是「事实」——本轮到底写到了哪一步。
    凡需要"已经发生了什么"的判断（后果留痕、余韵节奏），一律以此为准，
    不能拿机会等级代替，否则"许可发了但剧情没走到"会被误记为既成事实。
    """
    t = strip_neutral(text)
    if any(k in t for k in BODY_STRONG):
        return "越线"
    if any(k in t for k in BODY_MID):
        return "接触"
    return "无"


def after_reply(sid, reply):
    """生成后：本轮**实际**写出越线级亲密内容时，记一条旧账（后果留痕，不重置）。

    只记「越线」不记「接触」：旧账的文案是关系被改写（把柄/伤疤/人情债），对应
    性行为级后果；BODY_MID 词表偏宽（含 衣服/腰/贴 等），据此记账会凭空堆出大量
    轻账，后续命中触发词时整批激活、撑爆提示词。
    许可发了而剧情没走到 -> 不留后果，这正是「许可 ≠ 事实」的落点。
    """
    if detect_intimacy(reply) != "越线":
        return
    snap = memory.load(sid)
    snap.setdefault("ledger", []).append({
        "account": "本轮发生了亲密越线，关系被改写（把柄/伤疤/人情债）",
        "holder": "导演",
        "trigger_keys": ["提起", "旧账", "那晚", "那天", "还记得"],
        "last_called": None,
    })
    memory.save(sid, snap)


def _extract_json(text):
    """从模型可能夹带的文本里抠出第一个完整 JSON 对象。失败返回 None。"""
    if not text:
        return None
    s, e = text.find("{"), text.rfind("}")
    if s == -1 or e == -1 or e <= s:
        return None
    try:
        return json.loads(text[s:e + 1])
    except json.JSONDecodeError:
        return None


def validate_present(reply, present, known_names, allowed=None):
    """后处理：剥离非在场角色的台词块，修掉模型偶发写出已离场角色的出戏问题。

    reply 是"角色名："分段的多说话人叙事。出现在其中的、已知但不在保留集合（默认为
    在场名单 present，或显式传入的 allowed 焦点子集）内的角色台词块（含其续行）会被移除；
    无说话人的叙述行与保留集合内角色台词保留。
    返回 (清洗后文本, 是否发生违例)。
    """
    keep = set(allowed) if allowed else set(present)
    if not reply or not known_names or not keep:
        # 保留集合为空（异常态）时无法校验，原样返回，绝不把整段回复剥空
        return reply, False
    # 长名优先，避免短名误匹配长名前缀（如"老周" vs "老周的朋友"）
    names_sorted = sorted(set(known_names), key=len, reverse=True)
    pat = re.compile(r"^(?:" + "|".join(re.escape(n) for n in names_sorted) + r")\s*[:：]")
    out, dropping, violated = [], False, False
    for ln in reply.split("\n"):
        m = pat.match(ln)
        if m:
            sp = m.group(0).rstrip(" :：")
            if sp not in keep:            # 不在保留集合（含环境推手、已离场角色、镜头外角色）
                dropping, violated = True, True
                continue
            dropping = False
            out.append(ln)
        else:
            if dropping:                   # 被剥离角色的续行
                continue
            out.append(ln)
    return "\n".join(out), violated


def init_relations(cards_present):
    """角色卡未提供初始关系时，由 LLM 根据在场角色设定自动生成初始关系网。

    返回 { "源 → 目标": "描述", ... }；失败或无需生成返回空字典。
    """
    names = list(cards_present.keys())
    if not names:
        return {}
    desc_text = "\n".join(
        f"【{n}】{(cards_present[n].get('description') or '')}｜核心渴望：{(cards_present[n].get('core_desire') or '')}"
        for n in names)
    prompt = [
        {"role": "system",
         "content": "你是关系沙盘的纪官。根据给出的角色设定，生成他们之间的初始关系网。只输出一个 JSON 对象，不要任何解释或 Markdown。"},
        {"role": "user", "content": (
            f"在场角色：{', '.join(names)}\n设定：\n{desc_text}\n\n"
            "请输出 JSON：{ \"relations\": { \"源 → 目标\": \"关系描述\" } }，"
            "覆盖所有有意义的双向关系，键保持\"源 → 目标\"格式。"
        )},
    ]
    try:
        raw = llm.complete(prompt, max_tokens=700, temperature=0.4, timeout=60)
        data = _extract_json(raw)
        if data and isinstance(data.get("relations"), dict):
            return {k: v for k, v in data["relations"].items() if v}
    except Exception:
        pass
    return {}


def reflect(sid, reply):
    """生成后状态回写：根据本轮叙事更新关系、短期目标，并检测潜伏秘密被揭露。

    这是“状态机自动演化”的核心——推演产生的后果必须落回快照，否则次日无痕。
    任何解析/调用失败都保持快照不变，绝不阻塞主流程。
    """
    snap = memory.load(sid)
    if not snap:
        return None
    present = snap.get("present", [])
    if not present:
        return snap

    rel_text = "\n".join(f"{k}: {v}" for k, v in snap["relations"].items()) or "（无）"
    goal_text = "\n".join(f"{k}: {v}" for k, v in snap.get("goals", {}).items()) or "（无）"
    latent_owners = sorted({s["owner"] for s in snap.get("secrets", [])
                            if s.get("state") == "潜伏"})
    secret_text = "、".join(latent_owners) if latent_owners else "（无潜伏秘密）"

    prompt = [
        {"role": "system",
         "content": "你是关系沙盘的纪官。根据本轮叙事，更新各角色的关系与短期目标，抽取本轮各角色的具体行为，并判断是否有潜伏秘密被叙事揭露。只输出一个 JSON 对象，不要任何解释或 Markdown 代码块。"},
        {"role": "user", "content": (
            f"在场角色：{', '.join(present)}\n"
            f"当前关系：\n{rel_text}\n"
            f"当前短期目标：\n{goal_text}\n"
            f"潜伏秘密归属：{secret_text}\n"
            f"本轮叙事：\n{reply}\n\n"
            "请输出 JSON：\n"
            "{\n"
            '  "relations": { "源 → 目标": "关系定性（只写稳定的人物关系定位，如\'妈妈，独占欲\'，不要包含本轮具体动作描写）" },\n'
            '  "actions": { "角色名": "本轮该角色做的一句具体行为（不含关系定性，只写这回合发生了什么）" },\n'
            '  "goals": { "角色名": "新的短期目标" },\n'
            '  "secret_exposures": [{"owner": "被揭露秘密的角色名", "by": "在本轮叙事中得知该秘密的角色名（环境推手主动揭示则写环境推手）"}]\n'
            "}\n"
            "规则：\n"
            "- relations 只写跨回合稳定的关系定性，严禁把本轮动作（如\'靠肩头\'\'护送\'\'命令其回房\'）写进关系描述；关系键保持\"源 → 目标\"格式；只更新确实变化的条目，不要删除未提及的关系。\n"
            "- actions 覆盖本轮所有在场角色的一句行为摘要，用于展示\'这回合谁做了什么\'；这是回合级信息，可每轮整体覆盖。\n"
            "- secret_exposures 只填那些在本轮叙事中其秘密被他人（某在场角色）知晓的条目；by 写得知者角色名，owner 写秘密归属者；环境推手主动揭示时 by 写环境推手。"
        )},
    ]
    try:
        raw = llm.complete(prompt, max_tokens=900, temperature=0.3, timeout=60)
    except Exception:
        return snap
    data = _extract_json(raw)
    if not data:
        return snap

    if isinstance(data.get("relations"), dict):
        for k, v in data["relations"].items():
            if v:
                # 剥离强/中亲密度动作词，防止关系被叙事污染后永久锁死满机会
                snap["relations"][k] = _sanitize_relation(v)
    if isinstance(data.get("actions"), dict):
        snap["actions"] = {k: v for k, v in data["actions"].items() if v}
    if isinstance(data.get("goals"), dict):
        for k, v in data["goals"].items():
            if v:
                snap["goals"][k] = v
    for exp in (data.get("secret_exposures") or []):
        owner = exp.get("owner")
        by = exp.get("by")
        if not owner or not by or by == owner:
            continue
        for s in snap.get("secrets", []):
            if s.get("owner") == owner and by not in s["known_by"]:
                # 确定性校验：回复须同时出现「秘密内容」+「发现动作」，否则视为 LLM 误判丢弃。
                if _reply_confirms_exposure(reply, s, set(present)):
                    _record_exposure(s, by, "叙事揭露", snap["scene"]["round"])
    memory.save(sid, snap)
    return snap
