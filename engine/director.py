"""导演简报：生成前读快照+core，跑若干项检查（A2 后果账本激活 / A4 场景计数等），产出内部 brief 与注入指令。

规则版（不额外调 LLM），保证速度。机会等级/内容尺度机制已随 NSFW 整体废弃（v0.8.0），引擎回归中性关系沙盘。
"""

import json
import re

import memory
import llm
import logger
import store

ENV_PUSHER = "环境推手"

# ---- 举证式归档（记录员模式）----
# 引擎不做语义判定："正文里有没有发生一次发现"是语义问题，交给 LLM 判断；
# 引擎只做结构校验，验证 LLM 上报的内容确实在正文里出现过（防幻觉）。
# 早先用关键词词表做语义判定（INFO_VERBS + DISCOVERY_VERBS + secret.keys）时，
# 末日题材的高频词（绷带/小臂/发烧/通风口/女儿）与"看见/察觉/露出"极易巧合共现，
# 实测 150 次判定放行 33 次（22%），校验形同虚设。详见 DEVLOG v0.5.8。
# 下限只用于挡掉「一两个字碰巧命中」的伪举证（如只写「伤口」「他」），不是长度门槛。
# 早前设为 8 会把真实短句误杀——压测实证纪官就死亡举证「没有脉搏。」（5 字，逐字出现在正文），
# 硬常量硬生生漏记。逐字核验本身已足够防伪，故下限压到 4。
EVIDENCE_MIN_LEN = 4

# （机会等级/内容尺度机制已随 NSFW 整体废弃，v0.8.0：ALONE/DEFENSE_DOWN/OBSTACLE/OPP_NOTE 已移除）


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
    # 确知情即结算其起疑记录：起疑是逼近过程，曝光是终点，二者不并存
    _clear_suspicion(s, by)
    s["state"] = _secret_state(s["holders"])


def _ledger_entry(snap, secret, by, round_no):
    """秘密曝光即记一笔后果账——让「被揭开的代价」能跨轮回响。

    账目由导演简报 A2 按触发词激活后注入提示词（此前 active_consequences 只进日志）。
    trigger_keys 复用世界书秘密条目的 keys 字段：该字段在旧词表判定方案废弃后一度成为
    死字段，此处复活为「回响触发词」；keys 为空时退回归属者名字。
    一条秘密对同一知情者只记一次（由 reflect 的 by not in holders 保证）。
    """
    owner = secret.get("owner", "")
    content = (secret.get("content") or "").strip()
    bottom = (secret.get("bottom_line") or "").strip()
    account = f"{owner} 的秘密已被 {by} 知晓（R{round_no}）：{content}"
    if bottom:
        account += f" ｜ 后果底线：{bottom}"
    keys = [k for k in (secret.get("keys") or []) if k]
    if not keys:
        keys = [owner] if owner else []
    entry = {
        "account": account,
        "trigger_keys": keys,
        "round": round_no,
        "source": "secret",
        "owner": owner,
        "by": by,
    }
    snap.setdefault("ledger", []).append(entry)
    return entry


# 每条秘密最多保留的起疑条数：叙事注意力有限，久远的疑点不该一直压着人物。
_SUSPICION_CAP = 4


def _record_suspicion(s, by, clue, round_no):
    """记录一次「起疑」——线索逼近但尚未坐实，是潜伏与曝光之间的中间态。

    曝光是二值且不可逆的，而戏剧张力最足的恰恰是曝光之前那段逼近过程。
    起疑只记「谁、因为什么疑点、在哪一轮」，**绝不存秘密真相**：起疑者尚未证实，
    引擎不得因起疑而剧透全文（信息边界与潜伏期一致）。

    同一人对同一秘密只保留最新一条疑点；一旦他确已知情（曝光），其起疑记录
    由 _record_exposure 结算移除，避免「已知情」与「起疑」两种提示同时注入。
    返回 True 表示确有变更。
    """
    susp = s.setdefault("suspicions", [])
    entry = {"by": by, "clue": (clue or "").strip()[:120], "round": round_no}
    for i, old in enumerate(susp):
        if old.get("by") == by:
            if old.get("clue") == entry["clue"] and old.get("round") == round_no:
                return False
            susp[i] = entry
            return True
    susp.append(entry)
    if len(susp) > _SUSPICION_CAP:
        del susp[:len(susp) - _SUSPICION_CAP]
    return True


def _clear_suspicion(s, by):
    """某人确已知情后结算其起疑记录。

    知情是起疑的终态，两者并存会同时注入「你在怀疑他」与「你握有他的把柄」
    两种提示，自相矛盾。
    """
    susp = s.get("suspicions") or []
    rest = [x for x in susp if x.get("by") != by]
    if len(rest) == len(susp):
        return False
    s["suspicions"] = rest
    return True


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


def _norm_text(s):
    """归一化：折叠所有空白字符。

    纪官引用的原文常带换行/缩进差异（正文里是空行分段，引用时挤成一行），
    逐字比对会被这类纯排版差异误杀，故比对前统一折叠空白。
    注意：只消排版差异，**不消字面差异**——把「她」改写成角色名这类篡改仍会被拒绝。
    """
    return re.sub(r"\s+", "", s or "")


def _evidence_ok(evidence, reply):
    """结构校验：LLM 的举证必须是本轮正文的原文片段。

    这是记录员模式的全部判定——引擎不猜"这算不算发现"，只验证举证确实出自正文
    （防幻觉编造）。语义判断由 reflect 的 LLM 承担，证据由它自己引用。

    举证缺失或不匹配时丢弃该条目：宁可漏记（状态滞后），不可误记
    （秘密提前暴露 -> 张力提前消耗、机会等级被顶格）。
    """
    e = _norm_text(evidence)
    if len(e) < EVIDENCE_MIN_LEN:
        return False
    return e in _norm_text(reply)


# ---- 身体接触词表 / 机会等级触发源已随 NSFW 整体废弃（v0.8.0）----
# 原 BODY_STRONG/BODY_MID/STRONG_AFFECTION/SOFT_AFFECTION/DIRECT_ASSAULT/
# COERCION_FORCE/COERCION_SEXUAL 均为「内容尺度判定」服务，随 nsfw 机制一并移除。
# 引擎回归中性关系沙盘：亲密与否由剧情自然决定，不再由词表驱动尺度信号。

# （_sexual_entry / _sexual_insert / NEUTRAL_HOMONYMS / strip_neutral /
#  _OPP_ORDER / AFTERMATH_ROUNDS / _opp_max 已随 NSFW 整体废弃，v0.8.0）




# （_opp_from_secrets / _opp_from_history / _opp_from_affection / _opp_from_coercion
#  已随 NSFW 废弃，v0.8.0；把柄/胁迫作为关系张力由 reflect 自然演化，不再映射为内容尺度信号）


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
    base = None
    named = [n for n in present if n in directive]
    prev = snap.get("focus") or {}
    if 0 < len(named) < len(present):
        base = {"subjects": named, "place": snap["scene"].get("place", ""), "sticky": False}
    elif (prev.get("forced") and prev.get("sticky")):
        # 上轮因高压秘密锁定了镜头：本轮即便指令没点名、也没指代代词，仍黏住那对焦点人物，
        # 直到碰撞发生（压力归零后 forced 自然消失）。否则导演一句「众人各自行动」就会把
        # 还没撞开的高压镜头打散，张力又断线。这里不依赖 _FOLLOW_WORDS，是高压锁定专属延续。
        subs = prev.get("subjects", [])
        if subs and all(s in present for s in subs):
            base = {"subjects": subs, "place": snap["scene"].get("place", ""), "sticky": True}
    elif prev and any(w in directive for w in _FOLLOW_WORDS):
        subs = prev.get("subjects", [])
        if subs and all(s in present for s in subs):
            base = {"subjects": subs, "place": snap["scene"].get("place", ""), "sticky": True}
    # 高压秘密的双方强制进镜头：否则当事人被判「镜头外不许写」，压力永远撞不出来
    return _merge_pressure_into_focus(base, snap, present)


def brief(sid, directive):
    """返回 (directives, snap)。会就地更新快照里的秘密状态与回合数。

    directive 是环境推手（导演）注入的扰动指令，用于驱动本轮推演。
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
            # 激活即结算：一条旧账只回响一次。此前从不写 last_called，命中后会每轮
            # 重复激活、把旧账变成常驻噪音（因账本本就无写入者，该问题从未暴露）。
            l["last_called"] = snap["scene"]["round"] + 1

    # A4 场景计数
    snap["scene"]["round"] += 1

    # A5 机会等级/内容尺度机制已随 NSFW 整体废弃（v0.8.0）：引擎回归中性关系沙盘，
    # 不再注入内容尺度信号、不再跑机会等级判定与余韵状态机。

    memory.save(sid, snap)
    return {
        "active_consequences": active,
        "revealed_secrets": revealed,
        "goals": snap["goals"],
        "relations": snap["relations"],
        "round": snap["scene"]["round"],
    }, snap


# （REFUSAL_MARKERS / _mask_refusal / detect_intimacy / after_reply 已随 NSFW 废弃，v0.8.0；
#  中性后果留痕由 ledger + A2 激活路径覆盖，不再绑定性行为「越线」判定）


def _salvage_json(text):
    """抢救被 max_tokens 截断的半成品 JSON：保留已完整输出的成员，丢弃半截那个。

    纪官输出条目多（关系/行动/目标/秘密三类/事实两层），一旦超出 max_tokens，
    尾部会在字符串中间被切断，整体解析失败、整轮回写全丢——比丢一两条严重得多。
    这里沿字符流跟踪括号深度与字符串状态，回退到最后一个完整成员的末尾再补 '}'。

    只接受深度回到 1（顶层对象内、成员之间）的位置，避免切进未闭合的子结构。
    """
    s = text.strip()
    if not s.startswith("{"):
        return None
    depth = 0
    in_str = False
    esc = False
    cut = -1                      # 最后一个完整成员的结束下标（不含）
    i = 0
    while i < len(s):
        ch = s[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch in "{[":
                depth += 1
            elif ch in "}]":
                depth -= 1
                if depth < 0:
                    return None           # 括号不配对，放弃抢救
                if depth == 1 and ch == "}":
                    cut = i + 1           # 刚闭合一个顶层成员
            elif ch == "," and depth == 1:
                cut = i                   # 成员分隔符：其前是完整成员
        i += 1
    # 不要求末尾深度回到 1：截断本就发生在任意深度，只要找到最后一个完整成员即可。
    # 卡在字符串里也不影响——cut 停在此前一个已闭合的成员末尾，切掉半截即可。
    if cut <= 1:
        return None                           # 连一个完整成员都没有
    try:
        return json.loads(s[:cut] + "}")
    except json.JSONDecodeError:
        return None


def _is_complete_json(text):
    """判断模型输出里的 JSON 是否完整（未被 max_tokens 截断）。"""
    if not text:
        return False
    s, e = text.find("{"), text.rfind("}")
    if s == -1 or e == -1 or e <= s:
        return False
    try:
        json.loads(text[s:e + 1])
        return True
    except json.JSONDecodeError:
        return False


def _extract_json(text):
    """从模型可能夹带的文本里抠出第一个完整 JSON 对象。失败返回 None。

    整体解析失败时先尝试抢救被截断的部分（见 _salvage_json）：纪官回写宁可少记一两条，
    也不能因为尾部半句话就把整轮的关系/行动/事实全丢掉。
    """
    if not text:
        return None
    s, e = text.find("{"), text.rfind("}")
    if s == -1 or e == -1 or e <= s:
        return None
    try:
        return json.loads(text[s:e + 1])
    except json.JSONDecodeError:
        return _salvage_json(text[s:])


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
    # 长名优先，避免短名误匹配长名前缀（如 "X" vs "X的朋友"）
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


# ---- 会话级辅助群演注册表（aux registry）----
# 导演/叙事在推演中刻意引入的临时辅助角色（如半路加入的配角）：随会话存续，不进角色卡库、
# 不进世界书、不进分发 zip。作用：① 被引擎识别（不误判为模型幻觉或背景人物活动化）；
# ② 跨回合名字与身份一致（continuity）；③ 存活于快照、便于复盘，但不污染 DEMO 红线。
_AUX_BEAT_WORDS = {
    "小声", "低声", "轻声", "大声", "旁白", "此时", "片刻", "突然", "接着", "随后",
    "于是", "然而", "可是", "但是", "原来", "现在", "之后", "之前", "不久", "很快",
    "终于", "其实", "显然", "看来", "似乎", "突然间", "那一刻", "与此同时", "过了一会",
    "半晌", "良久", "少顷", "俄而", "须臾", "片刻后", "不多时", "话音未落",
    # 元信息/说明前缀（非人名）：避免被误登记为辅助群演
    "提示", "注", "注释", "说明", "规则", "注意", "备注", "解说", "字幕", "画外音",
    "系统", "导演", "PS", "Ps", "ps", "此处", "这时", "这时", "至此", "总之",
    "换言之", "话说", "且说", "却说", "须知", "概言之",
}
_AUX_SPEAKER_RE = re.compile(r"^([\u4e00-\u9fffA-Za-z·•]{1,8})\s*[:：]")


def discover_aux_speakers(reply, exclude):
    """从本轮叙事里发现尚未登记的「说话人式」名字，作为候选辅助群演。

    exclude：已知名字集合（在场角色 + 角色卡库 + 已登记 aux + 背景人物 + 环境推手），
    这些不算新群演。返回去重后的新名字列表（已排除常见叙事节拍词/元信息前缀，
    仅保留 2~6 字、疑似人名的片段）。
    """
    if not reply:
        return []
    out, seen = [], set(exclude or [])
    for ln in reply.split("\n"):
        m = _AUX_SPEAKER_RE.match(ln.strip())
        if not m:
            continue
        name = m.group(1).strip()
        if not name or name in seen or name in _AUX_BEAT_WORDS:
            continue
        if len(name) > 6 or len(name) < 2:
            continue
        out.append(name)
        seen.add(name)
    return out


def register_aux(snap, names, round_no, notes=None):
    """把若干名字登记进快照 aux 注册表（去重，避免重复登记）。

    notes：可选 {名字: 身份说明}，来自导演显式【引入角色】指令。
    返回新增的名字列表（便于日志与前端呈现）。
    """
    aux = snap.setdefault("aux", [])
    existing = {a.get("name") for a in aux}
    added = []
    notes = notes or {}
    for n in names:
        if not n or n in existing:
            continue
        existing.add(n)
        aux.append({
            "name": n,
            "role": notes.get(n) or "会话群演（导演/叙事引入）",
            "intro_round": round_no,
            "note": "",
            "status": "活跃",
        })
        added.append(n)
    return added


def parse_aux_introductions(directive):
    """解析导演指令里的显式引入标记：【引入角色】名字｜身份：说明。

    返回 [(名字, 身份说明), ...]，供 register_aux 登记。无则空列表。
    该标记仅作服务端登记用途；导演也可直接在叙事里写「名字：」让引擎自动发现。
    """
    if not directive:
        return []
    pat = re.compile(r"【引入角色】\s*([^｜\n]+)\s*(?:｜\s*身份[：:]\s*([^\n]+))?")
    out = []
    for m in pat.finditer(directive):
        name = m.group(1).strip()
        if name:
            out.append((name, (m.group(2) or "").strip()))
    return out


def background_names_from_relations(snap, present):
    """从快照关系表中析出「背景人物」：在 relations 键里出现、但不在在场名单 present 的角色。

    这些角色无独立角色卡（store 不收录），仅在他人 relations 字段/世界书里被定位，
    属于「非在场」背景板。引擎应保证其不被活动化（见 detect_offscreen_activity）。
    """
    present_set = set(present or [])
    rel_names = set()
    for k in (snap or {}).get("relations", {}):
        for e in k.split("→"):
            rel_names.add(e.strip())
    return sorted(n for n in rel_names if n and n not in present_set)


def detect_offscreen_activity(reply, background_names):
    """自检「背景人物是否被活动化」——simon 验收标准：引擎把背景人物写成活动角色即失责。

    仅检测、不删正文（背景被在场角色提及本身是允许的，误删风险高）。返回 (是否失责, 命中行列表)。
    命中两类：
      ① 背景人物获得独立台词块（'背景名：' 起头）——被写了对白/独白；
      ② 第三人称段落以背景人物为主语并含动作/出场信号（如「X从门后走出」）——被写成主角行动。
    """
    if not reply or not background_names:
        return False, []
    names_sorted = sorted(set(background_names), key=len, reverse=True)
    pat = re.compile(r"^(?:" + "|".join(re.escape(n) for n in names_sorted) + r")\s*[:：]")
    action_re = re.compile(r"[走跑走进出开看说笑问拿放抱亲吻摸扯拉推挡站坐躺靠冲望回头转转身来到去迎送探伸]")
    hits = []
    for ln in reply.split("\n"):
        s = ln.strip()
        if not s:
            continue
        if pat.match(ln):                      # ① 独立台词块（对白/独白）
            hits.append(s)
            continue
        # ② 第三人称分句：以背景名作主语且含动作/出场信号（兼顡整段混写无换行的情况）
        for seg in re.split(r"[。！？；\n]", s):
            seg = seg.strip()
            if not seg:
                continue
            for n in names_sorted:
                if seg.startswith(n) and len(seg) > len(n) and action_re.search(seg[len(n):]):
                    hits.append(seg)
                    break
    return (len(hits) > 0), hits


def seed_relations_from_cards(cards_present):
    """从角色卡自带的 relations 字段确定性地构建初始关系表（"源 → 目标": 描述）。

    这是 simon 在角色卡里**显式写下**的关系网，作为权威基线（relations_base），
    优先级高于 LLM 自由生成——避免 LLM 把"小姨子"推成"妻子"之类漂移。
    卡片 relations 字段形如 { "角色A": "丈夫…", "角色B": "妹妹…" }，
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


# 亲属身份词表：关系定性里出现这些词即代表一种「亲属身份定位」。
# 引擎强制冻结其身份——作者定义的血缘/姻亲关系（父子、母子等）是固定事实，
# 模型只能演化情感/状态修饰，不得把「父亲」改写成「姐夫/嫂子」之类导致乱伦逻辑崩塌。
# 注意：恋人/情人等「关系状态」不在冻结之列（沙盘本就要演好感→恋人），只冻结亲属身份。
_KINSHIP_TOKENS = [
    "父亲", "母亲", "儿子", "女儿", "丈夫", "妻子", "哥哥", "弟弟", "姐姐", "妹妹",
    "叔叔", "舅舅", "姑姑", "阿姨", "侄子", "外甥", "公公", "婆婆", "媳妇", "女婿",
    "爷爷", "奶奶", "孙子", "孙女", "外公", "外婆", "姐夫", "嫂子", "妹夫", "弟妹",
    "连襟", "妯娌", "养父", "养母", "继父", "继母", "兄长", "爸爸", "妈妈", "爹爹",
    "娘亲", "老婆", "老公", "老爸", "老妈",
    "父", "母", "子", "女", "夫", "妻", "兄", "弟", "姐", "妹",
    "叔", "舅", "姑", "姨", "侄", "甥", "爷", "奶", "孙", "公", "婆", "婿",
]
_KINSHIP_TOKENS.sort(key=len, reverse=True)
_KINSHIP_RE = re.compile("|".join(re.escape(t) for t in _KINSHIP_TOKENS))


def _first_kinship(text):
    """返回文本里第一个亲属身份词（最长优先），无则 None。"""
    if not text:
        return None
    m = _KINSHIP_RE.search(text)
    return m.group(0) if m else None


def _preserve_kinship(base_val, new_val):
    """冻结亲属身份：若基线含亲属身份词，模型新值不得改写为另一种亲属身份。

    - 基线无亲属身份词：放行（模型可自由定义非血缘关系，如同事、上下级）。
    - 基线/新值亲属身份一致：放行（允许情感/状态修饰演化，如「父亲」→「父亲，关系紧张」）。
    - 新值亲属身份与基线冲突（父子→姐夫）：用基线身份替换新值里的错误身份，
      保留模型写出的情感/状态修饰，既守住血缘事实又不丢剧情演化。
    """
    bk = _first_kinship(base_val)
    if not bk:
        return new_val
    nk = _first_kinship(new_val)
    if nk and nk != bk:
        return new_val.replace(nk, bk, 1)
    return new_val


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
        # 卡组越大关系对越多（n 人最多 n*(n-1) 对），额度按人数放宽，避免截断后整体丢失。
        raw = llm.complete(prompt, max_tokens=max(700, 180 * max(len(present), 4)),
                           temperature=0.4, timeout=60)
        data = _extract_json(raw)
        if data and isinstance(data.get("relations"), dict):
            llm_rel = {k: v for k, v in data["relations"].items() if v}
            # 卡片显式关系优先，LLM 仅补缺
            return {**llm_rel, **base}
    except Exception:
        pass
    return dict(base)


def fill_relation_gaps(snap):
    """关系缺口补全：检测快照中是否有在场角色在关系基线里完全无任何边。

    返回触发推断的角色列表（空列表 = 无需推断，手填齐全）。
    若检测到缺口，调用纪官(init_relations)从同场角色描述推断缺失的双向关系，
    推断结果写回 snap["relations"] 与 snap["relations_base"]（受 v0.7.6 亲属冻结保护）。

    旧逻辑仅在「全部卡的 relations 合并为空」时才推断，导致「大部分有、个别缺」的剧本
    （如某张卡 relations 为空、且不被他人提及）漏网；本函数改为按「单个在场角色是否缺边」触发，
    手填齐全的卡不触发任何 LLM 调用，零开销。
    """
    present = snap.get("present") or []
    base_edges = snap.get("relations") or {}
    covered = set()
    for k in base_edges:
        if "→" in k:
            a, b = [p.strip() for p in k.split("→")]
            covered.add(a)
            covered.add(b)
    gap_chars = [c for c in present if c not in covered]
    if not gap_chars:
        return gap_chars
    cards = {c: store.load_card(c) for c in present}
    gen = init_relations(cards)
    if gen:
        snap["relations"] = gen
        snap["relations_base"] = dict(gen)
    return gap_chars


# 在场即须留痕：连续静默达到该轮数即由 prompter 注入硬性焦点。
SILENT_THRESHOLD = 2
# 秘密发酵压力上限：封顶以免长期无进展时无限加压，把剧情逼成机械碰撞。
PRESSURE_MAX = 5
# 高压档：达到该值即从「角色块内的一句提示」升级为全局强制（提级文案 + 强制进镜头）。
PRESSURE_FORCE = PRESSURE_MAX
# 同时只强制一条碰撞：多条并下达会互相打架，结果是全部僵住（见 pressure_targets）。
PRESSURE_FORCE_LIMIT = 1
# 纪官回写的输出额度：条目多（关系/行动/目标/秘密三类/事实两层），给窄了会被截断。
REFLECT_MAX_TOKENS = 1800


def _update_silent_rounds(snap, present):
    """按纪官的行为摘要累加各角色的连续静默轮数。

    判定依据是纪官抽取的 snap["actions"]（每角色本轮一句行为摘要），而非名字是否出现
    在正文里——后者判不出「被提到名字却毫无行为」这种事实上的缺席。
    镜头跟随时只统计镜头内角色：镜头外的人本轮本就不该被写，计沉默会误伤。
    躲避、负气不语、被压制这类有意为之的沉默，纪官同样会写成行为摘要，故不会被误判
    为遗忘——判定权在纪官，不在机械规则。
    """
    acts = snap.get("actions") or {}
    focus_subjects = set((snap.get("focus") or {}).get("subjects") or [])
    silent = snap.setdefault("silent_rounds", {})
    for c in present:
        if focus_subjects and c not in focus_subjects:
            continue
        if (acts.get(c) or "").strip():
            silent[c] = 0
        else:
            silent[c] = silent.get(c, 0) + 1


def _update_secret_pressure(snap, touches):
    """按纪官的 touched 判定更新每条未揭开秘密的发酵压力。

    触及（提及／暗示／回避／物证／追问任一）即归零，未触及则累加并封顶。
    已揭开的秘密不再需要发酵压力，恒为 0。
    纪官被要求对每条未揭开的秘密都给出判定；未列出的按未触及处理，与规则一致。
    """
    touched = {}
    for t in touches or []:
        o = (t or {}).get("owner")
        if o:
            touched[o] = bool(t.get("touched"))
    for s in snap.get("secrets", []):
        # 非「潜伏」即已公开（"暴露"，历史快照可能有 "全曝光"）——公开了就没有发酵问题。
        # 早前写成 == "曝光"，与引擎实际状态字面量对不上，这条守卫从未生效：
        # 压测实证已曝光的秘密压力挂 5 空转 4 轮，还继续占用强制镜头名额。
        if s.get("state") != "潜伏":
            s["pressure"] = 0
            continue
        if touched.get(s.get("owner"), False):
            s["pressure"] = 0
        else:
            s["pressure"] = min(PRESSURE_MAX, s.get("pressure", 0) + 1)


def pressure_targets(snap, present=None):
    """本轮处在高压档（必须碰撞）的秘密及其在场对手：[(owner, rival|None), ...]。

    只取未揭开的秘密（已曝光者压力恒为 0，不存在发酵问题）。
    对手优先取已起疑者（最可能撞出戏），其次握把柄/知情者；须在场且非归属者。
    每条秘密最多配一个对手——对手给多了镜头会被撑成全员，等于取消镜头。
    """
    present = list(present if present is not None else (snap.get("present") or []))
    out = []
    for s in snap.get("secrets") or []:
        if (s.get("pressure") or 0) < PRESSURE_FORCE:
            continue
        # 同上一处：状态字面量是「潜伏 / 暴露」，不是「曝光」。
        if s.get("state") != "潜伏":
            continue
        owner = s.get("owner")
        if owner not in present:
            continue
        rival = None
        for x in s.get("suspicions") or []:
            b = (x or {}).get("by")
            if b and b != owner and b != ENV_PUSHER and b in present:
                rival = b
                break
        if rival is None:
            for k in (s.get("holders") or s.get("known_by") or []):
                if k != owner and k != ENV_PUSHER and k in present:
                    rival = k
                    break
        out.append(((s.get("pressure") or 0), owner, rival))
    # 同时最多只逼一条：压测实证四条秘密会在开场几轮一起顶到上限（谁都没被碰），
    # 全局段同时下达三个「必须碰撞」时模型一个也满足不了，反而三条一起僵住（滞留 11 轮）。
    # 按压力降序取最久未碰的一条，它一旦撞开归零，下一条自然轮到——串行消化而非一拥而上。
    out.sort(key=lambda t: -t[0])
    return [(o, r) for _, o, r in out[:PRESSURE_FORCE_LIMIT]]


def _merge_pressure_into_focus(focus, snap, present):
    """镜头让位于高压碰撞：把高压秘密的双方强制锁定为镜头主角。

    压测实证：pressure 连续 7 轮封顶却毫无碰撞——根因是发酵文案只写在角色块内，
    优先级低于导演指令与镜头约束，且当事人常常根本不在镜头里（在镜头外就不许被写）。
    故高压档由镜头层兜底：把双方拉进镜头。

    关键设计（用户裁定）：高压秘密在场的轮次，镜头**不得退化为自然推演**。否则一旦
    导演指令没点名任何人、或并入后覆盖全体在场者，镜头就塌回「全员可写」，压力段失去
    镜头锚点，又回到「当事人淹没在群像里、谁都没被真正对准」的老路。锁定镜头保证张力
    与剧情连贯推进，符合观众/玩家「焦点人物该被对准」的心理预期。

    三条退化路径逐一封堵：
    1. focus 为 None（无人点名）但高压秘密在场 -> 锁定高压双方为镜头，sticky=True。
    2. 并入后覆盖全体在场者 -> 不再返回 None，改为仅聚焦高压双方（把无关者请出镜头）。
    3. 高压双方里没有任何一人在场 -> 才真正无戏可演，返回原 focus。
    """
    targets = pressure_targets(snap, present)
    if not targets:
        return focus
    owner, rival = targets[0]
    pair = [n for n in (owner, rival) if n and n in present]

    if focus is None:
        # 无人点名：高压秘密自己撑起一个镜头，且标记 sticky 以便下轮延续。
        return {"subjects": pair, "place": snap.get("scene", {}).get("place", ""),
                "sticky": True, "forced": True}

    subs = list(focus.get("subjects") or [])
    forced = False
    for n in pair:
        if n and n in present and n not in subs:
            subs.append(n)
            forced = True
    if not forced:
        return focus
    # 覆盖全体在场者时不再退化：收敛为只聚焦高压双方，把无关者请出镜头。
    if all(p in subs for p in present):
        subs = pair
    merged = dict(focus)
    merged["subjects"] = subs
    merged["forced"] = True
    # 高压轮次锁定延续：下轮即便指令不再点名，也要黏住这对焦点人物，直到碰撞发生。
    merged["sticky"] = True
    return merged


# ---- 事实保全：常量层（不可逆）与状态层（可刷新）----
# 起因：历史超过窗口后会被压缩成「指令前 80 字 + 叙事首 90 字」的骨架，早期确立的
# 世界事实（谁死了、谁残了、什么东西毁了、谁当众说过什么）随压缩蒸发，后面就会出现
# 死人开口、伤口痊愈、毁掉的东西又出现这类硬伤。关系/旧账只覆盖「人与人」，覆盖不了
# 「世界状态」，故另设一张事实表常驻提示词、不参与压缩。
#
# 分类口径（用户裁定）：常量 ≠ 「看起来很难改的事」，而是「后续任何一个动作都改不回来
# 的事」。门被封死可以被爆破、被内鬼打开，人离开了还会回来——这些都不是常量，属于状态层。
# 人死了才是常量：没有任何一个动作能把死人变回活人。
FACT_CORE_KINDS = {"death", "disable", "destroy", "identity"}
FACT_EVENT_KINDS = {"deed", "utterance", "other"}
# 分类上限：超出后把最老的同类折叠成一行（只留对象与摘要），体积恒定而信息不丢。
FACT_CAPS = {"core": 30, "event": 15}
# 状态层键上限：超出淘汰最久未更新的键（状态是覆盖式的，键数本由对象数决定，此为兜底）。
STATE_CAP = 20
# 键归一化忽略的字符：助词「的」与常见标点。仅用于判定「是不是同一个键」，不改写键名。
# 去助词与标点：只在此层面上完全相同才合并，不做子串包含匹配
# （「角色A」与「角色A手臂伤口」语义不同，子串匹配会把它们错误并成一个键）。
_STATE_NOISE = re.compile(r"[的\s，。、：:；;！!？?（）()【】《》\"'“”‘’]")
# 再剥一层泛称后缀：压测实证纪官会为同一对象造「角色A / 角色A情绪 / 角色A状态 /
# 角色A的情绪状态」四键、「角色B手臂伤口 / 角色B手臂咬伤 / 角色B的手臂伤口」三键。
# 这些后缀不携带区分信息，剥掉后归一到同一键，覆盖式存储才不会退化成追加式。
# 后缀可能叠加（「角色A的情绪状态」剥一次还剩「角色A情绪」），故用 + 反复剥到不动。
_STATE_SUFFIX = re.compile(r"(?:情绪|状态|情况|状况|精神|心理|身体|伤口|咬伤|创口|伤处|伤)+$")


def _fact_group(kind):
    return "core" if (kind or "other") in FACT_CORE_KINDS else "event"


def add_facts(snap, items, round_no, reply=None):
    """把纪官抽出的新常量写入事实表（举证核验 + 去重 + 分类上限折叠）。

    证据必须逐字出自正文：与秘密归档同一套纪律，防止纪官凭空造事实。
    """
    added = 0
    for f in items or []:
        subj = (f.get("subject") or "").strip()
        text = (f.get("text") or "").strip()
        if not subj or not text:
            continue
        if not _evidence_ok(f.get("evidence"), reply):
            logger.warn("fact", "常量举证未通过，已丢弃：%s｜%s" % (subj, text))
            continue
        kind = (f.get("kind") or "other").strip()
        if kind not in FACT_CORE_KINDS and kind not in FACT_EVENT_KINDS:
            kind = "other"
        # 去重：同一对象同一类同一句话只记一次（常量不可逆，重复上报多为纪官回看历史误报）
        for old in snap.get("facts", []):
            if (old.get("kind") == kind and (old.get("subject") or "").strip() == subj
                    and (old.get("text") or "").strip() == text):
                text = None
                break
        if text is None:
            continue
        snap.setdefault("facts", []).append({
            "kind": kind,
            "subject": subj,
            "text": text,
            "round": round_no,
            "quote": (f.get("evidence") or "").strip()[:80],
            "invalid": False,
            "reason": "",
        })
        added += 1
    if added:
        _compact_facts(snap)
    return added


def _compact_facts(snap):
    """分类超限折叠：把最老的若干条同类压进**该组唯一的一行摘要**，常数体积、不丢对象。

    早前实现每轮新建一行摘要，且不排除已折叠条目——下一轮它自己又成了最老的一条被再次
    折叠，压测实证出现「早期已确立（R1–R3）：早期已确立（R1–R1）：…」套娃，每轮还白占
    一个新条目，上限形同虚设。故：已折叠条目不再是折叠对象；摘要行每组唯一，只更新
    回合区间与对象名单（不重复拼接正文，避免摘要无限变长）。
    """
    facts = snap.get("facts", [])
    for grp, cap in FACT_CAPS.items():
        items = [f for f in facts
                 if not f.get("invalid") and not f.get("folded")
                 and _fact_group(f.get("kind")) == grp]
        if len(items) <= cap:
            continue
        items.sort(key=lambda f: f.get("round", 0))
        oldest = items[:len(items) - cap + 1]
        drop = {id(f) for f in oldest}
        names = [(f.get("subject") or "（未指名）").strip() for f in oldest]
        lo, hi = oldest[0].get("round", 0), oldest[-1].get("round", 0)

        summary = next((f for f in facts
                        if f.get("folded") and _fact_group(f.get("kind")) == grp), None)
        if summary is None:
            summary = {
                "kind": oldest[0].get("kind") or "other",
                "subject": "",
                "text": "",
                "round": lo,
                "quote": "",
                "folded": True,
                "invalid": False,
                "reason": "",
                "fold_lo": lo,
                "fold_hi": hi,
            }
            facts.append(summary)
        else:
            lo = min(lo, summary.get("fold_lo", lo))
            hi = max(hi, summary.get("fold_hi", hi))
            summary["fold_lo"], summary["fold_hi"] = lo, hi
        # 名单只留对象名（不拼正文片段）：早期细节交给历史摘要，摘要行只保证「谁被确立过」不丢。
        merged = list(dict.fromkeys(
            [s for s in (summary.get("subject") or "").split("、") if s]
            + [s for s in names if s]))
        summary["subject"] = "、".join(merged[-40:])
        summary["text"] = "早期已确立（R%s–R%s）：%s" % (lo, hi, summary["subject"])
        snap["facts"] = [f for f in facts if id(f) not in drop]


def state_key(snap, raw):
    """状态层键归一化：把「角色A的手臂伤口」并回既有键「角色A手臂伤口」。

    压测实证：纪官会为同一对象反复造同义新键（20 轮即造出 3 个「角色B手臂*」、3 个
    「角色A*情绪」），19 键逼近 20 上限——键变体不合并，覆盖式存储就退化成了追加式，
    膨胀防线失效。只在「去助词/标点后完全相同」时合并，不做子串包含匹配：
    「角色A」与「角色A手臂伤口」语义不同，子串匹配会把它们错误并成一个键。
    """
    st = snap.setdefault("states", {})
    key = (raw or "").strip()
    if not key:
        return ""
    def norm_key(k):
        n = _STATE_NOISE.sub("", k or "")
        n = _STATE_SUFFIX.sub("", n)
        return n

    norm = norm_key(key)
    if not norm:
        return key
    for k in st:
        if norm_key(k) == norm:
            return k
    return key


# 纪官偶发给「本轮没变化」的对象也填一条占位值（压测实证出现「未明确提及，维持现状」），
# 与「只填本轮发生变化的对象」规则相悖，还会白占键位。这类空值直接丢弃。
_STATE_PLACEHOLDER = re.compile(r"[。！!，,、；;\s]")
_PLACEHOLDER_VALUES = {
    "未明确提及维持现状", "未明确提及", "维持现状", "状态未变", "无变化",
    "未提及", "未变化", "暂无", "同上", "没变化", "未说明",
}


def update_states(snap, items, round_no):
    """状态层：一键一当前值，后写覆盖前写（因此不随回合膨胀）。

    只存「现在是什么样」，不存历史；被爆破、被偷走、被治愈都只是覆盖一次的事。
    """
    st = snap.setdefault("states", {})
    for it in items or []:
        subj = (it.get("subject") or "").strip()
        val = (it.get("value") or "").strip()
        if not subj or not val:
            continue
        if _STATE_PLACEHOLDER.sub("", val) in _PLACEHOLDER_VALUES:
            continue
        st[state_key(snap, subj)] = {"value": val, "round": round_no}
    if len(st) > STATE_CAP:
        for k in sorted(st, key=lambda k: st[k].get("round", 0))[:len(st) - STATE_CAP]:
            st.pop(k, None)
    return st


def invalidate_fact(snap, text_or_subject, reason=""):
    """作者手动作废一条常量（标记而非删除——留痕以免下轮被纪官重新抽回）。

    只作废、不改写：引擎绝不因剧情推翻常量，纠错权归作者。
    """
    key = (text_or_subject or "").strip()
    if not key:
        return False
    for f in snap.get("facts", []):
        if f.get("invalid"):
            continue
        if key in ((f.get("text") or "") + (f.get("subject") or "")):
            f["invalid"] = True
            f["reason"] = (reason or "作者手动作废").strip()
            return True
    return False


def check_fact_conflicts(snap, reply):
    """正文与常量矛盾时告警（只报不改——用户裁定：引擎不得擅自改写事实）。

    只做代价最低、误报可控的一类：已登记死亡者又作为说话人登场（「名字：」行首）。
    回忆、被提及不算矛盾，故不按「名字出现」判，按「名字开口」判。
    """
    dead = [(f.get("subject") or "").strip()
            for f in snap.get("facts", [])
            if f.get("kind") == "death" and not f.get("invalid")]
    dead = [d for d in dead if d]
    if not dead:
        return []
    hits = []
    for line in (reply or "").splitlines():
        head = line.split("：", 1)[0].strip().lstrip("【「").strip()
        if head in dead:
            hits.append(head)
    if hits:
        logger.warn("fact", "正文与既定事实冲突（已故者登场，仅告警不改写）："
                    + "、".join(dict.fromkeys(hits)))
    return hits


def init_address(snap):
    """新建会话时一次性推导在场角色之间的当面称呼，写入 snap["address"]。

    关系定性只说明「是什么关系」（如"领队，救命恩人"），但正文里角色开口怎么叫人才
    决定人设能否落地——「讨好领队」「顶撞权威」这类设定全部靠称呼体现。缺了这张表，
    应出现的称呼一次都不会出现，反倒是模型即兴发明的叫法乱冒（压测实证）。
    只在开新会话时调用一次：称呼比关系更稳定，随关系演化反复改写反而出戏。
    """
    present = snap.get("present") or []
    if len(present) < 2:
        return {}
    cards = {c: store.load_card(c) for c in present}
    rel_text = "\n".join(f"{k}: {v}" for k, v in (snap.get("relations") or {}).items()) or "（无）"
    card_lines = []
    for c in present:
        card = cards.get(c) or {}
        bits = [c]
        if card.get("description"):
            bits.append(card["description"][:90])
        if card.get("personality"):
            bits.append("性格：" + card["personality"][:70])
        card_lines.append("｜".join(bits))
    prompt = [
        {"role": "system",
         "content": "你是关系沙盘的设定助理。请为这些角色之间配一套当面称呼，"
                    "只输出一个 JSON 对象，不要任何解释或 Markdown 代码块。"},
        {"role": "user", "content": (
            f"在场角色与人设：\n" + "\n".join("- " + l for l in card_lines) + "\n\n"
            f"他们之间的关系：\n{rel_text}\n\n"
            "请输出 JSON：\n"
            '{"address": { "A → B": "A 当面叫 B 的称呼" }}\n'
            "规则：\n"
            "- 只给确实会当面对话的关系配称呼；每条键用「源 → 目标」格式，两端必须是上面列出的在场角色。\n"
            "- 称呼须贴合身份、年龄差、亲疏与当下关系氛围：可用职务、姓氏前缀、名字、外号、"
            "亲属称谓等；关系紧张或生疏时用带距离感的叫法，亲近时用亲昵的叫法。\n"
            "- 不要填「你」「喂」这类无信息量的词，也不要一律填全名——只有当确实会直呼全名时才这么写。\n"
            "- 双向都要给：A 怎么叫 B，以及 B 怎么叫 A，两条都要有。\n"
            "- 称呼要稳定、可在整段叙事里反复使用，不要写带具体情境的临时说法。"
        )},
    ]
    try:
        # 双向称呼条目数随人数平方增长，给窄了会在半途截断（现已有 _salvage_json 兜底）。
        raw = llm.complete(prompt, max_tokens=max(600, 120 * max(len(present), 4)),
                           temperature=0.4, timeout=60)
    except Exception:
        return {}
    data = _extract_json(raw)
    if not isinstance(data, dict):
        return {}
    # 兼容模型直接吐 {"A → B": "..."} 而省掉 address 外层的情况
    addr = data.get("address") if isinstance(data.get("address"), dict) else data
    out = {}
    for k, v in (addr or {}).items():
        if not v or not str(v).strip():
            continue
        parts = [p.strip() for p in str(k).split("→")]
        if len(parts) >= 2 and all(p in present for p in parts[:2]):
            out[parts[0] + " → " + parts[1]] = str(v).strip()
    snap["address"] = out
    return out


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
        sp = [x.get("by") for x in (s.get("suspicions") or []) if x.get("by") != ENV_PUSHER]
        line = (f"{s.get('owner')}（{s.get('state')}｜握有把柄者："
                f"{'、'.join(kb) if kb else '无'}")
        if sp:
            line += f"｜已起疑者：{'、'.join(sp)}"
        sec_lines.append(line + "）")
    secret_text = "\n".join(sec_lines) or "（无秘密）"
    # 既有状态键回喂：不把键名摆出来，纪官就会为同一对象造同义新键（压测实证 20 轮造出
    # 3 个「角色B手臂*」），覆盖式存储退化成追加式。列出既有键，要求沿用、勿造同义键。
    st_text = "、".join(sorted((snap.get("states") or {}).keys())) or "（无）"

    prompt = [
        {"role": "system",
         "content": "你是关系沙盘的纪官。根据本轮叙事，更新各角色的关系与短期目标，抽取本轮各角色的具体行为，并归档秘密的知情变化。只输出一个 JSON 对象，不要任何解释或 Markdown 代码块。"},
        {"role": "user", "content": (
            f"在场角色：{', '.join(present)}\n"
            f"当前关系：\n{rel_text}\n"
            f"当前短期目标：\n{goal_text}\n"
            f"秘密与把柄现状：\n{secret_text}\n"
            f"既有状态键：{st_text}\n"
            f"本轮叙事：\n{reply}\n\n"
            "请输出 JSON：\n"
            "{\n"
            '  "relations": { "源 → 目标": "关系定性（只写稳定的人物关系定位，如\'妈妈，独占欲\'，不要包含本轮具体动作描写）" },\n'
            '  "actions": { "角色名": "本轮该角色做的一句具体行为（不含关系定性，只写这回合发生了什么）" },\n'
            '  "goals": { "角色名": "新的短期目标" },\n'
            '  "secret_exposures": [{"owner": "秘密归属者", "by": "本轮得知该秘密的角色名", "evidence": "本轮叙事原文片段"}],\n'
            '  "secret_suspicions": [{"owner": "秘密归属者", "by": "本轮起了疑心的角色名", "evidence": "本轮叙事原文片段（引发怀疑的那句话/那个细节）"}],\n'
            '  "handle_releases": [{"owner": "秘密归属者", "from": "失去把柄的人", "to": "接过把柄的人（彻底失去则填空字符串）", "evidence": "本轮叙事原文片段"}],\n'
            '  "secret_touches": [{"owner": "秘密归属者", "touched": true}],\n'
            '  "new_facts": [{"kind": "death|disable|destroy|identity|deed|utterance|other", "subject": "对象（角色名或物件名）", "text": "一句话事实", "evidence": "本轮叙事原文片段"}],\n'
            '  "state_updates": [{"subject": "对象（如某道门、某件物品、某人的伤）", "value": "当前状态一句话"}]\n'
            "}\n"
            "规则：\n"
            "- relations 只写跨回合稳定的关系定性，严禁把本轮动作（如\'靠肩头\'\'护送\'\'命令其回房\'）写进关系描述；关系键保持\"源 → 目标\"格式；只更新确实变化的条目，不要删除未提及的关系。\n"
            "- 亲属身份是固定事实：父子/母子/夫妻/兄弟姐妹等血缘与姻亲身份由作者设定，只能演化其情感状态（如加「关系紧张」「疏离」），绝对不得改写为另一种亲属身份（例如不得把「父亲」写成「姐夫」、把「母亲」写成「嫂子」）。\n"
            "- actions 覆盖本轮所有在场角色的一句行为摘要，用于展示\'这回合谁做了什么\'；这是回合级信息，可每轮整体覆盖。\n"
            "- secret_exposures 只填本轮叙事里**确实发生**了「某人得知了某秘密」的条目；仅凭角色起了疑心、或只是提到相关物品，都不算。\n"
            "- secret_suspicions 填**线索逼近但尚未坐实**的条目：某人察觉对方言行反常、追问只得到含糊其辞的回答、发现了与旧事相关的物品或痕迹、或对某人的说法明显不信。只有当事人已经确知真相才算 secret_exposures，不算起疑。\n"
            "- secret_suspicions 的 by 不能是秘密归属者本人，也不能是已确知该秘密的人；同一处细节不要同时填进 secret_exposures 与 secret_suspicions，拿不准就填起疑（较轻），宁可让秘密晚一点被揭开。\n"
            "- handle_releases 只填本轮叙事里**确实发生**了「把柄消失或转手」的条目：例如药物/证据/信件被丢弃、被夺走、交给第三方、或当众说开后不再构成胁迫。to 为空字符串表示彻底消失。\n"
            "- secret_touches 对**每条仍未揭开**的秘密判断：本轮叙事里它有没有被任何形式触及——被提及、被暗示、被刻意回避、出现相关物证或痕迹、被人追问或试探，任一都算 touched=true；"
            "回避与掩饰本身也算被触及。只有整轮里完全无人提起、也没留下任何相关线索，才填 false。已揭开的秘密不必填。\n"
            "- evidence **必须逐字照抄**本轮叙事中的一段连续原文（不要改写、不要概括、不要润色），引擎会逐字核验它是否真的出现在叙事里；照抄不到原文就不要填该条目。\n"
            "- 照抄时**不得改动任何一个字**：正文写「她看得很清楚」就照抄「她看得很清楚」，不得把代词替换成角色名写成「某某看得很清楚」，也不得增删标点——改了字就核验不过，该条目会被丢弃。\n"
            "- 宁可少填也不要误填：填错会让秘密提前暴露或让把柄凭空失效。\n"
            "- new_facts 只填**本轮新确立、且再也改不回来**的事实，用来防止它被后续回合忘掉：\n"
            "  · death：角色死亡（死亡不可逆转；若世界设定允许复活则不填此项）\n"
            "  · disable：致残、失明、失聪、落下永久疤痕等永久性损伤（普通受伤不算）\n"
            "  · destroy：物件被销毁（烧毁、砸碎、吃掉、彻底损毁）\n"
            "  · identity：身份类事实（血亲、法定关系、真实身份被揭穿）\n"
            "  · deed / utterance：某人做过或当众说过的具体事（做过的事、说出口的话收不回）\n"
            "  · 判据：能被后续一个动作改掉的就不是常量。**门被封死、路被堵、断电**可被爆破/打开/修复，不算常量；\n"
            "    **人离开**还会回来，不算；**物品在谁手上**可被偷抢转送，不算；**受伤**可治愈，不算；\n"
            "    **承诺、欠债、人情**可被履行勾销，不算；关系好坏、态度、天气时间场景也不算——这些都填 state_updates。\n"
            "  · 若世界设定明确该类可被逆转（有复活手段、有治愈设定），一律不填 new_facts。\n"
            "  · 只填本轮**新发生**的，不要重复此前已确立的条目。\n"
            "  · text 只写**事实本身**（谁做了什么、说了什么），不得夹带推论与解读\n"
            "    （如「暴露了他隐瞒病情的事实」「说明两人关系破裂」）——推论会被固化成常量，错了无法回退。\n"
            "- state_updates 填**当前状态的最新值**：门是否封死、通道是否通行、物件在谁手上、某人伤情、电源是否可用等。\n"
            "  subject 沿用既有名称（此前叫「铁门」就继续用「铁门」），同一对象后一轮直接覆盖，不要另起新名造重复键。\n"
            "  只填本轮发生变化或新出现的对象；状态被解除时也要填（如「铁门：已被炸开，可通行」）。\n"
            "  subject 必须优先沿用上面「既有状态键」里的名字；只有当对象是全新的、与既有键明显不是同一样东西时才新建键。\n"
            "  严禁为同一对象造同义新键（如已有「角色A手臂伤口」就不得再写「角色A的手臂伤口」「角色A手臂咬伤」）。\n"
            "  角色只填具体伤情部位（如「角色A手臂伤口」），不得填角色裸名，也不得填「某人情绪／某人状态／\n"
            "  某人的心理状态」这类泛称——情绪与整体状态归关系与本轮行动，不占状态键（压测实证这类泛称\n"
            "  造出「角色A／角色A情绪／角色A状态／角色A的情绪状态」四键，把键表撑到上限）。"
        )},
    ]
    # 额度必须留足：纪官要吐关系/行动/目标/秘密三类/事实两层，900 会被截断在半句话上，
    # 曾导致整轮回写静默全丢（事实保全落地后输出更长，把既有隐患顶爆）。
    try:
        raw = llm.complete(prompt, max_tokens=REFLECT_MAX_TOKENS, temperature=0.3,
                           timeout=120)
    except Exception:
        logger.warn("director", "纪官调用失败，本轮状态未回写")
        return snap
    data = _extract_json(raw)
    if not data:
        logger.warn("director", "纪官输出无法解析，本轮状态未回写")
        return snap
    if not _is_complete_json(raw):
        # 抢救成功：字段已部分回写，但末尾条目多半丢了，留痕便于定位。
        logger.warn("director", "纪官输出疑似被截断，已抢救回写部分字段（末尾条目可能丢失）")

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
                # 两端都在场（镜头内角色）：允许关系随剧情演化；
                # 但若基线已确定亲属身份（父子/母子等），冻结身份、只允许情感状态修饰演化。
                if k in base and base.get(k):
                    v = _preserve_kinship(base[k], v)
                snap["relations"][k] = v
            else:
                # 涉及未在场/无卡关联人物（如某位仅被提及的亲属）：冻结为初始关系定位，
                # 禁止模型改写或升级（"小姨子"被写成"妻子"类漂移即在此拦截）。
                # 初始表无此键则丢弃该越权关系，不引入新条目。
                if k in base:
                    snap["relations"][k] = base[k]
    if isinstance(data.get("actions"), dict):
        snap["actions"] = {k: v for k, v in data["actions"].items() if v}
    # 在场即须留痕：用纪官的行为摘要判定谁本轮真的在戏里（替代 app.py 里按名字是否
    # 出现在正文的字符串判断——那个判不出「被提到名字但没有任何行为」）。
    # 镜头跟随时只统计镜头内角色：镜头外的人本轮就不该被写，计沉默会误伤。
    _update_silent_rounds(snap, present)
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
            # 举证不通过＝纪官上报了正文里没有的字面内容（多为改写/润色）。
            # 此前会静默丢弃，压测中表现为「线索明明出现却没归档」，难以定位；此处留痕。
            logger.warn("secret", "曝光举证未通过，已丢弃：%s 得知 %s 的秘密"
                        % (by, owner))
            continue
        for s in snap.get("secrets", []):
            holders = s.setdefault("holders", list(s.get("known_by", [])))
            if s.get("owner") == owner and by not in holders:
                _record_exposure(s, by, "叙事揭露", snap["scene"]["round"])
                _ledger_entry(snap, s, by, snap["scene"]["round"])
                break

    # 起疑（线索逼近）：同样按举证归档。只记疑点、不记真相，起疑者不得因此剧透。
    # 这是「潜伏／曝光」二态之外的中间态——曝光前的逼近过程才是张力最足的一段。
    for sus in (data.get("secret_suspicions") or []):
        owner = sus.get("owner")
        by = sus.get("by")
        if not owner or not by or by == owner:
            continue
        if by != ENV_PUSHER and by not in present:
            continue
        if not _evidence_ok(sus.get("evidence"), reply):
            logger.warn("secret", "起疑举证未通过，已丢弃：%s 对 %s 起疑"
                        % (by, owner))
            continue
        for s in snap.get("secrets", []):
            if s.get("owner") != owner:
                continue
            # 已确知真相者不再记起疑（知情是起疑的终态）
            if by in (s.get("known_by") or []) or by in (s.get("holders") or []):
                continue
            _record_suspicion(s, by, sus.get("evidence"), snap["scene"]["round"])
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

    # 秘密发酵压力：纪官判语义（本轮有没有触及），代码管计数（累加/归零/封顶）。
    # 数字只留在快照里，模型始终只看到 prompter 按档位生成的文案。
    # 必须排在曝光/起疑归档之后：本轮刚被揭开的秘密当轮就要把压力清零，
    # 否则它会在「已曝光」的状态下多带一轮压力（虽不足档位，但状态不自洽）。
    if "secret_touches" in data:
        _update_secret_pressure(snap, data.get("secret_touches") or [])

    # 事实保全：常量只增不改（须逐字举证），状态覆盖式刷新。
    # 与秘密归档同一套纪律：纪官说的不算，正文里查得到才算。
    # 回合数取容错写法：reflect 的既有分支本就依赖 snap["scene"]，但这两块无条件执行，
    # 缺键不该让整轮回写失败（事实保全只是增益，不得阻塞主流程）。
    rd = (snap.get("scene") or {}).get("round", 0)
    added = add_facts(snap, data.get("new_facts") or [], rd, reply)
    if added:
        logger.info("fact", "新确立常量 " + str(added) + " 条")
    update_states(snap, data.get("state_updates") or [], rd)
    # 矛盾只告警、不自动改写（纠错权归作者）
    check_fact_conflicts(snap, reply)

    memory.save(sid, snap)
    return snap
