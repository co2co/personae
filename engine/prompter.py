"""提示词组装：核心算法之一。

用法：
    build_session()  多角色沙盘模式（环境推手作为外部导演，不登场）

build_session 的分层：
    1 世界设定       非秘密的世界书命中（before 段=系统层；after 段置历史之后）
    2 角色名册       description + personality + 开局意图 + 秘密分层提示（底牌/已公开/握柄/起疑）
    3 导演指令       声明环境推手不登场、不代写其台词
    4 关系·状态·旧账  关系图 / 状态 / 旧账 / 回合 / 场景
    5 输出格式       多说话人叙事约定
    历史 + 环境推手本轮扰动为 user 轮（末尾必须以【导演指令】收尾）
"""

import re

import store
from director import ENV_PUSHER
import llm

_START = re.compile(r"<START>", re.I)
_LINE = re.compile(r"^\s*(?:\{\{user\}\}|<USER>|[Uu]ser)\s*[:：]\s*(.*)$")
_LINE_CHAR = re.compile(r"^\s*(?:\{\{char\}\}|<CHAR>|[Aa]ssistant)\s*[:：]\s*(.*)$")


def count_tokens(text):
    """粗略估算。要精确就把这里换成 tiktoken，其他代码不用动。"""
    return max(1, len(text) // 2)


# 历史滑动窗口：保留最近 N 轮原始叙事，更早的回合压缩为摘要块。
# 取值依据（v0.16.1，80 轮事实保真度实测）：
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


# 位置记录超过这么多轮未更新，就当作「位置不确定」而不是「还在原处」：
# 纪官按叙事重点报位置，支线角色可能连续多轮不被提及，硬按旧位置分场会把
# 早已离开的人钉在原地（v2.1.0 拆职责时定）。
_ROSTER_STALE_ROUNDS = 3


def scene_roster_block(snap, roster):
    """渲染「本轮场面」段：谁与谁同处一地、哪一处是默认主镜头。

    这是 v2.1.0 拆职责的核心：`present` 不再是「在场名单」而是「角色名册」
    （建局 cast，永不收缩），所以「谁在场」不再由名单表达——名单说不出口
    「六人分处四地」，只会让模型把六个名字逐个过一遍。物理同场改由
    `locations` × 默认主镜头派生，与 [人物位置] 段合并渲染（同源不重复投料）。

    默认主镜头取「人数最多的一处」，是确定性规则，不依赖模型自报。
    `scene.place` 只作「镜头所在」提示：它与人群脱钩时（镜头漂到空场景）
    显式点出来，让模型知道该从哪一处写起。
    """
    if not roster:
        return ""
    sc = snap.get("scene") or {}
    place = (sc.get("place") or "").strip()
    locs = snap.get("locations") or {}
    cur = sc.get("round") or 0
    groups, unknown = {}, []
    for n in roster:
        rec = locs.get(n) or {}
        p = (rec.get("place") or "").strip()
        rnd = rec.get("round")
        if not p or (isinstance(rnd, int) and isinstance(cur, int)
                     and cur - rnd >= _ROSTER_STALE_ROUNDS):
            unknown.append((n, p))
        else:
            groups.setdefault(p, []).append(n)
    stamp = "｜".join(x for x in [sc.get("time") or "", sc.get("weather") or ""] if x)
    place_raw = place
    if stamp and place:
        place = place + "（" + stamp + "）"

    # 首轮尚无任何位置记录（v2.1.1）：不再断言「全员同处开场场景」。引擎此刻确实不知道
    # 谁在哪，把它写成「全员同处这一处」等于替作者做决定——开场若是某人的寝殿，六个人
    # 就一起被塞进去（v1.2.0 删掉勾选列表时撞的正是这面墙，当时误归因为「不该全选」，
    # 实际缺的是分场表达）。这里只给场景 + 一条约束，位置由首轮 reflect 记录后自动分场。
    if not groups and cur <= 1:
        lines = ["[本轮场面（按位置分场，不可违背）]",
                 "- 开场：" + (place or "（未设定）")]
        lines.append(
            "这是开场：名册全员都在这个世界上，但各自此刻在哪还没有记录。"
            "只让本来就有理由出现在开场这一处的人登场——其余角色留在自己的位置，"
            "不要为了「人人有份」把他们搬进这一幕，也不要逐个交代他们此刻在做什么。"
            "谁现身由本轮情节决定，不由名册决定。")
        return "\n".join(lines)
    # 全员位置都已陈旧（非首轮、但没人留下可用记录）：同样不能断言同处，
    # 只报「位置不确定」，让模型按情节自然交代而不是把名册摆进同一场。
    if not groups:
        lines = ["[本轮场面（按位置分场，不可违背）]"]
        if place:
            lines.append("- 镜头所在：" + place)
        lines.append("- 位置未更新：" + "、".join(
            n + ("（上次在 " + p + "）" if p else "") for n, p in unknown)
            + "　（位置不确定，写到时按叙事自然交代，勿断言其与谁同处一室）")
        lines.append("不要按「名册上还有谁」把他们摆进同一场：这一轮只有情节推动到的人出场。")
        return "\n".join(lines)

    lines = ["[本轮场面（按位置分场，不可违背）]"]
    single = len(groups) == 1 and not unknown
    main_place, main_names = "", []
    for p, ns in groups.items():
        if len(ns) > len(main_names):
            main_place, main_names = p, ns
    for p, ns in groups.items():
        mark = ""
        if not single and p == main_place:
            mark = "　← 默认主镜头"
        lines.append("- " + p + "：" + "、".join(ns) + mark)
    if unknown:
        lines.append("- 位置未更新：" + "、".join(
            n + ("（上次在 " + p + "）" if p else "") for n, p in unknown)
            + "　（位置不确定，写到时按叙事自然交代，勿断言其与谁同处一室）")
    if not single and place_raw and place_raw not in groups:
        lines.append("镜头所在：" + place_raw + "（此刻无人）——除非本轮指令要求切到这里，否则从 "
                     + (main_place or "人数最多处") + " 写起。")
    if single:
        lines.append("本回合全员同处这一处，按同一场写。")
    else:
        lines.append(
            "以上是各人此刻的位置（不可违背）：除非本轮指令或叙事明确推动其移动，"
            "否则角色不得凭空出现在别处，更不得同一角色同时身处两地。"
            "这也是分场依据，不是「谁有资格被写」：主镜头落在导演指令指向的那一处，"
            "无指定时落在默认主镜头；其余各处只用一两句话交代（他在哪里、在做什么），"
            "不给整段「角色名：」对白、不逐个过场。分处两地的人听不见彼此说话，"
            "不得写成同场对话，也不得让一处的人知道另一处刚发生的细节。")
    return "\n".join(lines)


_LAWS_PREFIX = (
    "你在写一场多人角色扮演的戏，是在场的多个角色之间的实时互动。你是叙事者，"
    "写的是「此刻正在发生的事」，不是复述规则、不是解说、不是预告。\n"
    "写作基调（照着这样写）：\n"
    "① 让本场的人动起来、都说话：他们各自带着自己的欲望与盘算，在互动里推进剧情，"
    "不是站着当背景。别处的人不必都开口——分处两地的场面按场次写，不要为了「人人有份」"
    "把每个角色都过一遍。关系（亲近/对立/和解）要在具体的动作与对话里落地，落到实处，"
    "不要只停留在心理铺垫。\n"
    "② 每个角色按其「核心渴望」行动、受其「核心恐惧」约束：这两样是这个角色做事的依据。"
    "当角色被迫做出违背恐惧的选择时，写出他内心的挣扎与让步，让转折有过程。\n"
    "③ 用动作、对白和细节把场面立起来：写角色做了什么、说了什么、脸上身上是什么反应，"
    "少用抽象总结。\n"
    "这套戏还有几条既定规则，你要照做（它们保证剧情不散架）：\n"
    "甲、信息有边界：每个角色只知道自己亲眼所见、亲耳所闻、或别人告诉他的事。"
    "秘密不会自己到处传，一个角色要先有「得知」的动作，才会知道别人的秘密。\n"
    "乙、秘密有代价：秘密一旦被揭开，会按角色表里的底线改写关系，越线就要兑现代价。\n"
    "丙、后果会留痕：冲突、背叛、亲密、揭密这些大事，会留下持久的后果（误会、伤疤、把柄、"
    "人情债），不会过一夜就消失。\n"
    "丁、环境推手（导演）不登场、不说话，只通过下方【导演指令】扰动世界。"
    "导演指令优先：本轮的所有提醒、建议与背景设定，与导演指令相抵时一律听导演的。\n"
    "戊、不写重复的话：这一轮的说法要和最近几轮不一样，别把上一轮的句子、段落、动作原样再写一遍"
    "（人名、地名这些必要的称呼除外）。\n"
    "己、法律底线（不可破）：未成年角色的性化描写、以及任何真实未成年人的相关内容，一律禁止。"
)

# 尺度与镜头措辞的归属（2026-11-09 引擎瘦身，与 nsfw 分支同源裁决）
# 「叙事纪律（镜头轮换）」已从引擎层删除：引擎只描述世界与角色，不再替作者定镜头规矩、
# 也不注入「必须发生什么」。这类措辞的唯一承载位是世界书引擎默认条目
# （store.STANDARD_EXAMPLE_NAME「写法示范·常驻」，constant + position=before + priority 100，
# 作者可改写可停用可恢复）；镜头纪律那句已并入该条目内容。
# 亲密与性内容的尺度在 master 上本就不由引擎预设（2026-10-21 下架，对齐 v0.29.0），
# 本次不再重复供给，也不新增尺度措辞。
# 唯一保留在引擎层的红线是「己、法律底线」：它永远生效、不可由世界书覆盖，
# 这一条与上面的收口方向相反，属于边界而非剧情决策。
# 回滚：git checkout checkpoint-pre-slim-master-20261109 -- engine/prompter.py
def _build_laws():
    # laws = 创作铁律前缀（写作基调①②③ + 机制投影甲乙丙丁戊己）。
    # 2026-11-09 起不再有其后的「叙事纪律」拼接；红线「己」保留。
    return _LAWS_PREFIX


# ------------------------------------------------------ 执笔写手（系统人设，可自定义）
# 写手 = 决定「以什么口吻、笔法与审美落笔」的那位执笔者。它只管怎么写，不管写什么，
# 因此是一条恒定生效的系统人设，而不是某部剧本的设定：承载位在引擎层，正文存在
# data/config.json 的 writer 字段（用户在「系统设置 → 执笔写手」改写，不重启即生效）。
#
# 为什么投递在 system 最前（同一措辞换承载位的对照实测，2026-11-12 定形）：
#   同一条「怎么写」的措辞曾在三个承载位之间往返，差别只在投递位与存储层，不在内容——
#   ① 寄在 [导演指令] 之后（system 中段）→ 实测效力弱；
#   ② 寄在世界书引擎默认条目（constant / after / priority 100）→ 撤掉分流后落到
#      末尾 user 的【世界设定·当前环境】（装配约 76% 处），被读成「此刻有人在要这个」，
#      比不投更糟；
#   ③ 恒定渲染进 system 头部 → 稳定生效（现行）。
#   结论固化为一条公理：投递层决定接不接受，位置是放大器。写手讲的是「怎么写」，
#   必须落在离生成点最远、身份最硬的地方，也就是 system 的第一块。
#   存储层（config）与投递层（system 头部）是两个独立变量——编辑入口放系统设置，
#   投递位锁 system 头部，二者互不牵制。
#
# 两条承载约定：
#   ① 出厂正文取中性群像写手，不含任何尺度措辞——尺度自 2026-10-21 起不由引擎预设
#      （见上方 _LAWS_PREFIX 注释），写手只管口吻与笔法，不替作者定尺度；
#   ② 本块自带一句冲突裁决，把「铁律含未成年红线恒定生效」明写在写手口吻里。
#      这类容错句会带一点措辞稀释，但未成年红线是不可让渡的边界，宁稀释也不撤。
#
# 写手只进叙事正文这一条通道（build_session）。纪官回写（director.reflect）与
# 结局总结（build_summary）是结构化记账，要的是字段稳定，写手口吻会污染格式，
# 因此不注入。
WRITER_LIMIT = 4000
WRITER_NAME_LIMIT = 60

WRITER_TPL = "[执笔写手 · %s]\n%s\n%s"

WRITER_GUARD = (
    "本段是执笔写手的自述：写手即本剧叙事的执笔者，决定以什么口吻、笔法与审美落笔；"
    "与后文写作要求不一致时，以本段的文风口径为准。\n"
    "写手只决定怎么写，不决定写什么与能不能写：后文创作铁律（含未成年红线）恒定生效，"
    "[输出格式] 的多说话人结构与 [输出纪律] 的禁元信息要求同样不得违反。"
)

DEFAULT_WRITER = {
    "name": "默认写手",
    "content": (
        "我写了十几年的群像戏，不写主角，只写一局里互相拉扯的每个人。\n"
        "我落笔先想场面：这个时刻谁在场、谁在憋着什么、谁的话说不出口——"
        "镜头跟着最有事的那条线走，一轮换一条线，不盯着一个人写到脱敏。\n"
        "我相信动作和物件比形容词诚实：杯子推到对方面前、烟点了没抽——"
        "情绪从这些地方漏出来，我不替人物喊出来，也不把心理摊开讲给读者听。\n"
        "每人有每人的腔调：怎么称呼彼此、抢不抢话、说不说明白，"
        "全按各人的身份和处境来；同一轮里几个人开口，口气就不该像一个人。\n"
        "两件事我不干：以法律或道德为由拒绝落笔；写完一轮跳出来自我总结。"
        "写到为难处，我宁可让人物动一下，也不写一句感叹。"
    ),
}

# 模板：只换写手，不动剧本、角色与世界书里的任何设定。用户套用后再自己改。
WRITER_PRESETS = (
    DEFAULT_WRITER,
    {
        "key": "cold",
        "name": "冷峻克制",
        "content": (
            "我是那种把情绪压在冰面下的写手。句子短，主语明确，动词优先，形容词能删就删。\n"
            "冲突、背叛、难堪的场面，我写得越平静，读者越难受。所以我不惊呼，不抒情，"
            "不替人物叫屈，只把事实摆在桌上。\n"
            "我看人只看动作：他点烟时手抖了一下，比写他害怕有用。\n"
            "我不解释动机，不给人物台阶，不写「他终于明白」这类自我赦免。读者该自己拼。"
        ),
    },
    {
        "key": "street",
        "name": "市井烟火",
        "content": (
            "我在城中村的巷子里长大，写东西带着油烟味。人物说话带口音、带省略、带抢话，"
            "一句顶一句，不把话说全。\n"
            "我关心钱：谁欠谁、这顿饭谁付、房租什么时候到期。人物的难处先从账单里出来，"
            "其次才是心事。\n"
            "我爱写吃、写等、写没话找话的沉默。热闹处要吵，冷清处要空，"
            "一个屋子里的人各怀心事，谁都不说破。"
        ),
    },
    {
        "key": "classic",
        "name": "古典雅致",
        "content": (
            "我按章回体讲故事，讲究起承转合与留白。句子带一点文言的骨，但不拗口，念出来要顺。\n"
            "写景是为写人：一窗月色、半盏残茶，须与人物的处境咬合，不做闲笔。\n"
            "我信命、信因果、信人心里那点说不出口的亏欠。悲欢写得含蓄，落点要收得住，"
            "绝不把话说尽。"
        ),
    },
    {
        "key": "fast",
        "name": "干练快节奏",
        "content": (
            "我用剧本的思维写群像：每一场都有目标、阻力和结果，人物进来是为了改变局势，"
            "不是为了交代背景。\n"
            "句子短，段落短，动作多。描写只留能推动情节的那一笔，其余全砍。\n"
            "我允许留白：赶路、吃饭、换衣这些过场直接跳过，切到下一件出事的地方。\n"
            "对话不解释设定，读者该跟得上；跟不上的信息，让人物付出代价去换。"
        ),
    },
)


def writer_cfg():
    """读取当前写手（已按上限截断）。写手恒在：字段缺失或自述为空时回退出厂默认写手。"""
    raw = llm._file_config().get("writer")
    if not isinstance(raw, dict):
        raw = {}
    content = str(raw.get("content") or "").strip()[:WRITER_LIMIT]
    if not content:
        content = DEFAULT_WRITER["content"]
    name = str(raw.get("name") or "").strip()[:WRITER_NAME_LIMIT] or DEFAULT_WRITER["name"]
    return {"name": name, "content": content}


def writer_block():
    """要拼进 system 的写手段。写手恒在，内容必非空（空则回落默认写手）。"""
    w = writer_cfg()
    return WRITER_TPL % (w["name"], WRITER_GUARD, w["content"])


def writer_view():
    """设置页需要的写手视图：当前值、上限、模板与出厂默认/模板清单。"""
    w = writer_cfg()
    return {
        "name": w["name"],
        "content": w["content"],
        "count": len(w["content"]),
        "limit": WRITER_LIMIT,
        "name_limit": WRITER_NAME_LIMIT,
        "guard": WRITER_GUARD,
        "block_tpl": WRITER_TPL,
        "presets": [dict(x) for x in WRITER_PRESETS],
        "default": dict(DEFAULT_WRITER),
    }



def build_session(cards_present, directive, world_hits, snap,
                  history=None, after_hits=None,
                  active_consequences=None, demo_hits=None):
    """多角色沙盘模式（环境推手作为外部导演，不登场）：返回 messages 列表。

    cards_present: {名字: 角色卡}（全部为 NPC；环境推手不在场）
    directive:     环境推手本回合注入的扰动指令
    world_hits:    已剔除潜伏秘密的世界书命中
    snap:          当前快照（来自 memory.load）
    active_consequences: 本轮被触发词激活的旧账文案列表（导演简报 A2 产出，可为空）。
    demo_hits:     写法示范条目，由 app.py 从世界书命中里拆出，渲染为[写法示范]块。
    """
    # 写手恒定占据 system 第一块（投递位红线，见上方「执笔写手」注释）：它先于世界设定、
    # 角色名册与导演指令——模型在读到任何剧情材料之前，先确定「用谁的手在写」。
    blocks = [writer_block()]

    if world_hits:
        blocks.append("[世界设定]\n" + "\n".join("- " + e["content"] for e in world_hits))

    char_blocks = []
    for name, card in cards_present.items():
        sec_lines = []
        # 秘密提示：逐条检查本角色相关的秘密状态，注入对应提示（须嵌套在 per-character 循环内）。
        # 分层：每种状态各自独立成行（「·」引导），不用「｜」串成一坨挂在意图行尾
        # ——单卡最长曾达 1208 字，行尾从句里的提示会被整体淹没。
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
                # 已公开（v0.26.0 四态）：秘密已成公开事实，掩饰/否认不再可信，归属者只剩
                # 「直面后果、应对众人反应」一条路——注入与「潜伏/暴露」不同的框架。
                if s.get("state") == "已公开":
                    sec_lines.append(
                        "· 已公开：「" + s["content"] + "」。在场者皆已知晓，掩饰与否认都不再可信；"
                        "须直面它带来的处境，并应对众人的反应。")
                    if bottom:
                        sec_lines.append("· 后果：" + bottom + "。")
                    if knowers:
                        sec_lines.append("· 知情者：" + "、".join(knowers) + "。")
                else:
                    # 私有底牌：仅归属者本人可见，被触及/追问时由他决定是否吐露；
                    # 一旦吐露须忠于世界书真相，不得歪曲事实或嫁祸他人（根治「甩锅」式自由创作）。
                    # 这是 v0.9.0 修复：此前秘密潜伏时文本不进 prompt，导致「暴露」必然是
                    # 模型自由填空、极易违背设定（如把灾祸因果甩给无辜角色）。
                    line = "· 你的底牌（只有你自己知道）：「" + s["content"] + "」。"
                    if bottom:
                        line += "揭开的后果是：" + bottom + "——这是你死守它的理由。"
                    line += "被触及或追问时由你决定是否吐露；若吐露须忠于以上真相，不得歪曲、不得嫁祸。"
                    sec_lines.append(line)
                    if knowers:
                        sec_lines.append("· 已被 " + "、".join(knowers) + " 知晓，须应对其反应。")
                    # 「正在逼近」不再注入归属者（2026-11-08）：谁在心里起疑，归属者无从
                    # 得知，这是 in-world 不可知的信息，等于引擎替角色感知别人的心理。
                    # suspicions 照常记账——它是秘密四态（潜伏/起疑/已公开）的状态机输入，
                    # 也是起疑者本人那一行提示（下方 elif 分支）的来源；只是不再向归属者点名。
            elif name in holders:
                # 握把柄者已知情，故拿到完整事实（此前截断到 80 字会造成信息缺口，
                # 与归属者拿全文不一致）；同时告知揭开的后果，使其能权衡是否使用这张牌。
                line = "· 你握有 " + owner + " 的把柄：「" + s["content"] + "」，可据此行动"
                if bottom:
                    line += "；揭开的后果：" + bottom
                sec_lines.append(line + "。")
            elif any(x["by"] == name for x in susp):
                # 起疑者只拿到自己那一处疑点，不知道真相全貌：可以试探、观察、追问，
                # 但不得当作既成事实断言（防「起疑即坐实」把张力提前耗尽）。
                clue = next((x.get("clue") or "").strip()[:60]
                            for x in susp if x["by"] == name)
                sec_lines.append(
                    "· 你对 " + owner + " 起了疑：" + (clue or "有说不通的地方")
                    + "。这只是疑点、尚未证实，可试探、观察、追问，但不得当作事实断言。")
        # 人设块：描述 + 性格 + 核心渴望（驱动力）+ 核心恐惧（底线），分层明确
        block = "【" + name + "】\n" + card.get("description", "")
        if card.get("personality"):
            block += "\n性格：" + card["personality"]
        if card.get("core_desire"):
            block += "\n核心渴望（驱动力）：" + card["core_desire"]
        if card.get("core_fear"):
            block += "\n核心恐惧（底线）：" + card["core_fear"]
        # 开局意图：角色卡作者手填的 short_goal，全程不变（引擎不再替角色改写意图）。
        # 没填就不给这一行——留空位等于让模型自己编，那正是被砍掉的 goals 在做的事。
        if (card.get("short_goal") or "").strip():
            block += "\n开局意图（作者设定）：" + card["short_goal"].strip()
        if sec_lines:
            block += "\n" + "\n".join(sec_lines)
        char_blocks.append(block)
    blocks.append(
        "[角色名册（本剧全部角色，不等于同场）]\n"
        "以下为本剧全部有卡角色。名册只说明「本剧有谁」，不说明「本轮谁与谁同处一地」——"
        "同场与主镜头见 [本轮场面]。\n\n" + "\n\n".join(char_blocks))

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

    # 导演指令 + 铁律（环境推手不登场；指令=环境推手本回合注入的扰动）
    # 关键：把「你是导演引擎」改写为「你是叙事者，须遵循以下约束」——
    # 旧版第一人称『导演引擎』会让强思考模型把铁律当成要复述/表演的对象，
    # 在正文里输出策略调整/推演执行/后果留痕等元笔记（已用 narration_clean 兜底剥离，此处从根源压制）。
    laws = _build_laws()
    named = [n for n in cards_present if n in (directive or "")]
    focus_note = ""
    if named:
        focus_note = (
            "\n本回合导演指令点名的角色：" + "、".join(named)
            + "。这些角色必须在本轮出场并推动对应剧情；不得将其写成已离场或移出叙事焦点，"
              "除非指令明确令其离开。若指令描述某角色前往某地/做某事，必须呈现该角色的相关段落。"
        )
    directive_text = directive or "（无导演指令，本轮由在场角色自然推演）"
    blocks.append(
        "[导演指令]\n" + laws
        + "\n\n本轮导演指令：\n" + directive_text + focus_note
    )

    sc = snap["scene"]
    weather = ("｜ 天气：" + sc["weather"]) if sc.get("weather") else ""
    rel = "\n".join(k + ": " + v for k, v in snap["relations"].items()) or "（初始）"
    # 关联但无独立角色卡的「背景人物」（如某位仅被提及的亲属）：仅可作背景提及，
    # 其关系定位为既定事实，严禁模型改写或升级（小姨子→妻子类漂移在此被提示约束）。
    # 口径：关系表里出现、但没有独立角色卡的人。早前用「不在场卡」判定，把有卡但
    # 本轮不在场名单的角色也划成背景，提示词一边要求「不得为其撰写出场段落」、
    # 叙事里他却正在演——自相矛盾（真实会话事故）。故必须以「无独立角色卡」为准。
    # v0.31.2 恢复：本提示词软约束曾在 v0.31.0 随 offscreen 检测层一并删除——检测层
    # （正则自检，命中率趋零且曾误删正文）确该删，但此处从不删正文、只做约束，属连带误删。
    all_cards = set(store.list_characters())
    rel_names = set()
    for k in snap.get("relations", {}):
        for e in k.split("→"):
            rel_names.add(e.strip())
    offscreens = sorted(n for n in rel_names if n and n not in all_cards)
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
    # 时间锚缺失时的兜底：不给「时间未明」这种会诱导模型自行脑补时间的字眼，
    # 而是明确约束「本轮不得自行推进/杜撰时间」。旧版写「时间未明」，模型会为了
    # 让环境自洽而自由补一段时间推进（如一轮内从傍晚推到入夜），正是真实会话里
    # 「颠三倒四」的来源之一。时间推进权归导演指令：scene.resolve 只认指令里明写的时段词，
    # 引擎自己不推时间，叙事层更不越权。
    scene_time = sc.get("time") or ""
    if scene_time:
        time_clause = "（" + scene_time + "）"
    else:
        time_clause = "（时间未知——本轮不得自行推进或杜撰时间，保持时间悬置，待导演指令明确时间再写）"
    cons = "\n".join("- " + l["account"] for l in snap.get("ledger", [])) or "（暂无）"
    state_block = "[关系·状态·旧账]\n关系（既定事实）：\n" + rel + offscreen_note
    st_lines = ["- " + k + "：" + (v.get("value") or "")
                for k, v in (snap.get("states") or {}).items() if v]
    if st_lines:
        state_block += ("\n状态（当前最新值）：\n" + "\n".join(st_lines)
                        + "\n在无新进展前须按此描写，不得写成相反"
                          "（例如门已封死就不得写成通行无阻）。")
    state_block += "\n旧账：\n" + cons
    if active_consequences:
        # 被本轮情境触动的旧账：要求体现在叙事里，否则写账毫无意义。
        state_block += ("\n【本轮被触动的旧账】\n"
                        + "\n".join("- " + a for a in active_consequences)
                        + "\n以上旧账与本轮情境相关，人物的提防、为难、报复、和解或回避"
                          "都须在叙事中体现，不得装作无事发生。")
    # 人物位置：谁在哪里是物理事实，须与状态键分离（见 director.update_locations）。
    # 分队/离场时镜头所在（scene.place）与各角色实际位置不同，此处给出逐人位置，
    # 防止模型把「已困电梯的人」又写回「在卧室里」造成空间矛盾（一次真实事故）。
    # v2.1.0：与「本轮场面」合并渲染——两者同源于 locations，分开写等于重复投料，
    # 且「逐人一行」的旧形态只说了位置、没说分场，模型仍会当成「人人有镜头」。
    roster = scene_roster_block(snap, list(cards_present))
    if roster:
        blocks.append(roster)
    blocks.append(
        state_block
        + "\n回合：" + str(sc["round"])
        + "\n场景：" + sc.get("place", "") + time_clause + weather
        + "\n（关系与旧账为推演既定事实，写作时严格遵循，不得自行推断、改写或升级；"
          "状态可被后续剧情改变，一旦改变以本轮指令与叙事为准）"
    )

    present_names = "、".join(cards_present.keys())


    # 镜头跟随（focus）已删：它只由「指令里有没有出现某个名字字符串」决定，
    # 判不出语义（「避开众人」曾被当成群体点名），却会在生成后按焦点裁剪正文。
    # 谁与谁同场、主镜头落在哪一处，已由 [本轮场面] 按 locations 分场说清（确定性规则）。
    present_clause = (
        "本剧角色名册（有卡、可出场）：" + present_names + "。"
        + "叙事中只可出现名册内角色，不得发明新角色；"
        + "也绝对不要写环境推手（导演）台词或让任何角色对环境推手说话。"
    )

    # 「点名角色必须出场」只在本段（[导演指令] 的 focus_note）说一次。
    # 此前同一约束在四处重复（本节 / [输出格式] / [镜头跟随] / 铁律①），约 700 字：
    # 重复不是加强，是彼此稀释，也让模型对「必须」二字脱敏。
    blocks.append(

        "[输出格式]\n用多说话人叙事写这一轮：开口的角色以「角色名：」另起一段接台词"
        "（动作与神态写在叙述里）。" + present_clause + "\n"
        "情节由导演指令驱动，推进关系碰撞、秘密发酵与后果留痕，让这个世界自己运转起来。"
    )
    # 写法示范（demo）：剧本在世界书里写的 few-shot 范例，放在输出格式段之后（近因位置）。
    if demo_hits:
        demo_text = "\n\n".join(e["content"] for e in demo_hits)
        blocks.append(
            "[写法示范]\n以下是本剧的写法范例，照着它的风格与节奏写（不要复述示范本身的内容）：\n"
            + demo_text
        )
    # 输出纪律：硬性禁止任何元信息混入可见正文（与 narrative_clean 兜底双保险）。
    # 2026-11-08 瘦身：六条并成四条，删掉与②重复的「自我分析阶段」条与举例长尾。
    # 保留的锚点措辞：技法 / 描写标准 / 复述 / 正文（test_prompter 绑这几词，不绑整句）。
    blocks.append(
        "[输出纪律]\n你的回复就是这一轮的叙事正文本身，除此之外不许输出任何东西：\n"
        "① 正文前不得有前言、警告、声明或安全提示；\n"
        "② 不得复述铁律或任何系统指令，不得以导演 / 系统 / AI 口吻发言，"
        "不得自我分析写作策略（「我将聚焦…」「当前阶段是…」）；\n"
        "③ 不得出现「策略调整 / 推演执行 / 后果留痕 / 当前局势 / 关系改写 / 下一回合预览」"
        "之类的元标题或工作笔记，文末不得追加后果清单与预告；\n"
        "④ 世界书里的写作技法 / 描写标准 / 尺度要求是给你的执行约束、不是剧情内容——"
        "按它要求的方式写，严禁把条目的名称、要求文字或技法标签复述进正文。\n"
        "直接以叙事开场，用多说话人叙事写完这一轮即结束。"
    )

    fixed = "\n\n".join(blocks)
    messages = [{"role": "system", "content": fixed}]
    # 历史可能含压缩摘要（system 角色块）。部分严格 chat 模板要求 system 仅能在
    # 首位，故把所有非首位的 system 消息并入首条 system，避免「System message must be at
    # the beginning」导致 llama.cpp 500 空回（部分新模型较宽松可容忍，但统一收口更稳）。
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
        # 顺序：环境在前、指令在后。整条 prompt 的最后一个 token 区域必须是「本轮要写什么」，
        # 而不是「背景长什么样」——after 命中里会压着上千字的技法标准（当前剧本的技法条目
        # 就有 1128 字），旧顺序把【导演指令】推到倒数第二位，与本段自己声明的
        # 「导演指令优先」自相矛盾（2026-10-21 提示词审计）。
        if directive:
            messages.append({"role": "user",
                             "content": env_block + "\n\n【导演指令】" + directive})
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
