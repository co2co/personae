"""导演简报：生成前读快照+core，跑若干项检查（A2 后果账本激活 / A4 场景计数等），产出内部 brief 与注入指令。

规则版（不额外调 LLM），保证速度。机会等级/内容尺度机制已随 NSFW 整体废弃（v0.8.0），引擎回归中性关系沙盘。
"""

import json
import re

import memory
import llm
import logger
import store
import scene

ENV_PUSHER = "环境推手"

# ---- 举证式归档（记录员模式）----
# 引擎不做语义判定："正文里有没有发生一次发现"是语义问题，交给 LLM 判断；
# 引擎只做结构校验，验证 LLM 上报的内容确实在正文里出现过（防幻觉）。
# 早先用关键词词表做语义判定（INFO_VERBS + DISCOVERY_VERBS + secret.keys）时，
# 题材高频词（绷带/小臂/发烧/通风口/家人）与"看见/察觉/露出"极易巧合共现，
# 实测 150 次判定放行 33 次（22%），校验形同虚设。详见 tests/DEVLOG.md v0.5.8。
# 下限只用于挡掉「一两个字碰巧命中」的伪举证（如只写「伤口」「他」），不是长度门槛。
# 早前设为 8 会把真实短句误杀——压测实证纪官就死亡举证「没有脉搏。」（5 字，逐字出现在正文），
# 硬常量硬生生漏记。逐字核验本身已足够防伪，故下限压到 4。
EVIDENCE_MIN_LEN = 4

# 秘密「暴露」的合法信息获取方式（纪官 secret_exposures.via 白名单）。
# 只有这些「信息实际发生了跨角色传递」的动作才算暴露；缺 via、或 via 是
# 「猜透/心知肚明/早已知道」等单方面心证，一律不算——那些只能算起疑。
# 这是 v0.17.3 修复：此前曝光归档只看「举证逐字在正文」+ 纪官语义判断，
# 纪官会把「角色内心想到他早就知道」这类心理描写误报成「实际得知」，
# 导致潜伏秘密在开场即被翻成「暴露」（真实会话 256d924c 事故）。
EXPOSURE_VIA_WHITELIST = ("看见", "听见", "被告知", "发现物证")

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


_PUNCT = "，。！？、；：""''「」『』（）()<>《》,.!?;:…—–-·\"'"


def _strip_punct(s):
    """剥离标点/引号，用于举证比对容忍排版差异。只消标点、不动汉字字面。

    纪官引用原文时的标点/引号差异（正文「」，引用漏引号；句末句号截断）不该导致
    漏记；但「她」→角色名这类字面篡改仍保留，故只去标点不替换字。
    """
    return re.sub("[" + re.escape(_PUNCT) + "]", "", s or "")


def _evidence_ok(evidence, reply):
    """结构校验：LLM 的举证必须是本轮正文的原文片段。

    这是记录员模式的全部判定——引擎不猜"这算不算发现"，只验证举证确实出自正文
    （防幻觉编造）。语义判断由 reflect 的 LLM 承担，证据由它自己引用。

    举证缺失或不匹配时丢弃该条目：宁可漏记（状态滞后），不可误记
    （秘密提前暴露 -> 张力提前消耗、机会等级被顶格）。

    v0.17.4：比对在「折叠空白」之上再「剥离标点/引号」。纪官引用原文时最常犯的
    轻微差异是标点与引号（正文用「」、引用时漏掉；或句末句号截断），逐字比对会把
    这类纯排版差异误杀、造成漏记；而「把代词替换成角色名」这类**字面篡改**仍要
    拒绝（那是编造，不是引用）。故只消标点、不消字面。
    """
    e = _norm_text(evidence)
    if len(e) < EVIDENCE_MIN_LEN:
        return False
    return _strip_punct(e) in _strip_punct(_norm_text(reply))


# ---- 暴露语义护栏（v0.17.6，会话 467f1e4c 事故）----
# _evidence_ok 只验证「举证原文在不在正文里」，不验证「这段原文是否真的构成
# 该秘密的信息传递」。纪官会把「内心独白 / 猜测 / 讨论另一话题 / 家庭共享背景」
# 截成一段确实存在于正文的原文当证据，从而把潜伏秘密误翻成「暴露」——
# 会话 467f1e4c 第十回合多名角色秘密被误标暴露，正文却无任何暴露动作。
#
# 两个叠加护栏（AND）补上这层语义兜底，均**不引入引擎自持的题材语义词表**，
# 不违背记录员模式契约（语义判断仍归 LLM，引擎只做结构核验）：
#   护栏一 _evidence_related：证据须命中秘密的事实锚点（作者在 keys 里给的触发词，
#       非引擎硬编码）——拦住「讨论别的话题却去坐实某人某件秘密」这类话题错位。
#   护栏二 _evidence_transfer：证据片段内须出现信息接收方 by 或提供方 owner 的名字
#       （信息传递必有施/受方在场）——拦住「旁白心理独白」「不在场者听见」这类
#       无施受方的伪传递。
# 任一护栏不过 → 降级为起疑（证据仍真实存在于正文，只是语义不构成暴露），
# 而非直接丢弃；宁可漏记（状态滞后），不可误记（秘密提前暴露、张力提前消耗）。


def _bigrams(s):
    """提取文本的相邻双字片段（去标点后），用于锚点与证据的宽松重合判定。

    中文无天然分词边界，用双字滑动窗口近似「实质词重合」：证据若确实在讨论
    该秘密，必然与作者给的触发词（keys）共享某个 ≥2 字的连续片段（人名/关键词/
    短语）。纯单字重叠（的/了/他）不采信，避免放行无关描述。
    """
    t = _strip_punct(_norm_text(s))
    return {t[i:i + 2] for i in range(len(t) - 1)}


def _anchor_tokens(secret):
    """事实锚点：作者在秘密 keys 里给的触发词，keys 空则退回归属者名。

    这是作者提供的、每个秘密独有的锚点，不是引擎硬编码的通用题材词表——
    记录员模式里引擎不自创语义，只复用作者给定的事实边界做结构核验。
    """
    keys = [k for k in (secret.get("keys") or []) if k and len(_norm_text(k)) >= 2]
    if keys:
        return keys
    owner = _norm_text(secret.get("owner") or "")
    return [owner] if len(owner) >= 2 else []


def _evidence_related(evidence, secret):
    """护栏一：举证原文须触及秘密的事实锚点（keys 或归属者名）。

    用双字片段重合判定：证据与锚点共享任一 ≥2 字连续片段即视为相关。
    比「完整键逐字子串」宽松——纪官引的原文常是自然叙事语言，未必逐字照抄
    作者的触发词（如 key 是「角色甲的秘密」、正文写其同义/近义表述）；比单字严格——
    不会因「的/了/他」这类虚词重合误放行无关描述。
    锚点为空（keys 空且归属者名为单字）时放行，交由护栏二兜底。
    """
    anchors = _anchor_tokens(secret)
    if not anchors:
        return True
    ev = _bigrams(evidence)
    if not ev:
        return False
    for a in anchors:
        if ev & _bigrams(a):
            return True
    return False


def _evidence_transfer(evidence, by, owner):
    """护栏二：证据片段内须出现信息接收方 by 或提供方 owner 的名字。

    信息从 owner 传到 by 必有其一方在场作为动作主语/宾语；两者名字都缺席的
    证据（旁白心理独白、第三人转述、不在场者）不构成实际传递。
    名字短于 2 字（罕见单字名）时该项不参与判定，避免误伤。
    """
    names = [n for n in (by, owner)
             if n and len(_norm_text(n)) >= 2 and n != ENV_PUSHER]
    if not names:
        return True
    e = _strip_punct(_norm_text(evidence))
    return any(n in e for n in names)


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
# 群体点名：玩家显式把镜头交给全体在场者（「众人讨论」「大家商量」）。这类指令是玩家
# 明确的操控意图，须尊重、不得被高压秘密强制覆盖——否则不了解机制的玩家会以为引擎
# 不遵循指令（见会话 97589153 事故：导演指令「众人讨论去处」被高压镜头压成二人戏）。
_GROUP_WORDS = ["众人", "大家", "所有人", "全员", "每个人", "大家伙", "众人皆"]


def compute_focus(directive, snap):
    """计算本轮镜头焦点（被指令点名/引用的在场子集）。

    返回 {"subjects": [...], "place": "...", "sticky": bool} 或 None。
    - 指令点名一个真子集 -> 镜头跟随该子集（sticky=False）。
    - 指令无点名但含指代代词（两人/他们/...）且上轮有焦点 -> 延续上轮焦点（sticky=True），
      避免"2人逐渐深入"这类后续指令丢失焦点、镜头跳回初始位置。
    - 指令点名全体或无人 -> None，表示自然推演、全员在场皆可写。
    place 取快照当前场景地点（scene.apply 已更新为新地点）。

    玩家体验优先（v0.18.3 裁定）：镜头只由玩家的指令驱动，秘密发酵压力（pressure）不再
    对镜头施加任何强制——不强制并入、不强制锁定、不兜底撑镜头。引擎定位是小空间群像，
    空间本就局限，高压双方迟早会在某轮自然同场，碰撞由叙事自然命中，无需镜头层「导演」。
    压力只剩「提级文案」这一个提示出口（见 prompter），不再抢玩家的方向盘。
    """
    present = snap.get("present", [])
    if not present or not directive:
        return None
    named = [n for n in present if n in directive]
    prev = snap.get("focus") or {}

    # 群体点名：玩家显式把镜头交给全体在场者 -> 自然推演。
    if any(w in directive for w in _GROUP_WORDS):
        return None

    # 玩家点名具体子集 -> 镜头跟随该子集。
    if 0 < len(named) < len(present):
        return {"subjects": named, "place": snap["scene"].get("place", ""), "sticky": False}

    # 玩家点名全体（列出所有在场者名）-> 自然推演。
    if named:
        return None

    # 指令完全没点名任何角色：仅指代代词延续上轮焦点（非高压锁定，高压不再有镜头强制）。
    if prev and any(w in directive for w in _FOLLOW_WORDS):
        subs = prev.get("subjects", [])
        if subs and all(s in present for s in subs):
            return {"subjects": subs, "place": snap["scene"].get("place", ""), "sticky": True}
    return None


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


# ---- 纪官输出归一化（防御模型格式漂移）----
# 纪官偶发把本该是对象的字段写成字符串（如 actions: "角色甲翻看物资"），
# 或把本该是对象的列表写成字符串数组（如 state_updates: ["门坏了"]）。
# 80 轮压测实测两种漂移都会出现，抛出的 `'str' object has no attribute 'get'`
# 会让整个 reflect 回写中断——本轮的关系/行动/事实/状态全部丢失，且无任何告警。
# 语义未定的字段一律降级为空：宁可不记账，不可让整轮回写崩掉。
def _as_dict_list(val):
    """只保留列表中的 dict 元素；非列表或元素全非 dict 时返回空列表。"""
    if not isinstance(val, list):
        return []
    return [x for x in val if isinstance(x, dict)]



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

# 自称消解：模型台词里的「我叫X」把「泛称」与「本名」绑成同一人。
# 只认「我叫 / 名字叫 / 我名叫 / 我姓」这类**明确报姓名**的句式。
# 刻意不含「我是」——「我是护士」「我是医生」「我是学生」报的是身份不是姓名。
# 也不做模糊匹配——「年轻女子」与「X」在字符串上无从推断，
# 但「我叫X」是模型亲口给出的对应关系，是唯一可靠依据。
_AUX_SELFNAME_RE = re.compile(
    r"(?:我叫|名字叫|我名字叫|我名叫|我姓)\s*"
    r"([\u4e00-\u9fffA-Za-z·•]{2,6})"
)
# 泛称 / 描述词（v0.16.1 修 aux 重复登记）：模型常先用「年轻女子」「中年男人」
# 这类**描述**起段，待角色自我介绍后再转本名（「我叫X」→ 后续写「X：」）。
# 引擎若把两个称呼都登记成新群演，左栏会出现两个 chip 指同一个人。
# 这些词是外貌/身份/职业描述而非人名，一律不作为群演名登记。
_AUX_GENERIC_WORDS = {
    "女子", "男人", "女人", "老人", "孩子", "女孩", "男孩", "少年", "少女",
    "妇人", "汉子", "青年", "中年", "中年人", "老年人", "小孩", "姑娘", "小伙",
    "陌生人", "路人", "幸存者", "幸存者们", "身影", "那人", "此人", "对方",
    "男人", "妇女", "老妇人", "老翁", "少年人", "来人", "某人", "旁人",
    "女人", "男的", "女的", "有人", "众人", "大家",
    # 职业/身份描述（模型常以「医生：」起段介绍临时登场者）
    "医生", "大夫", "护士", "老师", "警察", "士兵", "工人", "农民",
    "司机", "厨师", "记者", "律师", "会计", "演员", "歌手", "病人", "伤员",
    "志愿者", "新人", "老板", "队长", "小姐", "先生", "女士", "大叔", "大妈",
}

# 修饰性泛称后缀（v0.16.1）：模型常把年龄/外貌修饰与称谓拼成复合泛称——
# 「年轻女子」「中年男人」「老妇人」「小女孩」。这些组合不在任何词表里，
# 但都含一个**修饰性后缀**，故这一组用「包含」匹配。
# 与 _AUX_PROFESSION_WORDS 的区别：职业词能合法构成人名（「李医生」），
# 修饰性称谓不能（「年轻女子」永远不是名字）。
_AUX_GENERIC_MODIFIERS = {
    "年轻", "中年", "年老", "老", "小", "大", "男", "女",
    "少女", "少年", "孩童", "苍老", "衰老", "年轻气盛",
}

# 身份 / 职业 / 亲属类词：跟在自称位置时是身份而非姓名，绝不能当本名。
_AUX_PROFESSION_WORDS = {
    "护士", "医生", "大夫", "教师", "老师", "学生", "工人", "农民", "警察",
    "军人", "士兵", "司机", "厨师", "会计", "律师", "记者", "编辑",
    "演员", "歌手", "孩子", "母亲", "父亲", "儿子", "女儿",
    "姐姐", "哥哥", "妹妹", "弟弟", "新人", "老人", "熟人", "外人", "自己人",
    "医生", "病人", "伤员", "志愿者", "幸存者",
}

# ---- 散文判据的额外护栏（v0.17.1）----
# 模型回归散文主体后，prose_said 正则会把描述性短语误当成人名。
# 真实案例：「威胁语气说道」→ 捕获「胁语气」；「想要问“…”」→ 捕获「想要」；
# 「她想道“…”」→ 捕获「她想」。这些不是角色，而是状语/能愿/代词碎片。
# 以下集合按「结构特征」过滤，不依赖具体题材。

# 以这些字/词开头的候选不是人名（代词、虚词），且 2~3 字短候选
# 无法被 _AUX_PREFIX_NOISE 完整剥离（剩 1 字）。
# 注意：不放「老/大/小」等可能作为真名前缀的字，避免误伤「老王」「大雄」。
_AUX_PRONOUN_PREFIXES = {
    "她", "他", "它", "我", "你", "您", "咱", "谁", "这", "那", "其",
    "有", "众", "人",
}

# 能愿动词 / 趋向动词：常出现在「想要问/会说道」这类结构里，不是名字。
_AUX_MODAL_WORDS = {
    "想要", "想", "要", "会", "能", "可以", "应该", "愿意", "需要", "必须",
    "得", "敢", "肯", "能够", "应当", "该当", "意欲", "将要", "快要",
}

# 抽象情绪 / 状态 / 描述词：「恐惧地说道」「威胁语气说道」里的“恐惧/威胁”。
_AUX_ABSTRACT_WORDS = {
    # 情绪 / 状态
    "恐惧", "绝望", "紧张", "愤怒", "痛苦", "疲惫", "冷静", "沉默", "警惕",
    "希望", "失望", "威胁", "压迫", "危险", "安全", "兴奋", "激动", "慌乱",
    "害怕", "害羞", "尴尬", "悲伤", "快乐", "高兴", "愉快", "难受", "舒服",
    "累", "困", "饿", "渴", "慌", "怒", "惧", "悲", "喜", "愁", "忧", "急",
    # 抽象描述名词（「威胁语气」被截断为「胁语气」的核心来源）
    "语气", "心情", "神情", "神态", "表情", "目光", "眼神", "声音", "口气",
    "态度", "动作", "举止", "模样", "样子", "心境", "状态", "情绪", "感觉",
    "神色", "口吻", "眼色", "姿态", "身影", "手势", "步伐", "意志", "意识",
}

# 描述性后缀：候选以这些词结尾，说明它是「X语气/神情说道」被截断的碎片。
_AUX_DESCRIBE_TAIL = {
    "语气", "神情", "神态", "表情", "目光", "眼神", "声音", "口气", "态度",
    "动作", "举止", "模样", "样子", "心情", "心境", "状态", "情绪", "感觉",
    "神色", "口吻", "眼色", "姿态", "身影", "手势", "步伐",
}

# 结构助词结尾：副词/状语碎片（「愤怒地说道」→ 捕获「愤怒地」）。
_AUX_PARTICLE_TAIL = {"地", "得", "着", "了", "过"}

# 说话拟声/方式动词（v0.17.2 新增）：「他喃喃道：“…”」里的「喃喃道」整体是
# 说话动词，正则会截出「喃喃」——它是动词的一部分，不是人名。这类词与
# 说话动词同位（甚至本身就是 _AUX_VERB_TAIL 里的「呢喃」「嘟囔」的同义词），
# 真正的说话人在更前面（往往是代词，剥离后本就不该登记）。
_AUX_SPEECH_ONOMATOPOEIA = {
    "喃喃", "呢喃", "嘟哝", "嘀咕", "念叨", "念及", "沉吟", "低语", "私语",
    "自语", "呻吟", "惊呼", "呜咽", "嗫嚅", "嘟囔", "呢哝", "絮语", "絮叨",
}


def _is_aux_speech_verb(nm):
    """候选是说话拟声/方式动词短语，而非人名。

    覆盖三种形态（均来自真实误报）：
      「喃喃」        —— AA 叠音说话动词（「他喃喃道」被截断）
      「喃喃自语」    —— 拟声词开头的复合动词短语（分段形判据把
                         「喃喃自语道：」整行当成「名字：」后剥掉「道」的产物）
      「咕哝/沉吟」   —— 非叠音的说话方式词本身

    AA 叠音做整体判断：中文真实人名确有叠音（冰冰/芳芳/明明），但散文判据里
    捕获到的叠音几乎总是「喃喃道」「呜呜地哭」这类动词/拟声碎片；按 simon 定的
    「宁可漏检（晚一轮登记），不可误检（左栏出现假角色）」取舍，一律拒绝。
    真叠音角色的登记走旁路：导演【引入角色】指令，不依赖正文形态。
    """
    nm = nm or ""
    if nm in _AUX_SPEECH_ONOMATOPOEIA:
        return True
    if len(nm) == 2 and nm[0] == nm[1]:
        return True
    # AABB 叠音（「呜呜咽咽」）：前两字叠 + 后两字叠，是拟声/动作碎片
    if len(nm) >= 4 and nm[0] == nm[1] and nm[2] == nm[3]:
        return True
    # 拟声词开头的复合短语（「喃喃自语」「呜呜咽咽」）
    if len(nm) > 2 and any(nm.startswith(w) for w in _AUX_SPEECH_ONOMATOPOEIA):
        return True
    # 说话方式词结尾的复合短语（「喃喃自语」「低声私语」）
    if any(nm.endswith(w) for w in ("自语", "私语", "低语", "梦呓", "呓语")):
        return True
    return False


# 语气状语本身（「沉声开口」剥掉动词后剩「沉声」）——全等过滤，不做后缀匹配，
# 「李沉声」这类真名即使存在也不受影响。
_AUX_TONE_ADVERBS = {
    "低声", "沉声", "冷声", "轻声", "大声", "哑声", "颤声", "急声", "高声", "厉声",
}


def _is_aux_garbage_name(nm):
    """结构性判定：这个名字碎片明显不是人名。

    供两处使用：① discover_aux_speakers 的候选过滤（散文/分段正则挖掘，已退居
    兜底）；② reflect 纪官语义登记的保险层（纪官偶发也会把动词碎片当名字上报）。
    全部是结构特征（代词/能愿/抽象/描述/拟声/泛称），不含任何题材词。
    """
    nm = (nm or "").strip()
    if not nm:
        return True
    return (any(nm.startswith(p) for p in _AUX_PRONOUN_PREFIXES)
            or nm in _AUX_MODAL_WORDS
            or nm in _AUX_ABSTRACT_WORDS
            or any(nm.endswith(t) for t in _AUX_DESCRIBE_TAIL)
            or any(nm.endswith(t) for t in _AUX_PARTICLE_TAIL)
            or _is_aux_speech_verb(nm)
            or nm in _AUX_TONE_ADVERBS)
    # 注意：泛称/职业词（年轻女子/李医生）**不在**本判定内——跨轮泛称可能真是
    # 不同角色，只做「同轮与本名消解」（_prune_aux_aliases ②），不无条件拒收。


def _is_aux_generic_name(nm):
    """结构性判定：这个名字是描述性泛称（年轻女子/路人/幸存者/李医生不含）。

    泛称跨轮可能真是不同角色，**不做无条件拒收**；用于两处：
    ① _prune_aux_aliases 的同轮消解（泛称 + 本名同轮出现只留本名）；
    ② reflect 改名合并的结构兜底（自报姓名 + 本轮唯一在场的泛称旧群演 → 合并）。
    """
    nm = (nm or "").strip()
    return (any(w in nm for w in _AUX_GENERIC_MODIFIERS)
            or nm in _AUX_GENERIC_WORDS
            or nm in _AUX_PROFESSION_WORDS)


def _resolve_aux_aliases(reply, names):
    """用「我叫X」这类自称句把泛称与本名消解为同一个角色。

    背景：模型常先以描述性称呼起段（「年轻女子：……我叫X……」），自我介绍后
    改用本名（「X：……」）。两处都会被 discover_aux_speakers 抓成候选，若不去重，
    同一个群演会在左栏显示两个 chip。

    返回 (保留名, 被消解的别名列表)。消解时**保留本名**（模型后续使用的那个），
    因为后续轮次大概率一直用本名，登记它对跨回合连续性更有用。
    """
    if not reply or not names:
        return list(names), []
    # 自称句里出现的名字 → 该名字的行首说话人就是「泛称」
    real_names = {m.group(1) for m in _AUX_SELFNAME_RE.finditer(reply)}
    real_names -= _AUX_PROFESSION_WORDS   # 「我叫医生」这种是身份不是姓名
    if not real_names:
        return list(names), []
    alias_of = {}      # 泛称 -> 本名
    for ln in reply.split("\n"):
        m = _AUX_SPEAKER_RE.match(ln.strip())
        if not m:
            continue
        speaker = m.group(1).strip()
        if speaker in names and speaker not in real_names:
            said = _AUX_SELFNAME_RE.search(ln)
            if said and said.group(1) in real_names:
                alias_of[speaker] = said.group(1)
    if not alias_of:
        return list(names), []
    kept, dropped = [], []
    for n in names:
        if n in alias_of:
            dropped.append(n)
        else:
            kept.append(n)
    return kept, dropped


def discover_aux_speakers(reply, exclude):
    """从本轮叙事里发现尚未登记的「说话人式」名字，作为候选辅助群演。

    exclude：已知名字集合（在场角色 + 角色卡库 + 已登记 aux + 背景人物 + 环境推手），
    这些不算新群演。返回去重后的新名字列表（已排除常见叙事节拍词/元信息前缀/
    泛称描述词/自称消解后的别名，仅保留疑似人名的片段）。

    **两种叙事形态都要认**（v0.17.0 移除「角色名：」分段格式契约后，模型回归散文主体）：
      ① 分段形：`X：（喘息）我是护士`  —— 行首「名字：」
      ② 散文形：`“X。”她抬起头` / `X喊道：……` —— 引号紧跟名字，或「名字 + 说话动词」
    只认 ① 时，散文体下该机制完全失效（临时群演无法登记、跨回合连续性丢失）。
    """
    if not reply:
        return []
    out, seen = [], set(exclude or [])
    # ② 散文形：**「人名 + 冒号/说话动词 + 引号」**（如「老陈说：“水够吗？”」）
    #
    #    【为什么不认「引号紧跟名字」】v0.17.0 实测误判率极高：模型写的
    #    「“角色乙，”角色甲没有抬头」（引号内是人名）与「“从今天起，”他的声音不高」
    #    （引号内是台词内容）在字面上无法区分，一轮正文能误抓十几个碎片
    #    （「从今天起」「我腿软」「真的要去吗」…），会把群演注册表填满垃圾。
    #
    #    【为什么不认「名字 + 说话动词」宽松匹配】中文无词边界，「角落里老陈咳了
    #    一声」这类前缀会让贪婪匹配切出「角落里老」，非贪婪又漏掉「老陈」，
    #    试过非贪婪/后向断言/窗口扫描均不可靠。中文人名边界本身不可机械判定。
    #
    #    **代价（明确接受）**：模型若写成「那个陌生人咳了一声。“水够吗？”」，
    #    该群演本轮不登记、下一轮才被发现。漏检的代价只是群演晚一轮进左栏；
    #    而误检的代价是左栏出现「从今天起」这种根本不存在的角色——后者大得多。
    #    旁路仍在：导演可用【引入角色】指令显式登记（parse_aux_introductions，
    #    不依赖任何正文形态），这是散文剧本下最可靠的入口。
    prose_said = re.compile(
        r"([\u4e00-\u9fff]{2,3}?)\s*(?:低声|沉声|冷声|轻声|大声|哑声|颤声|急声)?\s*"
        r"(?:说道|说|道|问道|问|答道|答|喊道|喊|叫道|开口|嘟囔|呢喃)\s*"
        r"[：:]?\s*[“\"]")
    # 说话动词与语气状语可能已被贪婪匹配吃进名字（「角色丙说」「角色丙低声」）——从尾部切掉。
    # 单字动词（叹/笑/吼…）只用于尾部剥离、不进正则交替：正则交替会让
    # 「爸爸叹道」仍捕获「爸爸叹」（惰性量词先短后长回溯），而尾部剥离能把
    # 「陈叔叹」还原成「陈叔」、把「爸爸叹」还原成叠音「爸爸」再被叠音判据拒绝。
    _AUX_VERB_TAIL = ("说道", "说", "道", "问道", "问", "答道", "答",
                      "喊道", "喊", "叫道", "叫", "开口", "嘟囔", "呢喃",
                      "低声", "沉声", "冷声", "轻声", "大声", "哑声", "颤声", "急声",
                      "叹", "笑", "吼", "骂", "嚷", "呻", "应", "催", "劝",
                      "喃", "嘀", "嘟", "呜", "嗫", "絮", "念", "喝")
    # 候选**前缀**污染：代词与常见动作/方位词开头的一律不是人名（「他转向角色丙」→ 切掉「他转向」）。
    # 用反复剥离而非一次替换——中文里「他转向」「她递给」可能叠着多层。
    _AUX_PREFIX_NOISE = (
        "他转向", "她转向", "他们", "她们", "转向", "看向", "望向", "递给", "递出",
        "走向", "走近", "靠近", "退开", "转身", "抬头", "低头", "回头",
        "拉起", "推开", "拿起", "放下", "转向", "朝着", "对着", "向着",
        "然后", "接着", "随后", "于是", "同时", "接着",
        "他", "她", "它", "我", "你", "有人", "众人",
    )
    # 代词/泛指：不作为人名候选（「她低声说」「有人喊道」）
    _AUX_PRONOUNS = {
        "她", "他", "它", "我", "你", "您", "咱", "谁", "这", "那", "其", "有人",
    }
    for ln in reply.split("\n"):
        m = _AUX_SPEAKER_RE.match(ln.strip())
        cands = []
        if m:
            cands.append(m.group(1).strip())          # ① 分段形：行首「名字：」
        else:
            cands.extend(g.strip() for g in prose_said.findall(ln))  # ② 散文形
        for name in cands:
            # 切掉被贪婪匹配吃进来的说话动词/状语尾部（「角色丙说」「角色丙低声」）
            changed = True
            while changed and len(name) > 2:
                changed = False
                for v in _AUX_VERB_TAIL:
                    if name.endswith(v) and len(name) - len(v) >= 2:
                        name = name[:-len(v)]
                        changed = True
            # 切掉被吃进来的**前缀**（「他转向角色丙」→「角色丙」）：代词与常见动词/方位词
            # 开头的候选一定是被前文污染的，不可能是人名。
            changed = True
            while changed and len(name) > 2:
                changed = False
                for pre in _AUX_PREFIX_NOISE:
                    if name.startswith(pre) and len(name) - len(pre) >= 2:
                        name = name[len(pre):]
                        changed = True
            if not name or name in seen or name in _AUX_BEAT_WORDS:
                continue
            if name in _AUX_PRONOUNS:
                continue
            # 代词 / 虚词 / 方位词开头的短候选不是人名（「她想」「有人」），
            # 前缀剥离会剩 1 字，不如直接拒绝。
            if any(name.startswith(p) for p in _AUX_PRONOUN_PREFIXES):
                continue
            # 能愿动词与抽象情绪/状态/描述词不是人名（「想要」「威胁」「冷静」）。
            if name in _AUX_MODAL_WORDS or name in _AUX_ABSTRACT_WORDS:
                continue
            # 描述性后缀结尾：通常是「威胁语气说道」被截断成「胁语气」的碎片。
            if any(name.endswith(t) for t in _AUX_DESCRIBE_TAIL):
                continue
            # 结构助词结尾：状语碎片（「愤怒地说道」→「愤怒地」）不是人名。
            if any(name.endswith(t) for t in _AUX_PARTICLE_TAIL):
                continue
            # 说话拟声/叠音动词碎片：「他喃喃道」→「喃喃」是动词不是人名。
            if _is_aux_speech_verb(name):
                continue
            # 语气状语本身：「沉声开口」剥掉动词后剩「沉声」。
            if name in _AUX_TONE_ADVERBS:
                continue
            # 泛称描述（年轻女子、中年男人、老翁）不是人名，不登记为群演。
            # 用**包含**匹配：「年轻女子」不是词表里的词，但含修饰性后缀「女子」。
            # 职业词只做**全等**——「李医生」「王医生」含「医生」但都是真名字，不能误伤。
            if any(w in name for w in _AUX_GENERIC_MODIFIERS):
                continue
            if name in _AUX_GENERIC_WORDS or name in _AUX_PROFESSION_WORDS:
                continue
            if len(name) > 6 or len(name) < 2:
                continue
            out.append(name)
            seen.add(name)
    # 自称消解：模型先用泛称起段、自报姓名后改用本名时，两者只算一个人（见 _resolve_aux_aliases）
    kept, dropped = _resolve_aux_aliases(reply, out)
    if dropped:
        logger.info("aux", "自称消解（同一人被两个称呼指代）：" + "、".join(dropped)
                    + " → 保留本名")
    return kept


def _prune_aux_aliases(snap):
    """清理已登记的 aux 中的别名与垃圾项。

    v0.16.1 之前的会话可能出现「年轻女子」与「X」两个 chip 指同一人
    （模型先以描述性称呼起段、自报姓名后改用本名）。discover_aux_speakers
    现在会在登记前消解，但**已落盘的脏数据不会自动回溯**——本函数在每次
    登记前跑一遍，让老会话在下轮自愈。

    v0.17.1 新增：散文判据会把描述性短语误当人名（「威胁语气说道」→「胁语气」、
    「想要问“…”」→「想要」、「她想道“…”」→「她想」），这些垃圾项也在此处清理。
    """
    aux = snap.get("aux") or []
    if not aux:
        return []

    def _is_garbage(nm):
        """明显不是人名的碎片（判据集中在 _is_aux_garbage_name，与登记链路共用）。"""
        return _is_aux_garbage_name(nm)

    def _is_generic(nm):
        """描述性泛称（年轻女子/中年男人/路人），判据集中在 _is_aux_generic_name。"""
        return _is_aux_generic_name(nm)

    dropped = []
    keep = []
    # ① 清理历史误登记的垃圾项
    for a in aux:
        if _is_garbage(a.get("name")):
            dropped.append(a["name"])
        else:
            keep.append(a)
    # ② 同一轮引入多条：带修饰性泛称后缀的只留本名/真名
    by_round = {}
    for a in keep:
        by_round.setdefault(a.get("intro_round"), []).append(a)
    keep2 = []
    for rnd, items in by_round.items():
        if len(items) < 2:
            keep2.extend(items)
            continue
        desc = [a for a in items if _is_generic(a.get("name"))]
        if len(desc) == 1 and len(items) - len(desc) >= 1:
            dropped.extend(d["name"] for d in desc)
            keep2.extend(a for a in items if a not in desc)
        else:
            keep2.extend(items)
    if dropped:
        snap["aux"] = keep2
        logger.info("aux", "清理群演脏数据/别名：" + "、".join(dropped))
    return dropped


def register_aux(snap, names, round_no, notes=None):
    """把若干名字登记进快照 aux 注册表（去重，避免重复登记）。

    notes：可选 {名字: 身份说明}，来自导演显式【引入角色】指令。
    返回新增的名字列表（便于日志与前端呈现）。
    """
    # 入表前先清理历史别名：老会话里的「泛称 + 本名」重复项在这里自愈
    _prune_aux_aliases(snap)
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


def background_names_from_relations(snap, present, extra_known=None):
    """从快照关系表中析出「背景人物」：在 relations 键里出现、但不在场的**无卡**角色。

    这些角色无独立角色卡（store 不收录），仅在他人 relations 字段/世界书里被定位，
    属于「非在场」背景板。引擎应保证其不被活动化（见 detect_offscreen_activity）。

    extra_known：调用方已知的角色名集合（省一次 list_characters 扫盘）；不传则自取。

    判定为「有独立角色卡即不是背景人物」是这个函数的设计本意（背景 = store 不收录者）。
    早前只做「relations 名字 − present」的集合差，把**有卡但本轮不在场名单**的角色也
    划成背景，于是他在叙事里的正常戏份被 detect_offscreen_activity 判失责并整句删除
    （真实事故：某有独立角色卡、全程在演的角色，27 字长句被删到只剩「。」）。
    已登记的会话群演（aux）同理——有名有姓的活跃参与者，不是背景板。
    """
    present_set = set(present or [])
    known = set(extra_known) if extra_known is not None else set(store.list_characters())
    known |= {a.get("name") for a in ((snap or {}).get("aux") or [])}
    rel_names = set()
    for k in (snap or {}).get("relations", {}):
        for e in k.split("→"):
            rel_names.add(e.strip())
    return sorted(n for n in rel_names
                  if n and n not in present_set and n not in known)


def detect_offscreen_activity(reply, background_names):
    """自检「背景人物是否被活动化」——simon 验收标准：引擎把背景人物写成活动角色即失责。

    仅检测、不删正文（背景被在场角色提及本身是允许的，误删风险高）。返回 (是否失责, 命中行列表)。
    命中三类（**三判据互补，不依赖输出格式**——v0.17.0 已移除「角色名：」分段格式契约，
    模型回归散文主体写法，故不能只靠行首匹配）：
      ① 独立台词块（'背景名：' 起头）——被写了对白/独白；
      ② 第三人称分句以背景名为主语且含动作/出场信号（如「X从门后走出」）——被写成主角行动；
      ③ **引号紧跟背景名**（如「“老王，走吧。”」）——被写成对白。这是散文写法下
         背景人物获得台词的唯一形态，缺了它该检测在散文体下完全失效。
    """
    if not reply or not background_names:
        return False, []
    names_sorted = sorted(set(background_names), key=len, reverse=True)
    pat = re.compile(r"^(?:" + "|".join(re.escape(n) for n in names_sorted) + r")\s*[:：]")
    action_re = re.compile(r"[走跑走进出开看说笑问拿放抱亲吻摸扯拉推挡站坐躺靠冲望回头转转身来到去迎送探伸]")
    # ③ 引号紧跟背景名：中文引号“” 与英文引号 "" 都算；名字后允许带标点
    quoted = re.compile(
        r"[“\"](?:" + "|".join(re.escape(n) for n in names_sorted) + r")"
        r"\s*[，。！？…、]?\s*[”\"]")
    hits = []
    for ln in reply.split("\n"):
        s = ln.strip()
        if not s:
            continue
        if pat.match(ln):                      # ① 独立台词块（对白/独白）
            hits.append(s)
            continue
        if quoted.search(s):                  # ③ 引号紧跟背景名（散文体下的对白）
            hits.append(s)
            continue
        # ② 第三人称分句：以背景名作主语且含动作/出场信号（兼顾整段混写无换行的情况）
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

    可选的 relations_kinship 字段形如 { "角色B": "小姨子" }，供引擎精确冻结血缘身份：
    它绕过词表猜测，作者直接声明「A 对 B 的亲属身份是什么」。写了这个字段，
    该边的身份即被冻结且不再依赖描述文案的写法（见 _preserve_kinship）。
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


def seed_kinship_from_cards(cards_present):
    """从角色卡可选的 relations_kinship 字段提取显式亲属身份声明。

    返回 { "源 → 目标": 身份词 }，只含在 _KINSHIP_TOKENS 里出现的合法身份词。
    血缘事实是作者定义的固定事实，不该靠从描述句里猜词——本字段让作者直说。

    ⚠ 本函数只服务「关系缺口补全」路径（fill_relation_gaps）；真实会话的显式声明
    走memory.new → kinship_base，那条链路**不过滤此表**，故本表缺词并不影响
    真实会话的冻结（v0.18.6 实测确认：姨父不在表时冻结照样生效）。

    注意：非法词是**静默丢弃**的（无报错、无日志）。作者声明了表外身份词后会以为
    冻结已生效、实则没有兜底，排查极难。故 v0.18.6 已把中国亲属称谓的常见缺项补齐。
    """
    out = {}
    for c, card in (cards_present or {}).items():
        rels = card.get("relations_kinship") or {}
        if not isinstance(rels, dict):
            continue
        for target, kin in rels.items():
            if not target or not kin:
                continue
            kin = str(kin).strip()
            if kin in _KINSHIP_TOKENS:
                out[f"{c} → {target}"] = kin
    return out


# 亲属身份词表：关系定性里出现这些词即代表一种「亲属身份定位」。
# 引擎强制冻结其身份——作者定义的血缘/姻亲关系（父子、母子等）是固定事实，
# 模型只能演化情感/状态修饰，不得把「父亲」改写成「姐夫/嫂子」之类导致乱伦逻辑崩塌。
# 注意：恋人/情人等「关系状态」不在冻结之列（沙盘本就要演好感→恋人），只冻结亲属身份。
#
# 词表只收**双字及以上**的完整身份词。早期版本混入「母」「子」「夫」「弟」等单字，
# 而单字在中文里几乎只作为长词的碎片出现（母子/母性/夫人/兄弟），实测在 demo 的
# 12 条关系里造成 8 条误判（如「A母子的生死」被判为「子」的身份声明），
# 冻结机制反而把正确的「妻子」改写成「子，关系紧张」。故单字一律不作为身份词。
#
# 【覆盖范围】按中国亲属称谓的完整体系补齐（v0.18.6）：原表 45 词只覆盖直系 +
# 少数旁系与姻亲，缺姨父/姑父/堂表兄弟姐妹/侄女外甥女/岳父岳母/继子女养子女等，
# 这些缺口让「妻姐之夫」「堂哥」等常见设定拿不到冻结保护——作者在
# relations_kinship 里显式声明了也会被seed_kinship_from_cards 静默丢弃。
#
# 【社会关系词为何一律不进表】同事/邻居/房东/医生/领导/上司/下属等一律不收：
#   1. 本引擎的核心能力是「关系演化」，社会关系正是演化主体（同事→恋人、
#      下属上位、房东变盟友）。入表即把这些演化冻死，等于关掉引擎的主要功能
#      （守护用例见 test_preserve_kinship_no_baseline_free）。
#   2. 职业/称谓类词在中文里大量作状语与口语称呼（「大哥别说」「领导在场」）
#      句首声明规则会大面积误判，把叙述句当身份声明反过来改坏关系。
#   若某个社会身份确需固定（如"法官/医生不得被改写成亲属"），
#   走 relations_kinship 显式声明通道——memory.new 写入 kinship_base 时不过滤此表，
#   该通道对任意身份词都生效。
_KINSHIP_TOKENS = [
    # ── 直系长辈 ──
    "父亲", "母亲", "祖父母", "曾祖父", "曾祖母", "高祖父", "高祖母",
    "外祖父", "外祖母", "外公", "外婆", "爷爷", "奶奶",
    "伯父", "伯母", "伯伯", "伯娘", "叔父", "叔母", "叔叔", "婶婶", "婶母",
    "姑母", "姑父", "姑妈", "姑姑", "舅舅", "舅妈", "舅母", "姨妈", "姨母", "姨父", "阿姨",
    # ── 直系晚辈 ──
    "儿子", "女儿", "孙子", "孙女", "外孙", "外孙女", "曾孙", "曾孙女",
    # ── 兄弟姐妹与同辈旁系 ──
    "哥哥", "弟弟", "姐姐", "妹妹", "兄长",
    "堂兄", "堂弟", "堂姐", "堂妹", "堂哥", "堂嫂",
    "表兄", "表弟", "表姐", "表妹", "表哥", "表嫂",
    "姨姐", "姨妹", "小姨子", "大姨子",
    # ── 侄辈 ──
    "侄子", "侄女", "外甥", "外甥女", "甥男", "甥女",
    # ── 核心姻亲（配偶）──
    "丈夫", "妻子", "老公", "老婆",
    # ── 核心姻亲（长辈/平辈/晚辈）──
    "岳父", "岳母", "岳丈",
    "公公", "婆婆", "儿媳", "媳妇", "女婿", "孙媳", "孙女婿",
    "姐夫", "妹夫", "弟夫", "嫂子", "弟媳", "弟妹", "连襟", "妯娌",
    "亲家", "亲家公", "亲家母",
    # ── 继嗣与收养 ──
    "养父", "养母", "养子", "养女", "义父", "义母",
    "继父", "继母", "继子", "继女", "继兄", "继弟", "继姐", "继妹",
    # ── 义亲与师承 ──
    "干爹", "干妈", "教父", "教母",
    # ── 口语与尊称（常见同义写法）──
    "爸爸", "妈妈", "爹爹", "娘亲", "老爸", "老妈",
]
_KINSHIP_TOKENS = sorted(set(_KINSHIP_TOKENS), key=len, reverse=True)
assert not [t for t in _KINSHIP_TOKENS if len(t) < 2], "身份词表混入单字词"
assert "同事" not in _KINSHIP_TOKENS and "恋人" not in _KINSHIP_TOKENS, \
    "社会关系/关系状态词不得进冻结表（会冻死关系演化，见词表注释）"

# 显式身份声明的形态：值以身份词**开头**，其后紧跟标点/空格/「是/为」等分隔。
# 只认这种形态是因为关系定性句里通篇都是身份词（叙述某人不敢戳破父亲已死、某人是弟弟云云），
# 从叙述句中间推断身份在语义上不成立——那句里的「父亲」指的是第三方，不是这条边的两端。
# 作者想冻结某条边的身份，把身份词写在开头即可（"母亲：…""父亲，…"）；
# 写在句中的叙述性身份词不触发冻结，交由模型自由演化。
_KINSHIP_DECL_RE = re.compile(
    r"^\s*(" + "|".join(re.escape(t) for t in _KINSHIP_TOKENS) + r")\s*[：:，,、。；;｜|—\-]|(?:是|为)\s*"
)
# 整值就是一个裸身份词时（模型常输出「父亲」这种极简定性）同样算显式声明。
_KINSHIP_ONLY_RE = re.compile(
    r"^\s*(" + "|".join(re.escape(t) for t in _KINSHIP_TOKENS) + r")\s*$"
)


def _first_kinship(text):
    """返回该关系值**显式声明**的亲属身份词，无则 None。

    只认两种形态（见 _KINSHIP_DECL_RE / _KINSHIP_ONLY_RE）：身份词出现在值开头
    紧跟分隔符，或整值就是该身份词。不从叙述句中间推断——句中出现的身份词
    指的是第三方，不是这条边声明的身份。
    """
    if not text:
        return None
    for rx in (_KINSHIP_DECL_RE, _KINSHIP_ONLY_RE):
        m = rx.match(text)
        if m:
            return m.group(1)
    return None


def _preserve_kinship(base_val, new_val, declared=None):
    """冻结亲属身份：基线声明了亲属身份时，模型新值不得改写为另一种亲属身份。

    - declared 非空：以该权威身份为基准（作者用 relations_kinship 显式声明的），
      基线描述里的身份词一律不采信。
    - 基线未声明身份：放行（叙述句里的身份词不构成声明，模型可自由演化关系定性）。
    - 基线/新值身份一致：放行（允许情感/状态修饰演化，如「父亲」→「父亲，关系紧张」）。
    - 新值身份与基线冲突（父亲→姐夫）：用基线身份替换新值里的错误身份，
      保留模型写出的情感/状态修饰，既守住血缘事实又不丢剧情演化。
    """
    bk = declared or _first_kinship(base_val)
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
# 高压档：达到该值即从「角色块内的一句提示」升级为全局软提醒（提级文案，玩家指令优先，不再强制进镜头）。
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


# 状态层键上限：超出淘汰最久未更新的键（状态是覆盖式的，键数本由对象数决定，此为兜底）。
STATE_CAP = 20
# 人物位置表上限：只存「谁在哪里」的当前值，一角色一位置，后写覆盖前写。
# 角色数（cast + aux）通常远小于 20，上限是防纪官把同名泛称造出一串位置键。
LOCATION_CAP = 40
# 键归一化忽略的字符：助词「的」与常见标点。仅用于判定「是不是同一个键」，不改写键名。
# 去助词与标点：只在此层面上完全相同才合并，不做子串包含匹配
# （「角色A」与「角色A手臂伤口」语义不同，子串匹配会把它们错误并成一个键）。
_STATE_NOISE = re.compile(r"[的\s，。、：:；;！!？?（）()【】《》\"'“”‘’]")
# 再剥一层泛称后缀：压测实证纪官会为同一对象造「角色A / 角色A情绪 / 角色A状态 /
# 角色A的情绪状态」四键、「角色B手臂伤口 / 角色B手臂咬伤 / 角色B的手臂伤口」三键。
# 这些后缀不携带区分信息，剥掉后归一到同一键，覆盖式存储才不会退化成追加式。
# 后缀可能叠加（「角色A的情绪状态」剥一次还剩「角色A情绪」），故用 + 反复剥到不动。
_STATE_SUFFIX = re.compile(r"(?:情绪|状态|情况|状况|精神|心理|身体|伤口|咬伤|创口|伤处|伤)+$")


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


def update_locations(snap, items, round_no):
    """人物位置层：一角色一当前位置，后写覆盖前写。

    与 states（物件/环境状态）分离的独立唯一真相源——「谁在哪里」是物理事实，
    不容「某人在电梯」「某人在卧室」两条记录并存（会话 9f2e16e9 R14 事故正是
    位置信息寄生在物件状态键 value 里、分队移动后旧键过期导致的矛盾）。
    同一角色后一轮的新位置覆盖旧位置，天然消解「同时两处」。
    """
    loc = snap.setdefault("locations", {})
    for it in items or []:
        who = (it.get("who") or "").strip()
        place = (it.get("place") or "").strip()
        if not who or not place:
            continue
        if _STATE_PLACEHOLDER.sub("", place) in _PLACEHOLDER_VALUES:
            continue
        # 同义键归并：去助词/标点后与既有位置键相同则覆盖，避免「角色A / 角色A的」
        # 之类变体造重复键。位置键是角色名，不复用 state_key 的「情绪/状态」后缀剥离
        # （那会把角色名本身误剥），只做 _STATE_NOISE 去助词标点。
        key = who
        norm = _STATE_NOISE.sub("", who)
        if norm:
            for k in loc:
                if _STATE_NOISE.sub("", k) == norm:
                    key = k
                    break
        loc[key] = {"place": place, "round": round_no}
    if len(loc) > LOCATION_CAP:
        for k in sorted(loc, key=lambda k: loc[k].get("round", 0))[:len(loc) - LOCATION_CAP]:
            loc.pop(k, None)
    return loc


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


def reflect(sid, reply, directive=""):
    """生成后状态回写：根据本轮叙事更新关系、短期目标，并检测潜伏秘密被揭露。

    这是“状态机自动演化”的核心——推演产生的后果必须落回快照，否则次日无痕。
    任何解析/调用失败都保持快照不变，绝不阻塞主流程。

    directive：本轮导演指令（玩家本人这轮的权威设定）。关键事实（如某群演死亡）
    可能只由指令承载、正文未清晰复述甚至被弱化，故退场判定须同时参照它。
    自然推演轮指令为空，prompt 不增行，零 token 增量。
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
    # 既有位置回喂：纪官须知道谁上一轮在哪，才能在本轮移动后正确更新、而非另造同义键。
    loc_lines = [f"{k}：{(snap['locations'][k].get('place') or '')}"
                 for k in sorted((snap.get("locations") or {}).keys())]
    loc_text = "；".join(loc_lines) or "（无）"
    # 已登记群演回喂：纪官必须知道「某个泛称」已在册，才能在她自报姓名时声明改名合并，
    # 否则会把「X」当成又一个新人物（真实回归：会话 1868b891 左栏出现两个 chip）。
    aux_lines = []
    for a in (snap.get("aux") or []):
        line = f"{a.get('name')}（{a.get('role') or ''}）"
        if a.get("status") == "已退场":
            line += "〔已退场〕"
        aux_lines.append(line)
    aux_text = "；".join(aux_lines) or "（无）"
    # 背景人物（无独立角色卡、不在场，仅存在于他人关系定位里）：回喂名单，纪官才能
    # 按语义判断本轮有没有人把他们写成有对白/独白的角色。这取代了原先的正则扫描——
    # 「分句主语 + 动作字表」把「来自远方的指令」这类合法提及也判成失责，实测 23 轮
    # 命中里真失责接近 0，且旧链路会整句删除正文（会话 d024172c 事故）。
    offscreens = background_names_from_relations(snap, present)
    off_text = "、".join(offscreens) or "（无）"
    # 导演指令回喂：关键事实（群演死亡等）可能只由玩家指令承载、正文未复述甚至弱化。
    # 仅当指令非空时占一行，自然推演轮零开销。指令是玩家本人的权威设定，优先级高于正文。
    dir_block = ("\n本轮导演指令（玩家设定，权威，正文与其冲突时以指令为准）：\n" + directive + "\n") if directive else ""

    prompt = [
        {"role": "system",
         "content": "你是关系沙盘的纪官。根据本轮叙事，更新各角色的关系与短期目标，抽取本轮各角色的具体行为，并归档秘密的知情变化。只输出一个 JSON 对象，不要任何解释或 Markdown 代码块。"},
        {"role": "user", "content": (
            f"在场角色：{', '.join(present)}\n"
            f"当前关系：\n{rel_text}\n"
            f"当前短期目标：\n{goal_text}\n"
            f"秘密与把柄现状：\n{secret_text}\n"
            f"既有状态键：{st_text}\n"
            f"既有位置：{loc_text}\n"
            f"已登记群演：{aux_text}\n"
            f"背景人物（无独立角色卡、不在场）：{off_text}\n"
            f"{dir_block}"
            f"本轮叙事：\n{reply}\n\n"
            "请输出 JSON：\n"
            "{\n"
            '  "relations": { "源 → 目标": "关系定性（只写稳定的人物关系定位，如\'妈妈，独占欲\'，不要包含本轮具体动作描写）" },\n'
            '  "actions": { "角色名": "本轮该角色做的一句具体行为（不含关系定性，只写这回合发生了什么）" },\n'
            '  "goals": { "角色名": "新的短期目标" },\n'
            '  "secret_exposures": [{"owner": "秘密归属者", "by": "本轮得知该秘密的角色名", "via": "信息获取方式，只能填「看见/听见/被告知/发现物证」四类之一", "evidence": "本轮叙事原文片段"}],\n'
            '  "secret_suspicions": [{"owner": "秘密归属者", "by": "本轮起了疑心的角色名", "evidence": "本轮叙事原文片段（引发怀疑的那句话/那个细节）"}],\n'
            '  "handle_releases": [{"owner": "秘密归属者", "from": "失去把柄的人", "to": "接过把柄的人（彻底失去则填空字符串）", "evidence": "本轮叙事原文片段"}],\n'
            '  "secret_touches": [{"owner": "秘密归属者", "touched": true}],\n'
            '  "state_updates": [{"subject": "对象（如某道门、某件物品、某人的伤）", "value": "当前状态一句话"}],\n'
            '  "location_updates": [{"who": "角色名", "place": "该角色本轮结束时所在的具体地点"}],\n'
            '  "aux_updates": [{"name": "新出场人物的名字或稳定称呼", "note": "一句话身份说明（如「隔壁的住户」「巡夜的保安」）", "replaces": "该人物在「已登记群演」里的旧称呼（仅当本轮才得知其真名时填）"}],\n'
            '  "aux_departures": [{"name": "退场群演的名字", "reason": "退场原因一句话（如死亡、逃离、离开队伍）"}],\n'
            '  "offscreen_activity": [{"name": "被写成活动角色的背景人物", "evidence": "本轮叙事原文片段"}],\n'
            '  "scene_shift": {"changed": false, "place": "本轮叙事末尾所处的地点", "time": "本轮叙事末尾的时间", "weather": "本轮叙事末尾的天气"}\n'
            "}\n"
            "规则：\n"
            "- relations 只写跨回合稳定的关系定性，严禁把本轮动作（如\'靠肩头\'\'护送\'\'命令其回房\'）写进关系描述；关系键保持\"源 → 目标\"格式；只更新确实变化的条目，不要删除未提及的关系。\n"
            "- 亲属身份是固定事实：父子/母子/夫妻/兄弟姐妹等血缘与姻亲身份由作者设定，只能演化其情感状态（如加「关系紧张」「疏离」），绝对不得改写为另一种亲属身份（例如不得把「父亲」写成「姐夫」、把「母亲」写成「嫂子」）。\n"
            "- actions 覆盖本轮所有在场角色的一句行为摘要，用于展示\'这回合谁做了什么\'；这是回合级信息，可每轮整体覆盖。\n"
            "- secret_exposures 只填本轮叙事里**确实发生**了「某人得知了某秘密」的条目；仅凭角色起了疑心、或只是提到相关物品，都不算。\n"
            "- secret_exposures 的「得知」必须是**信息实际发生了跨角色传递**：该角色本轮**亲眼看见**秘密事实（如看见伤痕、物证、现场）、**亲耳听见**对方自述或他人转述、**被当面告知**、或**亲手发现**了能坐实秘密的物证。除此之外一律不算暴露。\n"
            "- **内心活动不算得知**：正文里写「某人心想他早就知道」「某人暗自看穿」「某人早已心知肚明」「某人在心里确认了」这类**心理描写、内心独白、回忆、猜透**，即使明写了他「知道」，也**不是**实际的信息传递，**绝不填 secret_exposures**——它们只代表该角色单方面的心证，可能填进 secret_suspicions（起疑），不得翻成暴露。判断的唯一标准是：这一轮里，秘密事实有没有**从一个人传到另一个人**；没有传递动作，就没有暴露。\n"
            "- secret_suspicions 填**线索逼近但尚未坐实**的条目：某人察觉对方言行反常、追问只得到含糊其辞的回答、发现了与旧事相关的物品或痕迹、或对某人的说法明显不信。只有当事人已经确知真相才算 secret_exposures，不算起疑。\n"
            "- secret_suspicions 的 by 不能是秘密归属者本人，也不能是已确知该秘密的人；同一处细节不要同时填进 secret_exposures 与 secret_suspicions，拿不准就填起疑（较轻），宁可让秘密晚一点被揭开。\n"
            "- handle_releases 只填本轮叙事里**确实发生**了「把柄消失或转手」的条目：例如药物/证据/信件被丢弃、被夺走、交给第三方、或当众说开后不再构成胁迫。to 为空字符串表示彻底消失。\n"
            "- secret_touches 对**每条仍未揭开**的秘密判断：本轮叙事里它有没有被任何形式触及——被提及、被暗示、被刻意回避、出现相关物证或痕迹、被人追问或试探，任一都算 touched=true；"
            "回避与掩饰本身也算被触及。只有整轮里完全无人提起、也没留下任何相关线索，才填 false。已揭开的秘密不必填。\n"
            "- evidence **必须逐字照抄**本轮叙事中的一段连续原文（不要改写、不要概括、不要润色），引擎会逐字核验它是否真的出现在叙事里；照抄不到原文就不要填该条目。\n"
            "- 照抄时**不得改动任何一个字**：正文写「她看得很清楚」就照抄「她看得很清楚」，不得把代词替换成角色名写成「某某看得很清楚」，也不得增删标点——改了字就核验不过，该条目会被丢弃。\n"
            "- 宁可少填也不要误填：填错会让秘密提前暴露或让把柄凭空失效。\n"
            "- state_updates 填**当前状态的最新值**：门是否封死、通道是否通行、物件在谁手上、某人伤情、电源是否可用等。\n"
            "  subject 沿用既有名称（此前叫「铁门」就继续用「铁门」），同一对象后一轮直接覆盖，不要另起新名造重复键。\n"
            "  只填本轮发生变化或新出现的对象；状态被解除时也要填（如「铁门：已被炸开，可通行」）。\n"
            "  subject 必须优先沿用上面「既有状态键」里的名字；只有当对象是全新的、与既有键明显不是同一样东西时才新建键。\n"
            "  严禁为同一对象造同义新键（如已有「角色A手臂伤口」就不得再写「角色A的手臂伤口」「角色A手臂咬伤」）。\n"
            "  角色只填具体伤情部位（如「角色A手臂伤口」），不得填角色裸名，也不得填「某人情绪／某人状态／\n"
            "  某人的心理状态」这类泛称——情绪与整体状态归关系与本轮行动，不占状态键（压测实证这类泛称\n"
            "  造出「角色A／角色A情绪／角色A状态／角色A的情绪状态」四键，把键表撑到上限）。\n"
            "  **严禁把人物位置写进 state_updates**：不得填「卧室门：角色A在屋内」「客厅：某人守在门口」这类把\n"
            "  「谁在哪里」塞进物件/环境键的写法——人物位置一律走 location_updates，否则分队移动后旧键过期、\n"
            "  会造成同一角色同时出现在两处（位置不是物件状态，不共用状态键）。\n"
            "- location_updates 填**每个位置发生变化**的角色的当前位置：谁离开了哪里、到了哪里，只填 moved 的角色，\n"
            "  没动的角色不必重填（沿用上面「既有位置」）。place 写本轮叙事末尾该角色**实际所处**的具体地点\n"
            "  （如「电梯内」「地库」「卧室」「客厅」），不要写泛称「外面」「那边」。\n"
            "  位置是物理事实、每角色唯一：同一角色本轮只报一条，后写覆盖前写，绝不可报两条互相矛盾的位置。\n"
            "  who 用角色的正式名字（沿用「在场角色」「既有位置」里的写法）；刚移动过的在场角色与群演都要覆盖到。\n"
            "- aux_updates 只填本轮叙事里**新出场、或本轮才确认身份**的人物，引擎登记后跨回合追踪。绝对不填：代词（他/她/有人）、"
            "说话动词碎片（喃喃/呜呜/低声）、无名的背景一笔带过者。"
            "同一称呼此前出现过就不必重填；名字拿不准或人物只是被顺带提及，就不填——"
            "宁可少登记，也绝不造出叙事里不存在的人。\n"
            "- aux_updates 的改名合并（**最容易漏的一项，务必逐条对照**）：逐一看「已登记群演」名单，"
            "只要本轮叙事揭示了其中某人的真实姓名，**就必须走合并而非新增**——"
            "name 填真名、note 填最新身份、replaces 填她在名单里的旧称呼（**逐字照抄名单写法**），引擎会把旧条目改名。"
            "典型触发：名单里是职务/身份/外貌类称呼（巡逻员、队长、陌生女子、幸存者之类），"
            "本轮这人自报或被叫出姓名（「我叫X」「他叫X」「X，哪一队的」都算）。"
            "示例（X 为占位，与你的剧本无关）：名单里有「那个陌生女子」，本轮写「那名女子站在门口……“我叫X。”」"
            "→ aux_updates 填 {\"name\": \"X\", \"note\": \"自称某某身份\", \"replaces\": \"那个陌生女子\"}，"
            "绝不能把 X 当成又一个新人物。只有确认是同一个人时才填 replaces；拿不准就不填，按新人物处理。\n"
            "- aux_departures：逐一看「已登记群演」名单，判断其中某人是否处于**永久性退场**——死亡、"
            "被带走、彻底逃离队伍或离开故事线，再也不会回到当前场景。退场的判定**三条线索都要看**："
            "①本轮叙事里刚发生的退场；②「既有位置」里已经标明了永久退场态、但「已登记群演」里此人"
            "仍挂着〔活跃〕的人——这种存量漏报本轮一并补报，避免退场那一轮没赶上、之后永远追不上；"
            "③**本轮导演指令**里明确说某已登记群演死亡／被带走／彻底消失——退场事实可能只由玩家指令"
            "承载、正文没复述甚至弱化成「跑了」，此时即便「既有位置」仍停在旧地点，也按退场注销"
            "（指令是玩家的权威设定，优先级高于正文与既有位置）。"
            "name 用名单里该人的名字，reason 一句话说明原因。只填**已登记的群演**（在「已登记群演」"
            "名单里的人）；正式登场角色的进出由场景导演处理，不要填进这里。无人需退场就填空数组——"
            "宁可漏报，不可误报；位置里只是「翻窗逃到隔壁单元」「转移到别处躲藏」这类**还会回来**的"
            "暂时逃离一律不填（判断依据是「会不会再回来」，不是「有没有离开原位」）。\n"
            "- offscreen_activity：检查「背景人物」名单里的人，本轮有没有被**写成活动角色**——"
            "获得对白、独白、或作为动作主语亲自出场行动（如「X从门后走出」「X笑着说：“…”」）。\n"
            "  不算的情况（**一律不填**，填了就是误报）：被在场角色在台词或心里谈论、回忆、"
            "提及名字、收到其来信或指令、被想念或被担心——哪怕名字出现了也不算活动化；"
            "以「X不在场」「X说过的话」「想起X」这类间接形式出现也不算。\n"
            "  只有他本人**亲自登场说话或行动**才算。evidence 逐字照抄原文，引擎会核验。"
            "没有就填空数组——宁可漏报，不可误报。\n"
            "- scene_shift：本轮叙事里**地点／时间／天气有没有实际发生变化**（如从客厅走到楼道、"
            "天黑了、下起雨）。changed 填 true 时同时给出变化后的 place/time/weather，"
            "引擎据此把场景状态追上叙事（避免场景停在「清晨」而正文早已入夜）。"
            "没有变化就填 {\"changed\": false}。"
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
        # 作者显式声明的亲属身份（角色卡 relations_kinship），冻结基准优先于描述句推断。
        kinship = snap.get("kinship_base") or {}
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
                # 冻结基准优先取作者显式声明的 kinship_base，其次才从基线描述的句首身份词推断。
                if k in base and base.get(k):
                    v = _preserve_kinship(base[k], v, declared=kinship.get(k))
                snap["relations"][k] = v
            else:
                # 涉及未在场/无卡关联人物（如某位仅被提及的亲属）：冻结为初始关系定位，
                # 禁止模型改写或升级（"小姨子"被写成"妻子"类漂移即在此拦截）。
                # 初始表无此键则丢弃该越权关系，不引入新条目。
                if k in base:
                    snap["relations"][k] = base[k]
    actions_ok = isinstance(data.get("actions"), dict)
    if actions_ok:
        snap["actions"] = {k: v for k, v in data["actions"].items() if v}
    else:
        # 纪官把 actions 写成字符串/数组时，本轮行为摘要不可用。
        # 此时绝不能按「全员无行为」去累加静默轮数——那会把所有在场角色误记成
        # 被遗忘、误触发硬性焦点，一次格式漂移污染后续多轮。故本轮跳过静默判定。
        snap["actions"] = {}
    # 在场即须留痕：用纪官的行为摘要判定谁本轮真的在戏里（替代 app.py 里按名字是否
    # 出现在正文的字符串判断——那个判不出「被提到名字但没有任何行为」）。
    # 镜头跟随时只统计镜头内角色：镜头外的人本轮就不该被写，计沉默会误伤。
    if actions_ok:
        _update_silent_rounds(snap, present)
    if isinstance(data.get("goals"), dict):
        for k, v in data["goals"].items():
            if v:
                snap["goals"][k] = v
    # 秘密：举证式归档（记录员模式）——引擎不猜，只核验证据是否真的出自正文
    for exp in _as_dict_list(data.get("secret_exposures")):
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
        # via 护栏（v0.17.3）：纪官必须声明「信息获取方式」且属实传类白名单。
        # 缺 via 或 via 不在白名单（如纪官填了「猜透/心知肚明」），说明该「得知」
        # 不是实际的信息传递，而是单方面心证——不能翻成暴露，降级为起疑。
        via = (exp.get("via") or "").strip()
        if via not in EXPOSURE_VIA_WHITELIST:
            logger.warn("secret", "曝光 via 非法（%r），降级为起疑：%s 对 %s 的秘密"
                        % (via, by, owner))
            for s in snap.get("secrets", []):
                if s.get("owner") != owner:
                    continue
                if by in (s.get("known_by") or []) or by in (s.get("holders") or []):
                    continue
                _record_suspicion(s, by, exp.get("evidence"), snap["scene"]["round"])
                break
            continue
        for s in snap.get("secrets", []):
            if s.get("owner") != owner:
                continue
            holders = s.setdefault("holders", list(s.get("known_by", [])))
            if by in holders:
                break
            # 语义护栏（v0.17.6，会话 467f1e4c）：via 合法 + 举证逐字在正文，
            # 仍须通过「事实锚点相关」+「施受方在场」两关，才采信为暴露。
            # 任一不过 = 证据虽在正文、却不构成该秘密的实际传递（内心独白/话题错位/
            # 不在场者），降级为起疑——宁可漏记，不可误记。
            if not (_evidence_related(exp.get("evidence"), s)
                    and _evidence_transfer(exp.get("evidence"), by, owner)):
                logger.warn("secret", "曝光语义未通过（锚点/施受方缺失），降级为起疑："
                            "%s 对 %s 的秘密（via=%r）" % (by, owner, via))
                if by not in (s.get("known_by") or []):
                    _record_suspicion(s, by, exp.get("evidence"),
                                      snap["scene"]["round"])
                break
            _record_exposure(s, by, via, snap["scene"]["round"])
            _ledger_entry(snap, s, by, snap["scene"]["round"])
            break

    # 起疑（线索逼近）：同样按举证归档。只记疑点、不记真相，起疑者不得因此剧透。
    # 这是「潜伏／曝光」二态之外的中间态——曝光前的逼近过程才是张力最足的一段。
    for sus in _as_dict_list(data.get("secret_suspicions")):
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
    for rel in _as_dict_list(data.get("handle_releases")):
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
        _update_secret_pressure(snap, _as_dict_list(data.get("secret_touches")))

    # 事实保全：常量只增不改（须逐字举证），状态覆盖式刷新。
    # 状态层：当前值的覆盖式刷新（回合数取容错写法——缺键不该让整轮回写失败）
    rd = (snap.get("scene") or {}).get("round", 0)
    update_states(snap, _as_dict_list(data.get("state_updates")), rd)
    # 人物位置：独立唯一真相源，与状态键分离（见 update_locations 说明）。
    update_locations(snap, _as_dict_list(data.get("location_updates")), rd)

    # 群演登记（语义提取）：由纪官按语义判断谁是新出场人物。
    # v0.17.2 起这是唯一登记入口——原散文正则挖掘（discover_aux_speakers）无法区分
    # 「他喃喃道」与「陈叔说」，误报不可根治，已退出登记链路（函数保留作离线工具）。
    # 此处仍过一遍结构护栏：纪官偶发也会把动词碎片/泛称当名字上报。
    # 改名合并：纪官声明「此人就是已登记的旧称呼」（如「某个泛称」自报「我叫X」）时，
    # 引擎核验 replaces 确在册后把旧条目改名，不产生重复 chip。
    aux_updates = _as_dict_list(data.get("aux_updates"))
    if aux_updates:
        aux_list = snap.setdefault("aux", [])
        existing = {a.get("name") for a in aux_list}
        exclude = (set(present) | existing
                   | set(store.list_characters())
                   | set(background_names_from_relations(snap, present))
                   | {ENV_PUSHER})
        new_names, new_notes, merges = [], {}, []
        for u in aux_updates:
            nm = (u.get("name") or "").strip()
            if not nm or len(nm) > 8:
                continue
            note = (u.get("note") or "").strip()
            old = (u.get("replaces") or "").strip()
            if old and old != nm and old in existing and nm not in existing:
                merges.append((old, nm, note))
                continue
            if nm in exclude:
                continue
            if _is_aux_garbage_name(nm):
                logger.warn("aux", "纪官上报的群演名未通过结构校验，已丢弃：" + nm)
                continue
            new_names.append(nm)
            if note:
                new_notes[nm] = note
        # 结构兜底：纪官漏填 replaces 时，用「自报姓名 + 本轮唯一提及的泛称旧群演」
        # 做证据合并。证据链不完整（旧称呼不是泛称、或本轮提及多条泛称）就不合并，
        # 宁可保留两条等下轮裁决——误合并会把两个人捏成一个人，比重复 chip 严重。
        if new_names:
            self_named = {m.group(1) for m in _AUX_SELFNAME_RE.finditer(reply)}
            mentioned = [a.get("name") for a in aux_list
                         if a.get("name") and a.get("name") in reply]
            generic_mentioned = [x for x in mentioned if _is_aux_generic_name(x)]
            if len(generic_mentioned) == 1:
                old = generic_mentioned[0]
                for nm in list(new_names):
                    if nm in self_named and nm != old:
                        merges.append((old, nm, new_notes.get(nm, "")))
                        new_names.remove(nm)
                        new_notes.pop(nm, None)
        if new_names:
            added = register_aux(snap, new_names, snap["scene"]["round"], new_notes)
            if added:
                logger.info("aux", "纪官登记新群演：" + "、".join(added))
        if merges:
            by_name = {a.get("name"): a for a in snap.get("aux") or []}
            for old, nm, note in merges:
                entry = by_name.get(old)
                if entry is None or nm in by_name:
                    # 旧称呼已被本轮更早的合并改掉，或新名与另一条目撞名：留给下次裁决
                    continue
                if _is_aux_garbage_name(nm):
                    logger.warn("aux", "合并新名未通过结构校验，保留旧称呼：" + old)
                    continue
                entry["name"] = nm
                if note:
                    entry["role"] = note
                logger.info("aux", "群演改名合并：" + old + " → " + nm)

    # 群演退场注销（对称于正式角色的 scene.leave）：纪官按语义判断某个已登记
    # 群演本轮是否永久性退场（死亡/被带走/彻底逃离队伍），引擎核验名字确在册后
    # 把 status 置「已退场」。保留条目不删除——删了会让「同一人物重新出场」被当成
    # 全新人物重复登记；只注销展示，前端按 status 过滤掉非活跃 chip。
    for dep in _as_dict_list(data.get("aux_departures")):
        nm = (dep.get("name") or "").strip()
        if not nm:
            continue
        # 正式登场角色的进出由场景导演（scene.apply 的 leave）处理，群演注销通道不接管。
        if nm in set(present) or nm in store.list_characters() or nm == ENV_PUSHER:
            continue
        entry = {a.get("name"): a for a in (snap.get("aux") or [])}.get(nm)
        if entry is None:
            # 不在群演册（可能是未登记的背景人物或正式角色），群演通道不处理。
            continue
        if entry.get("status") == "已退场":
            continue
        entry["status"] = "已退场"
        reason = (dep.get("reason") or "").strip()
        if reason:
            entry["note"] = reason[:60]
        # 退场即注销其残留短期目标（goals 只增不删，死者目标会挂到换场景才被清空；
        # 这里按名字同步清掉，与 aux status 注销对称）。goals 键是角色名，pop 安全。
        if isinstance(snap.get("goals"), dict):
            snap["goals"].pop(nm, None)
        logger.info("aux", "群演退场注销：" + nm)

    # 背景人物活动化：语义判定交给纪官，引擎只做逐字举证核验（记录员模式，
    # 与 secret_exposures 同一套）。写得下轮提示词点名批评用的名单，engine 不再
    # 靠正则删正文——旧链路误判率过高（实测真失责≈0）且后果是切碎用户看到的叙事。
    offs = background_names_from_relations(snap, present)
    if offs:
        viol = []
        for it in _as_dict_list(data.get("offscreen_activity")):
            nm = (it.get("name") or "").strip()
            if nm not in offs:
                continue
            if not _evidence_ok(it.get("evidence"), reply):
                logger.warn("director", "背景人物活动化举证未通过，已丢弃：" + nm)
                continue
            viol.append({"name": nm, "evidence": it.get("evidence"),
                         "round": snap["scene"]["round"]})
        if viol:
            snap["offscreen_violated"] = viol
            logger.warn("director", "背景人物被写成活动角色：" +
                        "、".join(v["name"] for v in viol))
        else:
            snap.pop("offscreen_violated", None)
    else:
        snap.pop("offscreen_violated", None)

    # 场景信号并联（零额外 LLM 成本）：纪官从叙事里读出「场景其实已经变了」，
    # 补上 scene._triggered 关键词表枚举不完的洞（关键词漏触发 = 场景与叙事脱节）。
    # v0.17.4：本轮就直接把 scene 追上叙事（不再留到下轮 scene.apply 消费）——
    # 旧链路 scene 在生成前跑、reflect 在生成后跑，只能把 scene_shift 存进快照、
    # 等下轮 scene.apply 才读，导致快照时间永远滞后正文一拍（正文已入夜、scene.time
    # 还停在「清晨」，下一轮提示词才纠正）。纪官既已从正文读到「实际入夜」，本轮
    # 落库就是安全的。time 经 scene._norm_time 清洗，避免纪官把描述句（夜幕降临）
    # 写进结构化字段。
    ss = data.get("scene_shift")
    if isinstance(ss, dict) and ss.get("changed"):
        sc = snap.setdefault("scene", {})
        if (ss.get("place") or "").strip():
            sc["place"] = (ss.get("place") or "").strip()
        raw_time = (ss.get("time") or "").strip()
        if raw_time:
            sc["time"] = scene._norm_time(raw_time, "", sc.get("time", "")).strip()
        if (ss.get("weather") or "").strip():
            sc["weather"] = (ss.get("weather") or "").strip()
        # 仍留一份 scene_shift 供下一轮 scene.apply 兜底：若下轮指令本身又触发
        # 场景切换，scene.apply 会基于「已追平的 scene」再判，不会重复推进。
        snap["scene_shift"] = {
            "changed": True,
            "place": sc.get("place", ""),
            "time": sc.get("time", ""),
            "weather": sc.get("weather", ""),
        }
    else:
        snap.pop("scene_shift", None)

    memory.save(sid, snap)
    return snap
