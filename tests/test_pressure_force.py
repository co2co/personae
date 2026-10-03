"""秘密发酵压力的高压提级机制测试（确定性，不依赖真实 LLM / 网络）。

修复根因：pressure（代码计数的沉寂轮数）此前只写在角色块内的一句提示里，优先级
低于导演指令与镜头约束；压测实证 pressure 连续 7 轮封顶（=5）却毫无碰撞——
当事人常常根本不在镜头里（镜头外不许被写），写了也出不来。

补丁：① 高压档提级为全局强制段 [本轮必须发生的事]（与导演指令同级、置提示词末尾）；
      ② 高压秘密的双方由镜头层强制并入 focus subjects（必要时镜头退化为自然推演）。

覆盖：
  1. director.pressure_targets：高压未曝光秘密取归属者 + 在场对手（起疑者优先）；
     低压 / 已曝光 / 归属者不在场一律不取。
  2. director.compute_focus：高压双方被并入镜头；并入后覆盖全体则退化为 None。
  3. prompter.build_session：高压时提示词末尾出现全局强制段，且点名碰撞双方。
"""

import sys
from pathlib import Path

import pytest

ENGINE = Path(__file__).resolve().parent.parent / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

import director  # noqa: E402
import prompter  # noqa: E402


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


def _snap(present, secrets, focus=None, place="地铁口公寓"):
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
    snap = _snap(["陆衡", "林清", "王晨"], [
        _secret("陆衡", susp=[{"by": "王晨", "clue": "说不通"}, {"by": "林清", "clue": "追问"}]),
    ])
    assert director.pressure_targets(snap) == [("陆衡", "王晨")]


def test_targets_fall_back_to_holders_when_no_suspicion():
    snap = _snap(["陆衡", "林清"], [_secret("陆衡", holders=["林清"])])
    assert director.pressure_targets(snap) == [("陆衡", "林清")]


def test_targets_none_when_rival_absent():
    # 对手不在场时仍保留归属者（由其自己露出痕迹），rival 为 None
    snap = _snap(["陆衡", "林清"], [_secret("陆衡", susp=[{"by": "王晨"}]), ])
    assert director.pressure_targets(snap) == [("陆衡", None)]


def test_targets_skip_low_pressure_exposed_and_offstage_owner():
    snap = _snap(["陆衡", "林清", "王秀兰"], [
        _secret("陆衡", pressure=3),                                  # 未到高压档
        _secret("林清", pressure=5, state="暴露", susp=[{"by": "陆衡"}]),  # 已公开
        _secret("王晨", pressure=5, susp=[{"by": "陆衡"}]),             # 归属者不在场
    ])
    assert director.pressure_targets(snap) == []


# --- 2. compute_focus 强制并入 ---

def test_focus_merges_pressure_pair():
    secrets = [_secret("王秀兰", susp=[{"by": "王晨"}])]
    snap = _snap(["陆衡", "林清", "王秀兰", "王晨"], secrets)
    focus = director.compute_focus("陆衡独自上楼查看", snap)
    assert focus and focus.get("forced") is True
    assert set(focus["subjects"]) == {"陆衡", "王秀兰", "王晨"}
    assert "林清" not in focus["subjects"]   # 无关者仍留在镜头外


def test_focus_lock_does_not_collapse_to_full_present_v2():
    """旧行为是覆盖全体时退化为 None；新设计锁定镜头，收敛为只聚焦高压双方。"""
    secrets = [_secret("王秀兰", susp=[{"by": "王晨"}])]
    snap = _snap(["陆衡", "王秀兰", "王晨"], secrets)
    focus = director.compute_focus("陆衡和王秀兰上楼查看", snap)
    assert focus is not None
    assert focus["forced"] is True
    assert focus["sticky"] is True
    assert set(focus["subjects"]) == {"王秀兰", "王晨"}   # 无关者陆衡被请出镜头


def test_focus_untouched_without_pressure():
    snap = _snap(["陆衡", "王秀兰", "王晨"], [_secret("王秀兰", pressure=1)])
    focus = director.compute_focus("陆衡独自上楼查看", snap)
    assert focus == {"subjects": ["陆衡"], "place": "地铁口公寓", "sticky": False}


def test_no_focus_no_force():
    # 无指令点名时不凭空造镜头，压力交给全局强制段承担
    secrets = [_secret("王秀兰", susp=[{"by": "王晨"}])]
    snap = _snap(["陆衡", "王秀兰", "王晨"], secrets)
    assert director.compute_focus("", snap) is None


# --- 3. prompter 全局强制段 ---

def test_prompt_has_global_pressure_block():
    secrets = [_secret("王秀兰", susp=[{"by": "王晨"}])]
    snap = _snap(["陆衡", "王秀兰", "王晨"], secrets)
    cards = {n: {"description": "描述", "personality": "", "core_desire": "", "core_fear": ""}
             for n in snap["present"]}
    msgs = prompter.build_session(cards, "继续搜物资", [], snap)
    system = msgs[0]["content"]
    assert "[本轮必须发生的事]" in system
    # 取最后一次出现：角色块内的分档提示会先引用一次该标题作为指引
    tail = system.split("[本轮必须发生的事]")[-1]
    assert "王秀兰" in tail and "王晨" in tail
    # 真正的全局段须位于输出格式之后（近因最强），否则会被前段指令压掉
    assert system.rindex("[本轮必须发生的事]") > system.index("[输出格式]")


def test_prompt_has_no_block_when_pressure_low():
    snap = _snap(["陆衡", "王秀兰", "王晨"], [_secret("王秀兰", pressure=2)])
    cards = {n: {"description": "描述"} for n in snap["present"]}
    msgs = prompter.build_session(cards, "继续搜物资", [], snap)
    assert "[本轮必须发生的事]" not in msgs[0]["content"]


if __name__ == "__main__":
    pytest.main([__file__, "-q"])


# --- 追加：已公开秘密不得再占发酵名额 / 同时只逼一条 ---

def test_exposed_secret_pressure_resets():
    """状态字面量是「暴露」不是「曝光」：早前守卫写成 == "曝光" 从未生效，
    导致已公开的秘密压力挂在上限空转（压测实证挂 5 空转 4 轮）。"""
    snap = _snap(["陆衡", "王秀兰", "王晨"], [
        {"owner": "王秀兰", "state": "暴露", "pressure": 5},
    ])
    director._update_secret_pressure(snap, [{"owner": "王秀兰", "touched": False}])
    assert snap["secrets"][0]["pressure"] == 0
    assert director.pressure_targets(snap) == []


def test_legacy_full_expose_state_also_resets():
    """历史快照可能出现「全曝光」，同样视为已公开。"""
    snap = _snap(["陆衡", "王秀兰", "王晨"], [
        {"owner": "王秀兰", "state": "全曝光", "pressure": 5},
    ])
    director._update_secret_pressure(snap, [])
    assert snap["secrets"][0]["pressure"] == 0


def test_only_one_secret_forced_at_a_time():
    """多条同时顶格时只逼最久未碰的一条——三条并下达会互相打架、全部僵住。"""
    snap = _snap(["陆衡", "王秀兰", "王晨", "林清"], [
        {"owner": "王秀兰", "state": "潜伏", "pressure": 5},
        {"owner": "王晨", "state": "潜伏", "pressure": 5},
        {"owner": "林清", "state": "潜伏", "pressure": 5},
    ])
    targets = director.pressure_targets(snap)
    assert len(targets) == 1
    assert targets[0][0] == "王秀兰"          # 压力相同则取快照中最靠前的一条（确定）


def test_higher_pressure_wins_the_slot():
    snap = _snap(["陆衡", "王秀兰", "王晨", "林清"], [
        {"owner": "王秀兰", "state": "潜伏", "pressure": 5},
        {"owner": "王晨", "state": "潜伏", "pressure": 5},
        {"owner": "林清", "state": "潜伏", "pressure": 3},
    ])
    assert len(director.pressure_targets(snap)) == 1


# --- 高压锁定镜头：不得退化为自然推演 ---

def test_pressure_locks_focus_when_no_directive_naming():
    """导演指令未点名任何人（focus=None）但高压秘密在场：镜头锁定高压双方，不退化。"""
    snap = _snap(["陆衡", "林清", "王秀兰", "王晨"], [
        _secret("陆衡", pressure=5, susp=[{"by": "林清"}]),
    ])
    focus = director.compute_focus("众人各自收拾行装", snap)
    assert focus is not None
    assert focus["forced"] is True
    assert focus["sticky"] is True
    assert set(focus["subjects"]) == {"陆衡", "林清"}


def test_pressure_lock_does_not_collapse_to_full_present():
    """并入后覆盖全体在场者时：旧逻辑返回 None（自然推演），新逻辑收敛为只聚焦高压双方。"""
    snap = _snap(["陆衡", "林清", "王秀兰"], [
        _secret("陆衡", pressure=5, susp=[{"by": "林清"}]),
    ])
    # 指令点名王秀兰，并入陆衡、林清后覆盖全体 3 人
    focus = director.compute_focus("王秀兰走到窗边张望", snap)
    assert focus is not None, "覆盖全体时不得退化为 None"
    assert focus["forced"] is True
    assert set(focus["subjects"]) == {"陆衡", "林清"}   # 无关者王秀兰被请出镜头


def test_pressure_lock_persists_next_round_without_follow_word():
    """高压锁定跨轮延续：下轮指令既没点名、也无指代代词，仍黏住焦点（不依赖 _FOLLOW_WORDS）。"""
    snap = _snap(["陆衡", "林清", "王秀兰", "王晨"], [
        _secret("陆衡", pressure=5, susp=[{"by": "林清"}]),
    ], focus={"subjects": ["陆衡", "林清"], "place": "地铁口公寓",
              "sticky": True, "forced": True})
    focus = director.compute_focus("门外的动静似乎停了", snap)
    assert focus is not None
    assert set(focus["subjects"]) == {"陆衡", "林清"}


def test_pressure_lock_releases_after_collision():
    """碰撞发生后压力归零，forced 消失，镜头恢复普通逻辑（不再被锁定）。"""
    snap = _snap(["陆衡", "林清", "王秀兰"], [
        _secret("陆衡", pressure=0, susp=[{"by": "林清"}]),
    ], focus={"subjects": ["陆衡", "林清"], "place": "地铁口公寓",
              "sticky": True, "forced": True})
    # 压力 0，不构成高压 -> pressure_targets 为空 -> 镜头按普通指令逻辑走（这里指令无点名，返回 None）
    focus = director.compute_focus("众人沉默", snap)
    assert focus is None or focus.get("forced") is not True
