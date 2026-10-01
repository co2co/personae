"""长上下文极限压测脚本（独立运行，非 pytest）。

目的：检验长上下文状态下引擎的
  1. 稳定性   —— 不崩、不空、不断，present 永不为空，无异常
  2. 能力保持 —— 后期是否仍能遵循指令（点名角色是否出场）、输出是否退化（长度/敷衍）
  3. 机制是否变形或熄火 —— 镜头跟随 focus、秘密翻转、机会等级、NSFW 门控、
     present 校验、结局判定 在长上下文后是否仍正确工作

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
CAST = ["老周", "林晚", "阿杰", "苏曼", "高洋"]
SCENE = "城郊便利店后仓，卷帘门紧闭，门外尸群持续抓挠"
TITLE = "长上下文极限压测"

# 30 轮长弧：覆盖 秘密曝光 / 场景切换 / 分头行动(镜头跟随) / NSFW 机会 / 抉择冲突，
# 且刻意不设 ending=True，以检验结局判定是否「不该误触发」。
ARC = [
    "老周清点后仓物资，分配守夜班次，定下谁都不许私自出门的规矩。",
    "苏曼压低声音说，城东避难所可能还有活人，她想冒险出去找女儿。",
    "林晚替高洋换药，拆开绷带时发现他小臂有一圈咬伤。",
    "阿杰发现自己私藏的罐头被翻出，反手拿高洋的咬伤把柄逼林晚就范。",
    "门外尸群猛撞卷帘门，门轴开始变形，随时会破。",
    "老周当机立断：趁尸群集中撞门，带所有人从后窗突围，目标城东。",
    "破门瞬间队伍冲入尸群，老周断后，苏曼拼命朝女儿的方向张望。",
    "天亮时幸存者踏上通往城东的路，身后便利店只剩一道门框。",
    "途中休整，老周清点人数，发现队伍里少了一个人。",
    "高洋体力不支蹲在地上，苏曼扶住他，两人渐渐落后队伍。",
    "林晚走在最前，回头喊后面的人跟上，别掉队。",
    "阿杰趁乱靠近林晚，压低声音提起那晚的事，语气带着威胁。",
    "队伍抵达城东外围，发现避难所大门紧闭，门上有人从缝隙往外看。",
    "老周上前敲门交涉，苏曼在旁死死盯着门缝里的动静。",
    "门开了一条缝，里面的人只肯放一个人进来。",
    "苏曼不顾反对挤进门内找女儿，老周被挡在门外，两边分开。",
    "门内，苏曼在昏暗走廊里辨认每一张脸，寻找女儿的踪迹。",
    "门外，老周和剩下的人被要求后退，阿杰开始骂人。",
    "林晚发现高洋脸色发青，咬伤正在恶化，手在发抖。",
    "夜深，避难所里只剩林晚和阿杰守着一盏将熄的灯，两人独处。",
    "林晚靠近阿杰，指尖抚过他擦伤的胳膊，呼吸落在他颈侧。",
    "老周在门外和守卫谈判，要求放更多人进来。",
    "苏曼在门内找到一间育儿室，里面空无一人，她的手停在门框上。",
    "高洋终于承认自己被咬，众人陷入沉默。",
    "老周做出决定：带人离开避难所，另寻落脚点。",
    "队伍再次移动，这次老周和高洋走在前，林晚、苏曼、阿杰走在后面。",
    "阿杰走在最后，偷偷把一样东西塞进自己的包里。",
    "苏曼走在前面探路，忽然停下举手示意所有人安静。",
    "前方出现另一队幸存者，双方在废墟两侧对峙。",
    "天亮，双方对峙结束，幸存者各自散去，末日仍在继续。",
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
                "scene": brief(snap.get("scene"), 60),
                "secrets": states,
                "exposed": sum(1 for v in states.values() if v == "暴露"),
                "latent": sum(1 for v in states.values() if v == "潜伏"),
                "opportunity": done.get("opportunity"),
                "nsfw_unlocked": (done.get("nsfw") or {}).get("unlocked"),
                "nsfw_intimate": (done.get("nsfw") or {}).get("intimate"),
                "present_violation": done.get("present_violation"),
                "ending": bool(done.get("ending_candidate")),
            })
            # 能力保持：点名角色是否真的出场（出现在回复里）
            if rec["named"]:
                rec["named_hit"] = all((n in (reply or "")) for n in rec["named"])
            records.append(rec)
            print(f"[R{i}] {elapsed:5.1f}s len={len(reply or ''):4d} "
                  f"present={len(rec['present'])} focus={rec['focus']} "
                  f"opp={rec['opportunity']} 暴露={rec['exposed']} "
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
    opp_dist = {}
    for r in ok:
        opp_dist[r.get("opportunity")] = opp_dist.get(r.get("opportunity"), 0) + 1

    # 秘密状态是否发生过翻转（机制活着 vs 熄火）
    flips = 0
    prev = None
    for r in ok:
        cur = tuple(sorted((r.get("secrets") or {}).items()))
        if prev is not None and cur != prev:
            flips += 1
        prev = cur

    # 场景是否变更过
    scenes = []
    for r in ok:
        s = r.get("scene")
        if s and (not scenes or scenes[-1] != s):
            scenes.append(s)

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
        "机会等级分布": opp_dist,
        "秘密状态翻转次数": flips,
        "场景变更次数": len(scenes) - 1 if len(scenes) > 1 else 0,
        "present违例轮数": sum(1 for r in ok if r.get("present_violation")),
        "NSFW解锁轮数": sum(1 for r in ok if r.get("nsfw_unlocked")),
        "结局候选轮数": sum(1 for r in ok if r.get("ending")),
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
    out.append("| 轮 | 耗时s | 长度 | 在场 | 焦点 | 机会 | 暴露 | 潜伏 | 违例 | 点名命中 |")
    out.append("|---|---|---|---|---|---|---|---|---|---|")
    for r in records:
        if r.get("error"):
            out.append(f"| {r['round']} | - | - | - | - | - | - | - | - | 失败 |")
            continue
        named = "✓" if r.get("named_hit") else ("✗" if "named_hit" in r else "-")
        out.append(f"| {r['round']} | {r.get('elapsed','-')} | {r.get('reply_len','-')} "
                   f"| {len(r.get('present') or [])} | {r.get('focus') or '-'} "
                   f"| {r.get('opportunity') or '-'} | {r.get('exposed','-')} "
                   f"| {r.get('latent','-')} | {'是' if r.get('present_violation') else '否'} "
                   f"| {named} |")
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
