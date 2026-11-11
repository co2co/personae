"""出厂「写法示范·常驻」条目播种测试（常驻 few-shot 示范的引擎内置实现）。

契约：
  1. 新建世界 save_world(name, []) 自动播种「写法示范·常驻」demo 条目。
  2. 该条目标志：demo=True / first_round=False（每轮持续注入），措辞全中性（无专名/题材词）。
  3. 不重复播种：entries 已含「写法示范·常驻」时不再额外插入。
  4. 导入剧本 import_drama 时若模板未自带常驻示范，自动补种（创建+导入都播种）。
  5. 玩家主权：可停用/删除，引擎尊重（仅首建播种，不强制回填）。
"""
import sys
from pathlib import Path

import pytest

ENGINE = Path(__file__).resolve().parent.parent / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

import store  # noqa: E402

EX_NAME = "写法示范·常驻"


@pytest.fixture(autouse=True)
def _isolated_store(tmp_path, monkeypatch):
    data = tmp_path / "data"
    (data / "characters").mkdir(parents=True)
    (data / "worlds").mkdir(parents=True)
    monkeypatch.setattr(store, "DATA_DIR", data)
    monkeypatch.setattr(store, "EXAMPLES_DIR", data / "examples")
    store._cache.clear()
    yield data
    store._cache.clear()


def test_new_world_seeds_example_entry():
    """新建世界自动播种「写法示范·常驻」demo 条目。"""
    store.save_world("新世界", [])
    names = [e["name"] for e in store.load_world("新世界")]
    assert EX_NAME in names


def test_example_entry_has_demo_flags():
    """常驻示范条目标志：demo=True / first_round=False（每轮注入）。"""
    store.save_world("新世界", [])
    ex = next(e for e in store.load_world("新世界") if e["name"] == EX_NAME)
    assert ex.get("demo") is True
    assert ex.get("first_round") is False


def test_example_entry_is_neutral():
    """常驻示范措辞全中性：不含任何剧本专名/题材词，只用角色甲/乙占位。"""
    store.save_world("新世界", [])
    ex = next(e for e in store.load_world("新世界") if e["name"] == EX_NAME)
    content = ex["content"]
    # 题材类别词（只该出现在具体剧本世界书，绝不能出现在引擎默认示范里）
    banned = ["宫", "朝堂", "后宫", "边将", "文官", "宗室", "禁军",
              "名分", "礼制", "账簿", "兵权", "虎符", "勤王", "巫蛊"]
    for w in banned:
        assert w not in content, "常驻示范混入题材词：%s" % w


def test_no_double_seed_when_example_present():
    """entries 已含「写法示范·常驻」时不再额外插入。"""
    existing = {
        "name": EX_NAME, "keys": [], "content": "自定义常驻示范",
        "priority": 60, "enabled": True, "constant": False,
        "position": "before", "depth": None, "secret": False,
        "demo": True, "first_round": False,
    }
    store.save_world("新世界", [existing])
    loaded = [e for e in store.load_world("新世界") if e["name"] == EX_NAME]
    assert len(loaded) == 1
    assert loaded[0]["content"] == "自定义常驻示范"


def test_import_drama_seeds_example():
    """导入剧本时（模板未自带常驻示范）自动补种。"""
    tpl = {
        "world": {"name": "甲", "entries": [{"name": "设定", "keys": [], "content": "c"}]},
        "characters": [],
    }
    store.import_drama("甲", tpl)
    names = [e["name"] for e in store.load_world("甲")]
    assert EX_NAME in names


def test_import_drama_preserves_author_example():
    """导入剧本自带常驻示范时，保留作者版本，不覆盖。"""
    author_example = {
        "name": EX_NAME, "keys": [], "content": "作者自己的常驻示范",
        "priority": 60, "enabled": True, "constant": False,
        "position": "before", "depth": None, "secret": False,
        "demo": True, "first_round": False,
    }
    tpl = {
        "world": {"name": "甲", "entries": [author_example]},
        "characters": [],
    }
    store.import_drama("甲", tpl)
    loaded = [e for e in store.load_world("甲") if e["name"] == EX_NAME]
    assert len(loaded) == 1
    assert loaded[0]["content"] == "作者自己的常驻示范"


def test_user_can_delete_example():
    """玩家可删除常驻示范条，再次保存不复活（仅首建播种）。"""
    store.save_world("新世界", [])
    store.save_world("新世界", [e for e in store.load_world("新世界") if e["name"] != EX_NAME])
    assert all(e["name"] != EX_NAME for e in store.load_world("新世界"))
