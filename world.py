"""世界书：关键词命中才把设定塞进提示词。

SillyTavern 原版有 secondary_keys、position、depth、递归扫描、定时条目等一整套，
精简版复刻最核心的三件套（递归扫描留二期）：
    - constant：常量条目，不依赖关键词，每轮必注入（解决长文基础规则掉线）
    - depth：条目级扫描深度，只回看最近 N 条聊天匹配（默认取全局 default_depth）
    - position：插入位置 before（系统层）/ after（对话历史之后、导演指令之前）

条目格式（data/worlds/*.json）：
    {"keys": ["魔法学院", "学院"], "content": "...", "priority": 100, "enabled": true,
     "constant": false, "position": "before", "depth": null}
所有新字段均向后兼容：老条目不写则回退默认，行为不变。
"""


def _hit_keys(e, window):
    """条目 e 是否在窗口 window（文本片段列表）中命中任一 key。"""
    keys = [k.lower() for k in e.get("keys", [])]
    if not keys:
        return False
    return any(any(k in seg.lower() for k in keys) for seg in window)


def scan(entries, history, directive="", default_depth=4, character=None, max_entries=8):
    """返回命中条目，按 priority 从高到低，最多 max_entries 条。

    history: 聊天记录文本列表（调用方通常传最近若干条）。
    directive: 环境推手本轮扰动指令（也参与关键词匹配）。
    default_depth: 条目未指定 depth 时回看的最近聊天条数。
    character: 过滤带 character 字段的条目（与在场角色无关的世界书不剧透）；
               None 表示不过滤（沙盘多角色模式 / 编辑预览均用此值）。

    秘密条目（secret）不在此处剔除——由调用方从命中中筛掉，秘密走角色块提示。
    """
    history = list(history or [])
    matched = []
    for e in entries:
        if not e.get("enabled", True):
            continue
        if character is not None and e.get("character") and e["character"] != character:
            continue
        if e.get("constant"):
            # 常量条目：无条件纳入，不受关键词与 depth 限制
            matched.append(e)
            continue
        d = e.get("depth") or default_depth
        try:
            d = max(1, int(d))
        except (TypeError, ValueError):
            d = default_depth
        window = (history[-d:] if d < len(history) else history) + ([directive] if directive else [])
        if _hit_keys(e, window):
            matched.append(e)
    matched.sort(key=lambda e: -e.get("priority", 100))
    return matched[:max_entries]


def render(hits):
    """把命中条目拼成一段文本。"""
    if not hits:
        return ""
    blocks = ["[世界设定]"]
    blocks.extend(f"- {e['content']}" for e in hits)
    return "\n".join(blocks)
