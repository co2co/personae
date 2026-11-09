"""场景解析：把导演指令里明确写出的地点 / 时间 / 天气落成快照字段。纯规则，不调 LLM。

2026-11-08 引擎瘦身（回滚：git checkout checkpoint-pre-slim-20261108 -- engine/scene.py；
改动前的旧版另存 backup/removed-20261108/scene_pre_slim_20261108.py）：
原先这里每轮可能再发一次 LLM 请求（「场景导演」），把指令交给模型判 changed/place/
time/weather，再用正则清洗它的自由发挥。两处代价：
  1. 每轮多一次调用。触发词表含「去」「回」单字，实际几乎每轮都触发（审计实测 920 字/次）。
  2. AUTO_TIME_THRESHOLD「同场景停留 ≥3 轮必须推进一次」是在伪造剧情——指令没写时间，
     引擎却硬要时间流逝一次，正文跟着漂（真实会话里表现为时段乱跳）。
现在规则自己判：指令里有明确时间词就用它（将来时除外），有「切换到X」这类句式就取 X，
有天气词就归一。判不出就不改——场景是导演（环境推手）的设定，他说出口才算变化。
「谁在哪」不在本层：那是 locations 的职责，由纪官按正文举证维护（见 director.update_locations），
prompter 的 [本轮场面] 段据此分场。
"""

import re

# 开场场景字符串里的时间词：用于把「傍晚，公寓的客厅」这类混写拆成 (place, time)。
# 不含「过了一会」这类过程词——过程词要推进多久是猜的，不进结构化字段。
# 排序按长词优先，避免「第二天早」被「第二天」抢先截断（用「最长匹配」而非先后）。
INITIAL_TIME_KEYS = [
    "第二天晚上", "第二天早上", "第二天上午", "第二天下午", "第二天", "次日", "深夜", "半夜",
    "凌晨", "清晨", "早晨", "早上", "上午", "中午", "正午", "下午", "黄昏", "傍晚", "黎明",
    "入夜", "天黑", "天亮", "夜晚", "晚上", "白天", "午后",
]

# 将来时/预告词：指令里出现这些词时，时间词属「尚未发生」，只能算铺垫，不推进当前时间。
_FUTURE_MARKERS = ["即将", "快要", "快到了", "将", "马上", "待会", "稍后", "就要",
                   "再等", "等会", "就要到", "快要到", "明天", "明晚", "明早"]

# 位移句式：只有出现这类「明确把镜头挪到某处」的措辞才改 place。
# 单字「去 / 回」不进表——「去年」「进去」「回去」都会误伤（审计 P2 指出的过度触发）。
_MOVE_TO_RE = re.compile(
    r"(?:切换到|转移到|换到|挪到|搬到|移到|来到|前往|走到|走进|步入|拐进|钻进|登上|挤进|"
    r"退到|回到|转去)\s*([^\s，。；！？、：:""''（）()【】「」]{1,12})"
)
# 捕获串里遇到动作词就截断：中文没有空格，「走到门口看看」会一路吞到句读。
_PLACE_CUT_RE = re.compile(r"[看找等听说问睡坐站拿递抱拉推打跑想试]")
# 捕获到这些词时不当作地点（「回到从前」「退到原地」）。
_PLACE_STOPWORDS = {"从前", "过去", "原点", "原地", "原位", "这里", "那里", "现实", "梦境"}

# 天气变化要「动词 + 天气名」才成立：单字「雨 / 风」裸匹配会把「去年那场雨还没说完」
# 这种叙述当成本轮天气变化（旧版触发词表就有这毛病）。
_WEATHER_RE = re.compile(
    r"(?:下|飘|打|刮|起|转|放)(?:了|起)?([雨雪雷风雾晴])|雨势|雪势|天气(?:转|变)"
)
# 捕获到的天气名 → 快照里的规范值
_WEATHER_VALUE = {"雨": "雨", "雪": "雪", "雷": "雷", "风": "大风", "雾": "雾", "晴": "晴"}


def parse_initial_scene(text):
    """把开场场景字符串拆成 (place, time)。

    玩家在开局输入框里常把时间与地点混写在一起（如「傍晚，公寓的客厅」「晚饭后，客厅」），
    旧实现把整串塞进 place、time 恒空，导致时间锚丢失、正文只能靠模型自行脑补时间
    （一次真实会话：玩家给「傍晚」却丢失，正文一轮内自行从傍晚推到入夜）。

    此处按「最长匹配」从文本里识别一个时间词填入 time，剩余部分（去标点）填 place。
    识别不到时间词时 time 为空、place 为原文本——与旧行为一致，不破坏既有调用。
    返回 (place, time)，两者均已 strip。
    """
    t = (text or "").strip()
    if not t:
        return "", ""
    # 最长匹配：按长度降序，避免「第二天早」被「第二天」抢先命中
    matched = None
    for k in sorted(INITIAL_TIME_KEYS, key=len, reverse=True):
        if k in t:
            matched = k
            break
    if not matched:
        return t, ""
    place = t.replace(matched, "", 1)
    # 去残留下来的分隔标点与空白，避免「傍晚，公寓的客厅」拆出「，公寓的客厅」或「，」
    place = place.strip(" \t,，、。；;:：").strip()
    return place, matched


def _is_future_time(d):
    """判断指令里的时间词是否属「将来时预告」（尚未发生，不该推进当前时间）。

    命中模式：时间词后紧邻「快到了/快要/即将/将/就要/马上/待会」等将来标记，
    或「夜晚快到了」「天快黑了」这类「…快…了」预告句式。
    """
    d = d or ""
    for k in sorted(INITIAL_TIME_KEYS, key=len, reverse=True):
        if k in d:
            # 取时间词之后紧邻的 3 个字，看是否命中将来标记
            idx = d.find(k) + len(k)
            tail = d[idx:idx + 3]
            if any(m in tail for m in _FUTURE_MARKERS):
                return True
            # 「…快…了」句式：时间词后 4 字内含「快」+「了」
            if "快" in d[idx:idx + 4] and "了" in d[idx:idx + 6]:
                return True
    return False


def _clean_time(value):
    """从任意文本里取一个干净的「时刻/时段」名词，取不到返回 None。

    长词优先。只认词表里的时段词，描述句（「夜幕降临」「天色暗沉」）一律不采信——
    结构化字段里塞描述句，下一轮的时间锚就成了一句废话。
    """
    if not value:
        return None
    v = value.strip()
    for k in sorted(INITIAL_TIME_KEYS, key=len, reverse=True):
        if k in v:
            return k
    return None


def _extract_time(directive, current):
    """指令里的时间词 → 新 time；将来时预告、或没有时间词、或与当前相同 → None。"""
    d = directive or ""
    if _is_future_time(d):
        return None
    got = _clean_time(d)
    if not got or got == (current or ""):
        return None
    return got


def _extract_place(directive):
    """指令里的位移句式 → 新 place；取不到返回 None（不改）。"""
    m = _MOVE_TO_RE.search(directive or "")
    if not m:
        return None
    place = (m.group(1) or "").strip()
    place = _PLACE_CUT_RE.split(place, 1)[0].strip()
    # 只比起手两个字：「回到从前那种信任里」捕获到的是整串，不是干净的地点名。
    if len(place) < 2 or place[:2] in _PLACE_STOPWORDS:
        return None
    return place


def _extract_weather(directive):
    """指令里的天气词 → 归一 weather；取不到返回 None（不改）。"""
    m = _WEATHER_RE.search(directive or "")
    if not m:
        return None
    if m.group(1):
        return _WEATHER_VALUE.get(m.group(1))
    # 命中「雨势 / 雪势 / 天气转…」：从原句里找它说的是哪种天气
    tail = (directive or "")[m.start():m.start() + 6]
    for name, val in _WEATHER_VALUE.items():
        if name in tail:
            return val
    return None


def resolve(snap, directive):
    """按导演指令就地更新 snap["scene"]（地点 / 时间 / 天气）。返回 (changed, prop)。

    prop 为 None 表示本轮场景未变。场景只在指令明说时变化：
      - 「切换到阳台」→ place；「第二天」「入夜」→ time（将来时「天快黑了」不算）；
      - 「下起雨」→ weather。
    判不出就不变。引擎不再替叙事推进时间——旧版 AUTO_TIME_THRESHOLD 的「停够三轮必须
    推进一次」正是真实会话里时段乱跳的来源。
    """
    sc = snap.setdefault("scene", {})
    notes = []
    place = _extract_place(directive)
    if place:
        sc["place"] = place
        notes.append("地点 → " + place)
    new_time = _extract_time(directive, sc.get("time", ""))
    if new_time:
        sc["time"] = new_time
        notes.append("时间 → " + new_time)
    weather = _extract_weather(directive)
    if weather and weather != (sc.get("weather") or ""):
        sc["weather"] = weather
        notes.append("天气 → " + weather)
    if not notes:
        return False, None
    return True, {
        "changed": True,
        "place": sc.get("place", ""),
        "time": sc.get("time", ""),
        "weather": sc.get("weather", ""),
        "reason": "；".join(notes),
    }
