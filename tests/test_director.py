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
import pytest     # noqa: E402
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


def test_evidence_ok_tolerates_punct_variance():
    """v0.17.4：标点/引号差异不该漏记，但字面篡改仍拒绝。"""
    reply = f"{A}低头说：「我早就知道了。」"
    # 纪官引用时漏掉引号、句号截断——容忍，不因标点差异漏记
    assert director._evidence_ok("我早就知道了", reply) is True
    assert director._evidence_ok("我早就知道", reply) is True
    # 把「我」篡改成角色名——字面篡改，仍拒绝
    assert director._evidence_ok(f"{A}早就知道了", reply) is False


def test_strip_punct_only_strips_punct():
    """_strip_punct 只去标点，不动汉字字面。"""
    assert director._strip_punct("「我早就知道了。」") == "我早就知道了"
    assert director._strip_punct("看见、那道，抓痕。") == "看见那道抓痕"


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


def test_validate_present_multi_speaker_blocks():
    """v2.0.0 正文格式回归 v0.31.11：多说话人叙事按「角色名：」分段并正常清洗。"""
    r = f"{A}：我来帮你。\n{B}：别信他。\n{C}：不关我事。"
    out, v = director.validate_present(r, PRESENT, KNOWN)
    assert v is False and out == r


def test_validate_present_prefix_still_stripped_as_fallback():
    """模型偶发仍写「角色名：」前缀时，兜底剥离仍生效（离场角色/环境推手被剥）。"""
    # 该守卫只对仍写成分行体的回复生效，小说体下是惰性守卫，不删正文。
    r = (f"{D}：我来帮你。\n{B}：别信他。\n环境推手：我悄悄推了一把。\n{C}：不关我事。")
    out, v = director.validate_present(r, PRESENT, KNOWN)
    assert v is True
    assert D not in out and "环境推手" not in out
    assert B in out and C in out


def test_validate_present_prose_has_no_anchor_passthrough():
    r"""降级不误删：小说体正文没有行首「角色名：」锚点，含未入册名字也原样放行。

    validate_present 的行首前缀守卫 ^(名字)\s*[:：] 只在行首认说话人，
    小说体散文上没有匹配点，因此必须逐字返回、不报违例——
    否则散文里出现的未入册名字会被误剥。
    """
    r = f"{D}把门闩拧了半圈，{C}在门外听着。"   # D 有卡但不在名册，句中提及不带行首锚点
    out, v = director.validate_present(r, PRESENT, KNOWN)
    assert v is False
    assert out == r


def test_release_handle_drops_and_transfers():
    """全版把柄消除：转手给 to 时 to 入 holders 且入 known_by（转手即知情）。

    holders 清空后因已知情而落「暴露」（v0.26.0 四态：信息不可逆，不再回落「潜伏」；
    未众人皆知故不判「已公开」）。frm 的 known_by 不移除（它已知情，信息不可逆）。
    """
    s = {"owner": A, "state": "暴露",
         "known_by": [B, C], "holders": [B, C]}
    # 转交第三方：B 失去、D 接手；D 接手即知情，须入 known_by
    assert director._release_handle(s, B, D, 7) is True
    assert B not in s["holders"] and D in s["holders"]
    # 知情不可逆：known_by 仍含 B、C，且新增 D（转手即知情）
    assert s["known_by"] == [B, C, D]
    assert s["state"] == "暴露"          # C 仍在 holders
    # 彻底失效：C 也失去 -> 仅 D 在 holders
    assert director._release_handle(s, C, "", 8) is True
    assert s["holders"] == [D]
    assert s["state"] == "暴露"
    # D 失去 -> holders 空，但 known_by 非空 -> 落「暴露」（不回落潜伏）
    assert director._release_handle(s, D, "", 8) is True
    assert s["holders"] == []
    assert s["state"] == "暴露"
    # 不持有该把柄的人 -> 无变更
    assert director._release_handle(s, "角色戊", "", 9) is False


def test_record_exposure_adds_holder():
    """全版：曝光同时写入 known_by 与 holders；state 基于 holders。"""
    s = {"owner": A, "known_by": []}
    director._record_exposure(s, B, "叙事揭露", 3)
    assert B in s["known_by"] and B in s["holders"]
    assert s["state"] == "暴露"


# ---- 秘密四态（v0.26.0）----
# 潜伏 / 起疑 / 暴露（仍为把柄）/ 已公开。优先级：已公开 > 暴露 > 起疑 > 潜伏。

def test_secret_state_four_states():
    """_secret_state 的四态推定与优先级（无在场名单时按 public 标志宽松判定）。"""
    # 潜伏：无人知情、无人起疑
    assert director._secret_state(
        {"owner": A, "known_by": [], "holders": [], "suspicions": []}) == "潜伏"
    # 起疑：非归属者起疑，尚无人坐实（张力最足的一段）
    assert director._secret_state(
        {"owner": A, "known_by": [], "holders": [],
         "suspicions": [{"by": B}]}) == "起疑"
    # 暴露：有人知情且仍握把柄（可要挟）
    assert director._secret_state(
        {"owner": A, "known_by": [B], "holders": [B]}) == "暴露"
    # 暴露：知情但把柄尽失、且非众人皆知（holders 空、known_by 非空）
    assert director._secret_state(
        {"owner": A, "known_by": [B], "holders": []}) == "暴露"
    # 已公开：public 置位且无在场名单时放宽判为已公开
    assert director._secret_state(
        {"owner": A, "known_by": [B], "holders": [], "public": True}) == "已公开"
    # 优先级：public 压过 holders（既公开又有人握把柄 -> 已公开）
    assert director._secret_state(
        {"owner": A, "known_by": [B], "holders": [B], "public": True}) == "已公开"
    # 环境推手不作为知情/把柄持有者
    assert director._secret_state(
        {"owner": A, "known_by": [], "holders": ["环境推手"]}) == "潜伏"


def test_secret_state_public_requires_common_knowledge():
    """定义层护栏：public 置位仍须「众人皆知」才判已公开，防第三方当众指控被误标。

    有在场名单时，只要还有在场非归属者不知情，就落回「暴露」——绝不提前判公开。
    """
    # public 置位，但在场 [A,B,C] 中仅 B 知情 -> 未众人皆知 -> 暴露
    assert director._secret_state(
        {"owner": A, "known_by": [B], "holders": [], "public": True},
        present=[A, B, C]) == "暴露"
    # public 置位且在场非归属者（B、C）全部知情 -> 已公开
    assert director._secret_state(
        {"owner": A, "known_by": [B, C], "holders": [], "public": True},
        present=[A, B, C]) == "已公开"
    # 仅一名在场同伴且已知情 -> 已公开
    assert director._secret_state(
        {"owner": A, "known_by": [B], "holders": [], "public": True},
        present=[A, B]) == "已公开"


def test_record_exposure_self_disclosure_marks_public():
    """归属者自述/承认：只入 known_by、不入 holders，并置 public。

    本人自愿交出，他人无从据此要挟，故不再是「把柄」（区分于他人获取类 via）。
    未传 present 时按 public 标志判为「已公开」。
    """
    s = {"owner": A, "known_by": [], "holders": [], "public": False}
    director._record_exposure(s, B, "承认", 5)
    assert B in s["known_by"]
    assert B not in s["holders"]
    assert s["public"] is True
    assert s["state"] == "已公开"


def test_release_handle_empty_known_by_falls_to_latent():
    """holders 空且 known_by 也空时才回落「潜伏」（纯把柄消除、无人知情）。"""
    s = {"owner": A, "known_by": [], "holders": [B]}
    assert director._release_handle(s, B, "", 4) is True
    assert s["holders"] == []
    assert s["state"] == "潜伏"


def test_exposure_via_self_disclosure_marks_public(monkeypatch):
    """reflect 层：via=「承认」且众人皆知 -> 已公开，且 by 不入 holders。"""
    snap = _snap_with_secret(A, "角色甲的秘密", [])
    snap["present"] = [A, B]          # 在场除归属者外仅 B，承认后即众人皆知
    reply = f"{A}当众承认：“我确实藏了东西。”"
    payload = {"secret_exposures": [
        {"owner": A, "by": B, "via": "承认", "evidence": "我确实藏了东西"}]}
    s = _run_reflect(monkeypatch, snap, reply, payload)
    assert s["state"] == "已公开"
    assert B in s.get("known_by", []) and B not in s.get("holders", [])
    assert s.get("public") is True


def test_self_disclosure_partial_audience_not_public(monkeypatch):
    """归属者只对个别人承认（尚有在场者不知情）时，不判「已公开」，落「暴露」。"""
    snap = _snap_with_secret(A, "角色甲的秘密", [])   # present=[A,B,C]
    reply = f"{A}低声对{B}承认：“我确实藏了东西。”"
    payload = {"secret_exposures": [
        {"owner": A, "by": B, "via": "承认", "evidence": "我确实藏了东西"}]}
    s = _run_reflect(monkeypatch, snap, reply, payload)
    assert s["state"] == "暴露"        # C 尚不知情
    assert s.get("public") is True     # 标志置位，但未达众人皆知


def test_self_disclosure_overrides_existing_holder(monkeypatch):
    """探针 R6 事故回归：已握把柄者也在场、归属者当众承认（众人皆知）-> 已公开。

    旧版二态下这种情形会因把柄释放而回落「潜伏」，把「天下皆知」显示成「无人知晓」。
    """
    snap = _snap_with_secret(A, "角色甲的秘密", [])
    snap["present"] = [A, B]
    snap["secrets"][0]["known_by"] = [B]
    snap["secrets"][0]["holders"] = [B]
    snap["secrets"][0]["state"] = "暴露"
    reply = f"{A}当众承认：“我确实藏了东西。”"
    payload = {"secret_exposures": [
        {"owner": A, "by": B, "via": "承认", "evidence": "我确实藏了东西"}]}
    s = _run_reflect(monkeypatch, snap, reply, payload)
    assert s["state"] == "已公开"
    assert s.get("public") is True
    assert s.get("holders") == []      # 本人承认，原把柄作废


# ---- 人物位置层（v0.17.6，会话 9f2e16e9 空间矛盾事故）----
# 位置是「谁在哪里」的唯一真相源，独立于 states（物件/环境状态）。分队/离场时
# 同一角色后写覆盖前写，天然消解「同时出现在两处」的矛盾。

def test_update_locations_overwrites_per_character():
    """同一角色后一轮的新位置覆盖旧位置，不产生两条并存的位置。"""
    snap = {}
    director.update_locations(snap, [{"who": A, "place": "卧室"}], 3)
    assert snap["locations"][A]["place"] == "卧室"
    director.update_locations(snap, [{"who": A, "place": "电梯内"}], 5)
    assert snap["locations"][A]["place"] == "电梯内"
    assert snap["locations"][A]["round"] == 5
    assert len(snap["locations"]) == 1  # 不膨胀，仍是唯一键


def test_update_locations_multi_character_split():
    """分队时各角色位置独立记录，互不覆盖（镜头所在 ≠ 各人位置）。"""
    snap = {}
    director.update_locations(snap, [
        {"who": A, "place": "地库"}, {"who": B, "place": "电梯内"},
        {"who": "角色丙", "place": "电梯内"}], 7)
    assert snap["locations"][A]["place"] == "地库"
    assert snap["locations"][B]["place"] == "电梯内"
    assert snap["locations"]["角色丙"]["place"] == "电梯内"
    assert len(snap["locations"]) == 3


def test_update_locations_drops_empty_and_placeholder():
    """空 who/place 与占位值丢弃，不占键位。"""
    snap = {}
    director.update_locations(snap, [
        {"who": A, "place": ""}, {"who": "", "place": "地库"},
        {"who": B, "place": "维持现状"}], 3)
    assert snap.get("locations", {}) == {}


def test_update_locations_normalizes_synonym_keys():
    """同义键（去助词/标点后相同）归并，避免造重复键。"""
    snap = {}
    director.update_locations(snap, [{"who": A, "place": "卧室"}], 3)
    director.update_locations(snap, [{"who": A + "的", "place": "客厅"}], 5)
    # 「角色甲的」与「角色甲」归并到同一键，覆盖而非追加
    assert len(snap["locations"]) == 1
    assert snap["locations"][A]["place"] == "客厅"


def test_reflect_records_location_updates(monkeypatch):
    """reflect 归档 location_updates：纪官上报的逐人位置落进快照 locations。"""
    import json as _json
    snap = {"scene": {"round": 8}, "present": [A, B], "relations": {},
            "actions": {A: "移动", B: "移动"}, "silent_rounds": {},
            "secrets": [], "facts": [], "states": {}, "goals": {}, "ledger": []}
    payload = {"actions": {A: "进电梯", B: "进电梯"},
               "location_updates": [
                   {"who": A, "place": "电梯内"},
                   {"who": B, "place": "电梯内"}]}
    monkeypatch.setattr(director.llm, "complete",
                        lambda *a, **k: _json.dumps(payload, ensure_ascii=False))
    monkeypatch.setattr(director.memory, "load", lambda sid: snap)
    monkeypatch.setattr(director.memory, "save", lambda sid, s: None)
    out = director.reflect("sid", f"{A}和{B}退进电梯。")
    assert out["locations"][A]["place"] == "电梯内"
    assert out["locations"][B]["place"] == "电梯内"
    assert out["locations"][A]["round"] == 8


def test_reflect_location_fallback_only_for_characters_in_narrative(monkeypatch):
    """位置兜底只填「正文或指令写到过」的角色（v2.1.1）。

    起因：`present` 已从在场名单改为名册（全员）。旧兜底对全名册用 scene.place 占位，
    等于把正文没写的人也搬进这一场——寝殿独处那一轮，六个人全被记在寝殿，下一轮
    [本轮场面] 就照着错的记录分场。判据改为「本轮正文或导演指令点到过这个名字」，
    没点到的人留空，由 [本轮场面] 的「位置未更新」如实交代。
    """
    import json as _json
    monkeypatch.setattr(director.llm, "complete",
                        lambda *a, **k: _json.dumps({"actions": {},
                                                     "location_updates": []},
                                                    ensure_ascii=False))
    monkeypatch.setattr(director.memory, "save", lambda sid, s: None)
    snap = {"scene": {"round": 1, "place": "书房"}, "present": [A, B, C],
            "relations": {}, "actions": {}, "silent_rounds": {}, "secrets": [],
            "facts": [], "states": {}, "goals": {}, "ledger": [], "locations": {}}
    monkeypatch.setattr(director.memory, "load", lambda sid: snap)
    director.reflect("sid", A + "：把门关上。")   # 正文只写到 A
    assert snap["locations"][A]["place"] == "书房"
    assert B not in snap["locations"] and C not in snap["locations"], \
        "正文未写到的名册成员不该被兜底搬进当前场景"

    # 导演指令是权威设定：指令点名的人同样算「本轮写过」，兜底照填。
    snap["locations"] = {}
    director.reflect("sid", A + "：把门关上。", "让" + B + "从外面回来。")
    assert snap["locations"][B]["place"] == "书房"
    assert C not in snap["locations"]


def test_exposure_requires_real_transfer_via(monkeypatch):
    """v0.17.3：纪官报 secret_exposures 但 via 非实传类（或缺失）时，
    不得翻成暴露，降级为起疑——防止「内心早已看穿」这类心理描写被误判成
    「实际得知秘密」（会话 256d924c 事故：开场即暴露）。
    """
    snap = {"scene": {"round": 2}, "present": [A, B], "relations": {},
            "actions": {}, "silent_rounds": {}, "goals": {}, "ledger": [],
            "states": {}, "facts": [],
            "secrets": [{"owner": A, "known_by": [], "holders": [],
                         "content": "角色甲的秘密", "state": "潜伏",
                         "suspicions": []}]}
    reply = f"{A}心里一沉：他早就看穿了。"
    # via 是「猜透」——单方面心证，不是实际信息传递
    payload = {"secret_exposures": [
        {"owner": A, "by": B, "via": "猜透", "evidence": "他早就看穿了"}]}
    monkeypatch.setattr(director.llm, "complete",
                        lambda *a, **k: __import__("json").dumps(payload, ensure_ascii=False))
    monkeypatch.setattr(director.memory, "load", lambda sid: snap)
    monkeypatch.setattr(director.memory, "save", lambda sid, s: None)
    director.reflect("sid", reply)
    s = snap["secrets"][0]
    # 不翻暴露；降级为起疑（v0.26.0 四态：起疑是可显示中间态）
    assert s["state"] == "起疑"
    assert B not in s.get("known_by", []) and B not in s.get("holders", [])
    assert any(x.get("by") == B for x in s.get("suspicions", []))


def test_exposure_via_whitelist_missing_downgrades(monkeypatch):
    """纪官漏填 via 时同样降级为起疑，而非静默放行成暴露。"""
    snap = {"scene": {"round": 2}, "present": [A, B], "relations": {},
            "actions": {}, "silent_rounds": {}, "goals": {}, "ledger": [],
            "states": {}, "facts": [],
            "secrets": [{"owner": A, "known_by": [], "holders": [],
                         "content": "角色甲的秘密", "state": "潜伏",
                         "suspicions": []}]}
    reply = f"{B}盯着{A}手臂上的伤疤。"
    payload = {"secret_exposures": [
        {"owner": A, "by": B, "evidence": "手臂上的伤疤"}]}  # 无 via
    monkeypatch.setattr(director.llm, "complete",
                        lambda *a, **k: __import__("json").dumps(payload, ensure_ascii=False))
    monkeypatch.setattr(director.memory, "load", lambda sid: snap)
    monkeypatch.setattr(director.memory, "save", lambda sid, s: None)
    director.reflect("sid", reply)
    s = snap["secrets"][0]
    assert s["state"] == "起疑"
    assert B not in s.get("known_by", [])


@pytest.mark.parametrize("raw, want", [
    ("自述/承认", "自述"),
    ("自述／承认", "自述"),          # 全角斜杠同样要吃下
    ("看见/听见", "看见"),
    ("承认、被告知", "承认"),
    ("看见 ", "看见"),
    ("看见", "看见"),
    ("自述／猜透", "自述"),          # 组合里混非法词：合法的那一半仍成立
    ("猜透", ""),                    # 单方面心证：语义放宽一条都不给
    ("心知肚明", ""),
    ("", ""),
    (None, ""),
])
def test_normalize_via_table(raw, want):
    """via 归一只认白名单词的组合写法，语义放宽一条都不给。"""
    assert director._normalize_via(raw) == want


def test_reflect_via_slash_combo_still_exposes(monkeypatch):
    """纪官照抄 schema 的斜杠枚举（via="自述/承认"）必须照常算本人当众说开。

    事故出处（nsfw 线 2026-11-13 实机探针 _probe_suspicion_live.py，10 轮）：纪官连续 6 轮
    把归属者当众承认正确上报成 secret_exposures，via 填的正是 "自述/承认"，被旧版
    `via not in EXPOSURE_VIA_WHITELIST` 的精确匹配判成非法、逐条降级为起疑——秘密十轮不翻态，
    起疑 hits 刷到 13。schema 的六类本来就是斜杠串起来的，「自述」「承认」两个词被斜杠相连，
    模型无从分辨。这条锁住归一，并锁死「不得顺手记一条起疑」——降级路径一旦回来，
    慢热链条就又断了。
    """
    snap = _snap_with_secret(A, "角色甲的秘密", ["失联", "父亲"])
    snap["present"] = [A, B]
    reply = f'{A}当众承认：“我确实藏了东西。”'
    payload = {"secret_exposures": [
        {"owner": A, "by": B, "via": "自述/承认", "evidence": "我确实藏了东西"}]}
    s = _run_reflect(monkeypatch, snap, reply, payload)
    # 自述类：入 known_by、把柄作废、在场非归属者全知情 -> 已公开
    assert s["state"] == "已公开", s
    assert B in s.get("known_by", [])
    assert s.get("holders") == []
    assert not any(x.get("by") == B for x in s.get("suspicions", [])), \
        "via 的组合写法不得再被降级成起疑"
    assert snap.get("ledger"), "本人当众说开应留下后果账"


def test_reflect_schema_does_not_enumerate_vias_with_slash():
    """schema 文案护栏：六类 via 不得再用斜杠串起来写。

    归一只是补救，文案本身把「自述」「承认」用斜杠相连才是诱导源。这条静态断言防止
    后来者为了省事把枚举改回「看见/听见/被告知/发现物证/自述/承认」。
    """
    src = (ENGINE / "director.py").read_text(encoding="utf-8")
    assert "看见/听见/被告知/发现物证/自述/承认" not in src
    assert "只能填「看见/听见" not in src
    assert "六个词里只挑一个填" in src


def test_exposure_via_whitelist_ok(monkeypatch):
    """via 属实传类（如「看见」）时，正常翻成暴露。"""
    snap = {"scene": {"round": 2}, "present": [A, B], "relations": {},
            "actions": {}, "silent_rounds": {}, "goals": {}, "ledger": [],
            "states": {}, "facts": [],
            "secrets": [{"owner": A, "known_by": [], "holders": [],
                         "content": "角色甲的秘密", "state": "潜伏",
                         "suspicions": []}]}
    reply = f"{B}看见{A}手臂上的伤疤。"
    payload = {"secret_exposures": [
        {"owner": A, "by": B, "via": "看见", "evidence": "看见角色甲手臂上的伤疤"}]}
    monkeypatch.setattr(director.llm, "complete",
                        lambda *a, **k: __import__("json").dumps(payload, ensure_ascii=False))
    monkeypatch.setattr(director.memory, "load", lambda sid: snap)
    monkeypatch.setattr(director.memory, "save", lambda sid, s: None)
    director.reflect("sid", reply)
    s = snap["secrets"][0]
    assert s["state"] == "暴露"
    assert B in s.get("known_by", [])


# ---- 暴露语义护栏（v0.17.6，会话 467f1e4c 事故）----
# _evidence_ok 只验「举证在不在正文」，不验「是否真构成该秘密的信息传递」，
# 纪官把内心独白/话题错位/不在场者截成证据也能过检，误把潜伏秘密翻成暴露。
# 两个叠加护栏（事实锚点相关 + 施受方在场）补上语义兜底，任一不过降级为起疑。


def _snap_with_secret(owner, content, keys):
    return {"scene": {"round": 3}, "present": [A, B, C], "relations": {},
            "actions": {}, "silent_rounds": {}, "goals": {}, "ledger": [],
            "states": {}, "facts": [],
            "secrets": [{"owner": owner, "known_by": [], "holders": [],
                         "content": content, "keys": keys, "state": "潜伏",
                         "suspicions": []}]}


def _run_reflect(monkeypatch, snap, reply, payload):
    import json as _json
    monkeypatch.setattr(director.llm, "complete",
                        lambda *a, **k: _json.dumps(payload, ensure_ascii=False))
    monkeypatch.setattr(director.memory, "load", lambda sid: snap)
    monkeypatch.setattr(director.memory, "save", lambda sid, s: None)
    director.reflect("sid", reply)
    return snap["secrets"][0]


def test_exposure_rejects_evidence_off_topic(monkeypatch):
    """护栏一：证据虽在正文、却不触及秘密事实锚点（话题错位），降级为起疑。

    对应会话 467f1e4c R4：纪官报「被告知了角色甲『某人失联』的秘密」，
    但引的证据是讨论伤口、只字不提失联——锚点（keys）不命中，不得翻暴露。
    """
    snap = _snap_with_secret(A, "角色甲的秘密", ["父亲", "失联", "下落"])
    reply = f"{B}盯着{A}手臂上的伤口说：“还在发痒。”"
    payload = {"secret_exposures": [
        {"owner": A, "by": B, "via": "被告知",
         "evidence": "还在发痒"}]}
    s = _run_reflect(monkeypatch, snap, reply, payload)
    assert s["state"] == "起疑"
    assert B not in s.get("known_by", [])
    assert any(x.get("by") == B for x in s.get("suspicions", []))


def test_exposure_rejects_inner_monologue(monkeypatch):
    """护栏二：证据是旁白心理独白、无施受方名字在场，不得翻暴露。

    对应会话 467f1e4c R4：纪官引「她坚持救治的病人尸变」——那是叙述者旁白
    （owner 的内心活动），不是 owner 对 by 说出口的信息传递。
    """
    snap = _snap_with_secret(A, "角色甲的秘密", ["旧队", "覆灭"])
    reply = f"夜色里，{A}想起旧队覆灭那晚，那个病人最终尸变。"
    payload = {"secret_exposures": [
        {"owner": A, "by": B, "via": "被告知",
         "evidence": "那个病人最终尸变"}]}
    s = _run_reflect(monkeypatch, snap, reply, payload)
    assert s["state"] == "起疑"
    assert B not in s.get("known_by", [])


def test_exposure_rejects_absent_listener(monkeypatch):
    """护栏二：证据里只有第三方、没有接收方 by 的名字（不在场者），不得翻暴露。

    对应会话 467f1e4c R10：纪官报「某人听见某人的秘密」，但该听众留守不在场，
    引的证据里根本没有这个听众。
    """
    snap = _snap_with_secret(A, "角色甲的秘密", ["旧队", "覆灭"])
    reply = f"{B}压低声音对{C}说：“旧队那晚，我本可以早点救。”"
    payload = {"secret_exposures": [
        {"owner": A, "by": B, "via": "听见",
         "evidence": "我本可以早点救"}]}
    s = _run_reflect(monkeypatch, snap, reply, payload)
    assert s["state"] == "起疑"
    assert B not in s.get("known_by", [])


def test_exposure_accepts_real_transfer_with_anchor(monkeypatch):
    """护栏不误伤真实暴露：证据同时命中锚点 + 施受方在场，正常翻暴露。"""
    snap = _snap_with_secret(A, "角色甲的秘密", ["旧队", "覆灭"])
    reply = f"{A}低头说：“旧队覆灭那晚，我本可以早点救你。”"
    payload = {"secret_exposures": [
        {"owner": A, "by": B, "via": "被告知",
         "evidence": f"{A}低头说：“旧队覆灭那晚，我本可以早点救你。”"}]}
    s = _run_reflect(monkeypatch, snap, reply, payload)
    assert s["state"] == "暴露"
    assert B in s.get("known_by", [])


def test_evidence_anchor_helpers():
    """_anchor_tokens / _evidence_related / _evidence_transfer 的边界行为。"""
    # keys 含短于 2 字的词（单字「爸」）应被剔除，只留 ≥2 字锚点
    assert director._anchor_tokens({"keys": ["爸", "父亲", "失联"]}) == ["父亲", "失联"]
    # keys 空退回归属者名；归属者单字名则无锚点
    assert director._anchor_tokens({"owner": "角色甲", "keys": []}) == ["角色甲"]
    assert director._anchor_tokens({"owner": "甲", "keys": []}) == []
    # 相关：证据与锚点共享 ≥2 字连续片段即真（不必逐字命中完整键）
    assert director._evidence_related("提到父亲失联", {"keys": ["父亲", "失联"]}) is True
    # 自然叙事语言 vs 触发词：key「旧队的死法」、正文「旧队覆灭」→ 共享「旧队」仍相关
    assert director._evidence_related(
        "旧队覆灭那晚", {"keys": ["旧队的死法"]}) is True
    assert director._evidence_related("只是伤口发痒", {"keys": ["父亲", "失联"]}) is False
    # 无锚点时放行（交由护栏二兜底）
    assert director._evidence_related("任意", {"keys": [], "owner": "甲"}) is True
    # 施受方：证据含 by 或 owner 名字即真；两者名字都缺席即假
    assert director._evidence_transfer("角色乙看见伤口", "角色乙", "角色甲") is True
    assert director._evidence_transfer("伤口很痛", "角色乙", "角色甲") is False


# ---- 纪官输出格式漂移防御（v0.16.1，80 轮压测暴露）----
# 纪官偶发把对象字段写成字符串（actions: "角色甲翻看物资"）或把对象列表写成
# 字符串数组（new_facts: ["角色甲死了"]）。修复前抛 'str' object has no
# attribute 'get'，整个 reflect 回写中断，本轮关系/行动/事实/状态全丢且无告警。

def test_as_dict_list_filters_non_dict():
    """只保留 dict 元素；非列表输入返回空列表。"""
    assert director._as_dict_list([{"a": 1}, "坏数据", 5, None]) == [{"a": 1}]
    assert director._as_dict_list("不是列表") == []
    assert director._as_dict_list(None) == []


def test_reflect_survives_string_actions(monkeypatch):
    """actions 被写成字符串时，reflect 不得抛错，且本轮跳过静默判定。

    关键在「跳过」而非「按全员无行为计静默」：后者会把在场全员误记成被遗忘，
    一次漂移即误触发硬性焦点并污染后续多轮。
    """
    snap = {"scene": {"round": 5}, "present": [A, B], "relations": {},
            "actions": {}, "silent_rounds": {A: 0, B: 0}, "secrets": [],
            "facts": [], "states": {}, "goals": {}, "ledger": []}
    payload = {"actions": "角色甲翻看物资，角色乙清点药品"}
    monkeypatch.setattr(director.llm, "complete",
                        lambda *a, **k: __import__("json").dumps(payload, ensure_ascii=False))
    monkeypatch.setattr(director.memory, "load", lambda sid: snap)
    saved = {}
    monkeypatch.setattr(director.memory, "save", lambda sid, s: saved.update(s))
    out = director.reflect("sid", f"{A}翻看物资，{B}清点药品。")
    assert out["actions"] == {}
    # 静默轮数未被本轮污染（仍为原值，不被 +1）
    assert out["silent_rounds"] == {A: 0, B: 0}, out["silent_rounds"]


def test_reflect_survives_string_list_fields(monkeypatch):
    """state_updates 等列表字段混入字符串时，reflect 不得抛错。"""
    snap = {"scene": {"round": 5}, "present": [A, B], "relations": {},
            "actions": {A: "翻看物资", B: "清点药品"}, "silent_rounds": {},
            "secrets": [], "facts": [], "states": {}, "goals": {}, "ledger": []}
    payload = {
        "actions": {A: "翻看物资", B: "清点药品"},
        "state_updates": ["门坏了", {"subject": "木门", "value": "已撞裂"}],
        "secret_exposures": "角色甲得知了秘密",
        "secret_suspicions": [None, "角色乙起疑"],
        "handle_releases": "把柄没了",
        "secret_touches": "都碰到了",
    }
    reply = f"{A}翻看物资。\n木门被撞裂，{B}退开半步。"
    monkeypatch.setattr(director.llm, "complete",
                        lambda *a, **k: __import__("json").dumps(payload, ensure_ascii=False))
    monkeypatch.setattr(director.memory, "load", lambda sid: snap)
    monkeypatch.setattr(director.memory, "save", lambda sid, s: None)
    out = director.reflect("sid", reply)
    # 合法的 dict 元素仍被正常记账（防御不是丢弃整个字段）
    assert any("木门" in k for k in out["states"]), out["states"]


# ---- 人物位置兜底（v0.31.1）----
# 纪官偶发漏报 location_updates（relations/goals 膨胀把该字段顶出截断区）时，
# 兜底用 scene.place 给仍无位置记录的在场角色填最小正确值，避免左栏整片「位置未记录」。

def test_reflect_location_fallback_fills_missing(monkeypatch):
    """纪官未报 location_updates 时，在场角色用 scene.place 兜底填充。"""
    import json as _json
    snap = {"scene": {"round": 3, "place": "大殿"}, "present": [A, B],
            "relations": {}, "actions": {A: "站立", B: "站立"},
            "silent_rounds": {}, "secrets": [], "facts": [], "states": {},
            "goals": {}, "ledger": []}
    payload = {"actions": {A: "站立", B: "站立"}}  # 无 location_updates
    monkeypatch.setattr(director.llm, "complete",
                        lambda *a, **k: _json.dumps(payload, ensure_ascii=False))
    monkeypatch.setattr(director.memory, "load", lambda sid: snap)
    monkeypatch.setattr(director.memory, "save", lambda sid, s: None)
    out = director.reflect("sid", f"{A}和{B}立在原地。")
    assert out["locations"][A]["place"] == "大殿"
    assert out["locations"][B]["place"] == "大殿"
    assert out["locations"][A]["round"] == 3


def test_reflect_location_fallback_preserves_reported(monkeypatch):
    """纪官已报的精确位置不被兜底覆盖；只补漏报者。"""
    import json as _json
    snap = {"scene": {"round": 4, "place": "大殿"}, "present": [A, B],
            "relations": {}, "actions": {}, "silent_rounds": {},
            "secrets": [], "facts": [], "states": {}, "goals": {}, "ledger": []}
    payload = {"location_updates": [{"who": A, "place": "偏殿"}]}  # 只报 A
    monkeypatch.setattr(director.llm, "complete",
                        lambda *a, **k: _json.dumps(payload, ensure_ascii=False))
    monkeypatch.setattr(director.memory, "load", lambda sid: snap)
    monkeypatch.setattr(director.memory, "save", lambda sid, s: None)
    out = director.reflect("sid", f"{A}进了偏殿，{B}仍立在原处。")
    assert out["locations"][A]["place"] == "偏殿"  # 保留纪官精确值
    assert out["locations"][B]["place"] == "大殿"  # 漏报者兜底


def test_reflect_location_fallback_skips_without_scene_place(monkeypatch):
    """scene.place 本身为空时无从兜底，不填也不报错。"""
    import json as _json
    snap = {"scene": {"round": 5}, "present": [A], "relations": {},
            "actions": {}, "silent_rounds": {}, "secrets": [], "facts": [],
            "states": {}, "goals": {}, "ledger": []}
    payload = {"actions": {}}
    monkeypatch.setattr(director.llm, "complete",
                        lambda *a, **k: _json.dumps(payload, ensure_ascii=False))
    monkeypatch.setattr(director.memory, "load", lambda sid: snap)
    monkeypatch.setattr(director.memory, "save", lambda sid, s: None)
    out = director.reflect("sid", f"{A}沉默。")
    assert out.get("locations", {}) == {}


# ---- 名册不再收缩（v2.1.0 拆职责）----
# present 从「在场名单」改为「角色名册」（建局 cast，永不收缩）。原 present_change
# 语义兜底整段移除：它同时承担「本轮可写的人」与「物理上同处一地的人」，而群像多线
# 叙事里两者必然打架（实测：模型把与主角同处一室的角色踢出名单、把千里之外的人留场，
# arrive 又基本不填）。物理同场改由 locations 表达（[本轮场面] 段按位置分场渲染）。
# 以下用例反转原三例，守护「present_change 不再被消费、也不再出现在模板里」。

def _pc_snap():
    return {"scene": {"round": 3}, "present": [A, B, C], "relations": {},
            "actions": {}, "silent_rounds": {}, "secrets": [], "facts": [],
            "states": {}, "goals": {}, "ledger": [], "locations": {}}


def test_reflect_ignores_present_change_field(monkeypatch):
    """旧字段残留或模型臆造 present_change 时，名册不得收缩、也不得扩张。"""
    import json as _json
    snap = _pc_snap()
    payload = {"actions": {},
               "present_change": {"leave": [A], "arrive": [D]}}
    monkeypatch.setattr(director.llm, "complete",
                        lambda *a, **k: _json.dumps(payload, ensure_ascii=False))
    monkeypatch.setattr(director.memory, "load", lambda sid: snap)
    monkeypatch.setattr(director.memory, "save", lambda sid, s: None)
    monkeypatch.setattr(director.store, "list_characters", lambda: [A, B, C, D])
    monkeypatch.setattr(director.store, "load_card", lambda n: {"name": n})
    out = director.reflect("sid", f"{A}上朝去了，{D}恰好赶来。")
    assert out["present"] == [A, B, C]


def test_reflect_prompt_has_no_present_change(monkeypatch):
    """纪官 prompt 模板里不得再有 present_change：字段留在模板而代码不消费 = 死机制。

    v2.0.0 那次定向反向合并误删了模板行，写回代码却留着，于是字段成了死代码
    （模型拿不到模板就从不输出）。此例防止它再回到模板里。
    """
    import json as _json
    captured = []
    snap = _pc_snap()

    def _cap(prompt, **kw):
        text = prompt if isinstance(prompt, str) else "".join(
            m.get("content", "") for m in prompt)
        captured.append(text)
        return _json.dumps({"actions": {}}, ensure_ascii=False)

    monkeypatch.setattr(director.llm, "complete", _cap)
    monkeypatch.setattr(director.memory, "load", lambda sid: snap)
    monkeypatch.setattr(director.memory, "save", lambda sid, s: None)
    monkeypatch.setattr(director.store, "list_characters", lambda: [A, B, C])
    director.reflect("sid", "无人离开。")
    assert captured, "纪官必须被调用"
    assert '"present_change"' not in captured[0]




# 叙事复读检测（detect_narrative_repeat）回归守护
# ----------------------------------------------------------------------------
# v0.28.7 把比对窗口 _COMPARE_ROUNDS 3→30、_MIN_REPEAT_SPAN 30→50：旧 3 轮窗口
# 盖不住「隔多轮复发的场景母题」（实测会话 a20d1c03 最远一次复读隔了 14 轮被漏检），
# 上调 min_span 压住大窗口的远距离合理回扣误判。以下用例用中性占位 + 合成文本
# 固化该行为，防窗口/门槛被改回旧值时悄悄失去召回能力（普适性红线：不绑剧本名）。
# v0.31.2：随 detect_narrative_repeat 一并从 v0.31.0 误删恢复（会话 44259301 复读）。
# ============================================================================


# 一个 150 字的唯一「场景母题」块（≥ _MIN_REPEAT_SPAN=50，整段搬的判据）。
# 用「第 N 行」序号保证块内每段互不重复，整块与任何 filler 轮零重叠。
_REPEATED_BLOCK = (
    "长案上摆着青瓷茶盏，窗外落着细碎的雨。"
    "风把檐角的铜铃吹得轻响，案边的烛火却纹丝不动。"
    "甲端起茶盏慢慢啜了一口，乙望着窗外出神。"
    "桌上的书信散开一角，墨迹尚未全干。"
    "甲把最后一句话压得很低，乙没有接话。"
)


# 15 个彼此内容互不相同的中性短句（每句 ≥ _MIN_REPEAT_SPAN=50 字之外无 50 字
# 整段与别句/母题块重叠），用作「干净历史轮」池，保证干净轮之间零整段复用。
_CLEAN_SENTENCES = [
    "檐下的雨顺着瓦缝滴落，石阶上的青苔被冲出一道浅浅的水痕。",
    "案头摊开的舆图被一阵穿堂风掀起边角，墨线在纸上微微发颤。",
    "炉上的铜壶咕嘟作响，白汽顶开壶盖又缩回去，反复了好几次。",
    "墙角的更漏滴得更慢了些，烛芯结出一粒小小的灯花。",
    "门缝里透进来的风把桌上的薄页吹得哗哗作响，像有谁在翻页。",
    "院中的老槐抖落几片残叶，落在石桌上，又被风卷了半圈。",
    "窗纸上映着一个晃动的人影，手里的油灯上下起伏，迟迟没有进来。",
    "井台上结了薄薄一层霜，水桶的铁链在井沿轻轻碰出细响。",
    "廊下的灯笼被风压得东倒西歪，光晕在地上画出一圈一圈的波纹。",
    "灶膛里的火苗忽明忽暗，映得墙上挂着的蓑衣影子一伸一缩。",
    "门外的狗忽然低低地呜咽了一声，又很快安静下去，只剩风声。",
    "桌底的猫弓着背慢慢踱到门口，回头望了一眼，才轻轻跳了出去。",
    "挂在梁上的风铃被穿堂风拨了一下，发出一声极轻的金属脆响。",
    "地上的水渍被拖过一道，倒映着头顶的星子，慢慢洇开又收拢。",
    "远处的山脊线上滚过一层薄云，遮住了最后一点残照的余温。",
]


def _filler_round(i):
    """中性填充轮：取整句（i 在 0..14 范围内时轮与轮互不相同，无 50 字整段重叠）。"""
    return _CLEAN_SENTENCES[i % len(_CLEAN_SENTENCES)]


def test_repeat_catches_far_scene_motive_recurrence():
    """窗口放宽核心场景：隔 14 轮复发的整段母题必须命中。

    母题块在 history[0]（14 轮之前）原样复现——旧 3 轮窗口盖不到（漏检落盘），
    新 30 轮窗口必须抓到。这正是会话 a20d1c03 的失败模式。
    """
    history = [_REPEATED_BLOCK] + [_filler_round(i) for i in range(1, 15)]
    current = _filler_round(99) + _REPEATED_BLOCK
    is_repeat, _, kind = director.detect_narrative_repeat(current, history)
    assert is_repeat is True
    assert kind == "history"


def test_repeat_clean_round_not_flagged_by_wider_window():
    """min_span 上调防误伤：无整段搬、仅短词复用的干净轮不得判复读。

    干净轮与历史只有角色名/短句级重叠（< _MIN_REPEAT_SPAN=50），即便在 30 轮
    大窗口下也不应误判（对应实测 a20d1c03 的 R11/R12 宫斗轮）。
    history 取 14 句、current 取第 15 句——彼此内容全不同、无 50 字整段重叠。
    """
    history = [_CLEAN_SENTENCES[i] for i in range(14)]
    current = _CLEAN_SENTENCES[14]
    is_repeat, _, _ = director.detect_narrative_repeat(current, history)
    assert is_repeat is False


def test_repeat_intra_round_self_repeat_still_detected():
    """轮内自重复不受窗口/门槛改动影响：前半段几乎原样在后半段重现仍须命中。

    self 分支走独立阈值（>=0.5），与 compare_rounds / min_span 解耦，固化其
    在 v0.28.7 改动后依旧生效，避免「只调了 history 路径、self 路径悄悄失效」。
    """
    half = _REPEATED_BLOCK + "（上）"
    current = half + "（下）" + _REPEATED_BLOCK
    is_repeat, _, kind = director.detect_narrative_repeat(current, [])
    assert is_repeat is True
    assert kind == "self"


# 秘密真相回喂（reflect 提示词）回归守护
# ----------------------------------------------------------------------------
# 会话 f3fab11e：reflect 喂给纪官的「秘密与把柄现状」只回喂 owner 名 + 状态，
# 不喂每条秘密的 content（正文真相）与 keys（事实锚点词）。纪官蒙眼归档，
# 会把「出现归属者名字的无关情报」误挂到其秘密上（把「陛下剥苏妃衣服」塞进
# 「高昌怯战」起疑记录），真正该记的「怯战铁证」又因正文用「那张牌」等代称、
# 不命中 keys 被降级漏记。此处固化「content + keys 必须喂给纪官」，防回退。
# ============================================================================


def test_reflect_feeds_secret_content_and_keys_to_clerk(monkeypatch):
    """reflect 的纪官提示词必须包含每条秘密的正文真相与事实锚点词。

    捕获 llm.complete 实际收到的 prompt，断言「秘密真相」原文与「事实锚点词」
    都出现在其中——纪官归档时才有真相锚点可对，避免蒙眼错配。
    """
    import json as _json
    snap = _snap_with_secret(A, "角色甲的秘密真相", ["旧队", "覆灭"])
    captured = {}

    def _capture(*a, **k):
        # reflect 走 llm.complete(prompt, ...)，prompt 是位置参数（消息列表）
        msgs = a[0] if a else []
        for m in msgs:
            if m.get("role") == "user":
                captured["user"] = m.get("content", "")
        return _json.dumps({}, ensure_ascii=False)

    monkeypatch.setattr(director.llm, "complete", _capture)
    monkeypatch.setattr(director.memory, "load", lambda sid: snap)
    monkeypatch.setattr(director.memory, "save", lambda sid, s: None)
    director.reflect("sid", f"{A}翻看旧队覆灭的卷宗。")

    prompt = captured.get("user", "")
    assert "秘密真相：角色甲的秘密真相" in prompt
    assert "事实锚点词：旧队、覆灭" in prompt



def _reflect_payload(monkeypatch, snap, reply, payload):
    import json as _json
    monkeypatch.setattr(director.llm, "complete",
                        lambda *a, **k: _json.dumps(payload, ensure_ascii=False))
    monkeypatch.setattr(director.memory, "load", lambda sid: snap)
    monkeypatch.setattr(director.memory, "save", lambda sid, s: None)
    director.reflect("sid", reply)
    return snap


def _bare_snap(round_no=5, present=None):
    return {"scene": {"round": round_no, "place": "某处甲", "time": "", "weather": ""},
            "present": present or [A, B], "relations": {}, "actions": {},
            "silent_rounds": {}, "secrets": [], "facts": [], "states": {},
            "goals": {}, "ledger": []}


def test_locations_drop_names_absent_from_reply(monkeypatch):
    """同理，没出场的角色不得被写进 locations（虚报会把下一轮分场带偏）。"""
    snap = _bare_snap()
    payload = {"location_updates": [{"who": A, "place": "库房"},
                                    {"who": B, "place": "某处甲"}]}
    out = _reflect_payload(monkeypatch, snap, f"{A}进了库房。", payload)
    assert A in out["locations"]
    assert B not in out["locations"]      # 正文没提到 B，不许替他占位


def _reflect_payload(monkeypatch, snap, reply, payload):
    import json as _json
    monkeypatch.setattr(director.llm, "complete",
                        lambda *a, **k: _json.dumps(payload, ensure_ascii=False))
    monkeypatch.setattr(director.memory, "load", lambda sid: snap)
    monkeypatch.setattr(director.memory, "save", lambda sid, s: None)
    director.reflect("sid", reply)
    return snap


def _bare_snap(round_no=5, present=None):
    return {"scene": {"round": round_no, "place": "某处甲", "time": "", "weather": ""},
            "present": present or [A, B], "relations": {}, "actions": {},
            "silent_rounds": {}, "secrets": [], "facts": [], "states": {},
            "goals": {}, "ledger": []}


def test_locations_drop_names_absent_from_reply(monkeypatch):
    """同理，没出场的角色不得被写进 locations（虚报会把下一轮分场带偏）。"""
    snap = _bare_snap()
    payload = {"location_updates": [{"who": A, "place": "库房"},
                                    {"who": B, "place": "某处甲"}]}
    out = _reflect_payload(monkeypatch, snap, f"{A}进了库房。", payload)
    assert A in out["locations"]
    assert B not in out["locations"]      # 正文没提到 B，不许替他占位

