"""世界书：关键词命中才把设定塞进提示词。

SillyTavern 原版有 secondary_keys、position、depth、递归扫描、定时条目等一整套，
精简版只保留最有效的一条：主关键词命中 -> 按优先级取前 N 条 -> 注入。

条目格式（data/worlds/*.json）：
    {"keys": ["魔法学院", "学院"], "content": "...", "priority": 100, "enabled": true}
"""


def scan(entries, text, max_entries=8, character=None):
    """返回命中条目，按 priority 从高到低。text 通常是最近几条聊天 + 当前输入。

    character 用于过滤带 character 字段的条目：跟 A 聊天时不该剧透 B 的秘密。
    character 为 None 表示不过滤（沙盘多角色模式 / 编辑预览均用此值）。
    """
    lowered = text.lower()
    hits = [
        e for e in entries
        if e.get("enabled", True)
        and (character is None or not e.get("character") or e["character"] == character)
        and any(k.lower() in lowered for k in e.get("keys", []))
    ]
    hits.sort(key=lambda e: -e.get("priority", 100))
    return hits[:max_entries]


def render(hits):
    """把命中条目拼成一段文本。"""
    if not hits:
        return ""
    blocks = ["[世界设定]"]
    blocks.extend(f"- {e['content']}" for e in hits)
    return "\n".join(blocks)
