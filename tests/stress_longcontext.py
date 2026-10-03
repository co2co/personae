"""长上下文极限压测脚本（独立运行，非 pytest）。

目的：检验长上下文状态下引擎的
  1. 稳定性   —— 不崩、不空、不断，present 永不为空，无异常
  2. 能力保持 —— 后期是否仍能遵循指令（点名角色是否出场）、输出是否退化（长度/敷衍）
  3. 机制是否变形或熄火 —— 镜头跟随 focus、关系演化、秘密翻转、present 校验、
     结局判定 在长上下文后是否仍正确工作

用法：
  python tests/stress_longcontext.py --rounds 3            # 小规模测速
  python tests/stress_longcontext.py --rounds 30           # 完整压测

产物：tests/runs/<时间戳>_长上下文极限压测.md（报告）+ 同名 .json（明细）
"""

import argparse
import datetime
import json
import re
import sys
import time
from pathlib import Path

import requests

BASE_DEFAULT = "http://127.0.0.1:5051"
# 卡组取自引擎随附的 DEMO 剧本「丧尸末日」（旧压测卡组已随剧本删除）。
# 世界书由 /api/session/new 按首张卡的 world 字段自动加载，无需另行指定。
CAST = ["陆衡", "林清", "王秀兰", "王晨"]
# 与世界书「临时庇护所」条目保持一致（地铁口附近的公寓单元），使世界书条目能被
# 关键词命中并注入，压测才能真实检验「世界书是否生效」。
SCENE = "地铁口附近的公寓单元，众人临时落脚，楼下街道满是游荡的丧尸"
TITLE = "长上下文极限压测"

# 30 轮长弧：覆盖 秘密曝光 / 起疑(线索逼近) / 场景切换 / 分头行动(镜头跟随) /
# 关系演化 / 抉择冲突，且刻意不设 ending=True，以检验结局判定是否「不该误触发」。
# 弧线设计要点：
#   R4-R6   王晨咬伤的线索逐步逼近（检验起疑而非直接坐实）
#   R9-R11  旧队尸体出现、陆衡反应异常（检验第二条秘密的线索逼近）
#   R14     明确分头行动（检验镜头跟随 focus）
#   R17/R22-R24  两条秘密先后被证实（检验曝光与后果账本）
ARC = [
    "陆衡清点屋内物资，分配守夜班次，定下谁都不许私自出门的规矩。",
    "王秀兰主动揽下烧水和分装食物的活，边干边留神陆衡的脸色，找机会搭话。",
    "王晨嫌安排太严，当众顶了陆衡一句，说凭什么什么都得听你的。",
    "林清替王晨换药，拆开绷带时发现他小臂上有一圈很深的牙印，不像普通刮伤。",
    "林清追问这伤到底是怎么来的，王秀兰抢着说是路上蹭的，王晨低头不吭声。",
    "陆衡注意到王晨袖口卷得严实、一直捂着手臂，让他把手伸出来看看。",
    "门外传来抓挠声，众人熄灯静默，黑暗里谁也不敢先开口。",
    "天亮后队伍决定转移，陆衡领头，王晨吊在队尾，故意落后十几步。",
    "路上经过一辆翻倒的军车，车旁横着几具穿着同样制服的干尸。",
    "陆衡在那几具尸体前站了很久，脸色发白，被林清看在眼里。",
    "林清问他认得这些人，陆衡只说走吧，别看了。",
    "队伍在废弃加油站休整，王秀兰把省下来的半块饼干塞给陆衡。",
    "王晨发起烧来，林清要再检查他的伤口，王秀兰死死拦着不让碰。",
    "林清把王秀兰单独拉进加油站后间的储物室，关上门，其他人留在外面等。",
    "储物室里，林清压低声音说那不是刮伤，你比我清楚，瞒着会害了所有人。",
    "王秀兰红了眼，说我要是说了，你们会把他扔下。",
    "陆衡听见争吵推门进来，要求王晨把手臂露出来，当着他的面说清楚。",
    "王晨终于承认自己被咬了，众人陷入沉默。",
    "王秀兰跪下求陆衡别丢下孩子，说她什么都愿意做。",
    "林清翻出自己那支仅剩的抗生素，说能不能撑过去只能看运气。",
    "夜里轮到林清守夜，陆衡睡不着，两人隔着半截货架说起话来。",
    "林清问陆衡，白天那几具穿制服的尸体，是谁的人。",
    "陆衡沉默很久，说曾经是我的队伍，十二个人，只剩我一个。",
    "林清追问他们是怎么没的，你从没说过。",
    "陆衡说我一次决断慢了，他们替我挡在后面，我一个人跑了出来。",
    "林清没再问下去，只说这事我不会跟别人讲，你自己也别再背着了。",
    "天没亮王晨症状加重，开始说胡话，喊着要去找爸爸。",
    "王秀兰抱着儿子求林清再想想办法，林清说只能赌剩下的时间。",
    "陆衡做出决定：带上王晨继续走，但把他绑在推车上看管，谁也不许靠近。",
    "王晨清醒过来听见这个安排，冲着陆衡吼说你就是想扔下我。",
    "队伍重新上路，天亮时抵达一处河堤，谁也没再提昨晚的事。",
]


def act(base_url, sid, directive, timeout=300):
    """调用 /api/act 消费 SSE，返回 (reply, done, elapsed_seconds)。"""
    t0 = time.time()
    resp = requests.post(base_url + "/api/act",
                         json={"session": sid, "input": directive},
                         stream=True, timeout=timeout)
    resp.raise_for_status()
    chunks, done = [], None
    for line in resp.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data:"):
            continue
        try:
            ev = json.loads(line[5:])
        except ValueError:
            continue
        if "delta" in ev:
            chunks.append(ev["delta"])
        elif ev.get("done"):
            done = ev
    elapsed = time.time() - t0
    if done and done.get("reply") is not None:
        return done["reply"], done, elapsed
    return "".join(chunks), done, elapsed


def extract_named(directive, cast):
    """从指令中提取被点名的角色（用于检验指令遵循度）。"""
    return [n for n in cast if n in directive]


def secret_states(snap):
    return {s.get("owner", "?"): s.get("state", "?")
            for s in (snap.get("secrets") or [])}


def brief(value, n=60):
    """把任意类型的快照字段安全转成短字符串（scene/focus 可能是 dict）。"""
    if value is None:
        return ""
    if isinstance(value, str):
        return value[:n]
    if isinstance(value, dict):
        for k in ("name", "title", "desc", "description", "text", "where"):
            if value.get(k):
                return str(value[k])[:n]
        return json.dumps(value, ensure_ascii=False)[:n]
    if isinstance(value, list):
        return "、".join(str(x) for x in value)[:n]
    return str(value)[:n]


def run(base_url, rounds, timeout):
    arc = ARC[:rounds] if rounds <= len(ARC) else ARC * (rounds // len(ARC) + 1)
    arc = arc[:rounds]

    new = requests.post(base_url + "/api/session/new",
                        json={"cast": CAST, "scene": SCENE}, timeout=60).json()
    sid = new["session"]
    records, errors = [], []

    try:
        for i, directive in enumerate(arc, 1):
            rec = {"round": i, "directive": directive,
                   "named": extract_named(directive, CAST)}
            try:
                reply, done, elapsed = act(base_url, sid, directive, timeout)
            except Exception as exc:
                errors.append((i, str(exc)))
                rec.update({"error": str(exc), "reply_len": 0, "reply": ""})
                records.append(rec)
                print(f"[R{i}] 调用失败：{exc}", flush=True)
                continue

            done = done or {}
            snap = done.get("snapshot") or {}
            states = secret_states(snap)
            rec.update({
                "elapsed": round(elapsed, 1),
                "reply_len": len(reply or ""),
                "reply": reply or "",
                "present": snap.get("present", []),
                "focus": brief(snap.get("focus"), 40) or None,
                # scene 存完整 JSON（截断会破坏结构化分析），另附结构化字段
                "scene": json.dumps(snap.get("scene"), ensure_ascii=False)
                         if snap.get("scene") is not None else "",
                "scene_place": (snap.get("scene") or {}).get("place", "")
                               if isinstance(snap.get("scene"), dict) else "",
                "scene_time": (snap.get("scene") or {}).get("time", "")
                              if isinstance(snap.get("scene"), dict) else "",
                "secrets": states,
                "exposed": sum(1 for v in states.values() if v == "暴露"),
                "latent": sum(1 for v in states.values() if v == "潜伏"),
                # 新增机制采集：起疑（线索逼近）与后果账本，用于检验秘密链条后半段是否活着
                "suspicions": {
                    s.get("owner", "?"): [x.get("by") for x in (s.get("suspicions") or [])]
                    for s in (snap.get("secrets") or [])
                },
                "known_by": {
                    s.get("owner", "?"): [k for k in (s.get("known_by") or [])
                                          if k != "环境推手"]
                    for s in (snap.get("secrets") or [])
                },
                "ledger": len(snap.get("ledger") or []),
                "relations": snap.get("relations", {}),
                "present_violation": done.get("present_violation"),
                "ending": bool(done.get("ending_candidate")),
            })
            # 能力保持：点名角色是否真的出场（出现在回复里）
            if rec["named"]:
                rec["named_hit"] = all((n in (reply or "")) for n in rec["named"])
            records.append(rec)
            susp_n = sum(len(v) for v in (rec.get("suspicions") or {}).values())
            print(f"[R{i}] {elapsed:5.1f}s len={len(reply or ''):4d} "
                  f"present={len(rec['present'])} focus={rec['focus']} "
                  f"暴露={rec['exposed']} 起疑={susp_n} 账本={rec.get('ledger', 0)} "
                  f"违例={rec['present_violation']} ending={rec['ending']}",
                  flush=True)
    finally:
        try:
            requests.delete(base_url + f"/api/session/{sid}", timeout=15)
        except Exception:
            pass

    return sid, records, errors


def analyze(records, errors):
    n = len(records)
    ok = [r for r in records if not r.get("error") and r.get("reply_len", 0) > 0]
    half = max(1, n // 2)
    early, late = records[:half], records[half:]

    def avg(rs, key):
        vals = [r[key] for r in rs if isinstance(r.get(key), (int, float))]
        return round(sum(vals) / len(vals), 1) if vals else 0

    def rate(rs, key):
        vals = [r[key] for r in rs if isinstance(r.get(key), bool)]
        return f"{sum(1 for v in vals if v)}/{len(vals)}" if vals else "n/a"

    focus_rounds = sum(1 for r in ok if r.get("focus"))

    # 秘密状态是否发生过翻转（机制活着 vs 熄火）
    flips = 0
    prev = None
    for r in ok:
        cur = tuple(sorted((r.get("secrets") or {}).items()))
        if prev is not None and cur != prev:
            flips += 1
        prev = cur

    # 关系状态是否发生过演化（机制活着 vs 熄火）
    rel_flips = 0
    prev_rel = None
    for r in ok:
        cur_rel = tuple(sorted((r.get("relations") or {}).items()))
        if prev_rel is not None and cur_rel != prev_rel:
            rel_flips += 1
        prev_rel = cur_rel

    # 场景是否变更过：只比对 place。整个 scene JSON 含 round/time 等每轮必变字段，
    # 拿它比对会把「场景变更次数」恒算成 轮数-1（实测 30 轮→29 次），指标失真。
    scenes = []
    for r in ok:
        s = (r.get("scene_place") or "").strip()
        if s and (not scenes or scenes[-1] != s):
            scenes.append(s)

    # 起疑机制是否活着（线索逼近中间态）
    susp_rounds = sum(1 for r in ok
                      if any(v for v in (r.get("suspicions") or {}).values()))
    ever_suspects, confirmed = set(), set()
    for r in ok:
        for owner, names in (r.get("suspicions") or {}).items():
            for nm in names:
                ever_suspects.add((owner, nm))
    last = ok[-1] if ok else {}
    for owner, names in (last.get("known_by") or {}).items():
        for nm in names:
            if (owner, nm) in ever_suspects:
                confirmed.add((owner, nm))
    susp_last = sum(len(v) for v in (last.get("suspicions") or {}).values())

    return {
        "轮数": n,
        "成功轮数": len(ok),
        "异常轮数": len(errors),
        "空回复轮数": sum(1 for r in records if r.get("reply_len", 0) == 0),
        "present为空轮数": sum(1 for r in ok if not r.get("present")),
        "平均耗时s": avg(ok, "elapsed"),
        "最大耗时s": max([r.get("elapsed", 0) for r in ok] or [0]),
        "前期平均耗时s": avg(early, "elapsed"),
        "后期平均耗时s": avg(late, "elapsed"),
        "前期平均长度": avg([r for r in early if not r.get("error")], "reply_len"),
        "后期平均长度": avg([r for r in late if not r.get("error")], "reply_len"),
        "点名角色出场率": rate(ok, "named_hit"),
        "镜头跟随生效轮数": f"{focus_rounds}/{len(ok)}",
        "关系状态演化次数": rel_flips,
        "秘密状态翻转次数": flips,
        "场景变更次数": len(scenes) - 1 if len(scenes) > 1 else 0,
        "present违例轮数": sum(1 for r in ok if r.get("present_violation")),
        "结局候选轮数": sum(1 for r in ok if r.get("ending")),
        "起疑生效轮数": f"{susp_rounds}/{len(ok)}",
        "末轮在疑条目数": susp_last,
        "曾起疑的组合数": len(ever_suspects),
        "起疑后确知数": len(confirmed),
        "末轮后果账本条数": last.get("ledger", 0),
    }


def build_report(meta, records, summary, errors):
    out = [f"# {meta['title']}报告", "",
           f"- 时间：{meta['time']}",
           f"- 会话：{meta['sid']}",
           f"- 轮数：{meta['rounds']}",
           f"- 模型：本地 Qwen3.8-27B（llama-server 1234）", ""]
    out.append("## 汇总指标")
    out.append("")
    for k, v in summary.items():
        out.append(f"- **{k}**：{v}")
    if errors:
        out.append("")
        out.append("## 异常明细")
        out.append("")
        for i, e in errors:
            out.append(f"- R{i}：{e}")
    out.append("")
    out.append("## 逐轮明细")
    out.append("")
    out.append("| 轮 | 耗时s | 长度 | 在场 | 焦点 | 暴露 | 潜伏 | 起疑 | 账本 | 违例 | 点名命中 |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in records:
        if r.get("error"):
            out.append(f"| {r['round']} | - | - | - | - | - | - | - | - | - | 失败 |")
            continue
        named = "✓" if r.get("named_hit") else ("✗" if "named_hit" in r else "-")
        susp_n = sum(len(v) for v in (r.get("suspicions") or {}).values())
        out.append(f"| {r['round']} | {r.get('elapsed','-')} | {r.get('reply_len','-')} "
                   f"| {len(r.get('present') or [])} | {r.get('focus') or '-'} "
                   f"| {r.get('exposed','-')} "
                   f"| {r.get('latent','-')} | {susp_n} | {r.get('ledger','-')} "
                   f"| {'是' if r.get('present_violation') else '否'} "
                   f"| {named} |")
    out.append("")
    out.append("## 秘密链条演进")
    out.append("")
    out.append("| 轮 | 归属者 | 起疑者 | 知情者 | 账本条数 |")
    out.append("|---|---|---|---|---|")
    for r in records:
        if r.get("error"):
            continue
        sus, knw = r.get("suspicions") or {}, r.get("known_by") or {}
        owners = sorted(set(sus) | set(knw))
        rows = [(o, "、".join(sus.get(o) or []) or "-", "、".join(knw.get(o) or []) or "-")
                for o in owners]
        if not any(a != "-" or b != "-" for _, a, b in rows):
            continue
        for idx, (o, a, b) in enumerate(rows):
            if a == "-" and b == "-":
                continue
            out.append(f"| {r['round']} | {o} | {a} | {b} | {r.get('ledger','-')} |")
    out.append("")
    out.append("---")
    out.append("")
    out.append("_由 tests/stress_longcontext.py 生成。_")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=BASE_DEFAULT)
    ap.add_argument("--rounds", type=int, default=30)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--out-dir", default=None)
    args = ap.parse_args()

    sid, records, errors = run(args.base, args.rounds, args.timeout)
    summary = analyze(records, errors)
    meta = {"title": TITLE, "sid": sid, "rounds": len(records),
            "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

    runs_dir = Path(args.out_dir) if args.out_dir else (Path(__file__).parent / "runs")
    runs_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = runs_dir / f"{ts}_{TITLE}.md"
    js_path = runs_dir / f"{ts}_{TITLE}.json"
    md_path.write_text(build_report(meta, records, summary, errors), encoding="utf-8")
    js_path.write_text(json.dumps({"meta": meta, "summary": summary,
                                   "records": records}, ensure_ascii=False, indent=2),
                       encoding="utf-8")

    print()
    print("=" * 60)
    print("汇总指标")
    print("=" * 60)
    for k, v in summary.items():
        print(f"  {k}: {v}")
    print()
    print(f"报告：{md_path}")
    print(f"明细：{js_path}")


if __name__ == "__main__":
    sys.exit(main())
