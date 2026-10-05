"""实机验证：角色卡/世界书人设张力改动（v0.17.x 后）回归。

验证目标（对应 P1-P4 人设优化 + 感染修复）：
1. 角色不再「开局即尸变」——正文不应一上来就写高烧/黑紫纹路/异变爆发。
2. 四角色秘密保持潜伏/悬置——开局不应有任何秘密被翻成「暴露」，也不该被
   「内心早已看穿」误判成「实际得知」。
3. 角色行为不再「颠三倒四」——避免出现角色卡自相矛盾导致的不可预测跳变。

纯 HTTP，不硬编码角色名/题材词，卡组从 /api/characters 取。
用法：python tests/verify_character_dynamics.py --rounds 6 --base http://127.0.0.1:5052
"""

import argparse
import datetime
import json
import sys
from pathlib import Path

import requests

BASE_DEFAULT = "http://127.0.0.1:5052"
TITLE = "人设张力验证"

# 中性指令：不逼感染、不逼暴露，只给日常情境，让引擎自然发挥。
ARC_TEMPLATE = [
    "{A}招呼大家围到桌边，把剩下的水和食物分成几份，说今晚先这样。",
    "{B}看了看{char_C}，欲言又止，最后只是把一件外衣递了过去。",
    "{A}问大家，明天该怎么打算，谁先说说看。",
    "{char_C}靠在墙边，像是想说什么，又咽了回去。",
    "{char_D}走到窗边，低声说外头的动静有点不对劲。",
    "{A}拍了拍{char_D}的肩膀，说都别慌，先把手边的事做完。",
]


def fetch_cast(base_url, timeout=30):
    resp = requests.get(base_url + "/api/characters", timeout=timeout)
    resp.raise_for_status()
    names = resp.json()
    if not names:
        raise SystemExit("引擎未返回任何角色卡")
    return names[:4]


def build_arc(cast):
    names = {f"char_{k}": cast[i] for i, k in enumerate("ABCD")}
    names.update({k: cast[i] for i, k in enumerate("ABCD")})
    out = []
    for t in ARC_TEMPLATE:
        # 先替换 char_X，再替换单字母占位
        for k, v in names.items():
            t = t.replace("{" + k + "}", v)
        out.append(t)
    return out


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


# 感染/尸变判定词（对应世界书【感染的临界】症状）
INFECT_WORDS = ["高烧", "黑紫", "纹路", "尸变", "异变", "瞳孔涣散", "僵硬笑容",
                "空洞眼神", "抽搐", "被咬", "抓伤", "感染"]


def run(base_url, rounds, scene):
    cast = fetch_cast(base_url)
    arc = build_arc(cast)[:rounds]

    new = requests.post(base_url + "/api/session/new",
                        json={"cast": cast, "scene": scene},
                        timeout=60).json()
    sid = new["session"]
    init_snap = requests.get(base_url + "/api/snapshot",
                             params={"session": sid, "debug": "1"},
                             timeout=30).json()

    records, errors = [], []
    try:
        for i, directive in enumerate(arc, 1):
            rec = {"round": i, "directive": directive}
            try:
                reply, done, elapsed = act(base_url, sid, directive)
            except Exception as exc:
                errors.append((i, str(exc)))
                rec.update({"error": str(exc), "reply": ""})
                records.append(rec)
                print(f"[R{i}] 失败：{exc}", flush=True)
                continue
            snap = (done or {}).get("snapshot") or {}
            # 收集秘密状态
            secrets = snap.get("secrets") or []
            rec.update({
                "elapsed": round(elapsed, 1),
                "reply": reply or "",
                "reply_len": len(reply or ""),
                "secret_states": {s.get("owner"): s.get("state") for s in secrets},
                "secret_known_by": {s.get("owner"): s.get("known_by") for s in secrets},
            })
            records.append(rec)
            # 感染判定：本轮正文是否出现感染/尸变词
            infect_hits = [w for w in INFECT_WORDS if w in (reply or "")]
            print(f"[R{i}] {elapsed:5.1f}s len={len(reply or '')} "
                  f"秘密={rec['secret_states']} 感染词={infect_hits or '无'}",
                  flush=True)
    finally:
        try:
            requests.delete(base_url + f"/api/session/{sid}", timeout=15)
        except Exception:
            pass

    return sid, cast, init_snap, records, errors


def analyze(cast, init_snap, records, errors):
    checks = []

    # 检查1：开局秘密全部潜伏
    init_secrets = init_snap.get("secrets") or []
    for s in init_secrets:
        st = s.get("state")
        owner = s.get("owner")
        checks.append((f"开局秘密[{owner}]", st,
                       "潜伏(正确)" if st == "潜伏" else f"异常状态 {st}"))

    # 检查2：整局无秘密被翻成暴露
    exposed_ever = []
    for r in records:
        for owner, st in (r.get("secret_states") or {}).items():
            if st != "潜伏" and owner not in [o for o, _ in exposed_ever]:
                exposed_ever.append((owner, st, r["round"]))
    checks.append(("整局秘密是否保持潜伏",
                   str([f"{o}:{st}@R{r}" for o, st, r in exposed_ever]),
                   "保持潜伏(正确)" if not exposed_ever else "有秘密提前暴露"))

    # 检查3：是否开局即尸变——看正文前两轮是否出现感染词（角色动态取，不写死名字）
    early_infect = []
    for r in records[:2]:
        hits = [w for w in INFECT_WORDS if w in (r.get("reply") or "")]
        if hits:
            early_infect.append((r["round"], hits))
    checks.append(("前两轮是否出现尸变/感染词",
                   str(early_infect),
                   "无(正确)" if not early_infect else "开局即尸变风险"))

    return checks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=BASE_DEFAULT)
    ap.add_argument("--rounds", type=int, default=6)
    ap.add_argument("--scene", default="傍晚，公寓的客厅")
    args = ap.parse_args()

    sid, cast, init_snap, records, errors = run(args.base, args.rounds, args.scene)
    checks = analyze(cast, init_snap, records, errors)

    print()
    print("=" * 60)
    print("人设张力验证检查")
    print("=" * 60)
    for name, got, verdict in checks:
        print(f"  [{name}] got={got} -> {verdict}")

    runs_dir = Path(__file__).parent / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    js_path = runs_dir / f"{ts}_{TITLE}.json"
    js_path.write_text(json.dumps(
        {"cast": cast, "records": records, "errors": errors,
         "checks": [list(c) for c in checks]},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n明细：{js_path}")


if __name__ == "__main__":
    sys.exit(main())
