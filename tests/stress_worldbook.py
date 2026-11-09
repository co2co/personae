"""世界书专项压测（确定性，不调 LLM，独立运行）。

目的：在 60 轮长上下文下，用引擎真实代码路径检验非常量世界书条目的 3 个参数
是否严格生效：
  1. depth   —— 关键词命中后，条目是否恰好在「最近 depth 条聊天」窗口内触发、超窗即落；
               并验证 depth 重新提及会重新武装（re-arm）；
  2. before  —— 命中后是否固定落在系统层首条消息（messages[0]），且不在生成点前的
               当前环境块；
  3. after   —— 命中后是否落在生成点前最后一瞥（末尾 user 消息的「【世界设定·当前环境】」块），
               且在「【导演指令】」之后（recency 最强）。

方法：直接调用引擎真实路径
  - world.scan(entries, history[-WORLDBOOK_SCAN_WINDOW:], directive, default_depth=RECENT_FOR_SCAN)
    （与 app.py:470-473 完全一致）
  - prompter.build_session(..., history=history, after_hits=after_hits)
    （与 app.py:489-495 完全一致）
每轮用 depth 公式**独立推导**期望触发集合，与引擎实际命中比对，自动捕捉回归。
零 LLM 调用、零网络、不依赖已删除的 DEMO 剧本。

用法：
  python tests/stress_worldbook.py --rounds 60
产物：tests/runs/<时间戳>_世界书压测.md（报告）+ 同名 .json（明细）
"""

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE = HERE.parent / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

import world as world_mod
import prompter as prompter_mod

# 用引擎真实常量（与 app.py 一致）；导入失败时回落到已知值并打印提示。
try:
    import app as _app
    WORLDBOOK_SCAN_WINDOW = _app.WORLDBOOK_SCAN_WINDOW
    RECENT_FOR_SCAN = _app.RECENT_FOR_SCAN
except Exception as _e:  # pragma: no cover
    WORLDBOOK_SCAN_WINDOW = 60
    RECENT_FOR_SCAN = 4
    print(f"  （未能从 app 导入常量，回落到 60/4：{_e}）")

TITLE = "世界书专项压测（before/after/depth）"

# ---- 待测世界书：5 条非常量条目，覆盖 before/after × 不同 depth ----
ENTRIES = [
    {"name": "地铁口通道", "keys": ["地铁口"], "content": "附近有地铁口，是潜在的撤离通道",
     "priority": 100, "enabled": True, "constant": False, "position": "before", "depth": 4},
    {"name": "东南营地", "keys": ["营地"], "content": "城东南方向有处幸存者营地",
     "priority": 90, "enabled": True, "constant": False, "position": "after", "depth": 4},
    {"name": "下水道系统", "keys": ["下水道"], "content": "这栋楼的下水道系统四通八达",
     "priority": 85, "enabled": True, "constant": False, "position": "after", "depth": 8},
    {"name": "通风管道", "keys": ["通风口"], "content": "楼内通风管道彼此连通",
     "priority": 80, "enabled": True, "constant": False, "position": "before", "depth": 15},
    {"name": "楼顶天台", "keys": ["天台"], "content": "楼顶天台视野开阔，便于警戒",
     "priority": 75, "enabled": True, "constant": False, "position": "after", "depth": 2},
]
NAME_OF = {id(e): e["name"] for e in ENTRIES}


def _keyword_schedule():
    """轮次 -> 该轮 directive 注入的关键词（用于验证 depth 触发窗口与 re-arm）。

    设计要点：
    - 地铁口（before,d4）放在 R6 与 R50，验证「冷却后重新提及能重新武装」。
    - 通风口（before,d15）放在 R42，窗口覆盖至约 R48。
    - 营地（after,d4）放在 R44，刻意落入通风口窗口内 → R44~R48 同时有 before+after 命中，
      用以在同轮对比两种位置的落点差异。
    - 下水道（after,d8）放在 R30 与 R56，验证长窗口与 re-arm。
    - 天台（after,d2）放在 R54，验证极浅窗口仅 2 轮。
    """
    return {6: "地铁口", 30: "下水道", 42: "通风口", 44: "营地",
            50: "地铁口", 54: "天台", 56: "下水道"}


# 中性填充台词（绝不出现 5 个关键词，避免误命中）
_FILLER_USER = [
    "众人清点完物资，重新分配了守夜班次。",
    "有人提议先别急着移动，天黑路上太危险。",
    "小队里发生了争执，有人想分头行动。",
    "大家把能堵的门窗都用家具顶死。",
    "有人去翻了楼下的便利店，带回几罐罐头。",
    "夜里轮流守着楼梯口，谁都不敢睡死。",
    "有人提议明天天亮再想办法离开这栋楼。",
    "几个人围在一起低声商量下一步去哪。",
    "有人把伤口简单包扎了一下，脸色不太好。",
    "众人压低声音，怕惊动外面的东西。",
    "有人在水箱边接了点水，省着喝。",
    "小队决定先派人上楼看看情况。",
    "有人翻出一张城市地图，摊在地上研究。",
    "夜里风很大，窗户被吹得咯吱响。",
    "有人守在窗边，盯着街面的一举一动。",
    "大家分吃了最后一点干粮，气氛很沉。",
    "有人提议去别处找更安全的落脚点。",
    "几个人把楼梯间的杂物清了清，腾出退路。",
    "有人低声说听到远处有引擎声，又像是错觉。",
    "众人商量着要不要趁着夜色摸黑转移。",
    "有人把随身的东西重新打包，减轻负担。",
    "小队里有人开始发烧，被安排在里屋休息。",
    "有人守着门口，手里攥着临时做的长矛。",
    "大家轮流去窗口换气，每次只开一条缝。",
    "有人清点弹药，发现所剩无几。",
    "夜里有人做了噩梦，惊醒了旁边的人。",
    "众人决定天亮前保持静默，互不走动。",
    "有人在地上用粉笔画出据点的草图。",
    "小队里有人提议派人出去探一探外围。",
    "大家把值钱又轻便的东西集中到一处。",
    "有人守在门口，耳朵贴着门板听外面的动静。",
    "夜里有人悄悄起身，被同伴低声拦下。",
    "众人重新检查了一遍逃生路线是否通畅。",
    "有人把窗户的破洞用纸板临时糊上。",
    "小队决定派两个人出去侦察，天亮就出发。",
    "有人在小本子上记下每人负责的岗位。",
    "夜里外面的骚动渐渐平息，众人才松口气。",
    "有人把仅剩的药品按人头分成了小份。",
    "大家挤在相对安全的里间，彼此靠着取暖。",
    "有人提议在楼道设一个简易的报警机关。",
    "小队重新确认了各自的分工，避免再起摩擦。",
    "有人盯着黑漆漆的走廊，迟迟不敢闭眼。",
    "众人把能用的工具都集中到门口备用。",
    "有人低声提醒，天亮前千万别出声。",
    "小队里有人开始盘算离开后的汇合点。",
    "夜里有人听见楼上有脚步声，瞬间屏住呼吸。",
    "大家把手电调到最暗，只照脚下的路。",
    "有人把门口的脚印擦掉，怕留下痕迹。",
    "众人商量着如果被发现，就往哪个方向撤。",
    "有人守在窗边，数着外面游荡的身影。",
    "小队决定天亮后先派侦察组摸一圈外围。",
    "有人把干粮省下来，留给生病的人。",
    "夜里风停了，楼里静得能听见心跳。",
    "众人重新加固了临时路障，确保推不动。",
    "有人在小声教同伴怎么屏息装死。",
    "小队里有人提议往更偏僻的巷子绕行。",
]
_FILLER_REPLY = [
    "（众人默默点头，照着分工各自就位。）",
    "（空气里只剩压抑的呼吸声。）",
    "（几人交换了个眼神，没再多说。）",
    "（有人把工具往手心里攥了攥。）",
    "（大家压低声音，继续手上的事。）",
    "（短暂的沉默后，又有人轻轻应了一声。）",
]


# 关键词注入台词模板：把关键词自然嵌进一句话
_INJECT_TEMPLATES = {
    "地铁口": "有人望着街对面，低声问：这附近的地铁口还能走吗，会不会被堵死？",
    "营地": "有人压低声音说，听说城东南方向好像有个幸存者营地，要不要去碰碰运气？",
    "下水道": "有人掀开地漏，嘀咕这栋楼的下水道系统四通八达，总比走地面安全。",
    "通风口": "有人敲了敲墙，发现楼内的通风口彼此连通，说不定能通到别处。",
    "天台": "有人爬上去看了一眼，说楼顶天台视野开阔，放在这儿警戒再合适不过。",
}


def build_directives(rounds, schedule):
    out = []
    fi = 0
    for r in range(1, rounds + 1):
        kw = schedule.get(r)
        if kw:
            out.append(_INJECT_TEMPLATES[kw])
        else:
            out.append(_FILLER_USER[fi % len(_FILLER_USER)])
            fi += 1
    return out


def expected_hit(entry, history_strings, directive, default_depth):
    """用 depth 公式独立推导：条目在本轮是否应当命中（与引擎实现解耦）。"""
    if entry.get("constant"):
        return True
    d = entry.get("depth") or default_depth
    try:
        d = max(1, int(d))
    except (TypeError, ValueError):
        d = default_depth
    win = (history_strings[-d:] if d < len(history_strings) else history_strings) \
        + ([directive] if directive else [])
    keys = [k.lower() for k in entry.get("keys", [])]
    return any(any(k in s.lower() for k in keys) for s in win)


def run(rounds):
    schedule = _keyword_schedule()
    directives = build_directives(rounds, schedule)
    history_msgs = []          # [{role, content}] 累积的真实对话（user+assistant 交错）
    records = []

    for r in range(1, rounds + 1):
        directive = directives[r - 1]
        # 与 app.py 一致：扫描用「历史内容（截断至扫描窗口）+ 本轮 directive」
        history_strings = [m["content"] for m in history_msgs][-WORLDBOOK_SCAN_WINDOW:]
        matched = world_mod.scan(ENTRIES, history_strings, directive,
                                 default_depth=RECENT_FOR_SCAN, character=None)
        before_hits = [e for e in matched if e.get("position", "before") == "before"]
        after_hits = [e for e in matched if e.get("position", "before") == "after"]

        snap = {"present": [], "scene": {"place": "某处", "time": "夜晚", "round": r},
                "relations": {}, "ledger": [], "facts": [], "states": {}, "secrets": []}
        messages = prompter_mod.build_session(
            {}, directive, before_hits, snap,
            history=history_msgs, after_hits=after_hits,
            active_consequences=[])

        sys_content = messages[0]["content"]
        # 末尾 user 消息：after 命中与导演指令合并进同一条末尾 user 消息（指令在前、
        # 【世界设定·当前环境】块在后），即生成点前的最后一瞥。
        last_user = messages[-1]
        last_user_content = last_user["content"]
        last_role = last_user.get("role")
        # env 块在末尾消息内的位置（与导演指令合并时用于验证近因顺序）
        env_pos = last_user_content.find("【世界设定·当前环境】")
        dir_pos = last_user_content.find("【导演指令】")

        # 逐条目核验
        per_entry = []
        for e in ENTRIES:
            name = e["name"]
            pos = e["position"]
            exp = expected_hit(e, history_strings, directive, RECENT_FOR_SCAN)
            actual = e in matched
            depth_ok = (exp == actual)
            # 位置核验（仅在命中时检查落点）
            pos_ok = True
            if actual:
                if pos == "before":
                    in_sys = e["content"] in sys_content
                    in_last = e["content"] in last_user_content
                    pos_ok = in_sys and not in_last
                else:  # after
                    in_last = e["content"] in last_user_content
                    # after 段与导演指令合并在末尾 user 消息：env 块须紧跟在指令之后
                    # （同一消息内、近因最强），而非被埋进系统块。
                    recency_ok = (env_pos >= 0 and (dir_pos < 0 or env_pos > dir_pos))
                    pos_ok = in_last and recency_ok
            per_entry.append({
                "name": name, "position": pos, "depth": e.get("depth"),
                "expected": exp, "actual": actual,
                "depth_ok": depth_ok, "pos_ok": pos_ok,
            })

        rec = {
            "round": r, "directive": directive,
            "triggered": [NAME_OF[id(e)] for e in matched],
            "before": [NAME_OF[id(e)] for e in before_hits],
            "after": [NAME_OF[id(e)] for e in after_hits],
            "n_messages": len(messages),
            "env_block_present": (last_role == "user" and env_pos >= 0),
            "env_after_directive": (
                last_role == "user" and env_pos >= 0
                and (dir_pos < 0 or env_pos > dir_pos)),
            "per_entry": per_entry,
        }
        records.append(rec)

        # 追加本轮对话到历史（user + assistant），与引擎 load_chat 格式一致
        reply = _FILLER_REPLY[(r - 1) % len(_FILLER_REPLY)]
        history_msgs.append({"role": "user", "content": directive})
        history_msgs.append({"role": "assistant", "content": reply})

    return records


def analyze(records):
    n = len(records)
    # 逐条目：实际触发轮、期望触发轮、depth 一致率、位置正确率
    by_entry = {}
    for e in ENTRIES:
        name = e["name"]
        actual_rounds, expected_rounds, depth_mismatch, pos_mismatch = [], [], [], []
        for rec in records:
            pe = next(x for x in rec["per_entry"] if x["name"] == name)
            if pe["actual"]:
                actual_rounds.append(rec["round"])
            if pe["expected"]:
                expected_rounds.append(rec["round"])
            if not pe["depth_ok"]:
                depth_mismatch.append(rec["round"])
            if pe["actual"] and not pe["pos_ok"]:
                pos_mismatch.append(rec["round"])
        by_entry[name] = {
            "position": e["position"], "depth": e.get("depth"),
            "actual_rounds": actual_rounds, "expected_rounds": expected_rounds,
            "depth_match": len(depth_mismatch) == 0,
            "depth_mismatch_rounds": depth_mismatch,
            "pos_match": len(pos_mismatch) == 0,
            "pos_mismatch_rounds": pos_mismatch,
        }

    depth_all_ok = all(v["depth_match"] for v in by_entry.values())
    pos_all_ok = all(v["pos_match"] for v in by_entry.values())

    # 同轮 before+after 共存轮（位置对比有效性）
    co_occur = [rec["round"] for rec in records
                if rec["before"] and rec["after"]]

    # depth 窗口封顶校验（合成）：depth=100 在 60 条历史内命中、超出 60 条不命中
    cap_detail = _verify_cap()

    return {
        "轮数": n,
        "条目数": len(ENTRIES),
        "depth 全部轮次一致": depth_all_ok,
        "position 全部轮次正确": pos_all_ok,
        "before+after 同轮共存轮数": len(co_occur),
        "before+after 同轮共存轮次": co_occur,
        "depth 窗口封顶(60)校验": cap_detail,
        "逐条目": by_entry,
    }


def _verify_cap():
    """验证 WORLDBOOK_SCAN_WINDOW=60 的硬封顶：depth>60 等同 60。

    注意：封顶是在 app.py 调用 scan 之前把历史截断到 [-WORLDBOOK_SCAN_WINDOW:]
    完成的，world.scan 内部不做截断。故此处须模拟 app.py：先截断再扫。
    """
    e100 = {"keys": ["X锚点"], "content": "X", "depth": 100, "constant": False,
            "position": "before", "enabled": True}
    # 60 条历史：关键词在第 1 条（最老），截断后仍在窗内
    hist60 = ["X锚点"] + [f"fill{i}" for i in range(59)]
    hit60 = world_mod.scan([e100], hist60[-WORLDBOOK_SCAN_WINDOW:],
                           "", default_depth=4, character=None)
    # 70 条历史：关键词在第 1 条（距末尾 69，超出 60 窗），截断后落在窗外
    hist70 = ["X锚点"] + [f"fill{i}" for i in range(69)]
    hit70 = world_mod.scan([e100], hist70[-WORLDBOOK_SCAN_WINDOW:],
                           "", default_depth=4, character=None)
    return {
        "WORLDBOOK_SCAN_WINDOW": WORLDBOOK_SCAN_WINDOW,
        "depth100_在60条历史命中": len(hit60) == 1,
        "depth100_在70条历史不命中(超窗)": len(hit70) == 0,
        "结论": "depth>60 被 60 硬封顶" if (len(hit60) == 1 and len(hit70) == 0) else "异常",
    }


def build_report(meta, records, summary, anomalies):
    out = [f"# {meta['title']}报告", "",
           f"- 时间：{meta['time']}",
           f"- 轮数：{meta['rounds']}",
           f"- 方法：确定性模拟，调用真实 `world.scan` + `prompter.build_session`"
           f"（与 app.py 一致），不调 LLM",
           f"- 扫描窗口常量：`WORLDBOOK_SCAN_WINDOW={WORLDBOOK_SCAN_WINDOW}`，"
           f"`RECENT_FOR_SCAN(默认depth)={RECENT_FOR_SCAN}`", ""]

    out.append("## 汇总")
    out.append("")
    out.append(f"- **depth 全部轮次一致**：{summary['depth 全部轮次一致']}")
    out.append(f"- **position 全部轮次正确**：{summary['position 全部轮次正确']}")
    out.append(f"- **before+after 同轮共存轮数**：{summary['before+after 同轮共存轮数']}"
               f"（轮次 {summary['before+after 同轮共存轮次']}）")
    cap = summary["depth 窗口封顶(60)校验"]
    out.append(f"- **depth 窗口封顶校验**：{cap['结论']}"
               f"（WORLDBOOK_SCAN_WINDOW={cap['WORLDBOOK_SCAN_WINDOW']}，"
               f"depth100 在60条命中={cap['depth100_在60条历史命中']}，"
               f"在70条不命中={cap['depth100_在70条历史不命中(超窗)']}）")
    out.append("")

    out.append("## 逐条目：depth 触发区间与 position 落点")
    out.append("")
    out.append("| 条目 | 位置 | depth | 实际触发轮 | 期望触发轮 | depth一致 | 位置正确 |")
    out.append("|---|---|---|---|---|---|---|")
    for name, v in summary["逐条目"].items():
        ar = ",".join(map(str, v["actual_rounds"])) or "（无）"
        er = ",".join(map(str, v["expected_rounds"])) or "（无）"
        out.append(f"| {name} | {v['position']} | {v['depth']} | {ar} | {er} "
                   f"| {'✓' if v['depth_match'] else '✗(' + ','.join(map(str, v['depth_mismatch_rounds'])) + ')'} "
                   f"| {'✓' if v['pos_match'] else '✗(' + ','.join(map(str, v['pos_mismatch_rounds'])) + ')'} |")
    out.append("")

    out.append("## 逐轮明细（触发条目 / 落点）")
    out.append("")
    out.append("| 轮 | 触发条目 | before | after | 末尾含环境块 | 环境块在指令后 |")
    out.append("|---|---|---|---|---|---|")
    for rec in records:
        trig = "、".join(rec["triggered"]) or "—"
        out.append(f"| {rec['round']} | {trig} | "
                   f"{'、'.join(rec['before']) or '—'} | {'、'.join(rec['after']) or '—'} | "
                   f"{'是' if rec['env_block_present'] else '否'} | "
                   f"{'是' if rec['env_after_directive'] else '否'} |")
    out.append("")

    if anomalies:
        out.append("## 异常明细")
        out.append("")
        for a in anomalies:
            out.append(f"- {a}")
        out.append("")

    out.append("---")
    out.append("")
    out.append("_由 tests/stress_worldbook.py 生成。_")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=60)
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()

    records = run(args.rounds)
    summary = analyze(records)

    # 收集异常
    anomalies = []
    for name, v in summary["逐条目"].items():
        if not v["depth_match"]:
            anomalies.append(f"[{name}] depth 不一致轮次：{v['depth_mismatch_rounds']}")
        if not v["pos_match"]:
            anomalies.append(f"[{name}] position 落点错误轮次：{v['pos_mismatch_rounds']}")
    cap = summary["depth 窗口封顶(60)校验"]
    if cap["结论"] != "depth>60 被 60 硬封顶":
        anomalies.append(f"[depth封顶] 校验异常：{cap}")

    meta = {"title": TITLE, "rounds": len(records),
            "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    runs_dir = Path(args.out_dir) if args.out_dir else (HERE / "runs")
    runs_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    # 文件名安全化：Windows 不允许 / \ : * ? " < > |，统一替换为 _
    safe_title = re.sub(r'[\\/:*?"<>|]', "_", TITLE)
    md_path = runs_dir / f"{ts}_{safe_title}.md"
    js_path = runs_dir / f"{ts}_{safe_title}.json"
    md_path.write_text(build_report(meta, records, summary, anomalies), encoding="utf-8")
    js_path.write_text(json.dumps({"meta": meta, "summary": summary, "records": records},
                                 ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print("=" * 64)
    print("世界书压测汇总")
    print("=" * 64)
    print(f"  轮数={len(records)} 条目={summary['条目数']}")
    print(f"  depth 全部轮次一致 : {summary['depth 全部轮次一致']}")
    print(f"  position 全部轮次正确: {summary['position 全部轮次正确']}")
    print(f"  before+after 同轮共存: {summary['before+after 同轮共存轮数']} 轮 "
          f"{summary['before+after 同轮共存轮次']}")
    print(f"  depth 窗口封顶(60)   : {cap['结论']}")
    print()
    for name, v in summary["逐条目"].items():
        print(f"  {name} [{v['position']},d{v['depth']}] 触发 {v['actual_rounds']}")
    if anomalies:
        print("\n  ⚠ 异常:")
        for a in anomalies:
            print(f"    - {a}")
    else:
        print("\n  ✓ 无异常：3 个参数在 60 轮内均严格生效")
    print(f"\n报告：{md_path}")
    print(f"明细：{js_path}")


if __name__ == "__main__":
    sys.exit(main())
