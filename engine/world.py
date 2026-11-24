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


def _find_unreachable(entries):
    """找出「已启用、非恒定、非示范、非秘密、空 keys、且未被任何启用条目 #name# 引用」的条目。

    这类条目在运行期永远不会命中，但不会报错（静默失效），供预览面板显式提醒使用者。
    """
    referenced = set()
    for e in entries:
        if not e.get("enabled", True):
            continue
        for ref in _NAME_REF.findall(e.get("content", "") or ""):
            referenced.add(ref.strip())
    out = []
    for e in entries:
        if not e.get("enabled", True):
            continue
        if e.get("constant") or e.get("demo") or e.get("secret"):
            continue
        keys = [k for k in (e.get("keys") or []) if str(k).strip()]
        if keys:
            continue
        nm = (e.get("name") or "").strip()
        if nm and nm in referenced:
            continue
        out.append(e)
    return out


def scan_detail(entries, history, directive="", default_depth=4, character=None, max_entries=8,
                include_secret=True, round=0):
    """返回完整扫描明细：hits（命中）、dropped（被配额整条截断）、unreachable（永不命中）、stats（字数统计）。

    与 scan() 同源：scan() 直接取本函数的 hits，保证预览面板与实际注入逐条一致。
    """
    history = list(history or [])
    matched = []
    secret_matched = []
    demo_out = []  # 写法示范条目（demo）：独立于世界设定，供示范注入通道
    for e in entries:
        if not e.get("enabled", True):
            continue
        if character is not None and e.get("character") and e["character"] != character:
            continue
        if e.get("demo"):
            # 写法示范：first_round 仅首轮注入；否则持续注入（常驻示范）。
            # 示范不进[世界设定]，由调用方单独提取，故这里不 append 到 matched。
            if e.get("first_round") and round > 1:
                continue
            demo_out.append(e)
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
    kw_all = [e for e in matched if not e.get("constant")]
    kw_out = kw_all[:max_entries]
    kw_dropped = kw_all[max_entries:]
    out = const_out + kw_out
    if include_secret:
        # 预览模式：秘密一并返回（命中到的在前，被引用到的在后），但仍不挤掉设定。
        out = out + secret_matched + ref_secret
    # 写法示范条目（demo）恒附加在末尾：它们不占 max_entries 配额、不混入[世界设定]，
    # 由调用方按 demo 字段拆出走示范注入通道。first_round 的轮次过滤已在上面循环处理。
    if demo_out:
        out = out + demo_out

    const_chars = sum(len(e.get("content") or "") for e in const_out)
    dynamic_chars = sum(len(e.get("content") or "") for e in kw_out)
    return {
        "hits": out,
        "dropped": kw_dropped,
        "unreachable": _find_unreachable(entries),
        "stats": {
            "const_chars": const_chars,
            "dynamic_chars": dynamic_chars,
            "total_chars": const_chars + dynamic_chars,
            "max_entries": max_entries,
            "const_count": len(const_out),
            "dynamic_count": len(kw_out),
            "dropped_count": len(kw_dropped),
        },
    }


def scan(entries, history, directive="", default_depth=4, character=None, max_entries=8,
         include_secret=True, round=0):
    """返回命中条目，按 priority 从高到低，最多 max_entries 条（详见 scan_detail）。"""
    return scan_detail(entries, history, directive=directive, default_depth=default_depth,
                       character=character, max_entries=max_entries,
                       include_secret=include_secret, round=round)["hits"]


def render(hits):
    """把命中条目拼成一段文本。"""
    if not hits:
        return ""
    blocks = ["[世界设定]"]
    blocks.extend(f"- {e['content']}" for e in hits)
    return "\n".join(blocks)
