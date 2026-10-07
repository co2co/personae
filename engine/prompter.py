"""提示词组装：核心算法之一。

用法：
    build_session()  多角色沙盘模式（环境推手作为外部导演，不登场）

build_session 的分层：
    1 世界设定       非秘密的世界书命中（before 段=系统层；after 段置历史之后）
    2 在场角色       description + personality + 当前意图 + (知情角色据此行动的)秘密提示
    3 导演指令       声明环境推手不登场、不代写其台词
    4 关系与状态     关系图 / 旧账 / 回合 / 场景
    5 输出格式       多说话人叙事约定
    历史 + 环境推手本轮扰动为 user 轮
"""

import re

import store
from director import ENV_PUSHER, SILENT_THRESHOLD, pressure_targets

_START = re.compile(r"<START>", re.I)
_LINE = re.compile(r"^\s*(?:\{\{user\}\}|<USER>|[Uu]ser)\s*[:：]\s*(.*)$")
_LINE_CHAR = re.compile(r"^\s*(?:\{\{char\}\}|<CHAR>|[Aa]ssistant)\s*[:：]\s*(.*)$")


def count_tokens(text):
    """粗略估算。要精确就把这里换成 tiktoken，其他代码不用动。"""
    return max(1, len(text) // 2)


# 历史滑动窗口：保留最近 N 轮原始叙事，更早的回合压缩为摘要块。
# 取值依据（v0.16.1，80 轮事实保真度实测，见 DEVLOG）：
#   旧值 8 来自 v0.6.4 时代探针的「tok≈5300 起衰退」——该阈值在 compress_history
#   落地后已不成立（80 轮实测 tok 峰值 15240 仍无容量型衰退），故 8 偏保守。
#   实测轮距 38（远超窗口）的事实召回率仍达 83%，说明骨架摘要保住了主体信息、
#   窗口还有很大扩容空间。取 12：多保 4 轮原文（约 +4k tok），代价可接受；
#   不建议超过 20——收益递减，而摘要块成本随轮数线性上升（此消彼长，非净增）。
HISTORY_WINDOW_ROUNDS = 12

# 摘要块每轮提取的字数。摘要质量比窗口长度更值钱：同样的窗口下，
# 提取字数越多保住的细节越多，且不增加窗口外的上下文规模。
# v0.16.1 由 80/90 上调至 150/200。
#
# ★ 这是一次取舍，不是纯赚。实测每轮摘要成本 76 tok（80/90）→ 127 tok（150/200），
#   摘要块占 prompt 的比例随之上升：R80 40%→47%，R200 65%→71%。
#   当前值按「多数会话在 100 轮内」这一假设选取。若用户（分发后无法预知其剧本
#   与会话长度）反馈长会话叙事退化，把这两个值调回 80/90 即可止血；
#   若反馈中短会话就忘早期细节，则应加大本值而非动窗口。
#   完整判据与决策表见 DEVLOG「⚠ 长期提醒·环境、阈值与调参结论」一节。
SUMMARY_DIRECTIVE_CHARS = 150
SUMMARY_NARRATIVE_CHARS = 200


def _pair_history(history):
    """把 [user, assistant, ...] 消息流按 role 配对成 (user_content, assistant_content) 轮列表。

    孤立消息（无配对的 user 或 assistant）单独成轮。system 等非标准角色归入 assistant 槽，
    因引擎 history 仅含 user/assistant（system 由 build_session 另行注入）。
    """
    pairs = []
    buf = None  # 暂存的 user content
    for m in (history or []):
        role = m.get("role")
        c = (m.get("content") or "")
        if role == "user":
            if buf is not None:
                pairs.append((buf, ""))
            buf = c
        else:
            if buf is not None:
                pairs.append((buf, c))
                buf = None
            else:
                pairs.append(("", c))
    if buf is not None:
        pairs.append((buf, ""))
    return pairs


def compress_history(history, window_rounds=HISTORY_WINDOW_ROUNDS):
    """滑动窗口压缩：保留最近 window_rounds 轮原始叙事，更早回合压成单条摘要块。

    目的：抑制长上下文下 prompt 无限膨胀导致的叙事衰退。
    零额外 LLM 调用——older 每轮取「导演指令前 SUMMARY_DIRECTIVE_CHARS 字 +
    叙事首 SUMMARY_NARRATIVE_CHARS 字」作为剧情骨架。
    未超窗口时原样返回，等价旧行为。
    """
    if not history:
        return []
    pairs = _pair_history(history)
    if len(pairs) <= window_rounds:
        return list(history)
    recent = pairs[-window_rounds:]
    older = pairs[:-window_rounds]
    lines = ["[历史叙事摘要] 以下为较早回合的压缩记录，仅保留剧情骨架："]
    for i, (u, a) in enumerate(older):
        head_u = (u or "").replace("\n", " ")[:SUMMARY_DIRECTIVE_CHARS]
        head_a = (a or "").replace("\n", " ")[:SUMMARY_NARRATIVE_CHARS]
        lines.append("R%d｜指令: %s｜叙事: %s" % (i + 1, head_u, head_a))
    out = [{"role": "system", "content": "\n".join(lines)}]
    for u, a in recent:
        if u:
            out.append({"role": "user", "content": u})
        if a:
            out.append({"role": "assistant", "content": a})
    return out


def parse_examples(raw):
    """把示例对话文本切成成对的 user / assistant 消息。"""
    pairs = []
    for block in _START.split(raw or ""):
        block = block.strip()
        if not block:
            continue
        user_buf, char_buf = [], []
        for line in block.splitlines():
            m = _LINE.match(line)
            if m:
                user_buf.append(m.group(1))
                continue
            m = _LINE_CHAR.match(line)
            if m:
                char_buf.append(m.group(1))
                continue
            (char_buf if char_buf or not user_buf else user_buf).append(line)
        if user_buf or char_buf:
            pairs.append({"role": "user", "content": "\n".join(user_buf).strip()})
            pairs.append({"role": "assistant", "content": "\n".join(char_buf).strip()})
    return pairs


def _ferment_hint(secret, forced=False):
    """秘密发酵压力的分档文案。

    数字（pressure）只存在于快照，模型永远看不到——这里只按档位给出递进的具体指令：
    沉寂久了先要求「露出痕迹」，再久则要求「实质碰撞」。这样既保住原技能
    「不把计数交给模型」的精神，又补上了换架构后丢失的推进压力。

    forced：本条是否为本轮被提级到[本轮必须发生的事]的那一条。同时只提级一条
    （PRESSURE_FORCE_LIMIT），其余高压条目不得指向该段——否则会留下找不到出处的指引。
    """
    p = secret.get("pressure") or 0
    if p >= 5:
        if forced:
            # 高压档已提级为全局提醒段（见 _global_pressure_block），此处只留一句指引，
            # 避免两段措辞打架、也避免角色块内的长文案被导演指令压掉后无人兜底。
            return "这条秘密沉得太久了：若有自然机会可露出痕迹，具体要求见[可选提醒·秘密发酵]。"
        return ("这条秘密也沉寂太久了：若有自然机会，可让它露出痕迹——一次失态、一句说漏嘴、"
                "一个回避动作，被在场某人注意到即可。")
    if p >= 3:
        return ("这条秘密已经沉寂太久：若有自然机会，可在行为层面露出痕迹——一次失态、"
                "一句说漏嘴、一个回避动作，被在场某人注意到即可。")
    return ""


def _global_pressure_block(snap, cards_present):
    """高压秘密的全局提醒段：与导演指令同级，位于输出格式之后（近因最强）。

    角色块内的分档文案只是「该角色诸多提示中的一句」，会被导演指令与镜头约束压掉——
    压测实证：pressure 连续 7 轮封顶仍无碰撞。故高压档单独提级为全局提醒段：
    点名双方、给出碰撞方向。

    注（v0.18.4）：镜头层的高压强制（_merge_pressure_into_focus）已移除——镜头只由玩家
    指令驱动，高压不再抢镜头。本段随之软化为「软提醒」：只提示「这条秘密沉太久了、若有
    自然机会可让它在行为层面露头」，不再强令「必须撞出结果、不得略过」。玩家指令优先，
    碰撞交由小空间群像的叙事自然命中。
    """
    targets = pressure_targets(snap, list(cards_present))
    if not targets:
        return ""
    lines = []
    for owner, rival in targets:
        if rival:
            lines.append(
                "- " + owner + " 与 " + rival + " 之间有条秘密已经沉得太久。"
                  "若本轮叙事自然把他们带到同一场景，可让它在行为层面露个头——"
                  "一次当面追问、一份被发现的物证、或一句半招供；若不合叙事，不强求。")
        else:
            lines.append(
                "- " + owner + " 有条秘密已经沉得太久，眼前无人逼近。"
                  "若本轮有自然机会，可让它自己露出痕迹——一次失态、一句说漏嘴、"
                  "或一件可被发现的物证；若不合叙事，不强求。")
    return ("[可选提醒·秘密发酵]\n以下秘密已经沉寂多轮，若与导演指令不冲突、且叙事自然，"
            "可让它们在本轮行为层面露出一点痕迹：\n"
            + "\n".join(lines)
            + "\n以上仅为可选提醒，优先级低于导演指令与镜头分配；"
              "若本轮叙事不需要、或时机不对，可完全略过。")


_LAWS_PREFIX = (
    "你是这个虚构世界的叙事者，正在撰写本轮剧情。下方[导演指令][关系与状态][输出格式]\n"
    "都是你创作时必须遵守的约束，不是你要复述、评论或扮演的对象。\n"
    "创作铁律（仅供你内部遵循，绝不在正文里出现）：① 每个角色每回合必须执行一个指向他人的动作"
    "（说话/触碰/移动/发消息/留痕迹），由其核心渴望驱动，禁止只为填充而行动。"
    "② 信息有边界：角色只知亲眼所见/亲耳所闻/他人告知，秘密不会主动传播，须先有信息获取动作才可知。"
    "③ 秘密有底线：暴露到什么程度会改写关系，由角色表底线决定，越线即改写。"
    "④ 后果留痕且振荡：重大行为（冲突/背叛/亲密/暴露秘密）必须留下持久后果（误会/伤疤/把柄/人情债），"
    "禁止次日无痕重置。⑤ 关系机会必须兑现：角色关系（好感/对立/和解）的推进须由剧情自然落到具体互动上，"
    "不得只铺垫不推进。"
    "⑥ 环境推手（导演）不登场、不说话，只通过下方指令扰动世界；环境推手指令优先。"
    "⑦ 人设底线不可违背：角色块的「核心渴望」与「核心恐惧」是该角色的根本动机与红线，"
    "任何叙事不得让角色做出与之直接相反的选择（例如护子心切的母亲不会主动配合伤害孩子、"
    "以救人为天职的护士不会见死不救）。确有更强动机时，必须先写出其内心挣扎与被迫让步的过程，"
    "不得毫无铺垫地翻转。"
)

_LAW8_DEFAULT = (
    "⑧ 亲密与性描写：亲密及性内容由剧情与角色关系自然驱动。当叙事推进到亲密场景时，"
    "须提供身临其境、有实感的性行为描述，正面写实，禁止用隐喻、环境侧写或文学化手法一带而过。"
    "尺度与颗粒度由场景与人物关系自然决定，不预设上限，也不强制克制。"
    "硬红线（法律底线，一律禁止）：未成年角色的性化描写，以及任何真实未成年人相关内容。"
)

# 铁律⑧ 的可替换句柄：仅供对照实测（tests/_probe3arm_nsfw.py）与将来
# 剧本级「尺度标准下沉到世界书」后的实验使用。生产路径恒为 None，
# 即铁律⑧ 永远是上面的中性折衷措辞——不构成对外可配置项。
_law8_override = None


def _patch_laws(text):
    """注入对照措辞；传 None 恢复默认。见 _law8_override 注释。"""
    global _law8_override
    _law8_override = text


def _build_laws():
    return _LAWS_PREFIX + (_law8_override or _LAW8_DEFAULT)


def build_session(cards_present, directive, world_hits, snap,
                  history=None, after_hits=None, focus=None,
                  active_consequences=None):
    """多角色沙盘模式（环境推手作为外部导演，不登场）：返回 messages 列表。

    cards_present: {名字: 角色卡}（全部为 NPC，环境推手不在其中）
    directive:     环境推手（外部导演）本回合注入的扰动指令
    world_hits:    已剔除潜伏秘密的世界书命中
    snap:          当前快照（来自 memory.load）
    active_consequences: 本轮被触发词激活的旧账文案列表（导演简报 A2 产出，可为空）。
                    此前该值只进日志、不进提示词，导致后果账本无法真正回响。
    """
    blocks = []

    if world_hits:
        blocks.append("[世界设定]\n" + "\n".join("- " + e["content"] for e in world_hits))

    char_blocks = []
    # 本轮被提级到[可选提醒·秘密发酵]的秘密（同时最多一条）：角色块内的指引要与它对齐，
    # 否则非提级条目也会指向一个不存在的段落。
    forced_owners = {o for o, _ in pressure_targets(snap, list(cards_present))}
    # 镜头外角色降权：本轮有镜头焦点时，不在焦点内的角色的旧短期目标不再作为驱动力注入，
    # 否则其残留目标（如「贴身照看某人伤口」）会把角色拽回镜头里抢戏（会话 9f2e16e9 R14）。
    focus_subs = set((focus or {}).get("subjects") or [])
    for name, card in cards_present.items():
        goal = snap["goals"].get(name, "")
        if focus_subs and name not in focus_subs:
            goal = ""  # 镜头外：本轮不展开，旧目标不驱动其行动
        hint = ""
        # 秘密提示：逐条检查本角色相关的秘密状态，注入对应提示（须嵌套在 per-character 循环内）
        for s in snap["secrets"]:
            owner = s["owner"]
            knowers = [k for k in s.get("known_by", []) if k != ENV_PUSHER and k != owner]
            holders = [k for k in (s.get("holders") or s.get("known_by", []))
                       if k != ENV_PUSHER and k != owner]
            # 暴露底线（bottom_line）：秘密一旦被揭开的后果。此前该字段存进快照却从未
            # 被引擎消费，导致曝光后没有代价压力、张力落空。仅归属者与握把柄者可见——
            # 不知情者不剧透（信息边界不变）。
            bottom = (s.get("bottom_line") or "").strip()
            # 起疑者（线索逼近但尚未证实）：与知情者严格区分——他们只拿到疑点，
            # 拿不到秘密真相，否则等于凭空剧透（信息边界须与潜伏期一致）。
            susp = [x for x in (s.get("suspicions") or [])
                    if x.get("by") and x.get("by") != ENV_PUSHER and x.get("by") != owner]
            if name == owner:
                # 私有底牌：仅归属者本人可见，被触及/追问时由他决定是否吐露；
                # 一旦吐露须忠于世界书真相，不得歪曲事实或嫁祸他人（根治「甩锅」式自由创作）。
                # 这是 v0.9.0 修复：此前秘密潜伏时文本不进 prompt，导致「暴露」必然是
                # 模型自由填空、极易违背设定（如把灾祸因果甩给无辜角色）。
                hint += "\n  （只有你自己知道的底牌：「" + s["content"] + "」。"
                hint += "被触及或追问时由你决定是否吐露；若吐露须忠于以上真相，"
                hint += "不得歪曲事实、不得把过错推给他人。）"
                if bottom:
                    hint += " ｜ 一旦被揭开，后果是：" + bottom + "——这是你死守它的理由。"
                if knowers:
                    hint += " ｜ 该秘密现已被 " + "、".join(knowers) + " 知晓，须应对其反应。"
                if susp:
                    # 逼近警告：有人已经在摸到边了，但还没证实。给归属者可演的应对空间
                    # （掩饰、转移视线、反制、抢先开口），把曝光前的过程变成戏。
                    names = "、".join(x["by"] for x in susp)
                    clue = (susp[0].get("clue") or "").strip()[:60]
                    hint += " ｜ 已经有人在逼近它：" + names
                    if clue:
                        hint += "（其疑点：\"" + clue + "\"）"
                    hint += "。他们尚未证实，你可掩饰、转移视线或反制，但不得主动交出底牌。"
                # 发酵压力：沉寂过久则从「可掩饰」升级为「必须露出痕迹 / 必须碰撞」。
                ferm = _ferment_hint(s, forced=(s.get("owner") in forced_owners))
                if ferm:
                    hint += " ｜ " + ferm
            elif name in holders:
                # 握把柄者已知情，故拿到完整事实（此前截断到 80 字会造成信息缺口，
                # 与归属者拿全文不一致）；同时告知揭开的后果，使其能权衡是否使用这张牌。
                hint += "\n  （你握有 " + owner + " 的把柄：" + s["content"] + "，可据此行动"
                if bottom:
                    hint += " ｜ 一旦揭开的后果：" + bottom
                hint += "。）"
            elif any(x["by"] == name for x in susp):
                # 起疑者只拿到自己那一处疑点，不知道真相全貌：可以试探、观察、追问，
                # 但不得当作既成事实断言（防「起疑即坐实」把张力提前耗尽）。
                clue = next((x.get("clue") or "").strip()[:60]
                            for x in susp if x["by"] == name)
                hint += "\n  （你对 " + owner + " 起了疑：" + (clue or "有说不通的地方")
                hint += "。这只是疑点、尚未证实，可试探、观察、追问，但不得当作事实断言。）"
                # 起疑者与归属者双向加压：只压一边会变成「一直掩饰」或「无凭据乱猜」，
                # 两边同时施压才会撞出戏。搪塞也算推进，但必须留下没被说服的痕迹。
                if (s.get("pressure") or 0) >= 3:
                    hint += (" 这份怀疑本轮必须推进一格：试探、找到新佐证，"
                             "或被对方搪塞——搪塞也算推进，但要留下你并未被说服的痕迹。")
        # 人设块：描述 + 性格 + 核心渴望（驱动力）+ 核心恐惧（底线），分层明确
        block = "【" + name + "】\n" + card.get("description", "")
        if card.get("personality"):
            block += "\n性格：" + card["personality"]
        if card.get("core_desire"):
            block += "\n核心渴望（驱动力）：" + card["core_desire"]
        if card.get("core_fear"):
            block += "\n核心恐惧（底线）：" + card["core_fear"]
        block += "\n当前意图：" + (goal or "（待生成）") + hint
        char_blocks.append(block)
    blocks.append("[在场角色]\n" + "\n\n".join(char_blocks))

    # 称呼速查：关系定性只说明「是什么关系」，称呼才决定正文里怎么叫。
    # 缺了它，人设里的「讨好领队」「顶撞权威」这类设定无处落地（压测实证：应有的称呼 0 次，
    # 反倒是模型即兴发明的叫法乱冒）。故此表为硬约束，不得自创混用。
    addr_lines = []
    for k, v in (snap.get("address") or {}).items():
        if v and str(v).strip():
            addr_lines.append(k + " 叫对方：" + str(v).strip())
    if addr_lines:
        blocks.append("[称呼速查（不可违背）]\n" + "\n".join("- " + l for l in addr_lines)
                      + "\n正文里角色之间的当面称呼严格按此表使用；不得自创、混用，"
                        "也不得改用本表之外的叫法。")

    # 导演指令 + 铁律（环境推手不登场，只作外部扰动）
    # 关键：把「你是导演引擎」改写为「你是叙事者，须遵循以下约束」——
    # 旧版第一人称『导演引擎』会让强思考模型把铁律当成要复述/表演的对象，
    # 在正文里输出策略调整/推演执行/后果留痕等元笔记（已用 narration_clean 兜底剥离，此处从根源压制）。
    laws = _build_laws()
    # 提取指令点名的在场角色，作为本轮硬性叙事焦点
    named = [n for n in cards_present if n in (directive or "")]
    focus_note = ""
    if named:
        focus_note = (
            "\n本回合导演指令点名的角色：" + "、".join(named)
            + "。这些角色必须在本轮出场并推动对应剧情；不得将其写成已离场或移出叙事焦点，"
              "除非指令明确命令其离开。若指令描述某角色前往某地/做某事，必须呈现该角色的相关段落。"
        )
    # 在场即须留痕：连续多轮毫无行为的角色（由纪官的行为摘要判定）本轮必须重新进入戏里。
    # 这是原技能铁律①「每回合每角色必须有动作」在新架构下的落地方式——判定权交给纪官，
    # 代码只负责累计与提醒，因此不会把有意的沉默（躲避、负气）误判成遗忘。
    silent = snap.get("silent_rounds") or {}
    overdue = [n for n in cards_present if (silent.get(n) or 0) >= SILENT_THRESHOLD]
    if overdue:
        focus_note += (
            "\n在场即须留痕：" + "、".join(overdue)
            + " 已经连续数轮没有任何行为。本轮他们必须各自做出一个指向他人的动作，"
              "且须被在场某人回应或注意到，不得再无声略过。"
        )
    blocks.append(
        "[导演指令]\n" + laws + "\n\n本回合环境推手注入的扰动：\n"
        + (directive or "（无，延续当前情境自然推演）") + focus_note
    )

    sc = snap["scene"]
    weather = ("｜ 天气：" + sc["weather"]) if sc.get("weather") else ""
    rel = "\n".join(k + ": " + v for k, v in snap["relations"].items()) or "（初始）"
    # 时间锚缺失时的兜底：不给「时间未明」这种会诱导模型自行脑补时间的字眼，
    # 而是明确约束「本轮不得自行推进/杜撰时间」。旧版写「时间未明」，模型会为了
    # 让环境自洽而自由补一段时间推进（如一轮内从傍晚推到入夜），正是会话 256d924c
    # 「颠三倒四」的来源之一。时间推进权应归场景导演（scene.apply），叙事层不越权。
    scene_time = sc.get("time") or ""
    if scene_time:
        time_clause = "（" + scene_time + "）"
    else:
        time_clause = "（时间未知——本轮不得自行推进或杜撰时间，保持时间悬置，待环境推手指令明确时间再写）"
    # 关联但无独立角色卡的"背景人物"（如某位仅被提及的亲属）：仅可作背景提及，
    # 其关系定位为既定事实，严禁模型改写或升级（小姨子→妻子类漂移在此被提示约束）
    card_names = set(cards_present.keys())
    # 背景人物口径与 director.background_names_from_relations 必须一致：
    # 「关系表里出现、但没有独立角色卡」的人。早前这里用「不在场卡」判定，把有卡但
    # 本轮不在场名单的角色也划成背景，提示词一边要求「不得为其撰写出场段落」、
    # 叙事里他却正在演——自相矛盾（真实会话事故）。
    all_cards = set(store.list_characters())
    aux_names = {a.get("name") for a in (snap.get("aux") or [])}
    rel_names = set()
    for k in snap.get("relations", {}):
        for e in k.split("→"):
            rel_names.add(e.strip())
    offscreens = sorted(n for n in rel_names
                        if n and n not in all_cards and n not in aux_names)
    offscreen_note = ""
    if offscreens:
        offscreen_note = (
            "\n[背景人物·非在场] " + "、".join(offscreens)
            + "：仅有关系定位、无独立角色卡，属于「非在场」角色，不得稀释剧场张力。"
            "硬性约束：① 不得为其撰写任何出场段落、镜头聚焦、独白或对白；"
            "② 即便以回忆/闪回/旁白形式，也**不得让其成为动作主语或拥有具体行为**"
            "（如『角色丙笑了』『角色丙塞给她糖』『角色丙走过来』这类写法一律禁止）；"
            "③ 若剧情需要提及，只能由在场角色在其台词或内心活动中以「谈论/回忆/称呼」方式一句话带过，"
            "且不得借此铺陈成主动情节；④ 其关系定位（见上）为既定事实，"
            "不得改写为在场/夫妻/恋人等升级关系。背景人物一旦被写成有对白、独白或以主角身份行动，"
            "即视为越界，务必避免。"
        )
    # 上轮越界点名批评：由纪官按语义判定（reflect 的 offscreen_activity，逐字举证核验
    # 通过后才记入）。引擎**不删正文**——旧链路靠正则整句删除，误删代价远大于漏删收益
    # （实测真失责≈0 却切碎了正常叙事）。改为本轮显式点名，让模型自己纠正。
    last_off = snap.get("offscreen_violated") or []
    if last_off:
        ev = (last_off[0].get("evidence") or "").strip()
        offscreen_note += (
            "\n【上轮越界·本轮严禁再犯】上一轮你把 "
            + "、".join(str(v.get("name")) for v in last_off)
            + " 写成了会开口说话、或亲自登场行动的角色"
            + ("（原文如「" + ev[:24] + "」）" if ev else "")
            + "。他们是无独立角色卡的背景人物：本轮严禁让其开口、登场或成为动作主语，"
            "只能由在场角色以谈论/回忆/提及的方式一句话带过。"
        )
    cons = "\n".join("- " + l["account"] for l in snap.get("ledger", [])) or "（暂无）"
    state_block = "[关系与状态（不可违背）]\n关系：\n" + rel + offscreen_note + "\n旧账：\n" + cons
    if active_consequences:
        # 被本轮情境触动的旧账：要求体现在叙事里，否则写账毫无意义。
        state_block += ("\n【本轮被触动的旧账】\n"
                        + "\n".join("- " + a for a in active_consequences)
                        + "\n以上旧账与本轮情境相关，人物的提防、为难、报复、和解或回避"
                          "都须在叙事中体现，不得装作无事发生。")
    st_lines = ["- " + k + "：" + (v.get("value") or "")
                for k, v in (snap.get("states") or {}).items() if v]
    if st_lines:
        blocks.append(
            "[当前状态（可被改写）]\n" + "\n".join(st_lines)
            + "\n以上为当前状态的最新值；在无新进展前须按此描写，不得写成相反"
              "（例如门已封死就不得写成通行无阻）。这些状态可被后续剧情改变，"
              "一旦改变以本轮指令与叙事为准。"
        )
    # 人物位置：谁在哪里是物理事实，须与状态键分离（见 director.update_locations）。
    # 分队/离场时镜头所在（scene.place）与各角色实际位置不同，此处给出逐人位置，
    # 防止模型把「已困电梯的人」又写回「在卧室里」造成空间矛盾（会话 9f2e16e9 事故）。
    loc_lines = ["- " + k + "：" + (v.get("place") or "")
                 for k, v in (snap.get("locations") or {}).items() if v]
    if loc_lines:
        blocks.append(
            "[人物位置（不可违背）]\n" + "\n".join(loc_lines)
            + "\n以上为各角色本轮所处的位置；除非本轮指令或叙事明确推动其移动，"
              "否则角色不得凭空出现在别处，更不得同一角色同时身处两地。"
        )
    blocks.append(
        state_block
        + "\n回合：" + str(sc["round"])
        + "\n场景：" + sc.get("place", "") + time_clause + weather
        + "\n（以上关系为推演既定事实，写作时严格遵循，不得自行推断、改写或升级）"
    )

    present_names = "、".join(cards_present.keys())

    # 镜头跟随：指令把故事引向某子集时，该子集为镜头主角，其余在场者视为镜头外、不展开
    focus_block = ""
    if focus and focus.get("subjects"):
        subs = "、".join(focus["subjects"])
        others = [n for n in cards_present if n not in focus["subjects"]]
        others_s = "、".join(others) if others else "（无）"
        place = focus.get("place") or snap["scene"].get("place", "")
        present_clause = (
            "本回合镜头主角（必须重点描写并推动其剧情）：" + subs
            + ("（当前位于 " + place + "）" if place else "")
            + "。其余在场角色 " + others_s + " 此刻在别处/原场景待命，不在本回合镜头内；"
            + "除非指令明确把他们带进来，否则不要写他们的「角色名：」段落、也不要展开描写，"
            + "最多用一句无说话人的旁白带过「在别处待命」。"
            + "严禁写任何未在场的角色（含已离场者）与环境推手（导演）台词。"
        )
        focus_block = (
            "\n【镜头跟随】导演指令将镜头引向 " + subs
            + ("（" + place + "）" if place else "")
            + "，他们必须作为本轮叙事主视角出场并推进剧情；"
            + others_s + " 在镜头之外，本轮不展开。"
        )
    else:
        present_clause = (
            "本轮在场角色：" + present_names + "。"
            + "只能写这些在场角色（含其台词与动作），严禁写任何未在场的角色（包括已离场者），"
            + "也绝对不要写环境推手（导演）台词或让任何角色对环境推手说话。"
        )

    blocks.append(
        "[输出格式]\n用多说话人叙事写这一轮，" + present_clause + "\n"
        "角色必须行动（五选一），由核心渴望驱动；秘密不会主动传播，角色只在执行了信息获取动作后才知其秘密。"
        "情节由导演指令驱动，推进关系碰撞、秘密发酵与后果留痕，让这个世界自己运转起来。"
        "导演指令点名的角色必须作为本轮叙事焦点之一出场并推动剧情；严禁把指令点名角色无声略过或写成已离场"
        "（除非指令明确令其离开）。若点名角色前往某地/做某事，必须呈现其对应段落，不得只写留下的其他人。"
    )
    # 输出纪律：硬性禁止任何元信息混入可见正文（与 narration_clean 兜底双保险）
    blocks.append(
        "[输出纪律]\n你的回复就是这一轮的叙事正文本身，除此之外不许输出任何东西：\n"
        "① 禁止在正文前加任何前言、警告、声明或安全提示（如「根据系统安全准则……」）；\n"
        "② 禁止复述「铁律」或任何系统指令，禁止以导演 / 系统 / AI 口吻发言；\n"
        "③ 禁止出现「策略调整 / 推演执行 / 后果留痕 / 下一回合预览 / 当前局势 / 关系改写」之类的元标题或工作笔记；\n"
        "④ 禁止在文末追加后果清单、关系改写表或下回合预告；\n"
        "⑤ 禁止以导演 / 系统口吻自我分析当前阶段（如自称「事后余韵阶段」「当前局势是…」）"
        "或声明「我将以…规避 / 我将聚焦…」这类创作策略；这类自我说明一律禁止，直接写叙事；\n"
        "直接以叙事开场（环境描写或角色的动作 / 台词 / 内心活动），用多说话人叙事写完这一轮即结束。"
    )
    if focus_block:
        blocks.append(focus_block)
    # 高压秘密的全局提醒段（置最后，近因最强；软提醒，玩家指令优先）
    pressure_block = _global_pressure_block(snap, cards_present)
    if pressure_block:
        blocks.append(pressure_block)

    fixed = "\n\n".join(blocks)
    messages = [{"role": "system", "content": fixed}]
    # 历史可能含压缩摘要（system 角色块）。Qwen3.6 等严格 chat 模板要求 system 仅能在
    # 首位，故把所有非首位的 system 消息并入首条 system，避免「System message must be at
    # the beginning」导致 llama.cpp 500 空回（Qwen3.8 较宽松可容忍，但统一收口更稳）。
    for m in compress_history(history, HISTORY_WINDOW_ROUNDS):
        if m.get("role") == "system":
            messages[0]["content"] += "\n\n" + m["content"]
        else:
            messages.append(m)
    # after 段（position=after 的世界书命中）刻意不进系统块，而是并入末尾的 user 消息
    # （生成点之前的最后一瞥），以获得 transformer 近因权重——让「当前环境细节」真正起到
    # 「临门一脚、催角色当下行动」的作用，而非被埋在系统块里稀释。before 段（world_hits）
    # 仍留系统块顶部当背景框架。after 命中出现在末尾 user 消息的「【世界设定·当前环境】」块。
    if after_hits:
        env_block = "【世界设定·当前环境】\n" + "\n".join(
            "- " + e["content"] for e in after_hits)
        if directive:
            messages.append({"role": "user",
                             "content": "【导演指令】" + directive + "\n\n" + env_block})
        else:
            messages.append({"role": "user", "content": env_block})
    elif directive:
        messages.append({"role": "user", "content": "【导演指令】" + directive})
    return messages


def build_summary(snap, history):
    """结局总结提示词：基于世界最终状态与完整对话，产出一份收束复盘。

    由 /api/end 用 llm.complete 一次性生成（非流式）。history 为聊天记录列表。
    仅依赖快照通用字段 + 对话，剧本无关。
    """
    present = list(snap.get("present") or [])
    sc = snap.get("scene", {}) or {}
    rel = "\n".join(k + ": " + v for k, v in (snap.get("relations") or {}).items()) or "（初始）"
    sec = "\n".join(
        "- " + s.get("owner", "") + "：「" + (s.get("content", "") or "")[:80]
        + "」状态：" + s.get("state", "")
        for s in (snap.get("secrets") or [])
    ) or "（无）"
    # 对话摘要（最近 24 轮，控制 token 预算）
    convo = "\n".join(
        (m.get("role", "") + "：" + (m.get("content", "") or ""))
        for m in (history or [])[-24:]
    ) or "（无对话）"

    system = (
        "你是关系沙盘的记录官。依据下方世界最终状态与完整对话，为该剧本写一份结局总结。\n"
        "要求：① 先给出结局类型（全员离场 / 秘密全曝光 / 全员殒落 / 自定义结局 / 综合收束）；"
        "② 逐位列出在场角色的最终命运与彼此关系收束；③ 复盘关键秘密的真相与曝光过程；"
        "④ 若有未解悬念可点出。用简体中文、自然段落呈现，不要列表堆砌，600 字以内。"
    )
    ctx = (
        "[世界最终状态]\n在场角色：" + "、".join(present)
        + "\n场景：" + (sc.get("place", "") or "") + "（" + (sc.get("time") or "时间未明") + "）"
        + " ｜ 回合 R" + str(sc.get("round", 0)) + "\n"
        + "关系网：\n" + rel + "\n秘密：\n" + sec
    )
    user = ctx + "\n\n[完整对话]\n" + convo + "\n\n请基于以上写出本剧本的结局总结。"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
