"""director 的确定性单元测试（不调 LLM，快速）。

覆盖：validate_present 四类场景 + 举证式归档（_evidence_ok）+ 把柄消除
（_release_handle）。NSFW 机会等级机制已于 v0.8.0 整体废弃，相关用例已移除。
"""

import director

PRESENT = ["老周", "林晚", "阿杰"]
KNOWN = PRESENT + ["苏曼", "高洋", "环境推手"]


def test_validate_present_no_violation():
    r = "老周：清点物资。\n林晚：换药。\n阿杰：盯着看。"
    out, v = director.validate_present(r, PRESENT, KNOWN)
    assert v is False and out == r


def test_validate_present_strips_offstage_and_env():
    r = ("老周：开门。\n苏曼：我来帮你。（已离场不应出现）\n林晚：别信他。\n"
         "环境推手：我悄悄推了一把。\n阿杰：关我屁事。")
    out, v = director.validate_present(r, PRESENT, KNOWN)
    assert v is True
    assert "苏曼" not in out and "环境推手" not in out
    assert "老周" in out and "林晚" in out and "阿杰" in out


def test_validate_present_multiline_block():
    r = "老周：说着。\n苏曼：第一句。\n第二句续行。\n林晚：回应。"
    out, v = director.validate_present(r, PRESENT, KNOWN)
    assert "第二句续行" not in out
    assert "林晚：回应" in out


def test_validate_present_narrative_before_block_kept():
    r = "夜色渐深。\n苏曼：偷溜出去。\n老周：守夜。"
    out, v = director.validate_present(r, PRESENT, KNOWN)
    assert "夜色渐深" in out and "老周：守夜" in out
    assert "苏曼" not in out


def test_evidence_ok_requires_verbatim_quote():
    """举证必须是正文原文片段：逐字照抄才采信，改写/编造一律丢弃。"""
    reply = "老周一把扯开他臂弯的绷带，看见那道发黑的抓痕。"
    assert director._evidence_ok("看见那道发黑的抓痕", reply) is True
    assert director._evidence_ok("老周一把扯开他臂弯的绷带", reply) is True
    # 概括/改写（正文里没有这句）-> 丢弃
    assert director._evidence_ok("老周发现了高洋被咬伤", reply) is False
    # 凭空编造 -> 丢弃
    assert director._evidence_ok("阿杰翻出了私藏的巧克力", reply) is False


def test_evidence_ok_rejects_missing_or_too_short():
    """未举证或举证过短一律丢弃：宁可漏记，不可误记。"""
    reply = "老周一把扯开他臂弯的绷带，看见那道发黑的抓痕。"
    assert director._evidence_ok(None, reply) is False
    assert director._evidence_ok("", reply) is False
    assert director._evidence_ok("绷带", reply) is False


def test_no_semantic_wordlists_remain():
    """记录员模式契约：引擎不再持有语义词表，判定只靠举证。

    旧实现用 INFO_VERBS + DISCOVERY_VERBS + secret.keys 做语义判定，末日题材高频词
    （绷带/小臂/发烧/女儿）与「看见/察觉/露出」极易巧合共现，实测放行率 22%。
    """
    assert not hasattr(director, "DISCOVERY_VERBS")
    assert not hasattr(director, "INFO_VERBS")


def test_validate_present_empty_present_returns_as_is():
    # 回归：在场名单为空（异常态）时不得把整段回复剥空，应原样返回且不报违例
    r = "老周：清点物资。\n林晚：换药。"
    out, v = director.validate_present(r, [], KNOWN)
    assert v is False and out == r


def test_release_handle_drops_and_transfers():
    """全版把柄消除：仅改 holders、known_by 不变；holders 清空时状态回落潜伏。"""
    s = {"owner": "高洋", "state": "暴露",
         "known_by": ["阿杰", "林晚"], "holders": ["阿杰", "林晚"]}
    # 转交第三方：阿杰失去、老周接手
    assert director._release_handle(s, "阿杰", "老周", 7) is True
    assert "阿杰" not in s["holders"] and "老周" in s["holders"]
    # 知情不可逆：known_by 仍含阿杰、林晚
    assert s["known_by"] == ["阿杰", "林晚"]
    assert s["state"] == "暴露"          # 林晚仍在 holders
    # 彻底失效：林晚也失去 -> 仅老周在 holders
    assert director._release_handle(s, "林晚", "", 8) is True
    assert s["holders"] == ["老周"]
    assert s["state"] == "暴露"
    # 老周失去 -> holders 空 -> 回落潜伏
    assert director._release_handle(s, "老周", "", 8) is True
    assert s["holders"] == []
    assert s["state"] == "潜伏"
    # 不持有该把柄的人 -> 无变更
    assert director._release_handle(s, "苏曼", "", 9) is False


def test_record_exposure_adds_holder():
    """全版：曝光同时写入 known_by 与 holders；state 基于 holders。"""
    s = {"owner": "高洋", "known_by": []}
    director._record_exposure(s, "阿杰", "叙事揭露", 3)
    assert "阿杰" in s["known_by"] and "阿杰" in s["holders"]
    assert s["state"] == "暴露"
