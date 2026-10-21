"""亲密/性内容尺度「不预设」回归测试（2026-10-21 下架，对齐 v0.29.0）。

对齐 2026-10-21 simon 裁决：引擎**不预设**亲密/性内容的尺度基调。
- 删除铁律⑧ 尺度措辞（身临其境/正面写实/不预设上限/不强制克制）与时机层
  （提前引入/硬写），不再由 prompter 恒定注入。
- 停止随新建/导入剧本播种「亲密描写标准」世界书条目（见 test_standard_entry.py）。
- 尺度完全交回各剧本自己的世界书与剧情推进决定。

**唯一保留**：未成年法律硬红线（prompter._LAWS_PREFIX「己、法律底线」）仍是引擎级、
永远生效、不可由世界书覆盖。本文件的红线断言锁定这一边界。

回滚蓝本：v0.29.0 同款下架；v1.2.7 恢复版（_LAW8_DEFAULT 尺度+时机层）见
git tag / _backup_offshelf_nsfw_20261021/。

普适性红线：全文件只用中性占位，不绑定任何具体剧本角色名或题材词。
"""
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

import prompter  # noqa: E402
from fixtures import A, B  # noqa: E402

MIN_SNAP = {
    "scene": {"round": 1, "place": "某处", "time": "夜", "weather": ""},
    "relations": {}, "ledger": [], "secrets": [],
    "goals": {}, "present": [A, B],
}
CARDS = {n: {"name": n} for n in [A, B]}


def _system_prompt(snap=None, cards=None):
    msgs = prompter.build_session(
        cards or CARDS, "", [], snap or MIN_SNAP)
    return msgs[0]["content"]


def test_scale_wording_not_in_engine():
    """尺度措辞（正面写实/不预设上限/不强制克制/身临其境）不再由引擎注入。"""
    sys_p = _system_prompt()
    for word in ("亲密与性描写", "身临其境", "正面写实", "不预设上限", "不强制克制"):
        assert word not in sys_p, "引擎不应预设亲密尺度措辞：%s" % word


def test_timing_layer_not_in_engine():
    """时机层（未推进到亲密时刻前不得提前引入/硬写）不再由引擎注入。"""
    sys_p = _system_prompt()
    assert "提前引入" not in sys_p
    assert "硬写" not in sys_p


def test_law8_symbol_removed():
    """铁律⑧ 尺度层符号（_LAW8_DEFAULT / _law8_override）已从 prompter 移除。"""
    assert not hasattr(prompter, "_LAW8_DEFAULT")
    assert not hasattr(prompter, "_law8_override")


def test_minor_redline_kept_in_engine():
    """未成年法律红线必须始终在引擎层（不可下沉、不可由世界书覆盖）。"""
    sys_p = _system_prompt()
    assert "未成年" in sys_p
    assert "法律底线" in sys_p


def test_minor_redline_global_default():
    """未成年红线是全局默认：不依赖任何角色卡/世界书/秘密，空配置仍须出现。"""
    empty_cards = {n: {} for n in [A, B]}
    empty_snap = {
        "scene": {"round": 1, "place": "", "time": "", "weather": ""},
        "relations": {}, "ledger": [], "secrets": [],
        "goals": {}, "present": [A, B],
    }
    sys_p = _system_prompt(snap=empty_snap, cards=empty_cards)
    assert "未成年" in sys_p


def test_laws_neutral_wording():
    """普适性红线：措辞不得含具体角色名 / 剧本题材词。"""
    sys_p = _system_prompt()
    banned = ["苏晚", "顾庭深", "林见秋", "许照", "方哲", "陈默", "林瑶", "周凯",
              "丧尸", "末日", "庄园", "民宿", "避难所"]
    for b in banned:
        assert b not in sys_p, "提示词出现禁用名/题材词：%s" % b


def test_laws_use_neutral_placeholder_only():
    """铁律本身必须只用中性表述，不含任何专名。"""
    laws = prompter._build_laws()
    for name in [A, B]:
        assert name not in laws, "铁律混入专名：%s" % name
