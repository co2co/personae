"""「本轮场面」段与名册语义守护（v2.1.0 拆职责）。

背景：`present` 从「在场名单」改为「角色名册」（建局 cast，永不收缩）。
「本轮在场角色：A、B、C…只能写这些」在六人分处四地时会逼模型逐个过场；
物理同场改由 locations 派生成本段，按位置分场、并给出确定性的默认主镜头。

这里只测渲染规则（纯函数），不调 LLM、不碰真实数据目录。
角色名一律用中性占位（普适性红线）。
"""

import prompter

A, B, C, D = "角色甲", "角色乙", "角色丙", "角色丁"


def _snap(place="某处甲", round_no=5, locations=None, time="深夜", weather=""):
    return {
        "present": [A, B, C, D],
        "scene": {"place": place, "time": time, "weather": weather,
                  "round": round_no, "same_scene": 0},
        "locations": locations if locations is not None else {},
        "goals": {}, "relations": {}, "ledger": [], "secrets": [],
        "states": {}, "actions": {}, "silent_rounds": {}, "address": {},
    }


def test_groups_by_place_with_max_as_default_main_scene():
    snap = _snap("某处甲", locations={
        A: {"place": "某处甲", "round": 5},
        B: {"place": "某处甲", "round": 5},
        C: {"place": "某处乙", "round": 5},
        D: {"place": "某处丙", "round": 5},
    })
    out = prompter.scene_roster_block(snap, snap["present"])
    assert "某处甲：" + A + "、" + B + "　← 默认主镜头" in out
    assert "某处乙：" + C in out and "某处丙：" + D in out
    # 主镜头取人数最多处，不是 scene.place 的盲目复制（此处恰好一致，另见下例）
    assert out.index("某处甲") < out.index("某处乙")


def test_main_scene_is_majority_not_scene_place():
    """镜头漂到空场景时，主镜头仍取人数最多处，并把「镜头所在（无人）」点出来。"""
    snap = _snap("某处丙", locations={
        A: {"place": "某处甲", "round": 5},
        B: {"place": "某处甲", "round": 5},
        C: {"place": "某处乙", "round": 5},
        D: {"place": "某处乙", "round": 5},
    })
    out = prompter.scene_roster_block(snap, snap["present"])
    assert "某处甲：" + A + "、" + B + "　← 默认主镜头" in out
    assert "镜头所在：某处丙（此刻无人）" in out


def test_single_place_collapses_to_one_line():
    snap = _snap("某处甲", locations={n: {"place": "某处甲", "round": 5}
                                     for n in (A, B, C, D)})
    out = prompter.scene_roster_block(snap, snap["present"])
    assert out.count("- ") == 1
    assert "默认主镜头" not in out
    assert "全员同处这一处" in out


def test_first_round_does_not_assert_everyone_in_one_place():
    """首轮没有任何位置记录：只给开场场景 + 一条约束，不把名册全员摆进同一场。

    这是 v1.2.0 删勾选列表时撞的那面墙：首轮写「全员同处这一处」后，六个人被
    一起搬进开场场景——开场是某人的寝殿，朝堂六人也照塞。引擎此刻并不知道谁在哪，
    所以只约束「让本就有理由在此处的人登场」，位置等首轮 reflect 记录后再分场。
    """
    out = prompter.scene_roster_block(_snap("某处甲", round_no=0), [A, B, C])
    assert "位置未更新" not in out
    assert "- 开场：某处甲（深夜）" in out
    assert "全员同处" not in out
    # 不把名册列成分场行：列出来模型就会照着名单逐个过场
    assert A + "、" + B not in out
    assert "谁现身由本轮情节决定" in out


def test_all_stale_locations_not_asserted_as_same_place():
    """非首轮但全员位置都已陈旧：只报「位置不确定」，同样不断言同处。"""
    snap = _snap("某处甲", round_no=9, locations={
        n: {"place": "某处乙", "round": 1} for n in (A, B, C, D)})
    out = prompter.scene_roster_block(snap, [A, B, C, D])
    assert "全员同处" not in out
    assert "位置未更新" in out
    assert "不要按「名册上还有谁」" in out


def test_stale_location_listed_as_unknown():
    """位置连续多轮没更新 -> 归「位置未更新」，不再钉在原地当事实。"""
    snap = _snap("某处甲", round_no=8, locations={
        A: {"place": "某处甲", "round": 8},
        B: {"place": "某处乙", "round": 2},   # 落后 6 轮
        C: {},                                # 从未记录
    })
    out = prompter.scene_roster_block(snap, [A, B, C])
    assert "位置未更新" in out
    assert B + "（上次在 某处乙）" in out
    assert C in out


def test_multi_scene_forbids_same_room_dialogue():
    snap = _snap(locations={A: {"place": "某处甲", "round": 5},
                            B: {"place": "某处乙", "round": 5}})
    out = prompter.scene_roster_block(snap, [A, B])
    assert "听不见彼此说话" in out
    assert "不逐个过场" in out


def test_empty_roster_returns_empty():
    assert prompter.scene_roster_block(_snap(), []) == ""


def test_prompt_has_no_old_wording():
    """旧措辞必须彻底消失：它是「逐个过场」的直接指令来源。"""
    snap = _snap(locations={A: {"place": "某处甲", "round": 5},
                            B: {"place": "某处乙", "round": 5}})
    cards = {n: {"name": n, "description": "", "personality": "",
                 "core_desire": "", "core_fear": ""} for n in (A, B)}
    msgs = prompter.build_session(cards, "夜色渐深", [], snap, history=[],
                                  demo_hits=[])
    text = "\n".join(m["content"] for m in msgs)
    assert "本轮在场角色：" not in text
    assert "只能写这些在场角色" not in text
    assert "人物位置（不可违背）" not in text      # 已并入 [本轮场面]
    assert "[本轮场面（按位置分场，不可违背）]" in text
    assert "让本场的人动起来" in text              # 铁律①已改为本场口径
    # 格式锚点必须留在最前：v2.1.0 首版改写时丢掉了「台词」二字，实测 r03/r05/r06
    # 退化成散文式对白（「角色甲的声音平淡无奇：…」），不再是「角色名：」起段
    assert "开口的角色以「角色名：」另起一段接台词" in text
