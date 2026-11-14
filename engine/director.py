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
# 题材高频词（绷带/小臂/发烧/通风口/家人）与"看见/察觉/露出"极易巧合共现，
# 实测 150 次判定放行 33 次（22%），校验形同虚设。
# 下限只用于挡掉「一两个字碰巧命中」的伪举证（如只写「伤口」「他」），不是长度门槛。
# 早前设为 8 会把真实短句误杀——压测实证纪官就死亡举证「没有脉搏。」（5 字，逐字出现在正文），
# 硬常量硬生生漏记。逐字核验本身已足够防伪，故下限压到 4。
EVIDENCE_MIN_LEN = 4

# 秘密「暴露」的合法信息获取方式（纪官 secret_exposures.via 白名单）。
# 只有这些「信息实际发生了跨角色传递」的动作才算暴露；缺 via、或 via 是
# 「猜透/心知肚明/早已知道」等单方面心证，一律不算——那些只能算起疑。
# 这是 v0.17.3 修复：此前曝光归档只看「举证逐字在正文」+ 纪官语义判断，
# 纪官会把「角色内心想到他早就知道」这类心理描写误报成「实际得知」，
# 导致潜伏秘密在开场即被翻成「暴露」（一次真实事故）。
#
# v0.26.0：新增「自述/承认」——秘密**归属者本人**当众说开。它与「他人获取」类
# via（看见/听见/被告知/发现物证）语义不同：本人自愿交出，他人无从据此要挟，
# 故只写 known_by、不入 holders，并把秘密标记为「已公开」（见 SELF_DISCLOSURE_VIA）。
EXPOSURE_VIA_WHITELIST = ("看见", "听见", "被告知", "发现物证", "自述", "承认")

# 归属者自述/承认类 via：秘密由本人当众说开，信息扩散但不再构成把柄。
# 单独成组是为了让 _record_exposure 区分「他人获取（把柄入手）」与「本人交出（把柄作废）」：
# 前者入 holders -> 暴露（仍为把柄）；后者只入 known_by 且置 public -> 已公开。
SELF_DISCLOSURE_VIA = ("自述", "承认")

# （机会等级/内容尺度机制已随 NSFW 整体废弃，v0.8.0：ALONE/DEFENSE_DOWN/OBSTACLE/OPP_NOTE 已移除）


def _secret_state(s, present=None):
    """推定一条秘密当前所处的一态（四态：潜伏 / 起疑 / 暴露 / 已公开）。

    优先级：已公开 > 暴露 > 起疑 > 潜伏。

    - 已公开：秘密已成公开事实，无人能再据此胁迫。触发条件 = 归属者本人当众自述/承认
      （s["public"] 置位）**且众人皆知**（在场非归属者全部已知情）。第二重「众人皆知」
      是定义层护栏：模型易把「第三方的当众指控」也填成自述类 via（实测探针 R2 事故），
      若只看 public 标志会提前把「只有个别人知情」的秘密误标公开。有在场名单时以
      「在场非归属者是否都知情」为准；无在场名单（离线/单测）时退化为只看 public 标志。
    - 暴露：有人确已知情（known_by 非空，含把柄持有者），即「暴露（仍为把柄）」；
      秘密在部分人之间流转、尚未众人皆知。
    - 起疑：尚无人坐实，但有非归属者起了疑心（线索逼近）——张力最足的一段。
    - 潜伏：无人知情、无人起疑。

    与旧版二态（暴露/潜伏）的差异：旧版只看 holders，把柄一释放就回落「潜伏」，
    导致「归属者当众承认、天下皆知」被错误显示为「潜伏」（实测探针 R6 事故）。
    v0.26.0 引入四态，把「已公开」与「暴露」分开，并让 known_by 非空者永不回落潜伏。
    """
    if s.get("public"):
        peers = [p for p in (present or [])
                 if p and p != ENV_PUSHER and p != s.get("owner")]
        known = s.get("known_by") or []
        # 有在场名单：须众人皆知才算公开；尚有人不知情则不判公开（落回暴露/起疑）。
        if not peers or all(p in known for p in peers):
            return "已公开"
    holders = s.get("holders")
    if holders is None:
        holders = s.get("known_by", [])
    if any(k != ENV_PUSHER for k in holders):
        return "暴露"
    # 已知情（holders 空 = 把柄已失效/转走，或本人交出）：仍未众人皆知 -> 暴露（不判公开）。
    if any(k != ENV_PUSHER for k in (s.get("known_by") or [])):
        return "暴露"
    owner = s.get("owner")
    if any((x.get("by") or "") not in (ENV_PUSHER, owner)
           for x in (s.get("suspicions") or [])):
        return "起疑"
    return "潜伏"


def _record_exposure(s, by, via, round_no, present=None):
    """记录一次秘密曝光：写入知情者集合、（视 via）把柄持有集合，并重算状态。

    两类 via 语义分离（v0.26.0）：
    - 他人获取（看见/听见/被告知/发现物证）：by 同时成为知情者(known_by)与把柄持有者
      (holders) -> 状态「暴露（仍为把柄）」。
    - 归属者自述/承认（SELF_DISCLOSURE_VIA）：by 只成为知情者，**不入 holders**——
      秘密由本人当众交出，他人无从据此要挟；同时置 s["public"]。只有「众人皆知」
      （在场非归属者全知情，由 _secret_state 判定）才真正翻「已公开」。

    known_by 不可逆（知道了就无法不知道），holders 可因把柄消除而移除。
    present 用于 _secret_state 的「众人皆知」判定（缺省则退化为只看 public 标志）。
    """
    s.setdefault("holders", list(s.get("known_by", [])))
    if by not in s["known_by"]:
        s["known_by"].append(by)
    if via in SELF_DISCLOSURE_VIA:
        # 本人交出：扩知情、把柄作废（清 holders）-> 置公开标志。
        # 是否真公开由 _secret_state 结合在场名单判（须众人皆知）。
        s["public"] = True
        s["holders"] = []
    elif by not in s["holders"]:
        s["holders"].append(by)
    s.setdefault("exposures", []).append({"by": by, "via": via, "round": round_no})
    # 确知情即结算其起疑记录：起疑是逼近过程，曝光是终点，二者不并存
    _clear_suspicion(s, by, present)
    s["state"] = _secret_state(s, present)


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


def _record_suspicion(s, by, clue, round_no, present=None):
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
            s["state"] = _secret_state(s, present)
            return True
    susp.append(entry)
    if len(susp) > _SUSPICION_CAP:
        del susp[:len(susp) - _SUSPICION_CAP]
    # 由无到有的一条起疑：状态须从「潜伏」翻到「起疑」（四态下起疑是可显示态）。
    s["state"] = _secret_state(s, present)
    return True


def _clear_suspicion(s, by, present=None):
    """某人确已知情后结算其起疑记录。

    知情是起疑的终态，两者并存会同时注入「你在怀疑他」与「你握有他的把柄」
    两种提示，自相矛盾。
    """
    susp = s.get("suspicions") or []
    rest = [x for x in susp if x.get("by") != by]
    if len(rest) == len(susp):
        return False
    s["suspicions"] = rest
    s["state"] = _secret_state(s, present)
    return True


def _release_handle(s, frm, to, round_no, present=None):
    """把柄失效/转手（全版）：操作 holders（握把柄者）；转手给 to 时 to 也入 known_by。

    to 为空表示彻底失去（药物被丢弃、证据被销毁、当众说开后不再构成胁迫）。
    转手语义：to 接过把柄即必然知情（prompter 的 holders 分支会给其完整秘密真相，
    否则无从据此要挟），故 to 同时写入 known_by——知情不可逆，之后即便 to 再失去
    把柄也不「凭空失忆」。frm 的 known_by 不移除（它已知道，信息不可逆）。
    holders 清空后由 _secret_state 重算状态：known_by 非空者不再回落「潜伏」——
    归入「暴露（已知情）」，若归属者已公开且众人皆知则为「已公开」
    （v0.26.0 四态：旧版回落「潜伏」会让已天下皆知的秘密显示成没人知道，见探针 R6 事故）。
    返回 True 表示确有变更。
    """
    s.setdefault("holders", list(s.get("known_by", [])))
    hb = s["holders"]
    if frm not in hb:
        return False
    hb = [k for k in hb if k != frm]
    if to and to != s.get("owner"):
        if to not in hb:
            hb.append(to)
        # 转手即知情：to 接过把柄必然知道秘密，写入 known_by 保持「知情不可逆」。
        if to not in s.get("known_by", []):
            s.setdefault("known_by", []).append(to)
    s["holders"] = hb
    s["state"] = _secret_state(s, present)
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


# ---- 暴露语义护栏（v0.17.6，真实事故）----
# _evidence_ok 只验证「举证原文在不在正文里」，不验证「这段原文是否真的构成
# 该秘密的信息传递」。纪官会把「内心独白 / 猜测 / 讨论另一话题 / 家庭共享背景」
# 截成一段确实存在于正文的原文当证据，从而把潜伏秘密误翻成「暴露」——
# 一次真实会话第十回合多名角色秘密被误标暴露，正文却无任何暴露动作。
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


# （镜头跟随 compute_focus 已于 2026-11-08 引擎瘦身删除）
# 它判「镜头」的唯一依据是「指令字符串里有没有出现某个角色的名字」——判不出语义
# （「避开众人」曾被当成群体点名），却驱动两件实事：注入【镜头跟随】段压制其余角色、
# 生成后按焦点裁剪正文（被裁的角色连记账都吃不到）。谁与谁同场、主镜头落在哪一处，
# 已由 prompter.scene_roster_block 按 locations 分场表达，那是确定性规则。
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
        "round": snap["scene"]["round"],
    }, snap


# （REFUSAL_MARKERS / _mask_refusal / detect_intimacy / after_reply 已随 NSFW 废弃，v0.8.0；
#  中性后果留痕由 ledger + A2 激活路径覆盖，不再绑定性行为「越线」判定）


def _salvage_json(text):
    """抢救无法整体解析的半成品 JSON：保留已完整输出的头部成员，丢弃坏掉的尾部。

    纪官输出条目多（关系/行动/目标/秘密三类/事实两层），尾部可能在两种情况下损坏、
    导致整体解析失败而整轮回写全丢——比丢一两条严重得多：
      ① 截断：超出 max_tokens，尾部在字符串中间被硬切；
      ② 畸形：模型偶发在尾部吐出结构性坏 JSON（单引号键、裸控制符、裸键、夹带自我
         纠正长串）。实测这类坏区**恒在尾部**，头部（秘密簿记，已排最前）保持合法。
    这里沿字符流跟踪括号深度与字符串状态，收集**所有**深度回到 1（顶层成员边界）的
    候选切点，再**从最新往最旧逐个试解析**，返回第一个成功的。

    回退式的意义：取"最后一个**能解析**的边界"而非"最后一个边界"——尾部坏区之前的
    边界能解析成功，头部合法簿记就保住了，牺牲的只是尾部低危的冗长字段，与 reflect
    输出字段重排确立的"截断优先级"一致。纯截断场景（R01）行为不变：最后一个边界本就能
    解析，回退第一步即命中。
    """
    s = text.strip()
    if not s.startswith("{"):
        return None
    depth = 0
    in_str = False
    esc = False
    cuts = []                     # 所有顶层成员边界切点（不含该切点自身）
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
                    cuts.append(i + 1)    # 刚闭合一个顶层成员
            elif ch == "," and depth == 1:
                cuts.append(i)            # 成员分隔符：其前是完整成员
        i += 1
    # 不要求末尾深度回到 1：截断/畸形本就发生在任意深度，只要存在可解析的完整边界即可。
    # 从最新往最旧回退：尾部坏区之前的边界能解析成功即命中，保住头部合法簿记。
    for cut in reversed(cuts):
        if cut <= 1:
            continue                          # 连一个完整成员都没有
        try:
            return json.loads(s[:cut] + "}")
        except json.JSONDecodeError:
            continue                          # 该边界之前仍含坏区，继续往更前回退
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



def validate_present(reply, present, known_names):
    """后处理：只剥「不属于本局名册」的角色台词块（串剧本 / 幽灵角色）。

    判定口径：以行首「角色名：」认说话人，把有卡但不属于本局名册的角色台词块
    （含其续行）移除；无说话人的叙述行与名册内角色台词保留。
    返回 (清洗后文本, 是否发生违例)。

    v2.6.0 起正文定形为小说体散文（台词融在叙述里，不以「角色名：」起段），
    这条守卫因此是惰性的：正常小说体正文里没有可匹配的行首标记，一个字都不会被剥，
    它只在模型格式漂移回剧本分行体时才起作用——那正是它存在的理由（串剧本 / 幽灵角色）。

    v2.1.0：`present` 是「角色名册」（建局 cast，永不收缩），不是在场名单。
    2026-11-08 起不再接受焦点子集裁剪：焦点只由名字字符串判出，裁剪却会真删正文，
    被删的角色既没戏也没进任何记账（reflect 在裁剪后的正文上举证），事故无法回溯。
    """
    keep = set(present)
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
            if sp not in keep:            # 不在名册（含环境推手、别剧本的角色）
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

    这是剧本作者在角色卡里**显式写下**的关系网，优先级高于 LLM 自由生成——
    避免 LLM 把"小姨子"推成"妻子"之类漂移。
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
        # 额度口径用 cards_present 的人数：本函数没有 present 这个局部名，早先写错成
        # len(present) 会抛 NameError，被外层 except 吞掉——缺口推断因此从未真正调用过模型。
        raw = llm.complete(prompt, max_tokens=max(700, 180 * max(len(cards_present), 4)),
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
    推断结果写回 snap["relations"]；写回后即为最终口径，纪官不再改写关系
    （见 reflect 的字段归属注释）。

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
    return gap_chars


# 纪官回写的输出额度：纪官字段已收窄（秘密簿记 + 位置 + 状态），额度仍留宽裕——
# v0.28.4：实测满负荷轮（6 角色）输出 2.6~4.3k 字符（约 2~3k+ token），1800 明显不够，
# 截断后 JSON 变非法、_extract_json 解析失败、整轮秘密簿记静默丢失（4/6 暗牌全程潜伏）。
# v2.1.6：思考链模型把 reasoning 计入 max_tokens（实测 2557/2800 吃光预算致截断），
# 根因已由 llm 层关思考送达（reasoning_effort）修掉；2800→4096 作双保险，
# 纯 content 模型不触顶零成本（实测满负荷 content 仅 ~663 token）。
REFLECT_MAX_TOKENS = 4096


# 状态层键上限：超出淘汰最久未更新的键（状态是覆盖式的，键数本由对象数决定，此为兜底）。
STATE_CAP = 20
# 人物位置表上限：只存「谁在哪里」的当前值，一角色一位置，后写覆盖前写。
# 角色数（cast）通常远小于 20，上限是防纪官把同名泛称造出一串位置键。
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
    不容「某人在电梯」「某人在卧室」两条记录并存（一次真实会话 R14 事故正是
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


def _log_reflect_failure(sid, round_no, reason):
    """reflect 失败落盘：SSE 日志总线是内存环形缓冲，会话结束即丢，无法事后取证。

    把每次「本轮状态未回写」追加进会话目录的 reflect.jsonl（与 chat.jsonl 同目录、
    随 delete_session/prune_sessions 一起清理），使静默失败在会话结束后仍可追溯。
    纯留痕，任何异常都不阻断主流程（reflect 失败本就不得阻塞叙事）。
    """
    try:
        import time
        folder = memory.SESS_DIR / sid
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / "reflect.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(
                {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                 "round": round_no, "reason": reason},
                ensure_ascii=False) + "\n")
    except Exception:
        pass


def reflect(sid, reply, directive=""):
    """生成后状态回写（簿记，不做创意判断）：秘密的知情变化、人物位置、物件现状。

    纪官只回答「本轮之后世界里什么是真的」，不回答「接下来该写什么」。
    2026-11-08 引擎瘦身：原先它还改写关系定性、抽每轮行为摘要、编短期目标、判场景
    是否变化、判秘密有没有被触及——五者都是记账层越界替叙事层做决定（详见下面
    prompt 里的注释）。任何解析/调用失败都保持快照不变，绝不阻塞主流程。

    directive：本轮导演指令（环境推手本轮的权威设定）。关键事实（如某群演死亡）
    可能只由指令承载、正文未清晰复述甚至被弱化，故退场判定须同时参照它。
    自然推演轮指令为空，prompt 不增行，零 token 增量。
    """
    snap = memory.load(sid)
    if not snap:
        return None
    present = snap.get("present", [])
    if not present:
        return snap

    # 秘密全景（含已被谁知情 + 秘密正文真相）：把柄可失去/转手，纪官必须知道当前持有情况；
    # 同时喂 content 与 keys 作为语义锚点——此前只回喂 owner 名 + 状态，纪官蒙眼归档，
    # 会把「出现归属者名字的无关情报」误挂到其秘密上（一次真实会话：把「某角色剥另一角色衣服」
    # 塞进「另一角色怯战」起疑记录），而真正该记的「怯战铁证」因正文用代称、
    # 不命中 keys 被降级漏记。喂全文后纪官有真相锚点可对，错配与代称漏记双治。
    sec_lines = []
    for s in snap.get("secrets", []):
        kb = [k for k in (s.get("holders") or s.get("known_by", [])) if k != ENV_PUSHER]
        sp = [x.get("by") for x in (s.get("suspicions") or []) if x.get("by") != ENV_PUSHER]
        content = (s.get("content") or "").strip()
        keys = "、".join(k for k in (s.get("keys") or []) if k)
        line = (f"{s.get('owner')}（{s.get('state')}｜握有把柄者："
                f"{'、'.join(kb) if kb else '无'}")
        if sp:
            line += f"｜已起疑者：{'、'.join(sp)}"
        line += "）"
        if content:
            line += "\n    · 秘密真相：" + content
        if keys:
            line += "\n    · 事实锚点词：" + keys
        sec_lines.append(line)
    secret_text = "\n".join(sec_lines) or "（无秘密）"
    # 既有状态键回喂：不把键名摆出来，纪官就会为同一对象造同义新键（压测实证 20 轮造出
    # 3 个「角色B手臂*」），覆盖式存储退化成追加式。列出既有键，要求沿用、勿造同义键。
    st_text = "、".join(sorted((snap.get("states") or {}).keys())) or "（无）"
    # 既有位置回喂：纪官须知道谁上一轮在哪，才能在本轮移动后正确更新、而非另造同义键。
    loc_lines = [f"{k}：{(snap['locations'][k].get('place') or '')}"
                 for k in sorted((snap.get("locations") or {}).keys())]
    loc_text = "；".join(loc_lines) or "（无）"
    # 当前场景锚点回喂：给「原地未动的在场角色」一个基准地点。无此锚点时，模型判定
    # 「谁都没移动＝没有位置变化＝不报 location_updates」，整轮漏报导致左栏【人物位置】
    # 全员缺席（一次真实会话：朝会开局 6 人皆「停在原处」，actions 正常、locations 全空）。
    # 位置是物理事实而非猜测，喂了场景地点，原地未动者至少能报到场景基准处。
    _sc = snap.get("scene") or {}
    scene_text = "｜".join(x for x in (_sc.get("place"), _sc.get("time"), _sc.get("weather")) if x) or "（无）"
    # 导演指令回喂：关键事实（群演死亡等）可能只由导演指令承载、正文未复述甚至弱化。
    # 仅当指令非空时占一行，自然推演轮零开销。指令是环境推手的权威设定，优先级高于正文。
    dir_block = ("\n本轮导演指令（环境推手设定，权威，正文与其冲突时以指令为准）：\n" + directive + "\n") if directive else ""

    prompt = [
        {"role": "system",
         "content": "你是关系沙盘的纪官。只做簿记：归档本轮秘密的知情变化，记录各角色当前位置与物件现状。只输出一个 JSON 对象，不要任何解释或 Markdown 代码块。"},
        {"role": "user", "content": (
            f"在场角色：{', '.join(present)}\n"
            f"秘密与把柄现状：\n{secret_text}\n"
            f"既有状态键：{st_text}\n"
            f"既有位置：{loc_text}\n"
            f"当前场景：{scene_text}\n"
            f"{dir_block}"
            f"本轮叙事：\n{reply}\n\n"
            # 纪官字段的归属（2026-11-08 引擎瘦身，simon 裁决）
            # 纪官只留三样簿记：秘密知情变化（exposures/suspicions/handle_releases）、
            # 人物位置（location_updates）、物件现状（state_updates）。删掉五样：
            #   relations——纪官把关系压成 ≤30 字标签覆盖作者手写的细部（审计 P3：
            #     「他知道台阶是他递的」这类戏剧信息从 R2 起再也看不到）。关系归作者，
            #     由角色卡 relations 固化进 snap["relations"]，恒定回注、不再被模型改写。
            #   goals——短期目标是引擎替角色想的意图，与角色卡的核心渴望/恐惧重复供给；
            #   actions——只为「久未登场提醒」服务，提醒机器一并删除；
            #   scene_shift——场景由导演指令决定，见 scene.resolve；
            #   secret_touches——只为发酵压力服务，压力机器一并删除。
            # 字段顺序仍是截断优先级：条目短而脆弱的物理事实排在秘密簿记之后，
            # 保证被 max_tokens 截断时先丢冗长条目而不是丢位置（v0.31.1 的教训）。
            "请输出 JSON：\n"
            "{\n"
            '  "secret_exposures": [{"owner": "秘密归属者", "by": "本轮得知该秘密的角色名", "via": "信息获取方式，只能填「看见/听见/被告知/发现物证/自述/承认」六类之一", "evidence": "本轮叙事原文片段"}],\n'
            '  "secret_suspicions": [{"owner": "秘密归属者", "by": "本轮起了疑心的角色名", "evidence": "本轮叙事原文片段（引发怀疑的那句话/那个细节）"}],\n'
            '  "handle_releases": [{"owner": "秘密归属者", "from": "失去把柄的人", "to": "接过把柄的人（彻底失去则填空字符串）", "evidence": "本轮叙事原文片段"}],\n'
            '  "location_updates": [{"who": "角色名", "place": "该角色本轮结束时所在的具体地点"}],\n'
            '  "state_updates": [{"subject": "对象（如某道门、某件物品、某人的伤）", "value": "当前状态一句话"}]\n'
            "}\n"
            "规则：\n"
            "- secret_exposures 只填本轮叙事里**确实发生**了「某人得知了某秘密」的条目；仅凭角色起了疑心、或只是提到相关物品，都不算。\n"
            "- secret_exposures 的「得知」必须是**信息实际发生了跨角色传递**：亲眼看见、亲耳听见、被当面告知、亲手发现物证；除此之外一律不算暴露。\n"
            "- via 填「自述/承认」专指**秘密归属者本人**当众说开，只用于本人真的说开的轮次："
            "by 逐条填听到的在场者（同一秘密可多条）。"
            "反例触发词：他人转述、第三方指控、归属者否认。\n"
            "- **内心活动不算得知**：心理描写、内心独白、回忆、猜透——即使明写了他「知道」也只是单方面心证，绝不填 secret_exposures，至多填 secret_suspicions。反例触发词：心想他早就知道、暗自看穿、早已心知肚明、在心里确认了。\n"
            "- secret_suspicions 填**线索逼近但尚未坐实**的条目：某人察觉对方言行反常、追问只得到含糊其辞的回答、发现了与旧事相关的物品或痕迹、或对某人的说法明显不信。只有当事人已经确知真相才算 secret_exposures，不算起疑。\n"
            "- secret_suspicions 的 by 不能是秘密归属者本人，也不能是已确知该秘密的人；同一处细节不要同时填进 secret_exposures 与 secret_suspicions，拿不准就填起疑（较轻），宁可让秘密晚一点被揭开。\n"
            "- handle_releases 只填本轮叙事里**确实发生**了「把柄消失或转手」的条目：例如药物/证据/信件被丢弃、被夺走、交给第三方、或当众说开后不再构成胁迫。to 为空字符串表示彻底消失。\n"
            "- evidence 逐字照抄本轮叙事的一段连续原文，照抄不到就不要填（核验不过即丢弃）。"
            "反例触发词：改写概括、代词换角色名。\n"
            "- 宁可少填也不要误填：填错会让秘密提前暴露或让把柄凭空失效。\n"
            "- state_updates 填当前状态的最新值，只填本轮有变化的对象（状态被解除也算变化）；"
            "subject 沿用「既有状态键」的名字，同一对象直接覆盖、不造同义新键；"
            "人物位置不写进这里（走 location_updates）。"
            "反例触发词：角色裸名、情绪类泛称、把「谁在哪里」塞进物件键。\n"
            "- location_updates 给本轮正文写到的角色各报一条当前位置：写到的必报（人没动也报，"
            "未点明具体处就报当前场景基准处），who 用「在场角色」里的正式名字；"
            "正文没写到的不报、不替他占位；每角色只报一条。"
            "place 写叙事末尾他实际所处的具体地点（点明班次/站位就报具体），不写「外面」「那边」这类泛称。"
            "反例触发词：替没出场的人报基准处、泛称地点、同一角色报两条。"
            "「翻窗逃到隔壁单元」这类还会回来的暂时逃离不填。\n"
        )},
    ]
    try:
        raw = llm.complete(prompt, max_tokens=REFLECT_MAX_TOKENS, temperature=0.3,
                           timeout=120)
    except Exception:
        logger.warn("director", "纪官调用失败，本轮状态未回写")
        _log_reflect_failure(sid, (snap.get("scene") or {}).get("round", 0), "call_failed")
        return snap
    data = _extract_json(raw)
    if not data:
        logger.warn("director", "纪官输出无法解析，本轮状态未回写")
        _log_reflect_failure(sid, (snap.get("scene") or {}).get("round", 0), "unparseable")
        return snap
    if not _is_complete_json(raw):
        # 抢救成功：字段已部分回写，但末尾条目多半丢了，留痕便于定位。
        logger.warn("director", "纪官输出疑似被截断，已抢救回写部分字段（末尾条目可能丢失）")
        _log_reflect_failure(sid, (snap.get("scene") or {}).get("round", 0), "truncated")

    # 关系定性不再由纪官改写（2026-11-08 引擎瘦身）：snap["relations"] 建局时即由
    # 角色卡 relations 固化（作者口径），此后不变。旧版它先被压成 ≤30 字标签、
    # 再过两道冻结闸，作者手写的戏剧细部只活一轮（审计 P3）；闸本身就是为堵模型的
    # 越权改写而建的，源头撤掉后闸也不再需要。亲属身份漂移（"小姨子"→"妻子"）同理消失。
    # 举证窗口：纪官的「谁在哪里」只认正文（与 secret_exposures 的 evidence 核验同一
    # 原则——引擎不猜，只核验出处）。v2.1.2 实证：present 改成名册后，纪官把「名册」
    # 当「本轮在场」，把正文里根本没出现的角色报进 locations，把不在场的人钉进当前
    # 场景，下一轮 [本轮场面] 就照着错记录分场。
    _spoken = (reply or "") + "\n" + (directive or "")
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
                _record_suspicion(s, by, exp.get("evidence"),
                                  snap["scene"]["round"], present)
                break
            continue
        self_disc = via in SELF_DISCLOSURE_VIA
        for s in snap.get("secrets", []):
            if s.get("owner") != owner:
                continue
            holders = s.setdefault("holders", list(s.get("known_by", [])))
            # 他人获取类：已握把柄者不重复入账（把柄已在手，非新信息）。
            # 本人自述类无此限制——即便 by 已知情/已握把柄，归属者当众说开这一事实
            # 也须把状态翻到「已公开」（把柄作废），不能被「已在 holders」短路掉。
            if not self_disc and by in holders:
                break
            # 语义护栏（v0.17.6）：via 合法 + 举证逐字在正文，
            # 仍须通过「事实锚点相关」+「施受方在场」两关，才采信为暴露。
            # 任一不过 = 证据虽在正文、却不构成该秘密的实际传递（内心独白/话题错位/
            # 不在场者），降级为起疑——宁可漏记，不可误记。
            # 本人自述/承认天然成立（施受双方就是 owner 与 by，且本人复述必是真实传递），
            # 不做语义护栏，直接采信（是否真「已公开」由 _secret_state 结合在场名单判）。
            if not self_disc and not (_evidence_related(exp.get("evidence"), s)
                                      and _evidence_transfer(exp.get("evidence"), by, owner)):
                logger.warn("secret", "曝光语义未通过（锚点/施受方缺失），降级为起疑："
                            "%s 对 %s 的秘密（via=%r）" % (by, owner, via))
                if by not in (s.get("known_by") or []):
                    _record_suspicion(s, by, exp.get("evidence"),
                                      snap["scene"]["round"], present)
                break
            _record_exposure(s, by, via, snap["scene"]["round"], present)
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
            _record_suspicion(s, by, sus.get("evidence"),
                              snap["scene"]["round"], present)
            break

    # 把柄消除：同样按举证归档。仅操作 holders（握把柄者），known_by 保持不变；
    # holders 清空后由 _secret_state 重算（信息不可逆，不回落「潜伏」）。
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
                    s, frm, to, snap["scene"]["round"], present):
                break

    # 事实保全：常量只增不改（须逐字举证），状态覆盖式刷新。
    # 状态层：当前值的覆盖式刷新（回合数取容错写法——缺键不该让整轮回写失败）
    rd = (snap.get("scene") or {}).get("round", 0)
    update_states(snap, _as_dict_list(data.get("state_updates")), rd)
    # 人物位置：独立唯一真相源，与状态键分离（见 update_locations 说明）。
    # 同样按正文举证：纪官会把没出场的名册成员报进 location_updates（v2.1.2 实证，
    # 有配角被报成本轮场景），那种记录会把下一轮的分场带偏。
    update_locations(snap, [x for x in _as_dict_list(data.get("location_updates"))
                            if (x.get("who") or "").strip() in _spoken], rd)
    # 兜底（v0.31.1，v2.1.1 收窄到「正文写到的人」）：对仍无位置记录的角色，用 scene.place
    # 填最小正确值。位置是物理事实而非猜测——但 v2.1.0 起 present 是**名册**（全员），
    # 对全名册兜底等于把正文没写的人也搬进这一场：寝殿独处那一轮，六个人全被记在寝殿，
    # 下一轮 [本轮场面] 就照着错的记录分场。故判据为「本轮正文或指令点到过这个名字」，
    # 没点到的人留空，由 [本轮场面] 的「位置未更新」如实交代。
    _scene_place = ((snap.get("scene") or {}).get("place") or "").strip()
    if _scene_place:
        _loc = snap.setdefault("locations", {})
        for _who in present:
            if _who not in _spoken:
                continue
            _n = _STATE_NOISE.sub("", _who)
            if any(_STATE_NOISE.sub("", k) == _n for k in _loc):
                continue
            _loc[_who] = {"place": _scene_place, "round": rd}

    # 场景（地点/时间/天气）不再由纪官反推（2026-11-08 引擎瘦身）：场景是导演指令的
    # 领域，纪官从正文猜场景等于让正文去改导演的设定；它与 scene 层的规则判定并存时，
    # 同一次换场会被追平两次。场景变化只走 scene.resolve 的指令解析。

    # v2.1.0 拆职责：present 不再是「在场名单」而是「角色名册」（建局 cast，永不收缩），
    # 原 present_change 语义兜底整段移除。原因不是「模型判不准」，而是这个字段同时
    # 承担了两件互相冲突的事——「本轮可写的人」与「物理上同处一地的人」。实测（8 轮探针
    # + 手动插回模板复测）：模型按「本轮叙事重点」判离场，把与主角同处一室的角色踢出去、
    # 把千里之外的人留场；arrive 又基本不填。补回它会切断支线，不补则它始终是死代码。
    # 物理同场改由 locations 表达（[本轮场面] 段渲染），可写范围由名册表达。

    memory.save(sid, snap)
    return snap


# ----------------------------------------------------------------------------
# 叙事去重（v0.22.x，泛用性：与后端采样参数完全解耦）
# ----------------------------------------------------------------------------
# 背景：repeat_penalty 是 llama.cpp 私有扩展，多数非 llama.cpp 后端会静默忽略（返回 200
# 但采样层不生效），导致长上下文 + 高重复母题场景下出现整段复读（一次真实会话
# 的「还要多久？/是他吗？/穿好/我去看看窗户」及周围段落逐字重复）。采样层参数
# 无法跨后端统一，故在引擎层做「生成后复读检测」，检测到即由上层重生成。
# 完全不吃后端能力，任何 OpenAI 兼容后端分发出去都有效。
#
# v0.31.2 恢复：本机制曾在 v0.31.0「第二批机制精简」中被误判为「NSFW 特异化」而删除
# 但它是与 NSFW 无关的泛用防复读。一次真实会话普通叙事整段复读
# 证明删除后失去引擎层兜底、只剩采样层 frequency_penalty（压不住整段 n-gram 回卷）。
# ============================================================================

# 复读检测的 n-gram 长度：8 字窗口足够锚定「整段重复」，又不至于把正常的
# 「角色名 + 动作」局部复用（2-4 字）误判为复读。
_NGRAM = 8
# 复读判定阈值：本轮输出与最近一轮历史的 8-gram 重叠率超过该值即判复读。
# 0.2 为适中档（2026-10-12 选定）：覆盖大多数复读，又不把正常反复修辞误判。
_REPEAT_THRESHOLD = 0.2
# 参与比对的最近历史轮数（v0.28.7 放宽 3→30）：旧 3 轮窗口只抓「紧邻上一轮」的复读，
# 盖不住「隔多轮复发的场景母题」——一次真实会话实测最远复读隔了 14 轮
# （R3 某角色的肢体动作段落 R17/R35 原样复现），全部落在 3 轮窗口外被漏检落盘。
# 放宽到 30 覆盖此类母题复发。窗口是滑动截断 history_texts[-30:]，单轮成本恒定
# （不随总回合数增长，实测 18 轮会话平均 ~4ms/轮，相对 LLM 秒级生成可忽略）。
# 配合 _MIN_REPEAT_SPAN 上调（30→50）压住大窗口带来的远距离合理回扣误判。
_COMPARE_ROUNDS = 30
# 最长重复子串阈值（v0.28.7 上调 30→50）：窗口放宽到 30 后，比对历史变多，
# 远距离「同一场景名 / 同一句台词合理复现」会被 30 字门槛误判成复读。上调到 50
# 只抓「整段搬」（≥50 字逐字重复），放过短句呼应。实测 a20d1c03 的 6 例大幅复读
# 均 ≥100 字，50 字门槛对真复读零漏检、对 R11/R12 等干净情节轮（最长 15/26 字）零误伤。
_MIN_REPEAT_SPAN = 50


def _ngrams(s, n=_NGRAM):
    """提取文本的 n 字滑动窗口集合（去标点、折叠空白后）。"""
    t = _strip_punct(_norm_text(s))
    if len(t) < n:
        return set()
    return {t[i:i + n] for i in range(len(t) - n + 1)}


def _has_common_span(a, b, minlen=_MIN_REPEAT_SPAN):
    """a、b 去标点折叠空白后，是否存在 ≥minlen 字的逐字公共子串。

    只需判断「存在性」而非找最长——用 b 的所有 minlen 字子串建哈希集合，
    扫 a 的 minlen 字子串查表即可，O(n)。命中即返回 True。
    """
    sa = _strip_punct(_norm_text(a))
    sb = _strip_punct(_norm_text(b))
    if len(sa) < minlen or len(sb) < minlen:
        return False
    sb_set = {sb[i:i + minlen] for i in range(len(sb) - minlen + 1)}
    for i in range(len(sa) - minlen + 1):
        if sa[i:i + minlen] in sb_set:
            return True
    return False


def detect_narrative_repeat(text, history_texts, threshold=_REPEAT_THRESHOLD,
                            ngram=_NGRAM, compare_rounds=_COMPARE_ROUNDS,
                            min_span=_MIN_REPEAT_SPAN):
    """检测本轮叙事是否发生复读（三类：轮内自重复 + 整段历史重复 + 局部历史重复）。

    text：本轮生成的正文。
    history_texts：历史 assistant 正文列表（按时间序，末尾为最近一轮）。
    返回 (是否复读, 最大重叠率, 复读类型)。

    复读类型：
      'self'：同一轮内部整段重复（一次真实会话轮 19 的「我去看看窗户」重复两次）
      'history'：与最近历史轮整段/局部重复（轮 15 与轮 17 的「还要多久？」）
      None：未复读

    空文本或历史不足时返回 (False, 0.0, None)，不误判。
    """
    t = _strip_punct(_norm_text(text))
    cur = _ngrams(text, ngram)
    if not cur:
        return False, 0.0, None

    # 1) 轮内自重复：前半段 n-gram 在后半段是否大量重现
    best = 0.0
    kind = None
    if len(t) >= ngram * 2:
        half = len(t) // 2
        first_half = _ngrams(t[:half], ngram)
        second_half = _ngrams(t[half:], ngram)
        if first_half and second_half:
            self_overlap = len(first_half & second_half) / len(first_half)
            # 自重复判定更严格：前半段几乎原样在后半段重现才算（阈值上浮，避免正常排比/呼应误判）
            if self_overlap >= 0.5:
                return True, self_overlap, "self"
            if self_overlap > best:
                best = self_overlap

    # 2) 与历史轮重复：整段（8-gram 重叠率）+ 局部（最长公共子串）
    recent = (history_texts or [])[-compare_rounds:]
    for h in recent:
        if not h:
            continue
        hgrams = _ngrams(h, ngram)
        if hgrams:
            overlap = len(cur & hgrams) / len(cur)
            if overlap >= threshold:
                return True, overlap, "history"
            if overlap > best:
                best = overlap
        # 局部重复：存在 ≥min_span 字的逐字重复段即判复读
        if _has_common_span(text, h, min_span):
            return True, max(best, 0.0), "history"

    return False, best, kind


def _history_assistant_texts(sid):
    """读取会话最近的 assistant 正文列表（供复读检测比对）。失败返回空列表。"""
    try:
        chat = memory.load_chat(sid)
    except Exception:
        return []
    return [m.get("content", "") for m in chat if m.get("role") == "assistant"]
