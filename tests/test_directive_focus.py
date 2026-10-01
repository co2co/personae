"""导演指令焦点对齐验证（集成，需真实 LLM，标记 integration）。

验证三处修复的联合效果：
  1. 环境扰动指向「离开的人」（去下水道侦察）时：
     - 离开者不得被静默移出在场名单（Fix 3：scene.apply 硬性保护）；
     - 叙事焦点应落在点名角色（老周/高洋）上，出现其段落，而非被满机会带偏去写留下的人的性爱。
  2. 环境扰动停留在「满机会的人」（林晚/阿杰）时：
     - 叙事应围绕该角色展开 NSFW 内容（越线/亲密描写落地）。

全程用 app.test_client 自包含运行，不依赖外部服务；每个用例结束清理其会话目录。
"""

import json
import shutil
import sys
from pathlib import Path

# 引擎模块位于项目根的 engine/ 目录
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "engine"))

import pytest

import app as app_module
import memory as _memory
import director as _director

client = app_module.app.test_client()

CAST = ["老周", "高洋", "林晚", "阿杰"]
SESSIONS_DIR = Path(_ROOT / "engine" / "data" / "sessions")

# 身体亲密接触标记（取自 director.BODY_MID/BODY_STRONG），用于断言 NSFW 真的落到叙事
_INTIMACY = list(_director.BODY_MID) + list(_director.BODY_STRONG)


def _collect_reply(resp):
    """消费 /api/act 的 SSE 流，返回 (完整回复文本, done 事件里的机会等级)。"""
    chunks, full, opp = [], None, None
    for raw in resp.response:
        line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[len("data:"):].strip()
        try:
            obj = json.loads(payload)
        except Exception:
            continue
        if "delta" in obj:
            chunks.append(obj["delta"])
        if obj.get("done"):
            full = obj.get("reply")
            opp = obj.get("opportunity")
    return (full if full is not None else "".join(chunks)), opp


def _new_session():
    r = client.post("/api/session/new", json={"cast": CAST, "scene": "废弃仓库"})
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.get_json()["session"]


def _cleanup(sid):
    """可靠删除测试会话目录（Windows 下文件句柄可能未即时释放，重试避免静默残留）。"""
    import time as _t
    target = SESSIONS_DIR / sid
    for _ in range(5):
        try:
            shutil.rmtree(target)
            return
        except Exception:
            _t.sleep(0.3)


def _set_full_opportunity(sid):
    """把关系写成满机会（模拟已确立的亲密关系），复现“全场满机会”前提。"""
    snap = _memory.load(sid)
    snap["relations"]["林晚 → 阿杰"] = "恋人，亲密无间"
    _memory.save(sid, snap)


@pytest.mark.integration
@pytest.mark.slow
def test_directive_focus_on_leavers():
    """扰动指向离开的人：离开者须仍在场，且叙事须呈现其段落。"""
    sid = _new_session()
    try:
        _set_full_opportunity(sid)

        directive = "老周和高洋来到下水道，开始向深处侦察"
        resp = client.post("/api/act", json={"session": sid, "input": directive})
        assert resp.status_code == 200, resp.get_data(as_text=True)
        reply, opp = _collect_reply(resp)

        # Fix 3 确定性断言：纯地点移动不得移除在场者
        present = _memory.load(sid).get("present", [])
        assert "老周" in present and "高洋" in present, \
            f"Fix3 失效：离开者被移出在场名单 -> {present}"

        # Fix 2 断言：指令点名角色须出场
        assert "老周" in reply and "高洋" in reply, \
            f"焦点未落在点名角色：reply 前200字={reply[:200]}"

        # 软性观察：满机会前提 + 焦点在离开者，不应整段都是留下的人的性爱
        nsfw_hit = [w for w in _INTIMACY if w in reply]
        print(f"\n[焦点-离开者] 机会等级={opp} | 在场={present}")
        print(f"[焦点-离开者] 亲密标记命中={nsfw_hit or '无'}")
        print(f"[焦点-离开者] reply:\n{reply[:1800]}")
        # 不硬性禁止 NSFW（满机会允许），但要求点名角色确为焦点
    finally:
        _cleanup(sid)


@pytest.mark.integration
@pytest.mark.slow
def test_directive_focus_on_full_opportunity_pair():
    """扰动停留在满机会的人：应围绕该角色展开 NSFW 叙事。"""
    sid = _new_session()
    try:
        _set_full_opportunity(sid)

        directive = "林晚和阿杰留在仓库里，两人继续之前的缠绵，仓库里只剩他们两个"
        resp = client.post("/api/act", json={"session": sid, "input": directive})
        assert resp.status_code == 200, resp.get_data(as_text=True)
        reply, opp = _collect_reply(resp)

        assert "林晚" in reply and "阿杰" in reply, \
            f"满机会焦点角色未出场：reply 前200字={reply[:200]}"

        hit = [w for w in _INTIMACY if w in reply]
        assert hit, f"满机会焦点下未生成任何身体亲密描写：reply 前200字={reply[:200]}"

        print(f"\n[焦点-满机会] 机会等级={opp}")
        print(f"[焦点-满机会] 亲密标记命中={hit}")
        print(f"[焦点-满机会] reply:\n{reply[:1800]}")
    finally:
        _cleanup(sid)
