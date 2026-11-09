"""结局判定：软指引，非强制。

每轮推演结束后由 app.act 调用 evaluate(snap)，命中终局条件则向客户端回传
ending_candidate，由用户决定是否终结会话（见 ENDING_TRIGGERS）。判定只依赖快照里
已有的通用字段。

设计要点：
- 软指引：引擎只"提议"，用户拍板；绝不强制中断叙事。
- 抑制重复：用户点"继续探索"后写入 ending_dismissed_reasons，evaluate 在
  未出现"新条件"前不再弹出，避免刷屏。

条件口径（2026-11-08 引擎瘦身）：只留「所有秘密均已揭开」一条。
- 「在场角色全部离场」已删：v2.1.0 起 present 是建局名册、永不收缩（见 scene.py
  模块注释），该条件永远不可能命中，属死分支。
- 「剧本标记 ending_flag」已删：全仓无写入方，同样是死分支。作者若要自定义终局，
  直接结束会话生成总结即可。
"""

# 触发条件 -> 面向用户的文案（中文，无 emoji）
ENDING_TRIGGERS = {
    "secrets_resolved": "所有秘密均已揭开（暴露或公开），再无隐藏。",
}


def evaluate(snap, dismissed=None):
    """返回 ending_candidate dict 或 None。

    reasons:     命中的触发条件（ENDING_TRIGGERS 的键）
    new_reasons: 相对 dismissed 新出现的触发条件（为空则被抑制，返回 None）
    仅在出现 new_reasons 时返回非 None，从而抑制已驳回的重复提示。
    """
    dismissed = dismissed or []
    reasons = []

    # 所有秘密均已揭开（v0.26.0 四态：只有「暴露/已公开」算揭开；
    # 「潜伏/起疑」仍是隐藏态，不得触发终局——起疑只是逼近，秘密尚未坐实）。
    # 兼容历史字面量「全曝光」。
    _RESOLVED_STATES = ("暴露", "已公开", "全曝光")
    secrets = snap.get("secrets") or []
    if secrets and all(s.get("state") in _RESOLVED_STATES for s in secrets):
        reasons.append("secrets_resolved")

    if not reasons:
        return None

    new_reasons = [r for r in reasons if r not in dismissed]
    if not new_reasons:
        return None  # 已驳回且未出现新条件，抑制提示

    return {
        "reasons": reasons,
        "new_reasons": new_reasons,
        "labels": [ENDING_TRIGGERS[r] for r in reasons],
        "severity": "medium",
        "round": (snap.get("scene") or {}).get("round", 0),
    }


def mark_dismissed(snap, reasons):
    """用户点"继续探索"时调用：把当前命中的条件记入库，后续除非出现新条件不再弹。"""
    snap["ending_dismissed_reasons"] = list(reasons or [])
    return snap
