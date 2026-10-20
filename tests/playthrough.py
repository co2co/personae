"""走查驱动 + markdown 落盘。

复用引擎 HTTP API，按脚本化的"环境扰动弧"逐轮推进，把每轮
→「你（导演）发过去的环境扰动」与「引擎生成的内容」写入
tests/runs/<时间戳>_<剧本>.md，直到剧本 ending（弧末标记）。

纯 HTTP，不依赖引擎内部模块；可作为库被 pytest 调用，也可独立运行
（见 run_playthrough.py）。

普适性红线：卡组运行时从 /api/characters 取，扰动弧用 {A}..{E} 占位，
不在脚本里写死任何剧本的角色名或题材词——换剧本无须改本文件。
"""

import json
import datetime
from pathlib import Path

import requests

BASE_DEFAULT = "http://127.0.0.1:5000"
DEFAULT_SCENE = "城郊仓库后间，卷帘门紧闭，门外撞击声不停"
DEFAULT_TITLE = "默认走查"
DEFAULT_MODEL_NOTE = "tencent/Hy4-preview（真实 LLM）"

# 脚本化环境扰动弧：驱动故事走向结局。最后一步 ending=True 标记为结局。
# 每一步的 directive 即"你"以环境推手身份注入的扰动；notes 仅作走查备注。
# {A}..{E} 为角色占位，运行时按实际 cast 顺序替换。
DEFAULT_ARC_TEMPLATE = [
    {"directive": "{A}清点后间物资，分配守夜班次，定下谁都不许私自出门的规矩。",
     "notes": "建立秩序，定调主心骨"},
    {"directive": "{D}压低声音说，城东一带可能还有活人，她想冒险出去找家人。",
     "notes": "埋下外出行程目标"},
    {"directive": "{C}替{B}换药，拆开绷带时，发现他小臂有一圈勒痕。",
     "notes": "触发秘密曝光"},
    {"directive": "{E}发现自己私藏的物资被翻出，他反手拿{B}的伤情把柄，逼{C}就范。",
     "notes": "把柄胁迫 → 关系张力"},
    {"directive": "门外猛撞卷帘门，门轴开始变形，随时会破。",
     "notes": "升级威胁"},
    {"directive": "{A}当机立断：趁门外集中撞门，带所有人从后窗突围成撤离队形，目标城东。",
     "notes": "关键决策"},
    {"directive": "破门瞬间，队伍冲出门外，{A}断后，{D}拼命拉住家人的方向——",
     "notes": "高潮，逼近结局"},
    {"directive": "天亮时，一行人跌跌撞撞踏上通往城东的路，身后的仓库只剩一道门框。",
     "ending": True, "notes": "结局"},
]

ARC_SLOTS = ["{A}", "{B}", "{C}", "{D}", "{E}"]


def fetch_cast(base_url, size=None, timeout=30):
    """从引擎取当前可用角色名（size=None 取全量）。取不到则报错退出。

    普适性红线：走查卡组必须跟随磁盘上的实际剧本，不能在脚本里写死人名。
    v2.1.1 起建局不接受部分登场，本函数只用于取名字填弧线模板与统计点名率。
    """
    resp = requests.get(base_url + "/api/characters", timeout=timeout)
    resp.raise_for_status()
    names = resp.json()
    if not names:
        raise SystemExit("引擎未返回任何角色卡：先在界面导入或使用随包 demo。")
    return names[:size] if size else names


def build_arc(cast, template=None):
    """把弧线模板里的 {A}..{E} 占位替换为实际角色名。"""
    tpl = template or DEFAULT_ARC_TEMPLATE
    mapping = {}
    for i, slot in enumerate(ARC_SLOTS):
        mapping[slot] = cast[i] if i < len(cast) else cast[-1]
    out = []
    for step in tpl:
        s = dict(step)
        s["directive"] = step.get("directive", "").format(**mapping)
        out.append(s)
    return out


def _act(base_url, sid, directive, timeout=120):
    """调用 /api/act 并消费 SSE，返回 (reply, done_payload)。"""
    resp = requests.post(base_url + "/api/act",
                         json={"session": sid, "input": directive},
                         stream=True, timeout=timeout)
    resp.raise_for_status()
    reply_chunks = []
    done = None
    for line in resp.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data:"):
            continue
        try:
            ev = json.loads(line[5:])
        except ValueError:
            continue
        if "delta" in ev:
            reply_chunks.append(ev["delta"])
        elif ev.get("done"):
            done = ev
    if done and done.get("reply") is not None:
        return done["reply"], done
    return "".join(reply_chunks), done


def build_markdown(meta, rounds):
    out = []
    out.append(f"# {meta['title']} · 自动测试走查")
    out.append("")
    out.append(f"- 时间：{meta['time']}")
    out.append(f"- 角色：{'、'.join(meta['cast'])}")
    out.append(f"- 场景：{meta['scene']}")
    out.append(f"- 模型：{meta['model_note']}")
    out.append(f"- 轮数：{len(rounds)}")
    out.append("")
    for i, rd in enumerate(rounds, 1):
        heading = "## 结局" if rd.get("ending") else f"## 第 {i} 轮"
        out.append(heading)
        out.append("")
        out.append("**环境扰动（导演 / 你）：**")
        out.append("")
        out.append(rd["directive"])
        out.append("")
        out.append("**引擎生成：**")
        out.append("")
        out.append(rd["reply"])
        out.append("")
        flags = []
        if rd.get("present_violation"):
            flags.append("⚠ present 违例（已剥离非在场角色）")
        if rd.get("notes"):
            flags.append(f"备注：{rd['notes']}")
        if flags:
            out.append("> " + " ｜ ".join(flags))
            out.append("")
    out.append("---")
    out.append("")
    out.append("_由 群像弈（Personae）自动化测试套件生成。_")
    return "\n".join(out)


def run_playthrough(base_url=BASE_DEFAULT, cast=None, scene=None, arc=None,
                    runs_dir=None, title=DEFAULT_TITLE, model_note=DEFAULT_MODEL_NOTE,
                    keep_session=False):
    """跑完一整轮走查并保存 markdown。返回 (out_path, rounds)。

    - 自动建会话、按 arc 逐轮推进、解析 SSE 取 reply 与 done 载荷
    - 把每轮"环境扰动 + 引擎生成"写入 tests/runs/<时间戳>_<title>.md
    - 默认跑完删除会话（keep_session=True 则保留以便 UI 继续）
    """
    cast = cast or fetch_cast(base_url)
    scene = scene or DEFAULT_SCENE
    arc = arc or build_arc(cast)

    # 不传 cast：v2.1.1 起名册由后端按剧本取全量（引擎不接受部分登场）。
    new = requests.post(base_url + "/api/session/new",
                        json={"scene": scene}, timeout=30).json()
    sid = new["session"]
    rounds = []
    try:
        for step in arc:
            directive = step.get("directive", "")
            try:
                reply, done = _act(base_url, sid, directive)
            except Exception as exc:  # 单轮失败不中断整轮走查
                reply, done = f"[调用失败：{exc}]", None
            rounds.append({
                "directive": directive or "（延续当前情境自然推演）",
                "reply": reply,
                "ending": step.get("ending", False),
                "notes": step.get("notes", ""),
                "present_violation": (done or {}).get("present_violation"),
                "present": (done or {}).get("snapshot", {}).get("present", []),
            })
    finally:
        if not keep_session:
            try:
                requests.delete(base_url + f"/api/session/{sid}", timeout=10)
            except Exception:
                pass

    meta = {
        "title": title, "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "cast": cast, "scene": scene, "model_note": model_note,
    }
    md = build_markdown(meta, rounds)

    runs_dir = Path(runs_dir) if runs_dir else (Path(__file__).parent / "runs")
    runs_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = runs_dir / f"{ts}_{title}.md"
    out_path.write_text(md, encoding="utf-8")
    return out_path, rounds
