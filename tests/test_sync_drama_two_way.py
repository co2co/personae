"""sync_drama.collect_divergences 的「两方」口径守护。

背景（2026-11-15 分发红线）：`engine/data/examples/` 撤出分发包与版本库后，
install 不再写它、包内也不含它。若比对仍按三方（作者源/运行态/demo）走，
打包就每次都得 `--skip-sync-check` 绕过，真正该拦的「改了作者源忘记 install」
被一起跳过——守卫等于失效。

本测试锁死两方口径的两条边界：
  1. 作者源 ↔ 运行态有差异 → 必须报出来（守卫仍在工作）；
  2. 仅 examples/ 与作者源不一致 → 必须不报（demo 已与分发无关）。

全部走临时目录（monkeypatch ROOT/AUTHOR/运行态路径），不碰真实 data/ 与 dramas/，
不调 LLM。剧本名与角色名一律占位，不含题材词。
"""

import importlib.util
import json
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "_sync_drama_under_test",
    Path(__file__).resolve().parent.parent / "scripts" / "sync_drama.py",
)
sync_drama = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(sync_drama)


DRAMA = "样例剧本"
NAMES = ("甲", "乙")


def _write(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _seed(author: Path, worlds: Path, chars: Path) -> dict:
    """铺一份「作者源与运行态完全一致」的最小剧本，返回世界书对象。"""
    world = {"name": DRAMA, "entries": []}
    _write(author / DRAMA / "world.json", world)
    _write(worlds / f"{DRAMA}.json", world)
    for n in NAMES:
        card = {"name": n, "world": DRAMA}
        _write(author / DRAMA / "characters" / f"{n}.json", card)
        _write(chars / f"{n}.json", card)
    return world


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """把 sync_drama 的四条路径全指向临时目录。"""
    author = tmp_path / "dramas"
    worlds = tmp_path / "engine" / "data" / "worlds"
    chars = tmp_path / "engine" / "data" / "characters"
    for d in (author / DRAMA / "characters", worlds, chars):
        d.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(sync_drama, "ROOT", tmp_path)
    monkeypatch.setattr(sync_drama, "AUTHOR", author)
    monkeypatch.setattr(sync_drama, "RUNTIME_WORLDS", worlds)
    monkeypatch.setattr(sync_drama, "RUNTIME_CHARS", chars)
    return author, worlds, chars, tmp_path


# ---------------------------------------------------------------------------
# 1. 一致基线
# ---------------------------------------------------------------------------

def test_consistent_returns_no_issue(sandbox):
    author, worlds, chars, _ = sandbox
    _seed(author, worlds, chars)
    drama, issues = sync_drama.collect_divergences()
    assert drama == DRAMA
    assert issues == []


# ---------------------------------------------------------------------------
# 2. 两方必须报：作者源与运行态分叉（守卫不能因改口径而失效）
# ---------------------------------------------------------------------------

def test_author_world_edit_without_install_is_reported(sandbox):
    author, worlds, chars, _ = sandbox
    world = _seed(author, worlds, chars)
    world["entries"].append({"keys": ["x"], "content": "改了作者源没 install"})
    _write(author / DRAMA / "world.json", world)

    _, issues = sync_drama.collect_divergences()
    assert len(issues) == 1
    assert "世界书不一致" in issues[0]
    assert "运行态" in issues[0]


def test_missing_runtime_card_is_reported(sandbox):
    author, worlds, chars, _ = sandbox
    _seed(author, worlds, chars)
    (chars / "甲.json").unlink()

    _, issues = sync_drama.collect_divergences()
    assert len(issues) == 1
    assert "角色卡缺失（运行态）" in issues[0]
    assert "甲.json" in issues[0]


def test_extra_runtime_card_is_reported(sandbox):
    author, worlds, chars, _ = sandbox
    _seed(author, worlds, chars)
    _write(chars / "丙.json", {"name": "丙", "world": DRAMA})

    _, issues = sync_drama.collect_divergences()
    assert len(issues) == 1
    assert "多余" in issues[0]
    assert "丙.json" in issues[0]


def test_author_card_edit_without_install_is_reported(sandbox):
    author, worlds, chars, _ = sandbox
    _seed(author, worlds, chars)
    _write(author / DRAMA / "characters" / "乙.json", {"name": "乙", "world": DRAMA, "x": 1})

    _, issues = sync_drama.collect_divergences()
    assert len(issues) == 1
    assert "角色卡不一致" in issues[0]
    assert "乙" in issues[0]


# ---------------------------------------------------------------------------
# 3. demo 目录必须被忽略（本次改动的核心回归点）
# ---------------------------------------------------------------------------

def test_examples_dir_divergence_is_ignored(sandbox):
    """examples/ 里塞满与作者源不一致的内容，两方口径下必须一条都不报。

    这些内容以前会各报一条「世界书不一致 / 角色卡缺失 / 角色卡不一致」，
    逼得打包加 --skip-demo-check；撤出分发后它们与出包无关。
    """
    author, worlds, chars, tmp = sandbox
    _seed(author, worlds, chars)

    ex_worlds = tmp / "engine" / "data" / "examples" / "worlds"
    ex_chars = tmp / "engine" / "data" / "examples" / "characters"
    _write(ex_worlds / f"{DRAMA}.json", {"name": DRAMA, "entries": [{"content": "旧版本"}]})
    _write(ex_chars / "甲.json", {"name": "甲", "world": DRAMA, "stale": True})
    _write(ex_chars / "已退役.json", {"name": "已退役", "world": DRAMA})

    # 别的剧本的残留也一并忽略
    _write(ex_worlds / "另一部.json", {"name": "另一部", "entries": []})

    _, issues = sync_drama.collect_divergences()
    assert issues == []


def test_install_no_longer_populates_examples(sandbox, capsys):
    """install 只铺运行态，不再生成 examples/（否则僵尸目录会被反复续命）。"""
    author, worlds, chars, tmp = sandbox
    _seed(author, worlds, chars)
    # 破坏运行态，确认 install 真的写了
    (worlds / f"{DRAMA}.json").unlink()
    (chars / "乙.json").unlink()

    rc = sync_drama._install(DRAMA, do_backup=False)

    assert rc == 0
    assert (worlds / f"{DRAMA}.json").exists()
    assert (chars / "乙.json").exists()
    assert not (tmp / "engine" / "data" / "examples").exists()
    out = capsys.readouterr().out
    assert "作者源 -> 运行态" in out
    assert "demo" not in out


# ---------------------------------------------------------------------------
# 4. 打包脚本入口：新旧 flag 名都要能认
# ---------------------------------------------------------------------------

def test_package_accepts_both_skip_flags():
    """--skip-sync-check 是正名，--skip-demo-check 保留兼容（旧命令与肌肉记忆）。"""
    import argparse
    import re

    src = (Path(__file__).resolve().parent.parent / "package.py").read_text(encoding="utf-8")
    assert "--skip-sync-check" in src
    assert "--skip-demo-check" in src
    # 两个名字指向同一 dest，避免出现「两个独立开关只认一个」的静默退化
    m = re.search(r'add_argument\(\s*"--skip-sync-check",\s*"--skip-demo-check",\s*dest="(\w+)"', src)
    assert m, "两个 flag 名必须并存且共用一个 dest"
    assert m.group(1) == "skip_sync_check"
    # 确认 argv 层面确实能解析（argparse 只是被 __main__ 包裹，规则可单独复现）
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-sync-check", "--skip-demo-check", dest="skip_sync_check", action="store_true")
    assert ap.parse_args(["--skip-sync-check"]).skip_sync_check is True
    assert ap.parse_args(["--skip-demo-check"]).skip_sync_check is True
    assert ap.parse_args([]).skip_sync_check is False
