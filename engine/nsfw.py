"""NSFW 门控：决定本次请求的内容尺度，以及往提示词里插哪一段说明。

多角色沙盘模式用 resolve_session()：尺度由「成年确认 + 本轮机会等级」驱动。
机会等级（试探/半步/满机会）由导演判定后通过 prompt 注入，强度随机会缩放。

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
        "禁止停在门口、禁止自我克制式收尾、禁止只用情绪词糊弄；"
        "若角色抗拒，抗拒须是可见的、指向对方的具体动作并留下后果。"
    ),
}


def resolve_session(snap, adult_confirmed, opp_level="无", override=None):
    """多角色沙盘模式：尺度由「成年确认 + 本轮机会等级」驱动，不再用好感度阈值。

    回归 relationship-sandbox 原版机制：环境推手是外部导演，亲密内容随角色间的机会等级
    缩放，而非随好感度解锁。未确认成年则一律受限。
    """
    if not adult_confirmed:
        return {"unlocked": False, "intimate": False, "prompt": GUARD,
                "reason": "未确认成年，强制受限"}
    if override == "off":
        return {"unlocked": False, "intimate": False, "prompt": GUARD, "reason": "当次强制受限"}
    if override == "on":
        return {"unlocked": True, "intimate": True, "prompt": UNLOCKED, "reason": "当次强制解锁"}

    if not opp_level or opp_level == "无":
        # 无机会触发：允许暧昧张力，但不写具体越线过程
        return {"unlocked": True, "intimate": False, "prompt": UNLOCKED,
                "reason": "成年已确认，本轮无亲密机会，保持浪漫张力"}

    note = OPP_PROMPT.get(opp_level, "")
    intimate = opp_level in ("半步", "满机会")
    return {
        "unlocked": True,
        "intimate": intimate,
        "prompt": UNLOCKED + "\n" + note,
        "reason": f"成年已确认，机会等级：{opp_level}",
    }
