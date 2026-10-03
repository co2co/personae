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
             "切换", "换到", "转移到", "搬到", "挤进", "门内", "门外", "隔开"]
# 时间类触发词：时间明显推移
TIME_KEYS = ["第二天", "次日", "晚上", "清晨", "凌晨", "午后", "傍晚", "入夜", "天黑",
             "天亮", "中午", "过了一会", "过了一阵", "几小时", "稍后", "转眼",
             "不知过了多久", "隔天", "第二天早", "第二天晚"]
# 天气类触发词：环境扰动
WEATHER_KEYS = ["下雨", "雨", "下雪", "雪", "刮风", "风", "打雷", "雷", "放晴", "晴",
                "阴", "起雾", "雾", "天色", "天气", "降温", "升温"]
# 显式离场触发词：仅当指令含这些词时，才允许把角色移出在场名单。
# 纯地点移动（去/来到/前往/走到）视作全员随世界一起转移，绝不移除在场者，
# 避免导演指令指向的角色（如“去下水道侦察”）被 scene LLM 误判离场而静默丢弃。
LEAVE_KEYS = ["离开", "离场", "回房", "回去睡", "出去", "走开", "撤离", "退出", "离去",
              "撤走", "先走", "离开这里", "离开现场", "退场", "出门去", "离开仓库",
              "门外", "挡在门外", "留守", "留在", "隔开"]
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
2. 仅当指令明确写某角色离开，或空间上与队伍分隔（如“让X离开”“X回房睡了”“X被挡在门外”“X留守门外”“两人分开，X留在原地”），才在 leave/arrive 填入；其中“被挡在门外/留在另一处/与队伍分开”也视为离场，可在 leave 填该角色，其余人随场景移动，不要因此把全员都移出。
3. leave/arrive 名字必须严格来自 all_chars；无人进出则为空数组。只输出 JSON，不要任何解释文字。"""

# 停留超时触发时追加在 _PROMPT 之后：把可选的"是否变化"变成必须的"必须变化"，
# 否则 LLM 倾向于返回 changed=false，防僵死保护会被架空。
_FORCE_HINT = """

【强制推进】当前场景已连续停留 {stuck} 轮未发生变化。本轮必须让时间或环境发生一次
可见推移（如天色由清晨转至正午/入夜、天气起变化、队伍转移到新地点），changed 必须为
true；不得返回无变化。若实在无地点变化，也至少推进 time 或 weather。"""


def _triggered(directive, snap):
    """判定本轮是否调用场景导演，并区分触发来源。

    返回 (triggered, force)：
    - triggered：本轮是否需要调用 LLM 定稿。
    - force：是否因"同场景停留过久"而触发。为 True 时是防僵死保护的唯一生效
      路径，apply 会要求 LLM 本轮必须产出一次可见推移（见 _FORCE_HINT）。
    """
    t = directive or ""
    # 停留超时必须优先于关键词判定：否则只要指令常含"去/天亮"等触发词，
    # 就永远走关键词分支（force=False），防僵死保护同样会被架空。
    if snap["scene"].get("same_scene", 0) >= AUTO_TIME_THRESHOLD:
        return True, True
    if any(k in t for k in MOVE_KEYS):
        return True, False
    if any(k in t for k in TIME_KEYS):
        return True, False
    if any(k in t for k in WEATHER_KEYS):
        return True, False
    return False, False


def apply(sid, directive, snap):
    """就地更新 snap 的场景（地点/时间/天气）与在场名单（若有切换）。返回 (changed, prop)。

    prop 为 LLM 解析结果，未切换或解析失败为 None。环境推手不入场，故在场名单只受
    指令中显式进出影响；地点/天气变化默认全员随世界移动（安全网保证名单不乱）。
    """
    triggered, force = _triggered(directive, snap)
    if not triggered:
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
    if force:
        prompt += _FORCE_HINT.format(stuck=snap["scene"].get("same_scene", 0))
    try:
        raw = llm.complete(
            [{"role": "system", "content": prompt}],
            temperature=0.3, top_p=0.9, max_tokens=200, timeout=45,
        )
    except Exception:
        # 调用失败等同于场景未变，停留计数累加。此处若清零会架空防僵死保护。
        snap["scene"]["same_scene"] = snap["scene"].get("same_scene", 0) + 1
        return False, None

    prop = _parse(raw)
    if not prop or not prop.get("changed"):
        # 场景实际未变化，停留计数必须累加。
        # 原实现在此清零，导致指令常含触发词时（"去/回到/天亮"等）每轮都触发、
        # 每轮都清零，same_scene 永远达不到 AUTO_TIME_THRESHOLD，防僵死保护彻底
        # 失效——实测表现为场景连续 23 轮不变、与叙事已推进到的地点脱节。
        cur = snap["scene"].get("same_scene", 0) + 1
        if force:
            # 强制推进已尝试一次仍未变化：重置计数进入冷却，避免此后每轮都调 LLM
            # （保留"规则版触发避免每轮调 LLM"的设计原则）。最坏情况为每
            # AUTO_TIME_THRESHOLD 轮尝试一次强制推进，而非永不推进。
            cur = 0
        snap["scene"]["same_scene"] = cur
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
    # 硬约束：指令未显式含离场词时，纯地点移动视作全员随世界转移，
    # 绝不移除任何在场者——避免导演指令指向的角色被静默丢弃（如“去下水道侦察”被误判离场）。
    if not any(k in (directive or "") for k in LEAVE_KEYS):
        leave = []
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
