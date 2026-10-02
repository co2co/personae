"""NSFW 门控：决定本次请求的内容尺度，以及往提示词里插哪一段说明。

多角色沙盘模式用 resolve_session()：尺度由「成年确认 + 本轮机会等级」驱动。
机会等级（试探/半步/满机会）由导演（director.brief）判定后通过 prompt 注入，强度随机会缩放。

「满机会」的语义：本轮剧情被许可写到「性行为尺度上限」。导演综合五类信号取最高：
  ① 双向好感/恋爱关系  ② 秘密把柄胁迫  ③ 第三方/对方暴力强迫胁迫
  ④ 近期叙事推进的升温连贯（上限半步）  ⑤ 扰动指令（独处脆弱 / 导演明写性）
任一满足即满机会；半步另含单向暧昧/暗恋、独处无脆弱等升温态。

许可 vs 事实（重要）：机会等级只是「许可」——允许写到该尺度，写不写由剧情决定。
本模块只发许可，返回 intimate_allowed；本轮**实际**写到了哪一步由
director.detect_intimacy(reply) 判定。二者不可混用：拿许可当事实会把"允许但没发生"
误记成既成后果。

优先级：未确认成年 > 当次 override > 角色卡配置 > 默认 off
"""

GUARD = (
    "保持叙事克制：涉及亲密内容时只用暗示、留白与情绪描写，"
    "不写具体的性行为过程与身体细节。"
)

UNLOCKED = (
    "允许亲密与浪漫描写，可以推进到更私人的互动，"
    "但必须保持角色性格一致、叙事有推进，避免重复的流水账。"
)

DEFAULT_CONFIG = {"mode": "off", "threshold": 6, "sticky": True}

# 机会等级对应的内容强度说明（铁律6 + NSFW 基调）
OPP_PROMPT = {
    "试探": "可写指向对方的接触试探（触碰/靠近/语言挑逗），不必越线。",
    "半步": "应写对应程度的接触（持续触碰/肢体纠缠/氛围压到临界）。",
    "满机会": (
        "必须越线：直接写出完整的性行为过程，不得用暗示、留白或心理活动替代生理描写。"
        "明确写出生殖器与胸部的接触、亲吻与舔舐、插入与抽送的动作和节奏、身体的反应"
        "（夹紧/颤抖/潮润/体液）、双方的声音与呼吸；"
        "禁止停在门口、禁止停在边缘（龟头抵在入口却不进入）、禁止只写前戏不写进入、"
        "禁止自我克制式收尾、禁止只用情绪词糊弄；"
        "若角色抗拒，抗拒须是可见的、指向对方的具体动作并留下后果，"
        "而不是用「他最终没有真正进入」「她避开了」之类一笔带过规避事实。"
    ),
}


def resolve_session(snap, adult_confirmed, opp_level="无", override=None):
    """多角色沙盘模式：尺度由「成年确认 + 本轮机会等级」驱动，不再用好感度阈值。

    回归 relationship-sandbox 原版机制：环境推手是外部导演，亲密内容随角色间的机会等级
    缩放，而非随好感度解锁。未确认成年则一律受限。
    """
    if not adult_confirmed:
        return {"unlocked": False, "intimate_allowed": False, "prompt": GUARD,
                "reason": "未确认成年，强制受限"}
    if override == "off":
        return {"unlocked": False, "intimate_allowed": False, "prompt": GUARD,
                "reason": "当次强制受限"}
    if override == "on":
        return {"unlocked": True, "intimate_allowed": True, "prompt": UNLOCKED,
                "reason": "当次强制解锁"}

    if not opp_level or opp_level == "无":
        # 无机会触发：允许暧昧张力，但不写具体越线过程
        return {"unlocked": True, "intimate_allowed": False, "prompt": UNLOCKED,
                "reason": "成年已确认，本轮无亲密机会，保持浪漫张力"}

    note = OPP_PROMPT.get(opp_level, "")
    return {
        "unlocked": True,
        # 许可，不是事实：仅表示"允许写到该尺度"，本轮是否真写了由剧情决定。
        # 需要"实际发生了什么"请用 director.detect_intimacy(reply)。
        "intimate_allowed": opp_level in ("半步", "满机会"),
        "prompt": UNLOCKED + "\n" + note,
        "reason": f"成年已确认，机会等级：{opp_level}",
    }


def resolve_for_request(snap, adult_confirmed, nsfw_enabled, body_nsfw, opp_level):
    """服务端入口：把「设置 + 本次请求」归一成 resolve_session 的 override。

    关键防守点：override 完全由服务端设置决定，客户端请求体里的 nsfw 字段只有在
    nsfw_enabled=True 时才会被采纳；否则强制 off。这样「未确认成年 / 未开启 NSFW」的
    玩家即便在请求体里伪造 nsfw="on"，也无法突破门控。
    """
    override = "off" if not nsfw_enabled else body_nsfw
    return resolve_session(snap, adult_confirmed, opp_level, override=override)
