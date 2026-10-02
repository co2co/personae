"""导演简报：生成前读快照+core，跑 6 项检查，产出内部 brief 与注入指令。

规则版（不额外调 LLM），保证速度；后续可把 A5/A6 换成 LLM 判定，接口不变。
"""

import json
import re

import memory
import llm

ENV_PUSHER = "环境推手"

# ---- 举证式归档（记录员模式）----
# 引擎不做语义判定："正文里有没有发生一次发现"是语义问题，交给 LLM 判断；
# 引擎只做结构校验，验证 LLM 上报的内容确实在正文里出现过（防幻觉）。
# 早先用关键词词表做语义判定（INFO_VERBS + DISCOVERY_VERBS + secret.keys）时，
# 末日题材的高频词（绷带/小臂/发烧/通风口/女儿）与"看见/察觉/露出"极易巧合共现，
# 实测 150 次判定放行 33 次（22%），校验形同虚设。详见 DEVLOG v0.5.8。
EVIDENCE_MIN_LEN = 8

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


def _secret_state(leverage):
    """in-world 暴露状态：只要有人握有该秘密作为把柄（leverage 非空）即为「暴露」；
    仅环境推手/无人握把柄则「潜伏」。leverage 传 holders（握把柄者），
    与 known_by（知情者）分离——信息不可逆，但把柄可失去。"""
    return "暴露" if any(k != ENV_PUSHER for k in leverage) else "潜伏"


def _record_exposure(s, by, via, round_no):
    """记录一次秘密曝光：写入知情者集合与把柄持有集合，并重算暴露状态。

    全版语义：曝光 = 某人得知秘密 = 同时成为知情者(known_by)与把柄持有者(holders)。
    known_by 不可逆（知道了就无法不知道），holders 可因把柄消除而移除。
    """
    s.setdefault("holders", list(s.get("known_by", [])))
    if by not in s["known_by"]:
        s["known_by"].append(by)
    if by not in s["holders"]:
        s["holders"].append(by)
    s.setdefault("exposures", []).append({"by": by, "via": via, "round": round_no})
    s["state"] = _secret_state(s["holders"])


def _release_handle(s, frm, to, round_no):
    """把柄失效/转手（全版）：仅操作 holders（握把柄者），known_by（知情者）不变。

    to 为空表示彻底失去（药物被丢弃、证据被销毁、当众说开后不再构成胁迫）。
    holders 清空时 _secret_state 自动回落「潜伏」——这是「机会等级永久锁死」三因素中
    「秘密暴露后无回落路径」这一项的修复。known_by 不移除（信息不可逆）。
    返回 True 表示确有变更。
    """
    s.setdefault("holders", list(s.get("known_by", [])))
    hb = s["holders"]
    if frm not in hb:
        return False
    hb = [k for k in hb if k != frm]
    if to and to != s.get("owner") and to not in hb:
        hb.append(to)
    s["holders"] = hb
    s["state"] = _secret_state(hb)
    s.setdefault("releases", []).append(
        {"from": frm, "to": to or None, "via": "把柄失效/转手", "round": round_no})
    return True


def _evidence_ok(evidence, reply):
    """结构校验：LLM 的举证必须是本轮正文的原文片段。

    这是记录员模式的全部判定——引擎不猜"这算不算发现"，只验证举证确实出自正文
    （防幻觉编造）。语义判断由 reflect 的 LLM 承担，证据由它自己引用。

    举证缺失或不匹配时丢弃该条目：宁可漏记（状态滞后），不可误记
    （秘密提前暴露 -> 张力提前消耗、机会等级被顶格）。
    """
    e = (evidence or "").strip()
    if len(e) < EVIDENCE_MIN_LEN:
        return False
    return e in (reply or "")


# ---- 身体接触词表（尺度判定用，与关系亲密度无关；关系亲密度路径已废弃）----
# 性行为/性器官明确词：仅用于「事实越线」判定（detect_intimacy）与导演意图信号。
# 刻意不含「进入」「穴」等极通用词——「进入房间/下水道」是纯动作，「穴」单字中性义
# （穴位/巢穴/洞穴，虽已剔除常见组合仍有遗漏）会大规模误判越线，进而触发事后余韵
# 压制（把满机会强制压半步）与虚假亲密旧账。轻写法「进入身体」由 _sexual_entry 单独识别。
BODY_STRONG = ["阴道", "鸡巴", "阴茎", "阳具", "插入", "高潮", "抽送",
               "射精", "交合", "做爱", "上床", "性器", "肉棒"]
BODY_MID = ["压在身下", "按在身下", "吻", "脱掉", "脱了", "脱去",
            "抱紧", "骑", "跨坐", "腿间", "抚摸", "舔", "含住", "顶住", "呻吟"]

# ---- 满机会触发源（补充：双向好感 / 暴力强迫胁迫）----
# ① 双向好感/恋爱：镜头内一对角色为恋人/互有好感 -> 满机会（正向亲密推进的自然结果）
STRONG_AFFECTION = ["恋人", "相爱", "两情相悦", "互许", "定情", "伴侣", "夫妻",
                    "圆房", "身心相许", "热恋", "互有好感", "彼此喜欢",
                    "两心相悦", "相爱多年", "未婚夫妻", "情人"]
# 单向暧昧/暗恋 -> 半步（升温，不强制满机会，避免两个仅微有好感的人直接跳到性行为）
SOFT_AFFECTION = ["暗恋", "暧昧", "心动", "倾心", "在意", "眷恋", "恋慕",
                  "好感", "喜欢", "钟情", "倾慕"]
# ③ 第三方/对方暴力或强迫胁迫 -> 满机会（陌生男人性侵类场景）
# 直接点名性暴力的词单独出现即触发；其它暴力/强迫词需伴随性语境词才触发，
# 避免「强盗用枪威胁交钱」这类非性胁迫误开 NSFW 尺度。
DIRECT_ASSAULT = ["强暴", "强奸", "性侵", "奸污", "猥亵", "非礼"]
COERCION_FORCE = ["强迫", "威胁", "强行", "按住", "揪住", "拖进", "拖走", "压在墙上",
                  "压住", "捆住", "绑住", "刀抵", "刀架", "枪指", "劫持", "被迫",
                  "勒令", "掐住", "制服", "控制住", "锁住", "堵住嘴", "逼", "施暴"]
COERCION_SEXUAL = BODY_MID + BODY_STRONG + [
    "衣服", "脱", "撕", "唇", "腿", "腰", "胸", "私处", "下身", "肌肤",
    "赤裸", "就范", "身子", "强暴"]

# 导演意图信号：玩家在指令里明确推进到性行为（「进入」+身体/性语境）才给满机会；
# 纯场景移动（进入房间/下水道/车厢）不含身体语境，不应误判为亲密推进。
# 注意：本函数只用于 brief 的「导演意图」信号，不用于 detect_intimacy 的「事实越线」
# 判定——轻写法「进入身体」不算充分越线，不应触发事后余韵压制（见 MEMORY 许可≠事实）。
def _sexual_entry(text):
    """指令里玩家明确推进性行为（「进入」+身体/性语境）才算满机会信号。

    纯场景移动（进入房间/下水道）不含身体语境，不算。用于尊重导演意图：
    玩家写「男人进入了苏曼的身体」应给满机会，写「众人进入了下水道」不应。
    """
    t = text or ""
    if "进入" not in t:
        return False
    if "进入她" in t or "进入他" in t:
        return True
    return bool(re.search(r"进入[^，。；！？\n]{0,10}(身体|私处|下身|腿间|阴道|穴|里面)", t))


# 「插入」极通用：插入空间 / 插入话题 / 插入U盘 / 插入钥匙 都是非性语境，若与
# 「阴道 / 鸡巴」等其它 BODY_STRONG 同列会误判越线（会话 0ac57abf 第 2 轮
# "强行插入他们之间的空间" 即触发假越线并误记旧账）。仅"插入 + 身体/性语境"
# 才视为事实越线，与 _sexual_entry 同源（许可≠事实、通用词须加语境）。
def _sexual_insert(text):
    """「插入」只在伴随身体/性语境时算事实越线，否则（插入空间/话题/钥匙）不算。"""
    t = text or ""
    if "插入" not in t:
        return False
    # 注意 "插入他" 不能误匹配 "插入他们"（插入他们之间 = 空间隐喻），用负向先行排除"们"
    if re.search(r"插入他(?!们)", t) or re.search(r"插入她(?!们)", t) or re.search(r"插入我(?!们)", t):
        return True
    return bool(re.search(
        r"插入[^，。；！？\n]{0,12}(身体|体内|私处|下身|腿间|阴道|穴|后庭|菊|性器|"
        r"肉棒|阴茎|阳具|肛门|里面|深处|小腹)", t))

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




def _opp_from_secrets(snap, present, scope=None):
    """把柄胁迫 -> 满机会。**成对作用域**：只对「持有者 ↔ 归属者」这一对生效。

    把柄是成对关系，不该波及全场：阿杰握着高洋的把柄，与苏曼对老周无关。
    scope 为本轮镜头主角（focus.subjects）；仅当某一对的持有者与归属者
    **同在镜头内**时才构成当轮胁迫。未给 scope（自然推演、全员皆可写）时
    退回全场判定。
    """
    for s in snap.get("secrets", []):
        if s.get("state") == "潜伏":
            continue
        owner = s.get("owner")
        holders = [k for k in (s.get("holders") or s.get("known_by", []))
                   if k != ENV_PUSHER and k != owner and k in present]
        if not holders:
            continue
        if scope is None:
            return "满机会"
        for h in holders:
            if h in scope and owner in scope:
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


def _opp_from_affection(snap, scope):
    """① 双向好感/恋爱关系 -> 满机会（正向亲密推进）；单向暧昧/暗恋 -> 半步（升温）。

    关系亲密度路径此前废弃（好感度系统下线），但 snap["relations"] 仍由 reflect 的 LLM
    写入自由文本关系描述（如「恋人」「暗恋多年」）。这里补回「关系 -> 机会等级」的读取，
    让互有好感成为满机会的合法触发源之一。

    作用域：仅当关系两端（源与目标）同处镜头内（scope）或全场（scope=None 且两端都在场）
    时才对该对生效，避免镜头外的恋人误给全场满机会。relations 键形如「源 → 目标」，
    两端名与描述值都参与情感词匹配（描述里常写「恋人」「暗恋」）。
    """
    rels = snap.get("relations") or {}
    if not rels:
        return "无"
    best = "无"
    for key, val in rels.items():
        text = f"{key} {val}"
        # 解析两端角色名（键形如「源 → 目标」，兼容「->」）
        norm = key.replace("\u2192", "->")
        parts = [p.strip() for p in norm.split("->")] if "->" in norm else [key.strip()]
        a, b = (parts[0], parts[-1]) if len(parts) >= 2 else (parts[0], "")
        if scope is not None:
            if not (a in scope and b in scope):
                continue
        elif a and b and (a not in snap.get("present", [])
                          or b not in snap.get("present", [])):
            continue
        if any(k in text for k in STRONG_AFFECTION):
            best = _opp_max(best, "满机会")
        elif any(k in text for k in SOFT_AFFECTION):
            best = _opp_max(best, "半步")
    return best


def _opp_from_coercion(directive):
    """③ 第三方/对方暴力或强迫胁迫 -> 满机会（陌生男人性侵类场景）。

    直接点名性暴力的词（强暴/强奸/性侵/奸污/猥亵/非礼）单独出现即触发；
    其它暴力/强迫词（按住/揪住/刀抵/威胁/拖进…）需同时出现性语境词
    （身体/脱衣/腿/胸/衣服…或 BODY_MID/STRONG）才触发，
    避免「强盗用枪威胁交钱」这类非性胁迫误开 NSFW 尺度。
    纯场景移动（进入房间/下水道）不含身体语境，本函数不触发。
    """
    t = strip_neutral(directive or "")
    if any(k in t for k in DIRECT_ASSAULT):
        return "满机会"
    if any(k in t for k in COERCION_FORCE) and any(k in t for k in COERCION_SEXUAL):
        return "满机会"
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

    # A1（已移除）：原「指令含 keys + INFO_VERBS -> 记环境推手已知」是纯猜测——
    # 导演写"翻找"不代表真发现了什么。且其知情本就不翻 in-world 暴露状态
    # （_secret_state 剔除 ENV_PUSHER），删掉只在前端少一条展示，无实质损失。
    # 秘密的一切状态变更改由生成后 reflect 按正文举证归档（记录员模式）。
    revealed = []

    # A2 后果账本：命中触发词且未调用的旧账激活
    active = []
    for l in snap["ledger"]:
        if not l.get("last_called") and any(k in text for k in l.get("trigger_keys", [])):
            active.append(l["account"])

    # A4 场景计数
    snap["scene"]["round"] += 1

    # A5 机会等级 + 节奏状态机
    # 综合五类信号取最高（满机会 = 本轮剧情被许可写到性行为尺度上限）：
    #   ① 双向好感/恋爱关系（_opp_from_affection）
    #   ② 秘密把柄胁迫（_opp_from_secrets，成对作用域）
    #   ③ 第三方/对方暴力强迫胁迫（_opp_from_coercion，陌生男人性侵类）
    #   ④ 近期叙事推进的升温连贯（_opp_from_history，上限半步）
    #   ⑤ 扰动指令（独处脆弱 / 导演明写性）
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
    # 镜头主角（成对信号的作用域）：app 已算好写回 snap["focus"]
    scope = (snap.get("focus") or {}).get("subjects")
    # ① 把柄成对胁迫 -> 满机会
    opp = _opp_max(opp, _opp_from_secrets(snap, present, scope))
    # ② 双向好感/恋爱 -> 满机会；单向暧昧 -> 半步
    opp = _opp_max(opp, _opp_from_affection(snap, scope))
    # ③ 第三方/对方暴力强迫胁迫 -> 满机会（陌生男人性侵类）
    opp = _opp_max(opp, _opp_from_coercion(text))
    opp = _opp_max(opp, _opp_from_history(history))
    # 扰动指令：独处→半步；独处+软弱且无干扰→满机会
    if any(c in text for c in ALONE):
        opp = _opp_max(opp, "半步")
        if any(d in text for d in DEFENSE_DOWN) and not any(o in text for o in OBSTACLE):
            opp = _opp_max(opp, "满机会")
    # 扰动指令直接描述身体接触/亲密推进 -> 尊重导演意图
    # （先剔除同形中性词：导演写「躲进洞穴」不是亲密推进）
    tn = strip_neutral(text)
    # 导演意图信号：玩家直接在指令里推进到性行为（进入+身体/性语境）给满机会，
    # 纯场景移动（进入房间/下水道）不含身体语境则不给——否则误把普通移动当满机会。
    if any(k in tn for k in BODY_STRONG) or _sexual_entry(tn):
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


# 拒写/否定语境里的性词不算「事实越线」：模型拒绝描写时若在拒写文本里提到
# 「插入/性交」等词（如「我不能写强制插入内容」），会被误判为已发生，进而错误
# 记亲密旧账 + 触发事后余韵压制（把满机会强制压半步）。剔除含元层拒写标记的整句
# 后再判定；只剔拒写句，不伤世界内叙事（「他没有停下，继续插入她」不含拒写标记，
# 照常判越线）。这正是对「进入」误判的同源修复：事实判定须排除非叙事语境。
REFUSAL_MARKERS = ["抱歉", "我不能", "我无法", "我拒绝", "不能写", "不会按", "不按",
                   "无法按", "避免写", "避免露骨", "改写成", "改写此", "改为双方",
                   "不描写", "拒绝写", "不能按此", "不愿按", "不按你", "不按这条"]


def _mask_refusal(text):
    """返回剔除「元层拒写句」后的文本，供 detect_intimacy 的事实判定使用。"""
    parts = re.split(r"[。！？\n；;]", text or "")
    return "".join(p for p in parts if not any(m in p for m in REFUSAL_MARKERS))


def detect_intimacy(text):
    """检测正文中**实际**写出的亲密程度，返回 越线 / 接触 / 无。

    与机会等级的区分（关键）：机会等级（试探/半步/满机会）是「许可」——允许写到
    该尺度，写不写由剧情定；本函数返回的是「事实」——本轮到底写到了哪一步。
    凡需要"已经发生了什么"的判断（后果留痕、余韵节奏），一律以此为准，
    不能拿机会等级代替，否则"许可发了但剧情没走到"会被误记为既成事实。
    事实判定先剔除元层拒写句（_mask_refusal），避免拒写文本里的性词被当既成事实。
    """
    t = strip_neutral(_mask_refusal(text))
    # 「插入」极通用，需性语境才判越线（见 _sexual_insert）；其余 BODY_STRONG 照旧
    if "插入" in t and _sexual_insert(t):
        return "越线"
    if any(k in t for k in BODY_STRONG if k != "插入"):
        return "越线"
    if any(k in t for k in BODY_MID):
        return "接触"
    return "无"


def after_reply(sid, reply):
    """生成后：本轮**实际**写出越线级亲密内容时，记一条旧账（后果留痕，不重置）。

    只记「越线」不记「接触」：旧账的文案是关系被改写（把柄/伤疤/人情债），对应
    性行为级后果。BODY_MID 已收窄为明确接触动作（压在身下/按在身下/吻/抱紧/骑/跨坐/
    腿间/抚摸/舔/含住/顶住/呻吟），移除「按在/压在/衣服/贴/湿润/胸/腰」等末日题材
    高频中性词，避免误抬半步与凭空轻账。【v0.6.2 增补：T3 已解决】
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


def seed_relations_from_cards(cards_present):
    """从角色卡自带的 relations 字段确定性地构建初始关系表（"源 → 目标": 描述）。

    这是 simon 在角色卡里**显式写下**的关系网，作为权威基线（relations_base），
    优先级高于 LLM 自由生成——避免 LLM 把"小姨子"推成"妻子"之类漂移。
    卡片 relations 字段形如 { "周牧野": "丈夫…", "林梦琪": "妹妹…" }，
    逐条转成 "{卡名} → {目标}": 描述。
    """
    out = {}
    for c, card in (cards_present or {}).items():
        rels = card.get("relations") or {}
        if not isinstance(rels, dict):
            continue
        for target, desc in rels.items():
            if not target or not desc:
                continue
            out[f"{c} → {target}"] = desc
    return out


def init_relations(cards_present):
    """构建初始关系网：以角色卡 relations 字段为权威基线，LLM 仅补卡片未覆盖的空缺。

    返回 { "源 → 目标": "描述", ... }；全失败时返回空字典。
    """
    names = list(cards_present.keys())
    if not names:
        return {}
    base = seed_relations_from_cards(cards_present)
    desc_text = "\n".join(
        f"【{n}】{(cards_present[n].get('description') or '')}｜核心渴望：{(cards_present[n].get('core_desire') or '')}"
        for n in names)
    prompt = [
        {"role": "system",
         "content": "你是关系沙盘的纪官。根据给出的角色设定，补充生成他们之间尚未写明的关系网。只输出一个 JSON 对象，不要任何解释或 Markdown。"},
        {"role": "user", "content": (
            f"在场角色：{', '.join(names)}\n设定：\n{desc_text}\n\n"
            "已确定的关系（不要重复，仅补充缺失的双向关系）：\n"
            + ("\n".join(f"{k}: {v}" for k, v in base.items()) if base else "（无）")
            + "\n\n请输出 JSON：{ \"relations\": { \"源 → 目标\": \"关系描述\" } }，"
            "覆盖所有有意义的双向关系，键保持\"源 → 目标\"格式；已确定的关系不要再输出。"
        )},
    ]
    try:
        raw = llm.complete(prompt, max_tokens=700, temperature=0.4, timeout=60)
        data = _extract_json(raw)
        if data and isinstance(data.get("relations"), dict):
            llm_rel = {k: v for k, v in data["relations"].items() if v}
            # 卡片显式关系优先，LLM 仅补缺
            return {**llm_rel, **base}
    except Exception:
        pass
    return dict(base)


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
    # 秘密全景（含已被谁知情）：把柄可失去/转手，纪官必须知道当前持有情况
    sec_lines = []
    for s in snap.get("secrets", []):
        kb = [k for k in (s.get("holders") or s.get("known_by", [])) if k != ENV_PUSHER]
        sec_lines.append(f"{s.get('owner')}（{s.get('state')}｜握有把柄者："
                         f"{'、'.join(kb) if kb else '无'}）")
    secret_text = "\n".join(sec_lines) or "（无秘密）"

    prompt = [
        {"role": "system",
         "content": "你是关系沙盘的纪官。根据本轮叙事，更新各角色的关系与短期目标，抽取本轮各角色的具体行为，并归档秘密的知情变化。只输出一个 JSON 对象，不要任何解释或 Markdown 代码块。"},
        {"role": "user", "content": (
            f"在场角色：{', '.join(present)}\n"
            f"当前关系：\n{rel_text}\n"
            f"当前短期目标：\n{goal_text}\n"
            f"秘密与把柄现状：\n{secret_text}\n"
            f"本轮叙事：\n{reply}\n\n"
            "请输出 JSON：\n"
            "{\n"
            '  "relations": { "源 → 目标": "关系定性（只写稳定的人物关系定位，如\'妈妈，独占欲\'，不要包含本轮具体动作描写）" },\n'
            '  "actions": { "角色名": "本轮该角色做的一句具体行为（不含关系定性，只写这回合发生了什么）" },\n'
            '  "goals": { "角色名": "新的短期目标" },\n'
            '  "secret_exposures": [{"owner": "秘密归属者", "by": "本轮得知该秘密的角色名", "evidence": "本轮叙事原文片段"}],\n'
            '  "handle_releases": [{"owner": "秘密归属者", "from": "失去把柄的人", "to": "接过把柄的人（彻底失去则填空字符串）", "evidence": "本轮叙事原文片段"}]\n'
            "}\n"
            "规则：\n"
            "- relations 只写跨回合稳定的关系定性，严禁把本轮动作（如\'靠肩头\'\'护送\'\'命令其回房\'）写进关系描述；关系键保持\"源 → 目标\"格式；只更新确实变化的条目，不要删除未提及的关系。\n"
            "- actions 覆盖本轮所有在场角色的一句行为摘要，用于展示\'这回合谁做了什么\'；这是回合级信息，可每轮整体覆盖。\n"
            "- secret_exposures 只填本轮叙事里**确实发生**了「某人得知了某秘密」的条目；仅凭角色起了疑心、或只是提到相关物品，都不算。\n"
            "- handle_releases 只填本轮叙事里**确实发生**了「把柄消失或转手」的条目：例如药物/证据/信件被丢弃、被夺走、交给第三方、或当众说开后不再构成胁迫。to 为空字符串表示彻底消失。\n"
            "- evidence **必须逐字照抄**本轮叙事中的一段连续原文（不要改写、不要概括），引擎会核验它是否真的出现在叙事里；照抄不到原文就不要填该条目。\n"
            "- 宁可少填也不要误填：填错会让秘密提前暴露或让把柄凭空失效。"
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
        base = snap.get("relations_base") or {}
        present_set = set(present)
        for k, v in data["relations"].items():
            if not v:
                continue
            # 关系键形如 "源 → 目标"；解析两端点
            parts = [e.strip() for e in k.split("→")] if "→" in k else [k.strip()]
            ends = [p for p in parts if p]
            if len(ends) >= 2 and all(e in present_set for e in ends):
                # 两端都在场（镜头内角色）：允许关系随剧情演化
                snap["relations"][k] = v
            else:
                # 涉及未在场/无卡关联人物（如林梦琪）：冻结为初始关系定位，
                # 禁止模型改写或升级（"小姨子"被写成"妻子"类漂移即在此拦截）。
                # 初始表无此键则丢弃该越权关系，不引入新条目。
                if k in base:
                    snap["relations"][k] = base[k]
    if isinstance(data.get("actions"), dict):
        snap["actions"] = {k: v for k, v in data["actions"].items() if v}
    if isinstance(data.get("goals"), dict):
        for k, v in data["goals"].items():
            if v:
                snap["goals"][k] = v
    # 秘密：举证式归档（记录员模式）——引擎不猜，只核验证据是否出自正文
    for exp in (data.get("secret_exposures") or []):
        owner = exp.get("owner")
        by = exp.get("by")
        if not owner or not by or by == owner:
            continue
        if by != ENV_PUSHER and by not in present:
            continue
        if not _evidence_ok(exp.get("evidence"), reply):
            continue
        for s in snap.get("secrets", []):
            holders = s.setdefault("holders", list(s.get("known_by", [])))
            if s.get("owner") == owner and by not in holders:
                _record_exposure(s, by, "叙事揭露", snap["scene"]["round"])
                break

    # 把柄消除：同样按举证归档。仅操作 holders（握把柄者），known_by 保持不变；
    # holders 清空时 _secret_state 自动回落「潜伏」（状态回落路径）。
    for rel in (data.get("handle_releases") or []):
        owner = rel.get("owner")
        frm = rel.get("from")
        if not owner or not frm:
            continue
        to = (rel.get("to") or "").strip()
        if to == frm:
            continue
        if not _evidence_ok(rel.get("evidence"), reply):
            continue
        for s in snap.get("secrets", []):
            if s.get("owner") == owner and _release_handle(
                    s, frm, to, snap["scene"]["round"]):
                break

    memory.save(sid, snap)
    return snap
