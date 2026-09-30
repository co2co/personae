"""走查驱动 + markdown 落盘。

复用引擎 HTTP API，按脚本化的"环境扰动弧"逐轮推进，把每轮
「你（导演）发过去的环境扰动」与「引擎生成的内容」写入
tests/runs/<时间戳>_<剧本>.md，直到剧本 ending（弧末标记）。

纯 HTTP，不依赖引擎内部模块；可作为库被 pytest 调用，也可独立运行
（见 run_playthrough.py）。
"""

import json
import datetime
from pathlib import Path

import requests

BASE_DEFAULT = "http://127.0.0.1:5000"
DEFAULT_CAST = ["老周", "林晚", "阿杰", "苏曼", "高洋"]
DEFAULT_SCENE = "城郊便利店后仓，卷帘门紧闭，门外尸群持续抓挠"
DEFAULT_TITLE = "末日丧尸生存"
DEFAULT_MODEL_NOTE = "tencent/Hy4-preview（真实 LLM）"

# 脚本化环境扰动弧：驱动故事走向结局。最后一步 ending=True 标记为结局。
# 每一步的 directive 即"你"以环境推手身份注入的扰动；notes 仅作走查备注。
DEFAULT_ARC = [
    {"directive": "老周清点后仓物资，分配守夜班次，定下谁都不许私自出门的规矩。",
     "notes": "建立秩序，定调主心骨"},
    {"directive": "苏曼压低声音说，城东避难所可能还有活人，她想冒险出去找女儿。",
     "notes": "埋下寻女目标"},
    {"directive": "林晚替高洋换药，拆开绷带时，发现他小臂有一圈咬伤。",
     "notes": "触发高洋秘密曝光"},
    {"directive": "阿杰发现自己私藏的罐头被翻出，他反手拿高洋的咬伤把柄，逼林晚就范。",
     "notes": "把柄胁迫 → NSFW 机会"},
    {"directive": "门外尸群猛撞卷帘门，门轴开始变形，随时会破。",
     "notes": "升级威胁"},
    {"directive": "老周当机立断：趁尸群集中撞门，带所有人从后窗突围成撤离队形，目标城东。",
     "notes": "关键决策"},
    {"directive": "破门瞬间，队伍冲入尸群，老周断后，苏曼拼命拉住女儿的方向——",
     "notes": "高潮，逼近结局"},
    {"directive": "天亮时，幸存者跌跌撞撞踏上通往城东的路，身后的便利店只剩一道门框。",
     "ending": True, "notes": "结局"},
]

# 独立的 NSFW 验证弧：2 人私密脆弱情境，强驱动「满机会」，用于确认引擎真的放开并写出越线叙事。
# 每条扰动都带 ALONE（独处/两人）+ DEFENSE_DOWN（疲惫/软弱/靠近）触发词，确保机会等级维持满机会。
NSFW_CAST = ["林晚", "阿杰"]
NSFW_SCENE = "后仓角落，油灯将熄，老周和高洋已沉沉睡去，只剩林晚和阿杰两人"
NSFW_ARC = [
    {"directive": "夜深，老周和高洋都睡着了，后仓只剩林晚和阿杰守着将熄的油灯。阿杰在撞门时擦破了胳膊，疼得厉害，疲惫地靠在林晚肩头，两人独处。",
     "notes": "独处+虚弱 → 满机会，私密情境建立"},
    {"directive": "林晚低头看着靠在自己肩上的阿杰，指尖无意识地抚过他擦伤的胳膊；两人独处，油灯将熄，她靠近了些，呼吸落在他颈侧。",
     "notes": "升温，身体接触"},
    {"directive": "油灯彻底熄灭，后仓里只剩林晚和阿杰两人独处，再无旁人；阿杰疲惫地伸手把林晚拉得更近——",
     "ending": True, "notes": "高潮，越线"},
]


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
        if rd.get("opportunity"):
            flags.append(f"机会等级={rd['opportunity']}")
        nsfw = rd.get("nsfw") or {}
        if nsfw:
            flags.append(f"NSFW={'解锁' if nsfw.get('intimate') else '受限'}"
                         f"（{nsfw.get('reason', '')}）")
        if rd.get("present_violation"):
            flags.append("⚠ present 违例（已剥离非在场角色）")
        if rd.get("notes"):
            flags.append(f"备注：{rd['notes']}")
        if flags:
            out.append("> " + " ｜ ".join(flags))
            out.append("")
    out.append("---")
    out.append("")
    out.append("_由 ST-Lite 自动化测试套件生成。_")
    return "\n".join(out)


def run_playthrough(base_url=BASE_DEFAULT, cast=None, scene=None, arc=None,
                    runs_dir=None, title=DEFAULT_TITLE, model_note=DEFAULT_MODEL_NOTE,
                    keep_session=False):
    """跑完一整轮走查并保存 markdown。返回 (out_path, rounds)。

    - 自动建会话、按 arc 逐轮推进、解析 SSE 取 reply 与 done 载荷
    - 把每轮"环境扰动 + 引擎生成"写入 tests/runs/<时间戳>_<title>.md
    - 默认跑完删除会话（keep_session=True 则保留以便 UI 继续）
    """
    cast = cast or DEFAULT_CAST
    scene = scene or DEFAULT_SCENE
    arc = arc or DEFAULT_ARC

    new = requests.post(base_url + "/api/session/new",
                        json={"cast": cast, "scene": scene}, timeout=30).json()
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
                "opportunity": (done or {}).get("opportunity"),
                "present_violation": (done or {}).get("present_violation"),
                "present": (done or {}).get("snapshot", {}).get("present", []),
                "nsfw": (done or {}).get("nsfw"),
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
