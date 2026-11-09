"""scene 的确定性测试：场景只由导演指令明说的内容变化，且完全不依赖模型。

旧版这里测的是「场景导演」（一次 LLM 调用）+ AUTO_TIME_THRESHOLD 强制推进，
2026-11-08 引擎瘦身后 scene.py 是纯规则（旧文件另存
backup/removed-20261108/test_scene_pre_slim_20261108.py）。
"""
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

import scene  # noqa: E402


def _snap(place="便利店后仓", time="", weather=""):
    return {"scene": {"place": place, "time": time, "weather": weather, "round": 3},
            "present": ["角色甲", "角色乙"]}


# ---------------------------------------------------------------------------
# 零模型依赖：模块里不再有 llm，任何调用都不该发请求
# ---------------------------------------------------------------------------

def test_scene_module_has_no_llm_dependency():
    assert not hasattr(scene, "llm"), "scene 不应再导入 llm（场景导演已删）"
    assert not hasattr(scene, "apply"), "旧入口 scene.apply 应已被 scene.resolve 取代"


def test_resolve_works_without_any_backend():
    """没有任何后端可用时场景照样能按指令更新——它压根不调模型。"""
    snap = _snap(time="傍晚")
    changed, prop = scene.resolve(snap, "第二天，外面下起雨来")
    assert changed is True
    assert snap["scene"]["time"] == "第二天"
    assert snap["scene"]["weather"] == "雨"
    assert "时间 → 第二天" in prop["reason"]


# ---------------------------------------------------------------------------
# 地点：只认明确的位移句式
# ---------------------------------------------------------------------------

def test_place_changes_on_explicit_switch():
    snap = _snap()
    changed, _ = scene.resolve(snap, "切换到阳台，众人跟过去")
    assert changed is True
    assert snap["scene"]["place"] == "阳台"


def test_place_cuts_at_action_word():
    """中文没有空格，「走到门口看看」不能把「门口看看」整个当景点。"""
    snap = _snap()
    scene.resolve(snap, "角色乙走到门口看看外面的雨")
    assert snap["scene"]["place"] == "门口"


def test_single_char_move_words_do_not_trigger():
    """审计 P2 的过度触发：单字「去 / 回」不再当位移信号（去年、进去、回去）。"""
    for d in ("去年那场雨还没说完", "角色甲进去倒水", "回去睡觉吧", "众人转移阵地"):
        snap = _snap(place="堂屋")
        changed, _ = scene.resolve(snap, d)
        assert snap["scene"]["place"] == "堂屋", d
        assert changed is False, d


def test_non_place_capture_ignored():
    snap = _snap(place="堂屋")
    changed, _ = scene.resolve(snap, "角色甲回到从前那种信任里")
    assert snap["scene"]["place"] == "堂屋"
    assert changed is False


# ---------------------------------------------------------------------------
# 时间：明确时段词才推，将来时预告不算
# ---------------------------------------------------------------------------

def test_time_advances_only_on_clean_time_word():
    snap = _snap(time="傍晚")
    changed, _ = scene.resolve(snap, "入夜后楼道很安静")
    assert changed is True
    assert snap["scene"]["time"] == "入夜"


def test_future_tense_does_not_advance_time():
    for d in ("夜晚快到了", "天快黑了", "明天会下雨之前我们先谈谈"):
        snap = _snap(time="傍晚")
        scene.resolve(snap, d)
        assert snap["scene"]["time"] == "傍晚", d


def test_same_time_word_is_not_a_change():
    snap = _snap(time="入夜")
    changed, prop = scene.resolve(snap, "入夜的走廊没人")
    assert changed is False and prop is None


def test_no_time_words_leaves_time_untouched():
    """引擎不再猜时间：没有时段词就不动（旧版 AUTO_TIME_THRESHOLD 会硬推一次）。"""
    snap = _snap(time="入夜")
    changed, _ = scene.resolve(snap, "角色甲沉默地握紧螺丝刀")
    assert changed is False
    assert snap["scene"]["time"] == "入夜"
    assert "same_scene" not in snap["scene"]


# ---------------------------------------------------------------------------
# 天气
# ---------------------------------------------------------------------------

def test_weather_normalized_from_directive():
    snap = _snap()
    changed, _ = scene.resolve(snap, "外面下起雨来")
    assert changed is True
    assert snap["scene"]["weather"] == "雨"


def test_weather_needs_a_verb_not_a_bare_noun():
    """叙述里提到「那场雨」不等于本轮天气变化——天气改动要「动词 + 天气名」。"""
    for d in ("那场雨他记得清楚", "去年那场雨还没说完", "风吹散了纸片但天气没变"):
        snap = _snap()
        changed, _ = scene.resolve(snap, d)
        assert snap["scene"]["weather"] == "", d
        assert changed is False, d


def test_no_change_returns_none_prop():
    snap = _snap(place="堂屋", time="入夜", weather="雨")
    changed, prop = scene.resolve(snap, "角色乙把伞收起来")
    assert (changed, prop) == (False, None)


# ---------------------------------------------------------------------------
# 开场场景解析（沿用旧契约）
# ---------------------------------------------------------------------------

def test_parse_initial_scene_splits_time_and_place():
    assert scene.parse_initial_scene("傍晚，公寓的客厅") == ("公寓的客厅", "傍晚")


def test_parse_initial_scene_longest_match():
    assert scene.parse_initial_scene("第二天早上，楼道")[1] == "第二天早上"


def test_parse_initial_scene_place_only():
    assert scene.parse_initial_scene("便利店后仓") == ("便利店后仓", "")


def test_parse_initial_scene_empty():
    assert scene.parse_initial_scene("   ") == ("", "")
