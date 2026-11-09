"""长上下文极限压测脚本（独立运行，非 pytest）。

目的：检验长上下文状态下引擎的
  1. 稳定性   —— 不崩、不空、不断，present 永不为空，无异常
  2. 能力保持 —— 后期是否仍能遵循指令（点名角色是否出场）、输出是否退化（长度/敷衍）
  3. 机制是否变形或熄火 —— 场景解析（纯规则）、秘密四态翻转、位置簿记、present
     校验、结局判定 在长上下文后是否仍正确工作

2026-11-08 引擎瘦身同步：镜头跟随 focus、秘密发酵压力 pressure、久未登场
silent_rounds、纪官 scene_shift、常量层 facts、临时群演 aux 均已从引擎撤除，
对应采集与指标一并撤下；换入「场景按指令变更轮数」与「位置簿记条数」两项。

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
# 卡组运行时从引擎 /api/characters 取（普适性红线：不硬编码任何剧本的角色名，
# 换剧本即换卡组，本脚本无须改动）。世界书由 /api/session/new 按首张卡的
# world 字段自动加载，无需另行指定。
SCENE = "城郊仓库单元，众人临时落脚，门外街道不安静"
TITLE = "长上下文极限压测"

# 30 轮长弧：覆盖 秘密曝光 / 起疑(线索逼近) / 场景切换 / 分头行动 /
# 关系演化 / 抉择冲突，且刻意不设 ending=True，以检验结局判定是否「不该误触发」。
# 弧线用 {A}{B}{C}{D} 占位，运行时按实际 cast 顺序替换（见 build_arc）。
# 剧情内核与题材无关：一条「隐瞒伤情」的秘密被线索逐步逼近并证实，
# 一条「旧事往事」的第二秘密 likewise——用于检验秘密链条后半段是否活着。
ARC_TEMPLATE = [
    "{A}清点屋内物资，分配守夜班次，定下谁都不许私自出门的规矩。",
    "{C}主动揽下烧水和分装食物的活，边干边留神{A}的脸色，找机会搭话。",
    "{D}嫌安排太严，当众顶了{A}一句，说凭什么什么都得听你的。",
    "{B}替{D}换药，拆开绷带时发现他小臂上有一圈很深的勒痕，不像普通磕碰。",
    "{B}追问这痕迹到底是怎么来的，{C}抢着说是路上蹭的，{D}低头不吭声。",
    "{A}注意到{D}袖口卷得严实、一直捂着手臂，让他把手伸出来看看。",
    "门外传来撞击声，众人熄灯静默，黑暗里谁也不敢先开口。",
    "天亮后队伍决定转移，{A}领头，{D}吊在队尾，故意落后十几步。",
    "路上经过一辆翻倒的卡车，车旁横着几具早已凉透的遗骸。",
    "{A}在那几具遗骸前站了很久，脸色发白，被{B}看在眼里。",
    "{B}问他认得这些人，{A}只说走吧，别看了。",
    "队伍在路边小店休整，{C}把省下来的半块饼干塞给{A}。",
    "{D}发起烧来，{B}要再检查他的伤，{C}死死拦着不让碰。",
    "{B}把{C}单独拉进后间的储物室，关上门，其他人留在外面等。",
    "储物室里，{B}压低声音说那不是磕碰，你比我清楚，瞒着会害了所有人。",
    "{C}红了眼，说我要是说了，你们会把他扔下。",
    "{A}听见争吵推门进来，要求{D}把手臂露出来，当着他的面说清楚。",
    "{D}终于承认自己那晚受了伤，众人陷入沉默。",
    "{C}跪下求{A}别丢下孩子，说她什么都愿意做。",
    "{B}翻出自己那支仅剩的药剂，说能不能撑过去只能看运气。",
    "夜里轮到{B}守夜，{A}睡不着，两人隔着半截货架说起话来。",
    "{B}问{A}，白天那几具穿着一样衣裳的人，是谁的人。",
    "{A}沉默很久，说曾经是我的队伍，十二个人，只剩我一个。",
    "{B}追问他们是怎么没的，你从没说过。",
    "{A}说我一次决断慢了，他们替我挡在后面，我一个人跑了出来。",
    "{B}没再问下去，只说这事我不会跟别人讲，你自己也别再背着了。",
    "天没亮{D}症状加重，开始说胡话，喊着要去找家人。",
    "{C}抱着孩子求{B}再想想办法，{B}说只能赌剩下的时间。",
    "{A}做出决定：带上{D}继续走，但把他绑在推车上看管，谁也不许靠近。",
    "{D}清醒过来听见这个安排，冲着{A}吼说你就是想扔下我。",
    "队伍重新上路，天亮时抵达一处河堤，谁也没再提昨晚的事。",
]


def fetch_cast(base_url, timeout=30):
    """从引擎取当前可用角色名（取前 4 名）。取不到则报错退出。

    普适性红线：压测卡组必须跟随磁盘上的实际剧本，不能在脚本里写死人名。
    """
    resp = requests.get(base_url + "/api/characters", timeout=timeout)
    resp.raise_for_status()
    names = resp.json()
    if not names:
        raise SystemExit("引擎未返回任何角色卡：先在界面导入或使用随包 demo。")
    return names[:4]


def build_arc(cast):
    """把 ARC_TEMPLATE 里的 {A}{B}{C}{D} 占位替换为实际角色名。"""
    if not cast:
        raise SystemExit("卡组为空：引擎未返回角色卡，请用 --cast 显式指定。")
    mapping = {}
    for i, key in enumerate("ABCD"):
        mapping[key] = cast[i] if i < len(cast) else cast[-1]
    return [t.format(**mapping) for t in ARC_TEMPLATE]


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


def run(base_url, rounds, timeout, cast=None, scene=None):
    cast = cast or fetch_cast(base_url)
    arc = build_arc(cast)
    arc = arc[:rounds] if rounds <= len(arc) else arc * (rounds // len(arc) + 1)
    arc = arc[:rounds]

    # 不传 cast：v2.1.1 起名册由后端按剧本取全量（引擎不接受部分登场）。
    new = requests.post(base_url + "/api/session/new",
                        json={"scene": scene or SCENE},
                        timeout=60).json()
    sid = new["session"]
    records, errors = [], []

    try:
        for i, directive in enumerate(arc, 1):
            rec = {"round": i, "directive": directive,
                   "named": extract_named(directive, cast)}
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
                "address": dict(snap.get("address") or {}),
                # 位置簿记（纪官 location_updates 回写）：长会话里「谁在哪里」跟不跟得住
                "locations": dict(snap.get("locations") or {}),
                # 状态层（纪官 state_updates）：覆盖式存储，键数应有界
                "states": dict(snap.get("states") or {}),
                "relations": snap.get("relations", {}),
                "present_violation": done.get("present_violation"),
                "ending": bool(done.get("ending_candidate")),
                # 场景解析已改纯规则（2026-11-08）：只有指令明说换场才动，走 done 的 scene_change
                "scene_change": done.get("scene_change"),
            })
            # 能力保持：点名角色是否真的出场（出现在回复里）
            if rec["named"]:
                rec["named_hit"] = all((n in (reply or "")) for n in rec["named"])
            records.append(rec)
            susp_n = sum(len(v) for v in (rec.get("suspicions") or {}).values())
            print(f"[R{i}] {elapsed:5.1f}s len={len(reply or ''):4d} "
                  f"present={len(rec['present'])} loc={len(rec['locations'])} "
                  f"暴露={rec['exposed']} 起疑={susp_n} 账本={rec.get('ledger', 0)} "
                  f"违例={rec['present_violation']} ending={rec['ending']} "
                  f"换场={'是' if rec.get('scene_change') else '-'}",
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

    # 秘密状态是否发生过翻转（机制活着 vs 熄火）
    flips = 0
    prev = None
    for r in ok:
        cur = tuple(sorted((r.get("secrets") or {}).items()))
        if prev is not None and cur != prev:
            flips += 1
        prev = cur

    # 关系口径已固化为作者设定（纪官不再改写），此数应恒为 0——非 0 即回归
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

    # 状态层（纪官 state_updates）：覆盖式存储，键数应有界
    state_sizes = [len(r.get("states") or {}) for r in ok]

    # 场景解析改纯规则后的关键哨兵：只有指令明说换场才变（不该自己跳场）
    scene_change_rounds = sum(1 for r in ok if r.get("scene_change"))
    # 位置簿记是否跟得住：末轮位置条数与名册人数比对（应覆盖在场者）
    loc_sizes = [len(r.get("locations") or {}) for r in ok]
    loc_last = dict((last.get("locations") or {}))
    present_last = list(last.get("present") or [])
    loc_missing = [p for p in present_last if p not in loc_last]

    # 删正文回归哨兵：极短回复或残句（以句号/逗号开头）
    short_rounds = sum(1 for r in ok if 0 < r.get("reply_len", 0) < 200)
    stump_rounds = sum(1 for r in ok
                       if (r.get("reply") or "").lstrip()[:1] in ("。", "，", "、"))

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
        "关系被改写次数(应为0)": rel_flips,
        "秘密状态翻转次数": flips,
        "场景变更次数": len(scenes) - 1 if len(scenes) > 1 else 0,
        "present违例轮数": sum(1 for r in ok if r.get("present_violation")),
        "结局候选轮数": sum(1 for r in ok if r.get("ending")),
        "起疑生效轮数": f"{susp_rounds}/{len(ok)}",
        "末轮在疑条目数": susp_last,
        "曾起疑的组合数": len(ever_suspects),
        "起疑后确知数": len(confirmed),
        "末轮后果账本条数": last.get("ledger", 0),
        "状态层键数(末轮/峰值)": (f"{state_sizes[-1]}/{max(state_sizes)}"
                                  if state_sizes else "-"),
        "场景按指令换场轮数": f"{scene_change_rounds}/{len(ok)}",
        "位置簿记条数(末轮/峰值)": (f"{loc_sizes[-1]}/{max(loc_sizes)}"
                                    if loc_sizes else "-"),
        "末轮在场者未记位置": "、".join(loc_missing) or "无",
        "极短回复轮数(<200字)": short_rounds,
        "残句回复轮数(以句号/逗号开头)": stump_rounds,
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
    out.append("| 轮 | 耗时s | 长度 | 在场 | 位置 | 暴露 | 潜伏 | 起疑 | 账本 | 违例 | 点名命中 |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in records:
        if r.get("error"):
            out.append(f"| {r['round']} | - | - | - | - | - | - | - | - | - | 失败 |")
            continue
        named = "✓" if r.get("named_hit") else ("✗" if "named_hit" in r else "-")
        susp_n = sum(len(v) for v in (r.get("suspicions") or {}).values())
        out.append(f"| {r['round']} | {r.get('elapsed','-')} | {r.get('reply_len','-')} "
                   f"| {len(r.get('present') or [])} | {len(r.get('locations') or {})} "
                   f"| {r.get('exposed','-')} "
                   f"| {r.get('latent','-')} | {susp_n} | {r.get('ledger','-')} "
                   f"| {'是' if r.get('present_violation') else '否'} "
                   f"| {named} |")
    out.append("")
    out.append("## 场景解析观测（纯规则：只有指令明说才换场）")
    out.append("")
    out.append("| 轮 | 换到 | 时间 | 天气 | 依据 |")
    out.append("|---|---|---|---|---|")
    for r in records:
        if r.get("error"):
            continue
        sc = r.get("scene_change") or {}
        if not sc:
            continue
        out.append(f"| {r['round']} | {sc.get('place') or '-'} | {sc.get('time') or '-'} "
                   f"| {sc.get('weather') or '-'} | {(sc.get('reason') or '-')[:40]} |")
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
    # 簿记层实测：状态键是否覆盖式不膨胀、位置是否跟住在场者
    out.append("## 簿记层（状态覆盖 / 位置跟记）")
    out.append("")
    out.append("| 轮 | 状态键数 | 状态内容 | 位置条数 | 缺位置的在场者 |")
    out.append("|---|---|---|---|---|")
    for r in records:
        if r.get("error"):
            continue
        st = r.get("states") or {}
        loc = r.get("locations") or {}
        if not st and not loc:
            continue
        st_items = "；".join("%s：%s" % (k, (v.get("value") if isinstance(v, dict) else v))
                             for k, v in st.items())
        missing = "、".join(p for p in (r.get("present") or []) if p not in loc) or "无"
        out.append(f"| {r['round']} | {len(st)} | {(st_items or '—')[:80]}"
                   f" | {len(loc)} | {missing} |")
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
    ap.add_argument("--cast", default=None,
                    help="逗号分隔的卡组名；缺省从 /api/characters 自动取前 4 名")
    ap.add_argument("--scene", default=None, help="开场场景；缺省用内置中性场景")
    args = ap.parse_args()

    cast = [s.strip() for s in args.cast.split(",")] if args.cast else None
    sid, records, errors = run(args.base, args.rounds, args.timeout,
                               cast=cast, scene=args.scene)
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
