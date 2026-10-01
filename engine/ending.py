"""结局判定：软指引，非强制。

每轮推演结束后由 app.act 调用 evaluate(snap)，命中终局条件则向客户端回传
ending_candidate，由用户决定是否终结会话（见 ENDING_TRIGGERS）。判定只依赖快照里
已有的通用字段，导入任意剧本都能用，无需作者额外标注（剧本自定义标记属可选增强）。

设计要点：
- 软指引：引擎只"提议"，用户拍板；绝不强制中断叙事。
- 抑制重复：用户点"继续探索"后写入 ending_dismissed_reasons，evaluate 在
  未出现"新条件"前不再弹出，避免刷屏。
- Tier A（本次实现）：present 空 / 秘密全曝光 / 剧本自定义 ending 标记。
"""

# 触发条件 -> 面向用户的文案（中文，无 emoji）
ENDING_TRIGGERS = {
    "all_left": "在场角色全部离场，场景已无人。",
    "secrets_resolved": "所有潜伏秘密均已曝光，再无隐藏。",
    # 可选增强：剧本作者在世界书/元数据里置 ending_flag 时命中（snapshot 提供）
    "script_flag": "剧本标记的结局条件已达成。",
}

# 终止态严重度：用于前端展示与排序（high 会优先提示）
SEVERITY = {
    "all_left": "high",
    "secrets_resolved": "medium",
    "script_flag": "medium",
}


def _present_names(snap):
    """把 present 规范成名字列表（它可能是 list 或 dict）。"""
    present = snap.get("present") or []
    if isinstance(present, dict):
        return list(present.keys())
    return list(present)


def evaluate(snap, dismissed=None):
    """返回 ending_candidate dict 或 None。

    reasons:     命中的触发条件（ENDING_TRIGGERS 的键）
    new_reasons: 相对 dismissed 新出现的触发条件（为空则被抑制，返回 None）
    仅在出现 new_reasons 时返回非 None，从而抑制已驳回的重复提示。
    """
    dismissed = dismissed or []
    reasons = []

    # 终局态 1：全员离场
    if not _present_names(snap):
        reasons.append("all_left")

    # 终局态 2：所有潜伏秘密均曝光（state 非"潜伏"即视为已暴露，兼容"暴露"/"全曝光"）
    secrets = snap.get("secrets") or []
    if secrets and all(s.get("state") != "潜伏" for s in secrets):
        reasons.append("secrets_resolved")

    # 终局态 3（可选增强）：剧本作者显式标注的结局标记
    if snap.get("ending_flag"):
        reasons.append("script_flag")

    if not reasons:
        return None

    new_reasons = [r for r in reasons if r not in dismissed]
    if not new_reasons:
        return None  # 已驳回且未出现新条件，抑制提示

    severity = "high" if any(SEVERITY.get(r) == "high" for r in reasons) else "medium"
    return {
        "reasons": reasons,
        "new_reasons": new_reasons,
        "labels": [ENDING_TRIGGERS[r] for r in reasons],
        "severity": severity,
        "round": (snap.get("scene") or {}).get("round", 0),
    }


def mark_dismissed(snap, reasons):
    """用户点"继续探索"时调用：把当前命中的条件记入库，后续除非出现新条件不再弹。"""
    snap["ending_dismissed_reasons"] = list(reasons or [])
    return snap
