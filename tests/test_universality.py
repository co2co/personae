"""普适性红线护栏：测试层与文档层不得绑定任何具体剧本（角色名 / 题材词）。

背景（TODO S5）：引擎面向任意剧本，但测试层曾硬编码已删剧本的角色名并直接
store.load_card() 读磁盘卡组，换剧本即全红。本文件把该红线固化为自动断言，
任何人新写测试时再引入具体剧本名会当场红。

覆盖：
  1. tests/*.py 不得出现历史剧本角色名与题材词（护栏黑名单本身所在文件豁免）。
  2. tests/ 不得在运行期读磁盘剧本目录（data/characters、data/worlds）。
  3. 引擎源码（engine/*.py）不得硬编码具体角色名。
"""

import re
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
ENGINE_DIR = TESTS_DIR.parent / "engine"

# 历史已删剧本的角色名 + 题材词。引擎面向任意剧本，这些词一个都不该出现在
# 测试与引擎源码里（worldbook-guide.md 等教学文档另由 S4 处理，不在本文件范围）。
BANNED = [
    # 剧本一（丧尸末日 / 客服部之夜）
    "老周", "高洋", "林晚", "苏曼", "阿杰",
    "方哲", "陈默", "林瑶", "周凯",
    # 剧本二（早期 demo）
    "陆衡", "林清", "王秀兰", "王晨",
    "陈锋", "夏雨",
    "林梦雅", "周牧野", "林梦琪", "林泽宇",
    "老高", "李想", "周晓杰",
    "苏晚", "顾庭深", "林见秋", "许照",
    # 当前随包 demo（属私人/示例数据，测试层同样不应绑定）
    "沈川", "周岚", "周子航", "林小满",
    # 题材词
    "丧尸", "末日", "避难所", "尸群",
]

# 护栏自身所在文件：黑名单必须写在这里，故豁免
GUARD_FILES = {"test_universality.py"}
# test_intimacy_scale.py 亦持有黑名单（校验提示词不含具体名），属正当引用
ALLOW_FILES = GUARD_FILES | {"test_intimacy_scale.py"}


def _py_files():
    return [p for p in TESTS_DIR.rglob("*.py") if p.name not in ALLOW_FILES]


def test_tests_have_no_hardcoded_character_or_genre_names():
    offenders = []
    for p in _py_files():
        text = p.read_text(encoding="utf-8")
        for word in BANNED:
            if word in text:
                offenders.append(f"{p.relative_to(TESTS_DIR)} 含「{word}」")
    assert not offenders, "测试层出现具体剧本名/题材词：\n" + "\n".join(offenders)


def test_tests_do_not_read_disk_scripts():
    """测试不得在运行期读磁盘剧本目录（data/characters、data/worlds）。

    允许 import store 后 monkeypatch store.xxx；禁止的是把磁盘路径当数据源。
    """
    pattern = re.compile(r"""DATA_DIR\s*/\s*["'](characters|worlds)["']""")
    offenders = []
    for p in _py_files():
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                offenders.append(f"{p.relative_to(TESTS_DIR)}:{i} {line.strip()}")
    assert not offenders, "测试直读磁盘剧本目录：\n" + "\n".join(offenders)


def test_engine_source_has_no_hardcoded_character_names():
    """引擎源码零具体角色名（引擎普适性红线的源头防线）。"""
    offenders = []
    for p in ENGINE_DIR.glob("*.py"):
        text = p.read_text(encoding="utf-8")
        for word in BANNED:
            if word in text:
                offenders.append(f"{p.name} 含「{word}」")
    assert not offenders, "引擎源码出现具体剧本名/题材词：\n" + "\n".join(offenders)


def test_neutral_placeholders_available():
    """护栏自身依赖 tests/fixtures.py 的中性占位，别把它删了。"""
    import fixtures
    assert fixtures.NAMES == ["角色甲", "角色乙", "角色丙", "角色丁"]
    card = fixtures.make_card("角色甲")
    for key in ("name", "description", "personality", "core_desire",
                "core_fear", "short_goal", "relations"):
        assert key in card, f"make_card 缺字段 {key}"
