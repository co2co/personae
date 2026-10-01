"""director 的确定性单元测试（不调 LLM，快速）。

覆盖：validate_present 四类场景 + _reply_confirms_exposure 双信号门槛。
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


def test_reply_confirms_exposure_requires_both_signals():
    secret = {"keys": ["咬伤", "感染"], "content": "高洋被咬伤小臂"}
    names = set(PRESENT)
    # 只有秘密事实，无发现动作 -> 不采信
    assert director._reply_confirms_exposure("高洋小臂有咬伤痕迹", secret, names) is False
    # 只有发现动作，无秘密事实 -> 不采信
    assert director._reply_confirms_exposure("林晚拆开绷带发现了什么", secret, names) is False
    # 事实 + 动作齐备 -> 采信
    assert director._reply_confirms_exposure("林晚拆开绷带，发现高洋小臂咬伤", secret, names) is True


def test_reply_confirms_exposure_excludes_names_from_facts():
    secret = {"keys": ["咬伤", "感染"], "content": "高洋被咬伤"}
    names = set(PRESENT + ["高洋"])  # 高洋是人名，应从事实词中剔除
    # "高洋"+"咬伤" 但无发现动作 -> 仍不采信
    assert director._reply_confirms_exposure("高洋小臂咬伤", secret, names) is False


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
