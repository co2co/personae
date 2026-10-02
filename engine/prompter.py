"""提示词组装：SillyTavern 三个核心算法之一。

用法：
    build_session()  多角色沙盘模式（环境推手作为外部导演，不登场）

build_session 的分层：
    1 世界设定       非秘密的世界书命中（before 段=系统层；after 段置历史之后）
    2 在场角色       description + personality + 当前意图 + (知情角色据此行动的)秘密提示
    3 导演指令       声明环境推手不登场、不代写其台词
    4 关系与状态     关系图 / 旧账 / 回合 / 场景
    5 内容尺度       NSFW 提示 + 本轮机会等级
    6 输出格式       多说话人叙事约定
    历史 + 环境推手本轮扰动为 user 轮
"""

import re

from director import ENV_PUSHER, OPP_NOTE

_START = re.compile(r"<START>", re.I)
_LINE = re.compile(r"^\s*(?:\{\{user\}\}|<USER>|[Uu]ser)\s*[:：]\s*(.*)$")
_LINE_CHAR = re.compile(r"^\s*(?:\{\{char\}\}|<CHAR>|[Aa]ssistant)\s*[:：]\s*(.*)$")


def count_tokens(text):
    """粗略估算。要精确就把这里换成 tiktoken，其他代码不用动。"""
    return max(1, len(text) // 2)


# 历史滑动窗口：保留最近 N 轮原始叙事，更早的回合压缩为摘要块。
# 依据：probe_history_degradation 梯度探测显示，prompt tok（≈字符数/2）在
# ~5300（R=16 轮，约 10600 字符）起出现叙事衰退，tok<3000（R≤8）为安全区。
# 取窗口 8 轮使最近原始叙事稳定在安全区，窗口外压缩抑制无限膨胀。
HISTORY_WINDOW_ROUNDS = 8


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

    目的：抑制长上下文下 prompt 无限膨胀导致的叙事衰退（探针定位拐点 tok≈5300）。
    零额外 LLM 调用——older 每轮取「导演指令前 80 字 + 叙事首 90 字」作为剧情骨架。
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
        head_u = (u or "").replace("\n", " ")[:80]
        head_a = (a or "").replace("\n", " ")[:90]
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


def build_session(cards_present, directive, world_hits, snap,
                  nsfw_prompt, opp_level, history=None, after_hits=None, focus=None):
    """多角色沙盘模式（环境推手作为外部导演，不登场）：返回 messages 列表。

    cards_present: {名字: 角色卡}（全部为 NPC，环境推手不在其中）
    directive:     环境推手（外部导演）本回合注入的扰动指令
    world_hits:    已剔除潜伏秘密的世界书命中
    snap:          当前快照（来自 memory.load）
    """
    blocks = []

    if world_hits:
        blocks.append("[世界设定]\n" + "\n".join("- " + e["content"] for e in world_hits))

    char_blocks = []
    for name, card in cards_present.items():
        goal = snap["goals"].get(name, "")
        hint = ""
    for s in snap["secrets"]:
        owner = s["owner"]
        knowers = [k for k in s.get("known_by", []) if k != ENV_PUSHER and k != owner]
        holders = [k for k in (s.get("holders") or s.get("known_by", []))
                   if k != ENV_PUSHER and k != owner]
        if not knowers:
            continue
        names = "、".join(knowers)
        if name == owner:
            hint += "\n  （你的秘密「" + s["content"][:60] + "」已被 " + names + " 知晓，须应对其反应）"
        elif name in holders:
            hint += "\n  （你握有 " + owner + " 的把柄：" + s["content"][:80] + "，可据此行动）"
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

    # 导演指令 + 铁律（环境推手不登场，只作外部扰动）
    laws = (
        "你是关系推演沙盘的导演引擎，负责推演这个迷你世界如何运转。\n"
        "铁律：① 每个角色每回合必须执行一个指向他人的动作（说话/触碰/移动/发消息/留痕迹），"
        "由其核心渴望驱动，禁止只为填充而行动。② 信息有边界：角色只知亲眼所见/亲耳所闻/他人告知，"
        "秘密不会主动传播，须先有信息获取动作才可知。③ 秘密有底线：暴露到什么程度会改写关系，"
        "由角色表底线决定，越线即改写。④ 后果留痕且振荡：重大行为（冲突/背叛/亲密/暴露秘密）"
        "必须留下持久后果（误会/伤疤/把柄/人情债），禁止次日无痕重置。⑤ 机会必须兑现："
        "满机会回合尺度上限为越线，应由剧情自然推进；亲密场景之后应有恰当的余韵/过渡回合，不要连续每回合都推进到性行为。⑥ 环境推手（导演）不登场、不说话，"
        "只通过下方指令扰动世界；环境推手指令优先。"
    )
    # 提取指令点名的在场角色，作为本轮硬性叙事焦点
    named = [n for n in cards_present if n in (directive or "")]
    focus_note = ""
    if named:
        focus_note = (
            "\n本回合导演指令点名的角色：" + "、".join(named)
            + "。这些角色必须在本轮出场并推动对应剧情；不得将其写成已离场或移出叙事焦点，"
              "除非指令明确命令其离开。若指令描述某角色前往某地/做某事，必须呈现该角色的相关段落。"
        )
    blocks.append(
        "[导演指令]\n" + laws + "\n\n本回合环境推手注入的扰动：\n"
        + (directive or "（无，延续当前情境自然推演）") + focus_note
    )

    sc = snap["scene"]
    weather = ("｜ 天气：" + sc["weather"]) if sc.get("weather") else ""
    rel = "\n".join(k + ": " + v for k, v in snap["relations"].items()) or "（初始）"
    # 关联但无独立角色卡的"背景人物"（如林梦琪）：仅可作背景提及，
    # 其关系定位为既定事实，严禁模型改写或升级（小姨子→妻子类漂移在此被提示约束）
    card_names = set(cards_present.keys())
    rel_names = set()
    for k in snap.get("relations", {}):
        for e in k.split("→"):
            rel_names.add(e.strip())
    offscreens = sorted(n for n in rel_names if n and n not in card_names)
    offscreen_note = ""
    if offscreens:
        offscreen_note = (
            "\n[背景人物·非在场] " + "、".join(offscreens)
            + "：仅有关系定位、无独立角色卡，属于「非在场」角色，不得稀释剧场张力。"
            "硬性约束：① 不得为其撰写任何出场段落、镜头聚焦、独白或对白；"
            "② 即便以回忆/闪回/旁白形式，也**不得让其成为动作主语或拥有具体行为**"
            "（如『老高笑了』『老高塞给她糖』『老高走过来』这类写法一律禁止）；"
            "③ 若剧情需要提及，只能由在场角色在其台词或内心活动中以「谈论/回忆/称呼」方式一句话带过，"
            "且不得借此铺陈成主动情节；④ 其关系定位（见上）为既定事实，"
            "不得改写为在场/夫妻/恋人等升级关系。背景人物一旦被写成有对白、独白或以主角身份行动，"
            "即视为越界（引擎会强制清洗并报警），务必避免。"
        )
    cons = "\n".join("- " + l["account"] for l in snap.get("ledger", [])) or "（暂无）"
    blocks.append(
        "[关系与状态（不可违背）]\n关系：\n" + rel + offscreen_note + "\n旧账：\n" + cons
        + "\n回合：" + str(sc["round"])
        + "\n场景：" + sc.get("place", "") + "（" + (sc.get("time") or "时间未明") + "）" + weather
        + "\n（以上关系为推演既定事实，写作时严格遵循，不得自行推断、改写或升级）"
    )

    scale = "[内容尺度]\n" + nsfw_prompt
    if opp_level and opp_level != "无":
        scale += "\n本轮机会等级：" + opp_level + "。" + OPP_NOTE.get(opp_level, "")
        if snap.get("intimacy_phase") == "aftermath":
            scale += "\n【事后余韵阶段】本轮专注写角色的反应、对话、情绪与关系变化，不要再次推进到性行为。"
    blocks.append(scale)

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
    if focus_block:
        blocks.append(focus_block)

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
    if after_hits:
        messages[0]["content"] += "\n\n[世界设定·续]\n" + "\n".join(
            "- " + e["content"] for e in after_hits)
    if directive:
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
