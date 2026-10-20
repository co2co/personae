"""场景自动切换：环境推手注入扰动 / 时间推移时，调用一次轻量 LLM 产出新场景。

设计原则：
- 规则版触发（关键词命中）避免每轮都调 LLM；命中后才发一次小请求定稿。
- 同场景停留超过 AUTO_TIME_THRESHOLD 回合，自动让时间流逝一次，避免场景僵死。
- 只管场景本身（地点/时间/天气），**不判断角色进出**（v2.1.0）：`present` 是建局
  定下的角色名册，永不收缩；「谁在哪」由 locations 维护，并由 [本轮场面] 段按位置
  分场渲染。早期把「物理同场」塞进「可写名单」的做法已在 v2.1.0 移除。
"""

import json

import llm

# 移动类触发词：指令明确要求换地点
MOVE_KEYS = ["去", "回", "走到", "前往", "出门", "下楼", "上楼", "离开", "回到",
             "转去", "挪到", "步入", "拐进", "登上", "走回", "退到", "钻进",
             "切换", "换到", "转移到", "搬到", "挤进", "门内", "门外", "隔开"]
# 时间类触发词：时间明显推移
TIME_KEYS = ["第二天", "次日", "晚上", "夜晚", "深夜", "半夜", "清晨", "凌晨", "午后",
             "傍晚", "入夜", "天黑", "天亮", "中午", "正午", "早晨", "早上", "下午",
             "黄昏", "黎明", "半夜", "过了一会", "过了一阵", "几小时", "稍后", "转眼",
             "不知过了多久", "隔天", "第二天早", "第二天晚"]

# 开场场景字符串里的时间词：用于把「傍晚，公寓的客厅」这类混写拆成 (place, time)。
# 比 TIME_KEYS 更贴近「时刻/时段」语义，不含「过了一会」这类过程词。
# 排序按长词优先，避免「第二天早」被「第二天」抢先截断（用「最长匹配」而非先后）。
INITIAL_TIME_KEYS = [
    "第二天晚上", "第二天早上", "第二天上午", "第二天下午", "第二天", "次日", "深夜", "半夜",
    "凌晨", "清晨", "早晨", "早上", "上午", "中午", "正午", "下午", "黄昏", "傍晚", "黎明",
    "入夜", "天黑", "天亮", "夜晚", "晚上", "白天", "午后",
]
# 天气类触发词：环境扰动
WEATHER_KEYS = ["下雨", "雨", "下雪", "雪", "刮风", "风", "打雷", "雷", "放晴", "晴",
                "阴", "起雾", "雾", "天色", "天气", "降温", "升温"]
# v2.1.0：LEAVE_KEYS（显式离场触发词表）随 leave/arrive 处理一并删除。
# 「谁在哪」改由 locations 表达，本层不再判断角色进出，也就没有「离场词」这个概念。
# 同场景停留这么多回合后，自动让时间/地点自然流逝一次（贴合原版 A4 的 ≥3 回合）
AUTO_TIME_THRESHOLD = 3

_PROMPT = """你是关系沙盘的“场景导演”。环境推手注入一条扰动指令，判断场景/天气是否变化，仅输出一行 JSON。
当前场景：{place} ｜ 时间：{time} ｜ 天气：{weather}
环境推手指令：{action}

输出 JSON 字段：
- changed: 布尔。仅当指令明确要求切换地点、推移时间或改变天气时为真。
- place: 新地点（无变化填原 place）。
- time: 新时间（无变化填原 time）。**必须是一个干净的「时刻/时段」名词**，例如
  傍晚/夜晚/深夜/清晨/凌晨/午后/中午/正午/第二天/次日/入夜/天亮/天黑/黄昏/黎明/早晨/早上/上午/下午/白天。
  严禁填入动作句、描写句或括号补充，例如「夜幕降临」「天色暗沉」「无（室内…）」「窗外夜色浓稠」这类都不允许。
- weather: 新天气（无变化填原 weather；可填 晴/雨/雪/阴/大风/雾 等，同样只填干净名词，不要带括号描述）。
- reason: 一句话说明。

约束（务必遵守）：
1. 若指令仅切换地点/时间/天气（如“切换到阳台”“天黑了”“下起雨”），只更新对应字段，其余保持原值。
2. 你**不判断角色进出**：谁在哪由事后从叙事里读位置来维护（纪官 location_updates），
   本层只管场景本身。指令若点名某人离开，place/时间照常更新，不要额外推断其余人的去向。
3. 只输出 JSON，不要任何解释文字。
4. **将来时态不算当前变化**：指令写「即将到来的夜晚」「明天会下雨」「稍后去某地」这类**尚未发生**的事，只是铺垫或预告，不代表时间/天气/地点此刻已经改变——此时 changed 填 false，time/weather/place 保持原值，不得把「即将到来」当成「已经到来」。「夜晚快到了」「天快黑了」等同属将来时预告，同样不推进。
5. **时间词原样采用**：指令里若出现明确时间词（如「第二天」「清晨」「入夜」「午后」），time 应**原样采用该词或其等价时段名词**，不得自由改写成别的时段——尤其「第二天」不得丢掉跨日语义、降级成「白天」「天亮」。「傍晚」不得被改写成「入夜」。"""

# 停留超时触发时追加在 _PROMPT 之后：把可选的"是否变化"变成必须的"必须变化"，
# 否则 LLM 倾向于返回 changed=false，防僵死保护会被架空。
_FORCE_HINT = """

【强制推进】当前场景已连续停留 {stuck} 轮未发生变化。本轮必须让时间或环境发生一次
可见推移（如天色由清晨转至正午/入夜、天气起变化、队伍转移到新地点），changed 必须为
true；不得返回无变化。若实在无地点变化，也至少推进 time 或 weather。"""


def parse_initial_scene(text):
    """把开场场景字符串拆成 (place, time)。

    玩家在开局输入框里常把时间与地点混写在一起（如「傍晚，公寓的客厅」「晚饭后，客厅」），
    旧实现把整串塞进 place、time 恒空，导致时间锚丢失、正文只能靠模型自行脑补时间
    （真实会话 256d924c：玩家给「傍晚」却丢失，正文一轮内自行从傍晚推到入夜）。

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
    # 纪官并联（v0.17.2）：上一轮叙事里场景/时间/天气已实际变化，但快照没跟上
    # （如正文早已入夜、scene.time 还停在「清晨」）。关键词表枚举不完这类变化，
    # 纪官从语义上读出来补上。零额外 LLM 成本——reflect 本来就每轮都跑。
    if (snap.get("scene_shift") or {}).get("changed"):
        return True, False
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
    # 纪官信号用后即清：它只是「上一轮的观察」，本轮已消费。留着会让同一次上报
    # 反复触发，把「规则版触发避免每轮调 LLM」的设计原则架空。
    shift = snap.pop("scene_shift", None) or {}
    if not triggered:
        snap["scene"]["same_scene"] = snap["scene"].get("same_scene", 0) + 1
        return False, None

    prompt = _PROMPT.format(
        place=snap["scene"].get("place", ""),
        time=snap["scene"].get("time", ""),
        weather=snap["scene"].get("weather", "") or "（未设定）",
        action=directive,
    )
    if force:
        prompt += _FORCE_HINT.format(stuck=snap["scene"].get("same_scene", 0))
    if shift.get("changed"):
        # 纪官从上一轮叙事里读到的实际场景：正文已经走到这儿了，快照还停在旧值。
        # 以叙事为准——场景与叙事脱节比场景少变一次严重得多。
        prompt += (
            "\n\n【纪官观察】上一轮叙事结束时场景已实际变为："
            + f"地点 {shift.get('place') or '（未变）'}"
            + f"｜时间 {shift.get('time') or '（未变）'}"
            + f"｜天气 {shift.get('weather') or '（未变）'}"
            + "。若与上方当前场景不一致，请以叙事为准更新（changed 填 true）。"
        )
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
    old_place = snap["scene"].get("place", "")
    new_place = (prop.get("place") or old_place).strip()
    snap["scene"]["place"] = new_place
    snap["scene"]["time"] = _norm_time(
        prop.get("time"), directive, snap["scene"].get("time", "")).strip()
    snap["scene"]["weather"] = (prop.get("weather") or snap["scene"].get("weather", "")).strip()
    snap["scene"]["same_scene"] = 0
    # 场景地点变化即短期目标作废：goal 是「当前情境下的短期意图」，地点一变情境即变，
    # 旧目标（如「贴身照看某人伤口」）会把角色错误锚定在原场景、无视本轮已转移到新地点
    # 的事实（会话 9f2e16e9 R14：角色被旧目标拽回电梯口救治已离场的同伴）。清空后下轮
    # 纪官基于新场景重新生成目标，避免残留锚定。
    if new_place and new_place != old_place:
        snap["goals"] = {}

    # v2.1.0 拆职责：present 是「角色名册」（建局 cast），不再随场景切换或人员进出收缩。
    # 「谁在哪」由 locations 表达（纪官的 location_updates → [本轮场面] 段按位置分场），
    # 本层只负责场景本身（地点/时间/天气）。原 leave/arrive 处理整段移除：它把「物理同场」
    # 硬塞进「可写名单」，而群像多线叙事里两者必然打架（实测会把与主角同处一室的角色
    # 踢出名单、让支线角色整条消失，且 arrive 基本不会被模型填）。
    return True, prop


def _parse(raw):
    if not raw:
        return None
    try:
        s = raw[raw.find("{"):raw.rfind("}") + 1]
        return json.loads(s)
    except Exception:
        return None


# 将来时/预告词：指令里出现这些词时，时间不能当作「已经推进」，只能算铺垫。
# 用于 _norm_time 从指令提取时间词时过滤掉「尚未发生」的将来时。
_FUTURE_MARKERS = ["即将", "快要", "快到了", "将", "马上", "待会", "稍后", "就要",
                   "再等", "等会", "就要到", "快要到", "明天", "明晚", "明早"]


def _norm_time(value, directive, fallback):
    """把场景导演返回的 time 清洗成「干净的时段名词」。

    场景导演（LLM）常把 time 自由发挥成描述句——「夜幕降临」「天色暗沉」
    「无（室内，窗外夜色浓稠）」——直接落进 scene.time 会让时间锚变成一句废话，
    后续 build_session 又得靠模型脑补（256d924c 事故的同类根因）。

    清洗顺序（定义层，不改变语义）：
    1. value 本身是干净时间词 → 直接采用。
    2. value 里能提取出一个时间词（含描述串里夹带的）→ 用该词。
    3. value 无干净词，但指令里含时间词且非将来时 → 采用指令里的词（去将来时）。
    4. 都不行 → 回退 fallback（原 time），宁可不推进也不写废话。
    """
    def _clean(v):
        if not v:
            return None
        v = v.strip()
        # 长词优先，避免「第二天早」被「第二天」截断
        for k in sorted(INITIAL_TIME_KEYS, key=len, reverse=True):
            if k in v:
                return k
        return None

    # 1/2：value 里取干净时间词
    got = _clean(value)
    if got:
        return got
    # 3：指令里取，但排除将来时态（「夜晚快到了」→ 不算已入夜）。
    #    判定：时间词后紧邻将来时标记（快到了/快要/即将/将到…），或指令整体是
    #    「时间词+到了」的预告句，则该时间词是预告而非当前，不采用。
    d = directive or ""
    if _is_future_time(d):
        return fallback
    got = _clean(d)
    if got:
        return got
    return fallback


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
