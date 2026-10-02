"""director 的确定性单元测试（不调 LLM，快速）。

覆盖：validate_present 四类场景 + 举证式归档（_evidence_ok）+ 把柄消除
（_release_handle）+ 机会等级成对作用域。
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


# ---- 机会等级辅助判定（确定性，不调 LLM）----

def test_opp_from_secrets_full_when_holder_present():
    """把柄胁迫 → 满机会：已暴露秘密且持有者在场。"""
    snap = {"secrets": [{"owner": "高洋", "state": "暴露", "known_by": ["林晚", "阿杰"]}]}
    assert director._opp_from_secrets(snap, ["林晚", "阿杰"]) == "满机会"
    # 持有者不在场则无机会
    assert director._opp_from_secrets(snap, ["苏曼"]) == "无"
    # 仍潜伏则不触发
    snap2 = {"secrets": [{"owner": "高洋", "state": "潜伏", "known_by": []}]}
    assert director._opp_from_secrets(snap2, ["林晚"]) == "无"


def test_opp_from_secrets_is_pair_scoped():
    """把柄是成对的：只对「持有者 ↔ 归属者」同在镜头内时生效，不波及全场。"""
    snap = {"secrets": [{"owner": "高洋", "state": "暴露", "known_by": ["阿杰"]}]}
    present = ["阿杰", "高洋", "苏曼", "老周"]
    # 镜头正对这一对 -> 满机会
    assert director._opp_from_secrets(snap, present, ["阿杰", "高洋"]) == "满机会"
    # 镜头在另一对身上，与阿杰的把柄无关 -> 不得顶格（这是本次修复的核心）
    assert director._opp_from_secrets(snap, present, ["苏曼", "老周"]) == "无"
    # 镜头只有持有者、归属者不在 -> 胁迫对象不在场，不构成当轮机会
    assert director._opp_from_secrets(snap, present, ["阿杰"]) == "无"
    # 无镜头（自然推演、全员皆可写）-> 退回全场判定
    assert director._opp_from_secrets(snap, present, None) == "满机会"


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


def test_known_but_not_holder_no_opportunity():
    """全版区分：known_by 有人但 holders 为空（知道却无把柄）-> 不顶格。"""
    s = {"owner": "高洋", "state": "潜伏", "known_by": ["阿杰"], "holders": []}
    snap = {"secrets": [s]}
    assert director._opp_from_secrets(snap, ["阿杰", "高洋"]) == "无"


def test_opp_from_relations_strong():
    snap = {"relations": {"林晚 → 阿杰": "偷情，肉体关系"}}
    assert director._opp_from_relations(snap, ["林晚", "阿杰"]) == "满机会"
    snap2 = {"relations": {"林晚 → 阿杰": "暗恋，心动"}}
    assert director._opp_from_relations(snap2, ["林晚", "阿杰"]) == "半步"


def test_opp_from_history_capped_at_half():
    """近期身体接触推进只作升温（半步上限），不永久锁满机会。"""
    hist = [{"role": "assistant", "content": "林晚吻了阿杰，贴近他胸口"}]
    assert director._opp_from_history(hist) == "半步"
    hist2 = [{"role": "assistant", "content": "老周清点物资"}]
    assert director._opp_from_history(hist2) == "无"


# ---- 同形中性词保护（「穴」在末日/野外题材高频且无性含义）----

def test_neutral_homonyms_not_treated_as_intimacy():
    """墓穴/洞穴/穴位 不得判为越线——否则会误记关系后果旧账、误触发余韵。"""
    for t in ["这可能成为五个人共同的墓穴", "他们躲进山洞的洞穴里",
              "老周按压太阳穴缓解头痛", "这是一处尸群巢穴"]:
        assert director.detect_intimacy(t) == "无", t


def test_real_intimacy_still_detected():
    """真实越线用词仍须判为越线（不能被中性剔除误伤）。"""
    assert director.detect_intimacy("他进入她，两人在仓库里做爱") == "越线"


def test_opp_from_history_ignores_neutral_homonyms():
    """历史里出现「墓穴」不应把机会等级抬到半步。"""
    hist = [{"role": "assistant", "content": "这地方可能成为五个人共同的墓穴"}]
    assert director._opp_from_history(hist) == "无"
