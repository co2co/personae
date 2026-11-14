"""首次运行播种（store._seed_examples）链路守护测试。

背景（2026-11-15 口径变更，simon 定）：**分发包不携带任何剧本数据**——`data/examples/`
既不进版本库（`.gitignore`）、也不进分发包（`package.py` 排除 + 出包后硬校验）。
`_seed_examples()` 因此只服务本机开发：`sync_drama.py install` 已不再写 `data/examples/`
（2026-11-15 同步收口），该目录没有生成源了——若本机要给 `_seed_examples` 喂料，需手工放置
世界书与角色卡，或用旧版备份目录里的副本。

本测试锁死三件事，防止三类静默回归：
  1. **播种契约**：空库才播种、按名去重、不覆盖用户已有文件、重复调用不重复。
  2. **缺目录安全早退**：分发包就是「examples 不存在」这个形态，播种必须静默跳过而不崩。
  3. **红线口径**：examples 必须在打包排除项里，且必须在 .gitignore 里（改动会当场红）。

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

    这是**分发包的常态**（2026-11-15 起包内无 examples），也是「本机误删」的哨兵场景。
    两个方向都要守住：不能崩，也不能悄悄造出半套数据。
    """
    monkeypatch.setattr(store, "EXAMPLES_DIR", data / "不存在的目录")
    assert store.list_characters() == []
    assert store.list_worlds() == []


# ---------------------------------------------------------------------------
# 4. 红线守护：examples 既不出包、也不入库
# ---------------------------------------------------------------------------

def test_examples_dir_is_excluded_from_package():
    """红线（2026-11-15 simon 定）：随包 demo 不得进分发包。

    本条断言此前是**反的**——原本要求「examples 必须在包内白名单」。口径改成
    「分发物只含引擎本体，剧本数据一律不带」后翻转为排除断言，防止有人按旧注释改回去。
    """
    import importlib.util
    pkg_path = Path(__file__).resolve().parent.parent / "package.py"
    spec = importlib.util.spec_from_file_location("_pkg", pkg_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    excluded = mod.EXCLUDE_SUBPATHS
    # demo 必须被排除
    assert "data/examples" in excluded
    # 运行态私人数据同样必须被排除
    assert "data/characters" in excluded
    assert "data/worlds" in excluded


def test_examples_dir_is_gitignored():
    """红线另一半：examples 不进版本库（推送里也不得有剧本数据）。

    只排包不够——仓库是公开的，`git ls-remote` 就能看到全部历史。故 .gitignore 必须有
    这一条；若有人重新 `git add engine/data/examples`，本条会红。
    """
    root = Path(__file__).resolve().parent.parent
    lines = (root / ".gitignore").read_text(encoding="utf-8").splitlines()
    entries = [ln.strip().rstrip("/") for ln in lines if ln.strip() and not ln.strip().startswith("#")]
    assert "/engine/data/examples" in entries
