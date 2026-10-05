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

BASE = playthrough.BASE_DEFAULT


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
    assert len(rounds) == len(playthrough.DEFAULT_ARC_TEMPLATE)
    assert any(r.get("ending") for r in rounds), "至少一轮应标记为结局"
