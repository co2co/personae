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
# 测试与引擎源码里（`static/worldbook-guide.html` 等教学文档另由 S4 处理，
# 不在本文件范围）。
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
# 其余文件亦持有黑名单（校验出厂标准条 / 出厂写手不含具体名与题材词），属正当引用
# 前缀「_」为一次性工具脚本（压测探针等），跑完即删、不入库，绑定真实卡组是它们的用途本身
ALLOW_FILES = GUARD_FILES | {"test_intimacy_scale.py", "test_standard_entry.py",
                             "test_writer_persona.py"}

# ── 引擎非 .py 分发面扫描（与 package.py 排除口径对齐）──
# 引擎源码 .py 已由上面的 test_engine_source_has_no_hardcoded_character_names 覆盖；
# 此处补上「随包但非 .py 的文本文件」（index.html / worldbook-guide.html /
# README / INSTALL / config.json / requirements.txt），把打包后才查的泄漏前移为
# 开发期 pytest 必过项。
# 排除目录（与 package.py EXCLUDE_DIRS 一致，venv 内含大量第三方 .txt/.md）
_DISTRIB_EXCLUDE_DIRS = {"venv", "__pycache__", ".git"}
# 私有数据：不随分发，扫描必须跳过（否则误伤玩家私创/个人 DEMO）
_DISTRIB_PRIVATE_PREFIXES = (
    "data/characters", "data/worlds", "data/sessions",
    "data/state.json", "player-cast",
)
# 官方 demo 白名单：合法题材词（与 package.py 扫黑名单的豁免一致）
_DISTRIB_WHITELIST = ("data/examples/", "static/script-example-guide.html")
# 扫描的文件类型（打包扫描覆盖 .py/.html/.md/.txt/.json；.py 另有专测，此处只扫非 .py）
_DISTRIB_TEXT_SUFFIXES = {".html", ".md", ".txt", ".json"}


def _is_tool_script(rel):
    return rel.startswith("_")


def _py_files():
    out = []
    for p in TESTS_DIR.rglob("*.py"):
        rel = p.relative_to(TESTS_DIR).as_posix()
        if p.name in ALLOW_FILES or _is_tool_script(rel):
            continue
        out.append(p)
    return out


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


def _engine_distrib_text_files():
    """引擎内「随包的非 .py 文本文件」，口径与 package.py 排除规则一致。"""
    out = []
    for p in ENGINE_DIR.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in _DISTRIB_TEXT_SUFFIXES:
            continue
        rel = p.relative_to(ENGINE_DIR).as_posix()
        parts = rel.split("/")
        if any(x in _DISTRIB_EXCLUDE_DIRS for x in parts):
            continue
        if any(rel.startswith(pre) for pre in _DISTRIB_PRIVATE_PREFIXES):
            continue
        if any(w in rel for w in _DISTRIB_WHITELIST):
            continue
        out.append((rel, p))
    return out


def test_engine_distributable_non_py_has_no_hardcoded_names():
    """引擎随包的非 .py 文本文件零具体剧本名/题材词（开发期闸门）。

    把打包后才人工查的泄漏扫描，前移为每次 pytest 必过项，覆盖
    index.html / worldbook-guide.html / README / INSTALL / config.json 等
    （.py 源文件由 test_engine_source_has_no_hardcoded_character_names 覆盖）。
    """
    files = _engine_distrib_text_files()
    # 护栏自检：扫描面不能为空，否则等于没扫
    assert files, "引擎分发面非 .py 文本文件为空，扫描目标可能已被误排除"
    offenders = []
    for rel, p in files:
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for word in BANNED:
            if word in text:
                offenders.append(f"{rel} 含「{word}」")
    assert not offenders, "引擎随包非 .py 文件出现具体剧本名/题材词：\n" + "\n".join(offenders)


def test_neutral_placeholders_available():
    """护栏自身依赖 tests/fixtures.py 的中性占位，别把它删了。"""
    import fixtures
    assert fixtures.NAMES == ["角色甲", "角色乙", "角色丙", "角色丁"]
    card = fixtures.make_card("角色甲")
    for key in ("name", "description", "personality", "core_desire",
                "core_fear", "short_goal", "relations"):
        assert key in card, f"make_card 缺字段 {key}"
