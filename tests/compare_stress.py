"""压测对照分析：基线 vs 复测，一键出结论。

用法:
    python tests/compare_stress.py <基线.json> <复测.json>

输出三部分：
1. 稳定性 / 能力保持度（异常、空回复、耗时趋势、回复长度、点名出场）
2. 机制存活度（场景僵死、关系停滞、秘密停滞、在场变更）

不调 LLM，纯离线分析压测产物。
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(os.path.dirname(HERE), "engine")


def _load_director():
    """加载 engine/director，复用真实的分级判定（不依赖 conftest）。

    director 内部 import memory/llm/store 等同目录模块，故须把 engine/ 加入
    sys.path 后整体导入，不能用 spec_from_file_location 单独加载。
    """
    if ENGINE not in sys.path:
        sys.path.insert(0, ENGINE)
    try:
        import director  # noqa: E402
        return director
    except Exception as exc:
        print(f"  （未能加载 director，跳过账本模拟：{exc}）")
        return None


def load(path):
    d = json.load(open(path, encoding="utf-8"))
    return d.get("summary", {}), d["records"]


def max_stall(recs, key_fn):
    """最长连续不变轮数"""
    best = cur = 0
    prev = None
    for r in recs:
        v = key_fn(r)
        cur = cur + 1 if v == prev else 1
        best = max(best, cur)
        prev = v
    return best


def seg(recs, a, b, field="elapsed"):
    v = [r[field] for r in recs if a <= r["round"] <= b and r.get(field) is not None]
    return (sum(v) / len(v), max(v)) if v else (0, 0)


def scene_of(r):
    sc = r.get("scene") or {}
    if isinstance(sc, str):
        try:
            sc = json.loads(sc)
        except Exception:
            return {}
    return sc if isinstance(sc, dict) else {}


def _fallback(r, key):
    """兼容旧产物：scene 曾被截断成非法 JSON，用正则硬抠字段值。"""
    m = re.search(r'"%s"\s*:\s*"([^"]*)"' % key, r.get("scene") or "")
    return m.group(1) if m else ""


def place_of(r):
    if r.get("scene_place"):
        return r["scene_place"]
    return scene_of(r).get("place", "") or _fallback(r, "place")


def time_of(r):
    if r.get("scene_time"):
        return r["scene_time"]
    return scene_of(r).get("time", "") or _fallback(r, "time")


def sec_key(r):
    s = r.get("secrets") or {}
    if isinstance(s, list):
        return tuple(sorted((str(x.get("owner", "?")), str(x.get("state", "?"))) for x in s))
    if isinstance(s, dict):
        return tuple(sorted((str(k), str(v)) for k, v in s.items()))
    return str(s)


def rel_key(r):
    rel = r.get("relations") or {}
    if isinstance(rel, dict):
        return tuple(sorted((str(k), str(v)) for k, v in rel.items()))
    return str(rel)


def report(tag, summ, recs, director):
    print("=" * 62)
    print(tag, f"（{len(recs)} 轮）")
    print("=" * 62)
    print(f"  稳定性: 异常 {summ.get('异常轮数')} | 空回复 {summ.get('空回复轮数')} | "
          f"成功 {summ.get('成功轮数')}/{summ.get('轮数')} | present违例 "
          f"{sum(1 for r in recs if r.get('present_violation'))}")
    a1, _ = seg(recs, 1, 10)
    a3, m3 = seg(recs, 21, 30)
    if a1:
        print(f"  耗时: R1-10 均 {a1:.1f}s -> R21-30 均 {a3:.1f}s "
              f"（增幅 {(a3 / a1 - 1) * 100:+.0f}%）| 全程最大 {m3:.1f}s")
    l1, _ = seg(recs, 1, 10, "reply_len")
    l3, _ = seg(recs, 21, 30, "reply_len")
    if l1:
        print(f"  回复长度: 前期 {l1:.0f} -> 后期 {l3:.0f}（{(l3 / l1 - 1) * 100:+.0f}%）")
    print(f"  点名出场: {sum(1 for r in recs if r.get('named_hit'))}/{len(recs)} | "
          f"镜头跟随: {summ.get('镜头跟随生效轮数')}")
    print()
    print("  --- 机制存活度 ---")
    places = [place_of(r) for r in recs]
    changes = sum(1 for i in range(1, len(places)) if places[i] != places[i - 1])
    print(f"  场景: place变更 {changes} 次 | 最长僵死 {max_stall(recs, place_of)} 轮 | "
          f"出现过的地点 {len(set(places))} 个")
    s_changes = sum(1 for i in range(1, len(recs)) if sec_key(recs[i]) != sec_key(recs[i - 1]))
    print(f"  秘密: 翻转 {s_changes} 次 | 最长停滞 {max_stall(recs, sec_key)} 轮 | "
          f"末态 {dict(sec_key(recs[-1]))}")
    r_changes = sum(1 for i in range(1, len(recs)) if rel_key(recs[i]) != rel_key(recs[i - 1]))
    print(f"  关系: 演化 {r_changes} 次 | 最长停滞 {max_stall(recs, rel_key)} 轮")
    p_changes = sum(1 for i in range(1, len(recs))
                    if tuple(recs[i].get("present") or []) != tuple(recs[i - 1].get("present") or []))
    print(f"  在场: 变更 {p_changes} 次")
    print()
    print("  --- place/time 演进（仅列变化轮）---")
    prev = None
    for r in recs:
        p = f"{place_of(r)} [{time_of(r)}]"
        if p != prev:
            print(f"    R{r['round']:>2} -> {p}")
            prev = p
    print()


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    director = _load_director()
    sb, b = load(sys.argv[1])
    sn, n = load(sys.argv[2])
    report("【基线】", sb, b, director)
    report("【复测】", sn, n, director)
    return 0


if __name__ == "__main__":
    sys.exit(main())
