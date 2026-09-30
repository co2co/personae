"""场景自动切换：环境推手注入扰动 / 时间推移时，调用一次轻量 LLM 产出新场景与在场变化。

设计原则：
- 规则版触发（关键词命中）避免每轮都调 LLM；命中后才发一次小请求定稿。
- 同场景停留超过 AUTO_TIME_THRESHOLD 回合，自动让时间流逝一次，避免场景僵死。
- 始终保护在场名单：环境推手不入场，在场名单只受指令显式进出影响；去重、只认合法卡、离开/到达都做安全网过滤。
  这正是此前"在场角色" bug 的同一类坑，这里用与 session_new 一致的去重/剔除逻辑。
"""

import json

import llm
import store

# 移动类触发词：指令明确要求换地点
MOVE_KEYS = ["去", "回", "走到", "前往", "出门", "下楼", "上楼", "离开", "回到",
             "转去", "挪到", "步入", "拐进", "登上", "走回", "退到", "钻进",
             "切换", "换到", "转移到", "搬到"]
# 时间类触发词：时间明显推移
TIME_KEYS = ["第二天", "次日", "晚上", "清晨", "凌晨", "午后", "傍晚", "入夜", "天黑",
             "天亮", "中午", "过了一会", "过了一阵", "几小时", "稍后", "转眼",
             "不知过了多久", "隔天", "第二天早", "第二天晚"]
# 天气类触发词：环境扰动
WEATHER_KEYS = ["下雨", "雨", "下雪", "雪", "刮风", "风", "打雷", "雷", "放晴", "晴",
                "阴", "起雾", "雾", "天色", "天气", "降温", "升温"]
# 同场景停留这么多回合后，自动让时间/地点自然流逝一次（贴合原版 A4 的 ≥3 回合）
AUTO_TIME_THRESHOLD = 3

_PROMPT = """你是关系沙盘的“场景导演”。环境推手注入一条扰动指令，判断场景/天气/在场是否变化，仅输出一行 JSON。
当前场景：{place} ｜ 时间：{time} ｜ 天气：{weather}
当前在场：{present}
环境推手指令：{action}
已知全部角色卡：{all_chars}

输出 JSON 字段：
- changed: 布尔。仅当指令明确要求切换地点、推移时间、改变天气，或有人进出时为真。
- place: 新地点（无变化填原 place）。
- time: 新时间（无变化填原 time）。
- weather: 新天气（无变化填原 weather；可填 晴/雨/雪/阴/大风/雾 等）。
- leave: 明确离开场景、不再在场的角色（必须来自 all_chars）。
- arrive: 新进入场景的角色（必须来自 all_chars）。
- reason: 一句话说明。

约束（务必遵守）：
1. 若指令仅切换地点/时间/天气（如“切换到阳台”“天黑了”“下起雨”），全员随世界一起移动，leave/arrive 必须为空数组。
2. 仅当指令明确写某角色离开（如“让林泽宇离开”“周晓杰回房睡了”）或到来（“周晓杰进来了”），才在 leave/arrive 填入。
3. leave/arrive 名字必须严格来自 all_chars；无人进出则为空数组。只输出 JSON，不要任何解释文字。"""


def _triggered(directive, snap):
    t = directive or ""
    if any(k in t for k in MOVE_KEYS):
        return True
    if any(k in t for k in TIME_KEYS):
        return True
    if any(k in t for k in WEATHER_KEYS):
        return True
    if snap["scene"].get("same_scene", 0) >= AUTO_TIME_THRESHOLD:
        return True
    return False


def apply(sid, directive, snap):
    """就地更新 snap 的场景（地点/时间/天气）与在场名单（若有切换）。返回 (changed, prop)。

    prop 为 LLM 解析结果，未切换或解析失败为 None。环境推手不入场，故在场名单只受
    指令中显式进出影响；地点/天气变化默认全员随世界移动（安全网保证名单不乱）。
    """
    if not _triggered(directive, snap):
        snap["scene"]["same_scene"] = snap["scene"].get("same_scene", 0) + 1
        return False, None

    all_chars = store.list_characters()
    prompt = _PROMPT.format(
        place=snap["scene"].get("place", ""),
        time=snap["scene"].get("time", ""),
        weather=snap["scene"].get("weather", "") or "（未设定）",
        present="、".join(snap["present"]),
        action=directive,
        all_chars="、".join(all_chars),
    )
    try:
        raw = llm.complete(
            [{"role": "system", "content": prompt}],
            temperature=0.3, top_p=0.9, max_tokens=200, timeout=45,
        )
    except Exception:
        snap["scene"]["same_scene"] = 0
        return False, None

    prop = _parse(raw)
    if not prop or not prop.get("changed"):
        snap["scene"]["same_scene"] = 0
        return False, prop

    # 落实新场景
    snap["scene"]["place"] = (prop.get("place") or snap["scene"].get("place", "")).strip()
    snap["scene"]["time"] = (prop.get("time") or snap["scene"].get("time", "")).strip()
    snap["scene"]["weather"] = (prop.get("weather") or snap["scene"].get("weather", "")).strip()
    snap["scene"]["same_scene"] = 0

    # 落实場名单变化（安全网：去重、仅合法卡、离开者须当前在场、到达者须未在场）
    present = list(snap["present"])
    orig_present = set(present)
    leave = [c for c in dict.fromkeys(prop.get("leave", []))
             if c in all_chars and c in present]
    arrive = [c for c in dict.fromkeys(prop.get("arrive", []))
              if c in all_chars and c not in present]
    # 安全网增强：LLM 偶发把"全员随世界转移"误填进 leave（把"离开旧地点"理解成每人离场），
    # 一旦清空在场名单，下游 validate_present 会把整段回复剥空、用户拿到一片空白。
    # 规则：若 leave 覆盖全部在场者且无 arrive，判定为"随世界一起移动"，忽略 leave/arrive；
    # 若施加后名单仍为空（任何原因），同样回退为全员随世界移动，绝不允许空在场名单。
    if leave and set(leave) >= orig_present and not arrive:
        leave, arrive = [], []
    for c in leave:
        present.remove(c)
    for c in arrive:
        present.append(c)
        # 到达者补齐短期目标，避免前端/后续归因缺失
        snap.setdefault("goals", {})[c] = store.load_card(c).get("short_goal", "")
    if not present:
        present = list(orig_present)
    snap["present"] = present
    return True, prop


def _parse(raw):
    if not raw:
        return None
    try:
        s = raw[raw.find("{"):raw.rfind("}") + 1]
        return json.loads(s)
    except Exception:
        return None
