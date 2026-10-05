"""director 的确定性单元测试（不调 LLM，快速）。

覆盖：validate_present 四类场景 + 举证式归档（_evidence_ok）+ 把柄消除
（_release_handle）。NSFW 机会等级机制已于 v0.8.0 整体废弃，相关用例已移除。

普适性红线：全文件只用中性占位（角色甲/乙/丙/丁）与中性场景词，
不绑定任何具体剧本、角色名或题材词。
"""

import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

import director  # noqa: E402
from fixtures import A, B, C, D  # noqa: E402

PRESENT = [A, B, C]
KNOWN = PRESENT + [D, "环境推手"]


def test_validate_present_no_violation():
    r = f"{A}：清点物资。\n{B}：换药。\n{C}：盯着看。"
    out, v = director.validate_present(r, PRESENT, KNOWN)
    assert v is False and out == r


def test_validate_present_strips_offstage_and_env():
    r = (f"{A}：开门。\n{D}：我来帮你。（已离场不应出现）\n{B}：别信他。\n"
         "环境推手：我悄悄推了一把。\n" + f"{C}：不关我事。")
    out, v = director.validate_present(r, PRESENT, KNOWN)
    assert v is True
    assert D not in out and "环境推手" not in out
    assert A in out and B in out and C in out


def test_validate_present_multiline_block():
    r = f"{A}：说着。\n{D}：第一句。\n第二句续行。\n{B}：回应。"
    out, v = director.validate_present(r, PRESENT, KNOWN)
    assert "第二句续行" not in out
    assert f"{B}：回应" in out


def test_validate_present_narrative_before_block_kept():
    r = f"夜色渐深。\n{D}：溜出去。\n{A}：守夜。"
    out, v = director.validate_present(r, PRESENT, KNOWN)
    assert "夜色渐深" in out and f"{A}：守夜" in out
    assert D not in out


def test_evidence_ok_requires_verbatim_quote():
    """举证必须是正文原文片段：逐字照抄才采信，改写/编造一律丢弃。"""
    reply = f"{A}一把扯开他臂弯的绷带，看见那道发黑的抓痕。"
    assert director._evidence_ok("看见那道发黑的抓痕", reply) is True
    assert director._evidence_ok(f"{A}一把扯开他臂弯的绷带", reply) is True
    # 概括/改写（正文里没有这句）-> 丢弃
    assert director._evidence_ok(f"{A}发现了{B}受伤", reply) is False
    # 凭空编造 -> 丢弃
    assert director._evidence_ok(f"{C}翻出了私藏的物品", reply) is False


def test_evidence_ok_rejects_missing_or_too_short():
    """未举证或举证过短一律丢弃：宁可漏记，不可误记。"""
    reply = f"{A}一把扯开他臂弯的绷带，看见那道发黑的抓痕。"
    assert director._evidence_ok(None, reply) is False
    assert director._evidence_ok("", reply) is False
    assert director._evidence_ok("绷带", reply) is False


def test_no_semantic_wordlists_remain():
    """记录员模式契约：引擎不再持有语义词表，判定只靠举证。

    旧实现用 INFO_VERBS + DISCOVERY_VERBS + secret.keys 做语义判定，
    题材高频词与「看见/察觉/露出」极易巧合共现，实测放行率仅 22%。
    """
    assert not hasattr(director, "DISCOVERY_VERBS")
    assert not hasattr(director, "INFO_VERBS")


def test_validate_present_empty_present_returns_as_is():
    # 回归：在场名单为空（异常态）时不得把整段回复剥空，应原样返回且不报违例
    r = f"{A}：清点物资。\n{B}：换药。"
    out, v = director.validate_present(r, [], KNOWN)
    assert v is False and out == r


def test_release_handle_drops_and_transfers():
    """全版把柄消除：仅改 holders、known_by 不变；holders 清空时状态回落潜伏。"""
    s = {"owner": A, "state": "暴露",
         "known_by": [B, C], "holders": [B, C]}
    # 转交第三方：B 失去、D 接手
    assert director._release_handle(s, B, D, 7) is True
    assert B not in s["holders"] and D in s["holders"]
    # 知情不可逆：known_by 仍含 B、C
    assert s["known_by"] == [B, C]
    assert s["state"] == "暴露"          # C 仍在 holders
    # 彻底失效：C 也失去 -> 仅 D 在 holders
    assert director._release_handle(s, C, "", 8) is True
    assert s["holders"] == [D]
    assert s["state"] == "暴露"
    # D 失去 -> holders 空 -> 回落潜伏
    assert director._release_handle(s, D, "", 8) is True
    assert s["holders"] == []
    assert s["state"] == "潜伏"
    # 不持有该把柄的人 -> 无变更
    assert director._release_handle(s, "角色戊", "", 9) is False


def test_record_exposure_adds_holder():
    """全版：曝光同时写入 known_by 与 holders；state 基于 holders。"""
    s = {"owner": A, "known_by": []}
    director._record_exposure(s, B, "叙事揭露", 3)
    assert B in s["known_by"] and B in s["holders"]
    assert s["state"] == "暴露"
