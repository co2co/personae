"""首次运行播种（store._seed_examples）链路守护测试。

背景：examples/ 目录是「随包官方 demo」的唯一载体——package.py 白名单保留它、
git 跟踪它，而运行态 data/characters、data/worlds 被排除出包。新装用户解压后
这两个目录为空，靠 _seed_examples() 从 examples/ 播种，才能开箱即有 demo 剧本。

本测试锁死这条链路的契约，防止两类静默回归：
  1. 误删 examples/ 目录 → 新用户拿到空引擎（demo 消失）。
  2. 误删 _seed_examples 的调用点 → 播种机制失效。

全部走隔离的 store.DATA_DIR / EXAMPLES_DIR（临时目录），不碰真实 data/、不调 LLM。
"""
import sys
from pathlib import Path

import pytest

ENGINE = Path(__file__).resolve().parent.parent / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

import store  # noqa: E402


@pytest.fixture
def data(tmp_path, monkeypatch):
    """隔离 store 数据目录；EXAMPLES_DIR 默认指向 data/examples（可被用例改写）。"""
    d = tmp_path / "data"
    (d / "characters").mkdir(parents=True)
    (d / "worlds").mkdir(parents=True)
    monkeypatch.setattr(store, "DATA_DIR", d)
    monkeypatch.setattr(store, "EXAMPLES_DIR", d / "examples")
    store._cache.clear()
    yield d
    store._cache.clear()


def _make_examples(monkeypatch, data):
    """在 examples/ 下铺一套 demo（1 世界书 + 2 角色卡），并让 EXAMPLES_DIR 指向它。"""
    ex = data / "examples"
    (ex / "characters").mkdir(parents=True)
    (ex / "worlds").mkdir(parents=True)
    (ex / "worlds" / "示例世界.json").write_text(
        '{"name": "示例世界", "entries": [{"name": "x", "content": "设定"}]}',
        encoding="utf-8",
    )
    (ex / "characters" / "示例甲.json").write_text(
        '{"name": "示例甲", "world": "示例世界"}', encoding="utf-8",
    )
    (ex / "characters" / "示例乙.json").write_text(
        '{"name": "示例乙", "world": "示例世界"}', encoding="utf-8",
    )
    monkeypatch.setattr(store, "EXAMPLES_DIR", ex)
    return ex


# ---------------------------------------------------------------------------
# 1. 播种主链路：examples 有内容 + 运行态空 → 播种成功
# ---------------------------------------------------------------------------

def test_seed_copies_demo_when_runtime_empty(data, monkeypatch):
    _make_examples(monkeypatch, data)
    # 触发播种（list_characters 内部调 _seed_examples）
    chars = store.list_characters()
    worlds = store.list_worlds()
    assert "示例甲" in chars and "示例乙" in chars
    assert "示例世界" in worlds


def test_seed_is_idempotent_no_overwrite(data, monkeypatch):
    """用户已有私人剧本（运行态非空）时，播种整份跳过、不覆盖用户文件。"""
    _make_examples(monkeypatch, data)
    # 用户在运行态先建了私人世界/角色
    store.save_world("私人世界", [{"name": "a", "content": "我的"}])
    store.save_card("私人角", {"name": "私人角", "world": "私人世界"})
    # 触发播种：因运行态非空，examples 里的 demo 不应被拷入
    store.list_characters()
    worlds = store.list_worlds()
    assert "私人世界" in worlds
    assert "示例世界" not in worlds, "运行态非空时不得再播种 demo"


def test_seed_copies_world_and_characters_into_data(data, monkeypatch):
    """播种后 demo 文件确实落在运行态 data/{characters,worlds}/ 下（物理文件存在）。"""
    _make_examples(monkeypatch, data)
    store.list_characters()
    assert (data / "characters" / "示例甲.json").exists()
    assert (data / "worlds" / "示例世界.json").exists()


# ---------------------------------------------------------------------------
# 2. 播种触发点：list_characters / list_worlds 必须带 _seed_examples 调用
# ---------------------------------------------------------------------------

def test_list_characters_triggers_seed(data, monkeypatch):
    """list_characters 必须触发播种——这是「开箱即有 demo」的入口。"""
    _make_examples(monkeypatch, data)
    # 不手动调 _seed_examples，直接 list，应已包含 demo
    assert "示例甲" in store.list_characters()


def test_list_worlds_triggers_seed(data, monkeypatch):
    """list_worlds 同样触发播种。"""
    _make_examples(monkeypatch, data)
    assert "示例世界" in store.list_worlds()


# ---------------------------------------------------------------------------
# 3. examples 目录缺失的哨兵：安全跳过（不崩溃），但必须被显式认知
# ---------------------------------------------------------------------------

def test_seed_noop_when_examples_dir_missing(data, monkeypatch):
    """examples 目录不存在时 _seed_examples 安全跳过、不抛错。

    这是「demo 消失」的哨兵场景——若有人误删 examples/，新用户只会静默拿到空引擎，
    而不会报错。本用例锁死「安全跳过」这一行为本身，配合 package.py 白名单守护
    （test_universality 的 _DISTRIB_WHITELIST）共同防误删。
    """
    monkeypatch.setattr(store, "EXAMPLES_DIR", data / "不存在的目录")
    assert store.list_characters() == []
    assert store.list_worlds() == []


# ---------------------------------------------------------------------------
# 4. 打包口径守护：examples 是唯一随包 demo 白名单
# ---------------------------------------------------------------------------

def test_examples_dir_is_package_whitelist():
    """examples/ 必须仍在分发包白名单里（package.py 排除 data/characters、data/worlds，
    只保留 data/examples/）。锁死「随包 demo」口径不被悄悄推翻。"""
    # 读取 package.py 的排除集合，断言 examples 不在排除项、且 data/characters、data/worlds 在
    import importlib.util
    pkg_path = Path(__file__).resolve().parent.parent / "package.py"
    spec = importlib.util.spec_from_file_location("_pkg", pkg_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    excluded = mod.EXCLUDE_SUBPATHS
    # examples 不得被排除（白名单）
    assert "data/examples" not in excluded
    assert not any("data/examples" == sp or "data/examples" in sp for sp in excluded)
    # 运行态私人数据必须被排除（demo 的种子源才进包）
    assert "data/characters" in excluded
    assert "data/worlds" in excluded
