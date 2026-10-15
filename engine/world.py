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

    返回 (引用拉入的非秘密条目, 引用拉入的秘密条目)：
    - 被引的秘密条目单独返回，不进主列表——秘密不注入 prompt（见 scan 的 include_secret）。
    - 非秘密的被引条目**排到主列表末尾之后**：被引用者是依赖项，优先级由引用方决定，
      不应凭自身 priority 挤掉引用方的其他命中。
    matched 直接被原地扩展；调用方负责排序与截断。
    """
    by_name = {e["name"]: e for e in entries if e.get("name")}
    if not by_name:
        return matched, []
    seen = {id(e) for e in matched}
    queue = list(matched)
    ref_plain, ref_secret = [], []
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
            (ref_secret if tgt.get("secret") else ref_plain).append(tgt)
            queue.append(tgt)
    # 被引条目排在 matched 之后（matched 已按 priority 排序），保持「引用方优先」次序
    return matched + ref_plain, ref_secret


def scan(entries, history, directive="", default_depth=4, character=None, max_entries=8,
         include_secret=True):
    """返回命中条目，按 priority 从高到低，最多 max_entries 条。

    history: 聊天记录文本列表（调用方通常传最近若干条）。
    directive: 环境推手本轮扰动指令（也参与关键词匹配）。
    default_depth: 条目未指定 depth 时回看的最近聊天条数。
    character: 过滤带 character 字段的条目（与在场角色无关的世界书不剧透）；
               None 表示不过滤（沙盘多角色模式 / 编辑预览均用此值）。

    include_secret: 秘密条目（secret）是否参与 max_entries 配额。秘密**不进 prompt**，
    调用方（app.py）会在 scan 之后把秘密剔除，所以它们默认**不占配额**——否则秘密挤掉
    真正要注入的设定（实测 8 条里秘密占 3，把「逼近的尸潮」静默挤掉）。
    命中预览（编辑器）需要看到秘密，故传 True。
    """
    history = list(history or [])
    matched = []
    secret_matched = []
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
            (secret_matched if e.get("secret") else matched).append(e)
    matched.sort(key=lambda e: -e.get("priority", 100))
    # 递归扫描：命中条目 content 里的 #name# 引用会拉入被引条目（BFS 防环）
    # 被引的非秘密条目排到命中条目之后，秘密被引条目单独返回（不占注入配额）。
    matched, ref_secret = _resolve_recursive(entries, matched, character)
    # 常量条目「无条件纳入」，不受 max_entries 上限约束；上限只作用于关键词命中的非常量条目。
    # （此前把常量与关键词命中混在一个 matched 里再截断，常量条目偏多时会把低优先级常量挤掉。）
    const_out = [e for e in matched if e.get("constant")]
    kw_out = [e for e in matched if not e.get("constant")][:max_entries]
    out = const_out + kw_out
    if include_secret:
        # 预览模式：秘密一并返回（命中到的在前，被引用到的在后），但仍不挤掉设定。
        out = out + secret_matched + ref_secret
    return out


def render(hits):
    """把命中条目拼成一段文本。"""
    if not hits:
        return ""
    blocks = ["[世界设定]"]
    blocks.extend(f"- {e['content']}" for e in hits)
    return "\n".join(blocks)
