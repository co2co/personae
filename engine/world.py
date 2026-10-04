"""世界书：关键词命中才把设定塞进提示词。

世界书（Lorebook）核心机制：
    - constant：常量条目，不依赖关键词，每轮必注入（解决长文基础规则掉线）
    - depth：条目级扫描深度，只回看最近 N 条聊天匹配（默认取全局 default_depth）
    - position：插入位置 before（系统层）/ after（对话历史之后、导演指令之前）
    - 引用展开：条目 content 内用 #条目名# 引用其他条目，命中后自动把被引条目拉入
      （BFS 展开 + visited 防环）。条目用可选 name 字段命名，供 #name# 引用。

条目格式（data/worlds/*.json）：
    {"name": "可选命名（供 #name# 引用）",
     "keys": ["魔法学院", "学院"], "content": "...详见 #魔法学院#...", "priority": 100,
     "enabled": true, "constant": false, "position": "before", "depth": null}
所有新字段均向后兼容：老条目不写则回退默认，行为不变。
"""

import re


def _hit_keys(e, window):
    """条目 e 是否在窗口 window（文本片段列表）中命中任一 key。"""
    keys = [k.lower() for k in e.get("keys", [])]
    if not keys:
        return False
    return any(any(k in seg.lower() for k in keys) for seg in window)


# 递归引用：条目 content 里 #条目名# 会把同名条目拉入
_NAME_REF = re.compile(r"#([^#\n]+)#")


def _resolve_recursive(entries, matched, character):
    """把 matched 中条目 content 的 #name# 引用展开：引用的同名条目（enabled、通过 character
    过滤）被拉入。BFS + visited（对象 id）防环，避免互相引用死循环。

    matched 直接被原地扩展；返回扩展后的列表（调用方负责排序与截断）。
    """
    by_name = {e["name"]: e for e in entries if e.get("name")}
    if not by_name:
        return matched
    seen = {id(e) for e in matched}
    queue = list(matched)
    while queue:
        cur = queue.pop(0)
        for ref in _NAME_REF.findall(cur.get("content", "")):
            tgt = by_name.get(ref.strip())
            if not tgt or id(tgt) in seen:
                continue
            if not tgt.get("enabled", True):
                continue
            if character is not None and tgt.get("character") and tgt["character"] != character:
                continue
            seen.add(id(tgt))
            matched.append(tgt)
            queue.append(tgt)
    return matched


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
    # 递归扫描：命中条目 content 里的 #name# 引用会拉入被引条目（BFS 防环）
    matched = _resolve_recursive(entries, matched, character)
    matched.sort(key=lambda e: -e.get("priority", 100))
    return matched[:max_entries]


def render(hits):
    """把命中条目拼成一段文本。"""
    if not hits:
        return ""
    blocks = ["[世界设定]"]
    blocks.extend(f"- {e['content']}" for e in hits)
    return "\n".join(blocks)
