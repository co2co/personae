"""10 轮实机验证：玩家提示词的时间语义解析（v0.17.3 时间承接修复回归）。

目的：验证引擎能否正确「承接」玩家输入里的时间锚点，防止 256d924c 那种
「时间被吞进 place、正文一轮内三段跳」的事故复发。

重点观测：
1. 开场场景拆分 —— 「傍晚，公寓的客厅」是否拆成 place=公寓的客厅、time=傍晚
2. 时间推进承接 —— 指令含「夜晚/第二天/入夜」时 scene.time 是否被正确推进
3. 将来时态不误判 —— 「即将到来的夜晚」是预告，不应直接把 time 翻成「夜晚」
4. 时间不再脱钩 —— 正文不再出现「时间未明」下的一轮内多段跳跃

纯 HTTP，不硬编码角色名/题材词，卡组从 /api/characters 取。

用法：
  python tests/verify_time_semantics.py --rounds 10
"""

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

import requests

BASE_DEFAULT = "http://127.0.0.1:5051"
TITLE = "时间语义解析验证"

# 逐轮指令：刻意嵌入时间词，检验引擎是否承接。
# {A}{B}{C}{D} 为角色占位，运行时替换。题材中性（只谈时间/空间/动作）。
# R1 起手「傍晚」；R2 用「即将到来的夜晚」检验将来时；R3 用「夜晚」检验词表补漏；
# R4 用「第二天」检验跨日推进；R5 用「入夜」；R6 无时间词（应保持不动）；
# R7 用「清晨」；R8 用「天亮」；R9 无时间词；R10 用「午后」。
ARC_TEMPLATE = [
    "{A}借着傍晚最后一缕光，清点屋里还剩下的东西，招呼大家把门闩好。",
    "{B}看着窗外，说夜晚快到了，得趁这之前把蜡烛找出来。",
    "夜色沉下来，{C}把几根蜡烛依次点亮，屋里总算有了点暖光。",
    "第二天，{D}第一个醒来，推醒大家说该重新商量接下来怎么办。",
    "入夜后气温更低了，{A}让所有人挤到里屋，别分散。",
    "{B}把最后一口水递给了{C}，没说话。",
    "清晨，{D}推开窗缝，外头起了薄雾，看不太清路。",
    "天光大亮，众人把剩下的东西打包装车，准备动身。",
    "{A}最后回头看了一眼这间屋子，什么也没说。",
    "午后，队伍停在路边歇脚，{C}分着最后几块饼干。",
]

# 每轮指令期望触发的「时间词」，用于人工核对 engine 是否承接。
EXPECT_TIME = {
    1: "傍晚", 2: None, 3: "夜晚", 4: "第二天", 5: "入夜",
    6: None, 7: "清晨", 8: "天亮", 9: None, 10: "午后",
}


def fetch_cast(base_url, timeout=30):
    resp = requests.get(base_url + "/api/characters", timeout=timeout)
    resp.raise_for_status()
    names = resp.json()
    if not names:
        raise SystemExit("引擎未返回任何角色卡")
    return names[:4]


def build_arc(cast):
    mapping = {}
    for i, key in enumerate("ABCD"):
        mapping[key] = cast[i] if i < len(cast) else cast[-1]
    return [t.format(**mapping) for t in ARC_TEMPLATE]


def act(base_url, sid, directive, timeout=300):
    import time
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
    reply = done.get("reply") if done and done.get("reply") is not None \
        else "".join(chunks)
    return reply, done, elapsed


def run(base_url, rounds, scene):
    cast = fetch_cast(base_url)
    arc = build_arc(cast)[:rounds]

    new = requests.post(base_url + "/api/session/new",
                        json={"cast": cast, "scene": scene},
                        timeout=60).json()
    sid = new["session"]
    # 开场快照：走 /api/snapshot?debug=1 拿完整初始 scene（含 time/place）
    init_snap = requests.get(base_url + "/api/snapshot",
                             params={"session": sid, "debug": "1"},
                             timeout=30).json()
    init_scene = init_snap.get("scene", {})
    records, errors = [], []

    try:
        for i, directive in enumerate(arc, 1):
            rec = {"round": i, "directive": directive,
                   "expect_time": EXPECT_TIME.get(i)}
            try:
                reply, done, elapsed = act(base_url, sid, directive)
            except Exception as exc:
                errors.append((i, str(exc)))
                rec.update({"error": str(exc), "reply": "", "reply_len": 0})
                records.append(rec)
                print(f"[R{i}] 失败：{exc}", flush=True)
                continue
            snap = (done or {}).get("snapshot") or {}
            sc = snap.get("scene") or {}
            rec.update({
                "elapsed": round(elapsed, 1),
                "reply_len": len(reply or ""),
                "reply": reply or "",
                "time": sc.get("time", ""),
                "place": sc.get("place", ""),
                "scene_shift": snap.get("scene_shift"),
            })
            records.append(rec)
            # 判定：本轮指令含时间词时，scene.time 是否被承接
            print(f"[R{i}] {elapsed:5.1f}s time={rec['time']!r:14} "
                  f"期望={rec['expect_time']!r:8} 换场={ (snap.get('scene_shift') or {}).get('changed') } "
                  f"len={rec['reply_len']}", flush=True)
    finally:
        try:
            requests.delete(base_url + f"/api/session/{sid}", timeout=15)
        except Exception:
            pass

    return sid, cast, init_scene, records, errors


def analyze(cast, init_scene, records, errors):
    checks = []

    # 检查1：开场拆分
    init_place = (init_scene or {}).get("place", "")
    init_time = (init_scene or {}).get("time", "")
    checks.append(("开场地点拆分", init_place,
                   "应不含时间词（傍晚等）" if not _has_timeword(init_place) else "含时间词，未拆分干净"))
    checks.append(("开场时间锚", repr(init_time),
                   "应为时间词" if init_time else "空，时间锚丢失"))

    # 检查2：逐轮时间承接
    for r in records:
        if r.get("error"):
            continue
        exp = r.get("expect_time")
        got = r.get("time", "")
        if exp is None:
            # 无时间词的轮次，不应发生时间推进（允许保持上一轮）
            continue
        hit = _has_timeword_of(got, exp)
        checks.append((f"R{r['round']} 时间承接({exp})", repr(got),
                       "命中" if hit else f"未命中期望词 {exp}"))

    # 检查3：将来时态误判（R2 用了「夜晚快到了」，time 不应被直接推进成「夜晚」）
    r2 = next((r for r in records if r["round"] == 2), None)
    if r2 and not r2.get("error"):
        got = r2.get("time", "")
        checks.append(("R2 将来时「夜晚快到了」是否误判", repr(got),
                       "未误判(保持傍晚/未明)" if not _has_timeword_of(got, "夜晚") else "误判成已入夜"))

    return checks


def _has_timeword(s):
    words = ["傍晚", "夜晚", "晚上", "第二天", "次日", "入夜", "清晨", "凌晨",
             "深夜", "半夜", "黄昏", "黎明", "天亮", "天黑", "午后", "中午",
             "早晨", "早上", "白天", "正午"]
    return any(w in s for w in words)


def _has_timeword_of(s, w):
    if not s:
        return False
    # 词族匹配：期望「夜晚」时，time 落在夜晚/深夜/晚上 都算承接
    fam = {
        "傍晚": ["傍晚", "黄昏"],
        "夜晚": ["夜晚", "晚上", "深夜", "入夜"],
        "第二天": ["第二天", "次日"],
        "入夜": ["入夜", "夜晚", "晚上"],
        "清晨": ["清晨", "凌晨", "早晨", "早上"],
        "天亮": ["天亮", "清晨", "早晨", "白天"],
        "午后": ["午后", "下午", "中午"],
    }
    cand = fam.get(w, [w])
    return any(c in s for c in cand)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=BASE_DEFAULT)
    ap.add_argument("--rounds", type=int, default=10)
    ap.add_argument("--scene", default="傍晚，公寓的客厅", help="开场场景（含时间锚）")
    args = ap.parse_args()

    sid, cast, init_scene, records, errors = run(args.base, args.rounds, args.scene)
    checks = analyze(cast, init_scene, records, errors)

    print()
    print("=" * 60)
    print("时间语义解析检查")
    print("=" * 60)
    for name, got, verdict in checks:
        print(f"  [{name}] got={got} -> {verdict}")

    # 落盘
    runs_dir = Path(__file__).parent / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    js_path = runs_dir / f"{ts}_{TITLE}.json"
    js_path.write_text(json.dumps(
        {"cast": cast, "init_scene": init_scene, "records": records,
         "errors": errors, "checks": [list(c) for c in checks]},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n明细：{js_path}")


if __name__ == "__main__":
    sys.exit(main())
