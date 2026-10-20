"""秘密发酵压力的高压提级机制测试（确定性，不依赖真实 LLM / 网络）。

修复根因：pressure（代码计数的沉寂轮数）此前只写在角色块内的一句提示里，优先级
低于导演指令与镜头约束；压测实证 pressure 连续 7 轮封顶（=5）却毫无碰撞——
当事人常常根本不在镜头里（镜头外不许被写），写了也出不来。

补丁：① 高压档提级为全局提醒段 [可选提醒·秘密发酵]（软提醒、置提示词末尾、玩家指令优先）；
      ② 高压秘密的双方不再由镜头层强制（v0.18.3 已删除 _merge_pressure_into_focus，
         v0.18.4 起提醒段同步软化为「可选」，碰撞交由小空间群像叙事自然命中）。

覆盖：
  1. director.pressure_targets：高压未曝光秘密取归属者 + 在场对手（起疑者优先）；
     低压 / 已曝光 / 归属者不在场一律不取。
  2. director.compute_focus：玩家点名 / 群体词 / 纯环境三种情况镜头行为（高压不再强制）。
  3. prompter.build_session：高压时提示词末尾出现软提醒段，且点名双方。
"""

import sys
from pathlib import Path

import pytest

ENGINE = Path(__file__).resolve().parent.parent / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

import director  # noqa: E402
import prompter  # noqa: E402
from fixtures import A, B, C, D  # noqa: E402


def _secret(owner, pressure=5, state="潜伏", susp=None, holders=None, known=None):
    return {
        "owner": owner,
        "content": owner + " 的秘密",
        "state": state,
        "pressure": pressure,
        "suspicions": susp or [],
        "holders": holders or [],
        "known_by": known or (holders or []),
    }


def _snap(present, secrets, focus=None, place="街角仓库"):
    return {
        "present": list(present),
        "scene": {"place": place, "time": "", "round": 3, "weather": ""},
        "focus": focus,
        "goals": {},
        "secrets": secrets,
        "relations": {},
        "ledger": [],
        "actions": {},
        "silent_rounds": {},
        "address": {},
    }


# --- 1. pressure_targets ---

def test_targets_pick_rival_from_suspicions_first():
    snap = _snap(["角色甲", "角色乙", "角色丁"], [
        _secret("角色甲", susp=[{"by": "角色丁", "clue": "说不通"}, {"by": "角色乙", "clue": "追问"}]),
    ])
    assert director.pressure_targets(snap) == [("角色甲", "角色丁")]


def test_targets_fall_back_to_holders_when_no_suspicion():
    snap = _snap(["角色甲", "角色乙"], [_secret("角色甲", holders=["角色乙"])])
    assert director.pressure_targets(snap) == [("角色甲", "角色乙")]


def test_targets_none_when_rival_absent():
    # 对手不在场时仍保留归属者（由其自己露出痕迹），rival 为 None
    snap = _snap(["角色甲", "角色乙"], [_secret("角色甲", susp=[{"by": "角色丁"}]), ])
    assert director.pressure_targets(snap) == [("角色甲", None)]


def test_targets_skip_low_pressure_exposed_and_offstage_owner():
    snap = _snap(["角色甲", "角色乙", "角色丙"], [
        _secret("角色甲", pressure=3),                                  # 未到高压档
        _secret("角色乙", pressure=5, state="暴露", susp=[{"by": "角色甲"}]),  # 已公开
        _secret("角色丁", pressure=5, susp=[{"by": "角色甲"}]),             # 归属者不在场
    ])
    assert director.pressure_targets(snap) == []


# --- 2. compute_focus 高压不强制并入（玩家指令优先） ---

def test_focus_merges_pressure_pair():
    """玩家点名角色甲 -> 镜头只跟随角色甲，高压不强制并入（玩家指令优先）。"""
    secrets = [_secret("角色丙", susp=[{"by": "角色丁"}])]
    snap = _snap(["角色甲", "角色乙", "角色丙", "角色丁"], secrets)
    focus = director.compute_focus("角色甲独自上楼查看", snap)
    assert focus is not None
    assert focus.get("forced") is not True
    assert focus["subjects"] == ["角色甲"]          # 只聚焦玩家点名的角色甲


def test_focus_lock_does_not_collapse_to_full_present_v2():
    """玩家点名角色甲+角色丙 -> 镜头聚焦这两人，高压不强制收敛、不强制并入。"""
    secrets = [_secret("角色丙", susp=[{"by": "角色丁"}])]
    snap = _snap(["角色甲", "角色丙", "角色丁"], secrets)
    focus = director.compute_focus("角色甲和角色丙上楼查看", snap)
    assert focus is not None
    assert focus.get("forced") is not True
    assert focus["sticky"] is False
    assert set(focus["subjects"]) == {"角色甲", "角色丙"}   # 尊重玩家点名


def test_focus_untouched_without_pressure():
    snap = _snap(["角色甲", "角色丙", "角色丁"], [_secret("角色丙", pressure=1)])
    snap["locations"] = {"角色甲": {"place": "二楼走廊"}}
    focus = director.compute_focus("角色甲独自上楼查看", snap)
    # v2.1.0：焦点地点取焦点角色的实际位置，不再回退 scene.place
    assert focus == {"subjects": ["角色甲"], "place": "二楼走廊", "sticky": False}


def test_no_focus_no_force():
    # 无指令点名时不凭空造镜头，压力交给全局提醒段承担（软提醒，不强制造镜头）
    secrets = [_secret("角色丙", susp=[{"by": "角色丁"}])]
    snap = _snap(["角色甲", "角色丙", "角色丁"], secrets)
    assert director.compute_focus("", snap) is None


def test_pressure_rival_requires_same_place():
    """同场判据改由 locations 承担（v2.1.0）。

    present 现在是「角色名册」（全员），拿它判「眼前有没有人逼近」等于恒真——
    千里之外的起疑者也会被当成当场对峙。任一方位置未记录时不做否定（不夺其资格）。
    """
    snap = _snap(["角色甲", "角色乙"],
                 [_secret("角色甲", state="起疑", susp=[{"by": "角色乙"}])])
    snap["locations"] = {"角色甲": {"place": "某处甲"},
                         "角色乙": {"place": "某处乙"}}
    assert director.pressure_targets(snap) == [("角色甲", None)]
    snap["locations"]["角色乙"]["place"] = "某处甲"
    assert director.pressure_targets(snap) == [("角色甲", "角色乙")]
    snap["locations"] = {}          # 位置未记录：不否定其在场资格
    assert director.pressure_targets(snap) == [("角色甲", "角色乙")]


# --- 3. prompter 全局提醒段 ---

def test_prompt_has_global_pressure_block():
    secrets = [_secret("角色丙", susp=[{"by": "角色丁"}])]
    snap = _snap(["角色甲", "角色丙", "角色丁"], secrets)
    cards = {n: {"description": "描述", "personality": "", "core_desire": "", "core_fear": ""}
             for n in snap["present"]}
    msgs = prompter.build_session(cards, "继续搜物资", [], snap)
    system = msgs[0]["content"]
    assert "[可选提醒·秘密发酵]" in system
    # 取最后一次出现：角色块内的分档提示会先引用一次该标题作为指引
    tail = system.split("[可选提醒·秘密发酵]")[-1]
    assert "角色丙" in tail and "角色丁" in tail
    # 真正的全局段须位于输出格式之后（近因最强），否则会被前段指令压掉
    assert system.rindex("[可选提醒·秘密发酵]") > system.index("[输出格式]")


def test_prompt_has_no_block_when_pressure_low():
    snap = _snap(["角色甲", "角色丙", "角色丁"], [_secret("角色丙", pressure=2)])
    cards = {n: {"description": "描述"} for n in snap["present"]}
    msgs = prompter.build_session(cards, "继续搜物资", [], snap)
    assert "[可选提醒·秘密发酵]" not in msgs[0]["content"]


if __name__ == "__main__":
    pytest.main([__file__, "-q"])


# --- 追加：已公开秘密不得再占发酵名额 / 同时只逼一条 ---

def test_exposed_secret_pressure_resets():
    """状态字面量是「暴露」不是「曝光」：早前守卫写成 == "曝光" 从未生效，
    导致已公开的秘密压力挂在上限空转（压测实证挂 5 空转 4 轮）。"""
    snap = _snap(["角色甲", "角色丙", "角色丁"], [
        {"owner": "角色丙", "state": "暴露", "pressure": 5},
    ])
    director._update_secret_pressure(snap, [{"owner": "角色丙", "touched": False}])
    assert snap["secrets"][0]["pressure"] == 0
    assert director.pressure_targets(snap) == []


def test_legacy_full_expose_state_also_resets():
    """历史快照可能出现「全曝光」，同样视为已公开。"""
    snap = _snap(["角色甲", "角色丙", "角色丁"], [
        {"owner": "角色丙", "state": "全曝光", "pressure": 5},
    ])
    director._update_secret_pressure(snap, [])
    assert snap["secrets"][0]["pressure"] == 0


def test_suspicion_state_still_ferments():
    """v0.26.0 四态：起疑是中间态，仍须发酵；「已公开」才是停压终态。"""
    snap = _snap(["角色甲", "角色丙"], [
        {"owner": "角色丙", "state": "起疑", "pressure": 2},
    ])
    director._update_secret_pressure(snap, [])
    assert snap["secrets"][0]["pressure"] == 3
    snap2 = _snap(["角色甲", "角色丙"], [
        {"owner": "角色丙", "state": "已公开", "pressure": 5},
    ])
    director._update_secret_pressure(snap2, [])
    assert snap2["secrets"][0]["pressure"] == 0


def test_suspicion_secret_can_be_pressure_target():
    """起疑态 + 高压 -> 仍作为强制碰撞目标（对手取起疑者）。"""
    snap = _snap(["角色甲", "角色乙"], [
        {"owner": "角色甲", "state": "起疑", "pressure": 5,
         "suspicions": [{"by": "角色乙"}], "holders": [], "known_by": []},
    ])
    targets = director.pressure_targets(snap)
    assert targets == [("角色甲", "角色乙")]


def test_only_one_secret_forced_at_a_time():
    """多条同时顶格时只逼最久未碰的一条——三条并下达会互相打架、全部僵住。"""
    snap = _snap(["角色甲", "角色丙", "角色丁", "角色乙"], [
        {"owner": "角色丙", "state": "潜伏", "pressure": 5},
        {"owner": "角色丁", "state": "潜伏", "pressure": 5},
        {"owner": "角色乙", "state": "潜伏", "pressure": 5},
    ])
    targets = director.pressure_targets(snap)
    assert len(targets) == 1
    assert targets[0][0] == "角色丙"          # 压力相同则取快照中最靠前的一条（确定）


def test_higher_pressure_wins_the_slot():
    snap = _snap(["角色甲", "角色丙", "角色丁", "角色乙"], [
        {"owner": "角色丙", "state": "潜伏", "pressure": 5},
        {"owner": "角色丁", "state": "潜伏", "pressure": 5},
        {"owner": "角色乙", "state": "潜伏", "pressure": 3},
    ])
    assert len(director.pressure_targets(snap)) == 1


# --- 高压不再锁定镜头（玩家指令优先） ---

def test_pressure_locks_focus_when_no_directive_naming():
    """指令含群体词「众人」= 玩家显式点名全体 -> 尊重玩家，不锁定高压，返回自然推演。"""
    snap = _snap(["角色甲", "角色乙", "角色丙", "角色丁"], [
        _secret("角色甲", pressure=5, susp=[{"by": "角色乙"}]),
    ])
    focus = director.compute_focus("众人各自收拾行装", snap)
    assert focus is None                          # 群体点名 -> 自然推演，玩家优先


def test_pressure_lock_does_not_collapse_to_full_present():
    """玩家点名角色丙 -> 镜头只跟随角色丙，高压不强制并入（玩家指令优先）。"""
    snap = _snap(["角色甲", "角色乙", "角色丙"], [
        _secret("角色甲", pressure=5, susp=[{"by": "角色乙"}]),
    ])
    focus = director.compute_focus("角色丙走到窗边张望", snap)
    assert focus is not None
    assert focus.get("forced") is not True
    assert focus["subjects"] == ["角色丙"]        # 尊重玩家点名，不并入高压双方


def test_pressure_no_focus_force_when_truly_unnamed():
    """指令完全没点名任何角色（纯环境描述）-> 高压不再兜底撑镜头（玩家体验优先）。"""
    snap = _snap(["角色甲", "角色乙", "角色丙", "角色丁"], [
        _secret("角色甲", pressure=5, susp=[{"by": "角色乙"}]),
    ])
    focus = director.compute_focus("夜色更深了，仓库外传来脚步声", snap)
    assert focus is None                       # 高压不强制进镜头，交由叙事自然命中


def test_pressure_no_lock_persist_next_round():
    """高压不再跨轮黏住镜头：下轮指令没点名，就自然推演（不依赖 forced/sticky 延续）。"""
    snap = _snap(["角色甲", "角色乙", "角色丙", "角色丁"], [
        _secret("角色甲", pressure=5, susp=[{"by": "角色乙"}]),
    ], focus={"subjects": ["角色甲", "角色乙"], "place": "街角仓库",
              "sticky": True, "forced": True})
    focus = director.compute_focus("门外的动静似乎停了", snap)
    assert focus is None                       # 高压不再锁定镜头


def test_pressure_lock_releases_after_collision():
    """碰撞发生后压力归零，forced 消失，镜头恢复普通逻辑（不再被锁定）。"""
    snap = _snap(["角色甲", "角色乙", "角色丙"], [
        _secret("角色甲", pressure=0, susp=[{"by": "角色乙"}]),
    ], focus={"subjects": ["角色甲", "角色乙"], "place": "街角仓库",
              "sticky": True, "forced": True})
    # 压力 0，不构成高压 -> pressure_targets 为空 -> 镜头按普通指令逻辑走（这里指令无点名，返回 None）
    focus = director.compute_focus("众人沉默", snap)
    assert focus is None or focus.get("forced") is not True
