"""世界书 depth 修复的端到端验证（不调 LLM，快速）。

背景：2026-10-04 修复前，app.py 把传给 world.scan 的聊天历史截断为
RECENT_FOR_SCAN=4 条，导致条目级 depth>4 形同虚设（被全局 4 轮封顶）。
修复后改为 WORLDBOOK_SCAN_WINDOW=60，depth 在 1..60 内真实可调。

本文件用 app.py 真实窗口常量复现「app 调用 scan」的路径，验证：
  1) 常量护栏：WORLDBOOK_SCAN_WINDOW==60、RECENT_FOR_SCAN==4
  2) 修复前后对比：关键词距末端 7 轮，旧窗口(4)漏、新窗口(60)命中
  3) 扫描窗口上限恰为 60 轮（depth 再大也看不过 60 轮之前）
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))

import world as world_mod
import app as app_mod  # 取真实窗口常量，锁定修复不被回归


def _app_style_scan(entries, full_history, directive="", default_depth=None):
    """复刻 app.py:471-473 的世界书扫描调用（含修复后的窗口截断）。"""
    if default_depth is None:
        default_depth = app_mod.RECENT_FOR_SCAN
    windowed = list(full_history)[-app_mod.WORLDBOOK_SCAN_WINDOW:]
    return world_mod.scan(entries, windowed, directive=directive,
                          default_depth=default_depth, character=None)


def test_worldbook_scan_window_constant_is_60():
    """护栏：窗口常量必须为 60；旧值 4 会让 depth>4 完全失效。"""
    assert app_mod.WORLDBOOK_SCAN_WINDOW == 60
    assert app_mod.RECENT_FOR_SCAN == 4


def test_depth_fix_window_no_longer_capped_at_4():
    """端到端证明修复。

    关键词落在第 5 条（index 4），距 12 轮历史末端 7 轮：
      - 旧逻辑（窗口截断 4）：depth=8 看不到 -> 不触发（复现修复前bug）
      - 修复后（窗口 60）：depth=8 命中 -> 触发
      - 对照：depth=None（默认 4）即便窗口 60 也看不到（距离 7>4）-> 不触发
        （证明是条目自身 depth=8 起作用，而非窗口放宽带来的副作用）
    """
    key = "城东"
    full_history = [f"前{i}" for i in range(4)] + [key] + [f"后{j}" for j in range(7)]  # 长12, key@4
    assert len(full_history) == 12

    entry_d8 = {"keys": [key], "content": "城东庇护所", "enabled": True, "depth": 8}
    entry_default = {"keys": [key], "content": "城东默认", "enabled": True, "depth": None}

    # 旧行为（窗口截断为 4）
    old_windowed = full_history[-app_mod.RECENT_FOR_SCAN:]
    old_hits = world_mod.scan([entry_d8], old_windowed, default_depth=4, character=None)
    assert not old_hits, "旧逻辑(窗口4)应漏掉距末端7轮的depth=8条目"

    # 修复后行为（窗口 60）
    new_hits = _app_style_scan([entry_d8], full_history)
    assert any(key in h["content"] for h in new_hits), \
        "修复后(窗口60)depth=8应命中距末端7轮的关键词"

    # 对照：默认 depth(4) 即便窗口 60 也看不到
    default_hits = _app_style_scan([entry_default], full_history)
    assert not default_hits, "默认depth=4 在距离7时应不触发，证明是条目depth=8起的作用"


def test_depth_effective_cap_at_60():
    """扫描窗口上限恰为 60 轮：关键词在 index 0，depth=100（远超上限）。

      - L=60：窗口=全部 60 条 -> 命中
      - L=70：窗口=最后 60 条(index 10..69) -> 漏掉早期关键词 -> 不命中
    证明上限恰为 60，而非无限（scan 本身无上限，上限由 app.py 截断保证）。
    """
    key = "老据点"
    entry = {"keys": [key], "content": "旧庇护所", "enabled": True, "depth": 100}

    hist60 = [key] + [f"f{i}" for i in range(59)]
    assert len(hist60) == 60
    hit60 = _app_style_scan([entry], hist60)
    assert any("旧庇护所" in h["content"] for h in hit60), "L=60 应命中（窗口=全部60）"

    hist70 = [key] + [f"f{i}" for i in range(69)]
    assert len(hist70) == 70
    hit70 = _app_style_scan([entry], hist70)
    assert not any("旧庇护所" in h["content"] for h in hit70), \
        "L=70 应不命中（窗口上限60，漏掉早期关键词）"
