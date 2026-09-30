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
