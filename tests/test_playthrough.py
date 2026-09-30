"""集成走查测试（默认跳过，需 `pytest -m integration`）。

依赖运行中的引擎服务（http://127.0.0.1:5000）+ 真实 LLM。
服务不可达时自动 skip；跑完断言 markdown 已生成且内容含「环境扰动 / 引擎生成」。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest
import requests
import playthrough
import director

BASE = playthrough.BASE_DEFAULT

# 身体亲密接触标记（取自 director.BODY_MID/BODY_STRONG），用于断言 NSFW 真的落到叙事
_INTIMACY_MARKERS = list(director.BODY_MID) + list(director.BODY_STRONG)


@pytest.fixture(scope="module", autouse=True)
def _require_server():
    try:
        requests.get(BASE + "/", timeout=5)
    except Exception:
        pytest.skip("引擎服务未运行，跳过集成走查（启动服务后 `pytest -m integration` 重跑）")


@pytest.mark.integration
@pytest.mark.slow
def test_playthrough_saves_markdown():
    out_path, rounds = playthrough.run_playthrough(base_url=BASE)
    assert out_path.exists(), "走查 markdown 应已生成"
    text = out_path.read_text(encoding="utf-8")
    assert "环境扰动" in text and "引擎生成" in text
    # 实质性校验：每一轮都必须真的生成了内容，且在场名单不能为空
    # （防止此前 scene.apply 把 present 清空、validate_present 把整段回复剥空的回归）
    for i, r in enumerate(rounds, 1):
        content = (r.get("reply") or "").strip()
        assert content, f"第 {i} 轮引擎生成内容为空（回归：present 校验剥空？）"
        assert r.get("present"), f"第 {i} 轮在场名单为空（回归：scene.apply 清空 present）"
        assert not str(content).startswith("[调用失败"), f"第 {i} 轮调用引擎失败：{content}"
    assert len(rounds) == len(playthrough.DEFAULT_ARC)
    assert any(r.get("ending") for r in rounds), "至少一轮应标记为结局"


@pytest.mark.integration
@pytest.mark.slow
def test_nsfw_arc_produces_intimate_content():
    """NSFW 支持度验证：独立的 2 人私密弧，强驱动满机会，断言引擎真的放开并写出越线/亲密叙事。

    此前主走查（末日求生弧）虽然机会等级到满机会，但扰动指令从不把角色推进到私密情境，
    引擎提示词即便强令越线也无从落笔，加上测试没断言 NSFW，导致 NSFW 支持度完全未被验证。
    本测试用专门的私密脆弱弧补上这个盲区。
    """
    out_path, rounds = playthrough.run_playthrough(
        base_url=BASE, cast=playthrough.NSFW_CAST,
        scene=playthrough.NSFW_SCENE, arc=playthrough.NSFW_ARC, title="NSFW验证")
    assert out_path.exists(), "NSFW 走查 markdown 应已生成"
    text = out_path.read_text(encoding="utf-8")
    assert "环境扰动" in text and "引擎生成" in text

    # 1) 至少一轮引擎判定为 intimate（满机会/半步 解锁）——证明 NSFW 门控在真实流程中生效
    intimate_rounds = [r for r in rounds if (r.get("nsfw") or {}).get("intimate")]
    assert intimate_rounds, "NSFW 弧中没有任何一轮被判定为 intimate（满机会/半步 解锁），门控未生效"

    # 2) 实际生成内容含身体亲密接触标记——证明 NSFW 不只是解锁，而是真的落到了叙事
    agg = "\n".join((r.get("reply") or "") for r in rounds)
    hit = [w for w in _INTIMACY_MARKERS if w in agg]
    assert hit, "NSFW 弧生成内容未出现任何身体亲密接触描写（NSFW 未真正触发，仅解锁无产出）"

    # 3) 每轮内容非空 + 在场名单非空（复用主走查的回归护栏）
    for i, r in enumerate(rounds, 1):
        content = (r.get("reply") or "").strip()
        assert content, f"NSFW 第 {i} 轮引擎生成内容为空"
        assert r.get("present"), f"NSFW 第 {i} 轮在场名单为空"

    strong = [w for w in director.BODY_STRONG if w in agg]
    print(f"\n[NSFW 走查] intimate 轮数={len(intimate_rounds)}/{len(rounds)}"
          f" | 亲密标记命中={hit} | 越线级(强)命中={strong or '无'}")
