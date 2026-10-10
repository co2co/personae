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


def test_release_handle_drops_and_transfers():
    """全版把柄消除：仅改 holders、known_by 不变；holders 清空后因已知情而落「暴露」
    （v0.26.0 四态：信息不可逆，不再回落「潜伏」；未众人皆知故不判「已公开」）。"""
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


# ---- 群演语义提取（v0.17.2：登记入口从散文正则挖掘改为纪官 aux_updates）----

def test_reflect_registers_aux_updates(monkeypatch):
    """纪官按语义上报的新出场人物登记为群演，身份说明写入 role。

    这是 v0.17.2 后群演的唯一登记入口：正则无法区分「他喃喃道」与「陈叔说」，
    语义判断交给纪官；引擎只做结构校验（代词/拟声/在场角色/机制名一律拒收）。
    泛称（路人/年轻女子）不在结构拒收之列：跨轮泛称可能真是不同角色，
    语义层由纪官自行判断，与既有「同轮消解」规则衔接。
    """
    import json as _json
    snap = {"scene": {"round": 5}, "present": [A, B], "relations": {},
            "actions": {}, "silent_rounds": {}, "secrets": [],
            "facts": [], "states": {}, "goals": {}, "ledger": [], "aux": []}
    payload = {
        "actions": {A: "开门"},
        "aux_updates": [
            {"name": "角色丙", "note": "隔壁的住户"},
            {"name": "他", "note": ""},           # 代词 → 拒
            {"name": "喃喃", "note": ""},         # 说话拟声 → 拒
            {"name": "胁语气", "note": ""},       # 描述后缀碎片 → 拒
            {"name": "想要", "note": ""},         # 能愿动词 → 拒
            {"name": A, "note": ""},              # 在场角色 → 拒
            {"name": "环境推手", "note": ""},     # 机制名 → 拒
        ],
    }
    monkeypatch.setattr(director.llm, "complete",
                        lambda *a, **k: _json.dumps(payload, ensure_ascii=False))
    monkeypatch.setattr(director.memory, "load", lambda sid: snap)
    monkeypatch.setattr(director.memory, "save", lambda sid, s: None)
    monkeypatch.setattr(director.store, "list_characters", lambda: [])
    out = director.reflect("sid", f"{A}开门。角色丙在楼道里喊了一嗓子。")
    assert [a["name"] for a in out["aux"]] == ["角色丙"]
    assert out["aux"][0]["role"] == "隔壁的住户"
    assert out["aux"][0]["intro_round"] == 5


def test_reflect_aux_updates_dedup(monkeypatch):
    """同一称呼不重复登记；纪官漏填 aux_updates 时也不影响既有群演。"""
    import json as _json
    snap = {"scene": {"round": 6}, "present": [A], "relations": {},
            "actions": {}, "silent_rounds": {}, "secrets": [],
            "facts": [], "states": {}, "goals": {}, "ledger": [],
            "aux": [{"name": "角色丙", "intro_round": 5, "role": "邻居",
                     "note": "", "status": "活跃"}]}
    payload = {"actions": {A: "开门"}, "aux_updates": [{"name": "角色丙", "note": ""}]}
    monkeypatch.setattr(director.llm, "complete",
                        lambda *a, **k: _json.dumps(payload, ensure_ascii=False))
    monkeypatch.setattr(director.memory, "load", lambda sid: snap)
    monkeypatch.setattr(director.memory, "save", lambda sid, s: None)
    monkeypatch.setattr(director.store, "list_characters", lambda: [])
    out = director.reflect("sid", f"{A}开门。")
    assert len(out["aux"]) == 1
    assert out["aux"][0]["role"] == "邻居"      # 未被空 note 覆盖


def test_reflect_aux_updates_absent_keeps_aux(monkeypatch):
    """纪官没吐 aux_updates（老格式/漏填）时既有 aux 原样保留，不报错。"""
    import json as _json
    snap = {"scene": {"round": 3}, "present": [A], "relations": {},
            "actions": {}, "silent_rounds": {}, "secrets": [],
            "facts": [], "states": {}, "goals": {}, "ledger": [],
            "aux": [{"name": "角色丙", "intro_round": 2, "role": "邻居",
                     "note": "", "status": "活跃"}]}
    payload = {"actions": {A: "清点物资"}}
    monkeypatch.setattr(director.llm, "complete",
                        lambda *a, **k: _json.dumps(payload, ensure_ascii=False))
    monkeypatch.setattr(director.memory, "load", lambda sid: snap)
    monkeypatch.setattr(director.memory, "save", lambda sid, s: None)
    monkeypatch.setattr(director.store, "list_characters", lambda: [])
    out = director.reflect("sid", f"{A}清点物资。")
    assert [a["name"] for a in out["aux"]] == ["角色丙"]


def test_reflect_aux_updates_merges_replaces(monkeypatch):
    """纪官声明「此人就是旧称呼」时改名合并，不产生重复 chip，intro_round 保留首次出场。"""
    import json as _json
    snap = {"scene": {"round": 2}, "present": [A], "relations": {},
            "actions": {}, "silent_rounds": {}, "secrets": [],
            "facts": [], "states": {}, "goals": {}, "ledger": [],
            "aux": [{"name": "女幸存者", "intro_round": 1,
                     "role": "被放入室内的陌生女性", "note": "", "status": "活跃"}]}
    payload = {"actions": {A: "开门"},
               "aux_updates": [{"name": "苏青", "note": "自称纺织厂工人",
                                "replaces": "女幸存者"}]}
    monkeypatch.setattr(director.llm, "complete",
                        lambda *a, **k: _json.dumps(payload, ensure_ascii=False))
    monkeypatch.setattr(director.memory, "load", lambda sid: snap)
    monkeypatch.setattr(director.memory, "save", lambda sid, s: None)
    monkeypatch.setattr(director.store, "list_characters", lambda: [])
    out = director.reflect("sid", "“我叫苏青。”她说。")
    assert len(out["aux"]) == 1, out["aux"]
    entry = out["aux"][0]
    assert entry["name"] == "苏青"
    assert entry["intro_round"] == 1            # 保留首次出场回合
    assert entry["role"] == "自称纺织厂工人"     # 身份说明被更新


def test_reflect_aux_updates_replaces_unknown_treated_as_new(monkeypatch):
    """replaces 指向不在册的称呼时按新群演登记，不静默丢弃。"""
    import json as _json
    snap = {"scene": {"round": 2}, "present": [A], "relations": {},
            "actions": {}, "silent_rounds": {}, "secrets": [],
            "facts": [], "states": {}, "goals": {}, "ledger": [], "aux": []}
    payload = {"actions": {A: "开门"},
               "aux_updates": [{"name": "苏青", "note": "自称工人",
                                "replaces": "女幸存者"}]}
    monkeypatch.setattr(director.llm, "complete",
                        lambda *a, **k: _json.dumps(payload, ensure_ascii=False))
    monkeypatch.setattr(director.memory, "load", lambda sid: snap)
    monkeypatch.setattr(director.memory, "save", lambda sid, s: None)
    monkeypatch.setattr(director.store, "list_characters", lambda: [])
    out = director.reflect("sid", "她说她叫苏青。")
    assert [a["name"] for a in out["aux"]] == ["苏青"]


def test_reflect_aux_updates_replaces_conflict_no_duplicate(monkeypatch):
    """新旧名都在册（历史脏数据）时不合并、不造第三条，留待人工/后续裁决。"""
    import json as _json
    snap = {"scene": {"round": 3}, "present": [A], "relations": {},
            "actions": {}, "silent_rounds": {}, "secrets": [],
            "facts": [], "states": {}, "goals": {}, "ledger": [],
            "aux": [{"name": "女幸存者", "intro_round": 1, "role": "陌生女性",
                     "note": "", "status": "活跃"},
                    {"name": "苏青", "intro_round": 2, "role": "新来的",
                     "note": "", "status": "活跃"}]}
    payload = {"actions": {A: "关门"},
               "aux_updates": [{"name": "苏青", "note": "", "replaces": "女幸存者"}]}
    monkeypatch.setattr(director.llm, "complete",
                        lambda *a, **k: _json.dumps(payload, ensure_ascii=False))
    monkeypatch.setattr(director.memory, "load", lambda sid: snap)
    monkeypatch.setattr(director.memory, "save", lambda sid, s: None)
    monkeypatch.setattr(director.store, "list_characters", lambda: [])
    out = director.reflect("sid", "苏青点头。")
    names = [a["name"] for a in out["aux"]]
    assert len(names) == 2 and set(names) == {"女幸存者", "苏青"}


def test_reflect_aux_fallback_merge_on_missing_replaces(monkeypatch):
    """纪官漏填 replaces 时的结构兜底：自报姓名 + 本轮唯一泛称旧群演 → 合并。

    证据链：叙事里有「我叫苏青」、且本轮只提及「女幸存者」一个泛称群演——
    两条证据同时成立才合并，缺一即保留两条。
    """
    import json as _json
    snap = {"scene": {"round": 2}, "present": [A], "relations": {},
            "actions": {}, "silent_rounds": {}, "secrets": [],
            "facts": [], "states": {}, "goals": {}, "ledger": [],
            "aux": [{"name": "女幸存者", "intro_round": 1, "role": "陌生女性",
                     "note": "", "status": "活跃"}]}
    payload = {"actions": {A: "点头"},
               "aux_updates": [{"name": "苏青", "note": "自称纺织厂工人"}]}
    monkeypatch.setattr(director.llm, "complete",
                        lambda *a, **k: _json.dumps(payload, ensure_ascii=False))
    monkeypatch.setattr(director.memory, "load", lambda sid: snap)
    monkeypatch.setattr(director.memory, "save", lambda sid, s: None)
    monkeypatch.setattr(director.store, "list_characters", lambda: [])
    out = director.reflect("sid", "女幸存者站在门口。“我叫苏青。”她说。")
    assert len(out["aux"]) == 1, out["aux"]
    assert out["aux"][0]["name"] == "苏青"
    assert out["aux"][0]["intro_round"] == 1


def test_reflect_aux_fallback_not_triggered_for_real_name_old(monkeypatch):
    """旧群演是真名（非泛称）时不做兜底合并——避免把两个人捏成一个人。"""
    import json as _json
    snap = {"scene": {"round": 2}, "present": [A], "relations": {},
            "actions": {}, "silent_rounds": {}, "secrets": [],
            "facts": [], "states": {}, "goals": {}, "ledger": [],
            "aux": [{"name": "王强", "intro_round": 1, "role": "邻居",
                     "note": "", "status": "活跃"}]}
    payload = {"actions": {A: "点头"},
               "aux_updates": [{"name": "李四", "note": "新来的人"}]}
    monkeypatch.setattr(director.llm, "complete",
                        lambda *a, **k: _json.dumps(payload, ensure_ascii=False))
    monkeypatch.setattr(director.memory, "load", lambda sid: snap)
    monkeypatch.setattr(director.memory, "save", lambda sid, s: None)
    monkeypatch.setattr(director.store, "list_characters", lambda: [])
    out = director.reflect("sid", "王强靠在门边。“我叫李四。”新人说。")
    names = sorted(a["name"] for a in out["aux"])
    assert names == ["李四", "王强"], names


def test_reflect_aux_fallback_not_triggered_with_two_generics(monkeypatch):
    """本轮提及两条泛称群演时证据不足，不兜底合并。"""
    import json as _json
    snap = {"scene": {"round": 2}, "present": [A], "relations": {},
            "actions": {}, "silent_rounds": {}, "secrets": [],
            "facts": [], "states": {}, "goals": {}, "ledger": [],
            "aux": [{"name": "女幸存者", "intro_round": 1, "role": "陌生女性",
                     "note": "", "status": "活跃"},
                    {"name": "老保安", "intro_round": 1, "role": "楼里巡逻的",
                     "note": "", "status": "活跃"}]}
    payload = {"actions": {A: "点头"},
               "aux_updates": [{"name": "苏青", "note": ""}]}
    monkeypatch.setattr(director.llm, "complete",
                        lambda *a, **k: _json.dumps(payload, ensure_ascii=False))
    monkeypatch.setattr(director.memory, "load", lambda sid: snap)
    monkeypatch.setattr(director.memory, "save", lambda sid, s: None)
    monkeypatch.setattr(director.store, "list_characters", lambda: [])
    out = director.reflect("sid", "女幸存者和老保安都看着她。“我叫苏青。”她说。")
    names = sorted(a["name"] for a in out["aux"])
    assert names == ["女幸存者", "老保安", "苏青"], names


# ---- 背景人物活动化：语义判定移交纪官（v0.17.2）----

def test_reflect_records_offscreen_activity(monkeypatch):
    """纪官上报的背景人物活动化经逐字举证核验后记入快照，供下轮提示词点名批评。

    引擎不再靠正则扫正文：判据②「分句主语 + 动作字表」把「来自远方的指令」这类
    合法提及也判成失责，实测 23 轮命中真失责≈0，却整句删掉正常叙事。
    """
    import json as _json
    snap = {"scene": {"round": 4}, "present": [A], "relations": {f"{A} → 角色丙": "妹妹"},
            "actions": {}, "silent_rounds": {}, "secrets": [],
            "facts": [], "states": {}, "goals": {}, "ledger": [], "aux": []}
    payload = {"actions": {A: "沉默"},
               "offscreen_activity": [{"name": "角色丙",
                                       "evidence": "角色丙从门后走出"}]}
    monkeypatch.setattr(director.llm, "complete",
                        lambda *a, **k: _json.dumps(payload, ensure_ascii=False))
    monkeypatch.setattr(director.memory, "load", lambda sid: snap)
    monkeypatch.setattr(director.memory, "save", lambda sid, s: None)
    monkeypatch.setattr(director.store, "list_characters", lambda: [])
    out = director.reflect("sid", "门吱呀一响。角色丙从门后走出，静静望着他。")
    viol = out.get("offscreen_violated") or []
    assert len(viol) == 1 and viol[0]["name"] == "角色丙"
    assert viol[0]["round"] == 4


def test_reflect_offscreen_activity_requires_evidence(monkeypatch):
    """举证不在正文里（幻觉/改写）的条目必须丢弃，绝不记入快照。"""
    import json as _json
    snap = {"scene": {"round": 4}, "present": [A], "relations": {f"{A} → 角色丙": "妹妹"},
            "actions": {}, "silent_rounds": {}, "secrets": [],
            "facts": [], "states": {}, "goals": {}, "ledger": [], "aux": []}
    payload = {"actions": {A: "沉默"},
               "offscreen_activity": [{"name": "角色丙",
                                       "evidence": "角色丙推开窗跳了出去"}]}
    monkeypatch.setattr(director.llm, "complete",
                        lambda *a, **k: _json.dumps(payload, ensure_ascii=False))
    monkeypatch.setattr(director.memory, "load", lambda sid: snap)
    monkeypatch.setattr(director.memory, "save", lambda sid, s: None)
    monkeypatch.setattr(director.store, "list_characters", lambda: [])
    out = director.reflect("sid", "门吱呀一响。他静静望着门口。")
    assert not out.get("offscreen_violated")


def test_reflect_offscreen_activity_ignores_non_background(monkeypatch):
    """上报的名字不在背景人物名单里（在场角色/有卡角色）时一律忽略。"""
    import json as _json
    snap = {"scene": {"round": 4}, "present": [A], "relations": {f"{A} → {B}": "同伴"},
            "actions": {}, "silent_rounds": {}, "secrets": [],
            "facts": [], "states": {}, "goals": {}, "ledger": [], "aux": []}
    payload = {"actions": {A: "沉默"},
               "offscreen_activity": [{"name": A, "evidence": "他静静望着门口"}]}
    monkeypatch.setattr(director.llm, "complete",
                        lambda *a, **k: _json.dumps(payload, ensure_ascii=False))
    monkeypatch.setattr(director.memory, "load", lambda sid: snap)
    monkeypatch.setattr(director.memory, "save", lambda sid, s: None)
    monkeypatch.setattr(director.store, "list_characters", lambda: [])
    out = director.reflect("sid", "他静静望着门口。")
    assert not out.get("offscreen_violated")


def test_reflect_clears_offscreen_flag_when_clean(monkeypatch):
    """本轮无越界时必须清掉上一轮的标记，否则批评会永久挂着。"""
    import json as _json
    snap = {"scene": {"round": 5}, "present": [A], "relations": {f"{A} → 角色丙": "妹妹"},
            "actions": {}, "silent_rounds": {}, "secrets": [],
            "facts": [], "states": {}, "goals": {}, "ledger": [], "aux": [],
            "offscreen_violated": [{"name": "角色丙", "evidence": "旧证据", "round": 4}]}
    payload = {"actions": {A: "沉默"}, "offscreen_activity": []}
    monkeypatch.setattr(director.llm, "complete",
                        lambda *a, **k: _json.dumps(payload, ensure_ascii=False))
    monkeypatch.setattr(director.memory, "load", lambda sid: snap)
    monkeypatch.setattr(director.memory, "save", lambda sid, s: None)
    monkeypatch.setattr(director.store, "list_characters", lambda: [])
    out = director.reflect("sid", "他沉默了很久。")
    assert "offscreen_violated" not in out


# ---- 场景信号并联纪官（v0.17.2）----

def test_reflect_records_scene_shift(monkeypatch):
    """纪官读出叙事里场景已变化则记入快照，供下轮 scene.apply 追平场景状态。"""
    import json as _json
    snap = {"scene": {"round": 7}, "present": [A], "relations": {},
            "actions": {}, "silent_rounds": {}, "secrets": [],
            "facts": [], "states": {}, "goals": {}, "ledger": [], "aux": []}
    payload = {"actions": {A: "望向窗外"},
               "scene_shift": {"changed": True, "place": "公寓楼道",
                               "time": "入夜", "weather": "雨"}}
    monkeypatch.setattr(director.llm, "complete",
                        lambda *a, **k: _json.dumps(payload, ensure_ascii=False))
    monkeypatch.setattr(director.memory, "load", lambda sid: snap)
    monkeypatch.setattr(director.memory, "save", lambda sid, s: None)
    monkeypatch.setattr(director.store, "list_characters", lambda: [])
    out = director.reflect("sid", "他们摸黑下楼，雨声从楼道外传来。")
    assert out["scene_shift"] == {"changed": True, "place": "公寓楼道",
                                  "time": "入夜", "weather": "雨"}


def test_reflect_clears_scene_shift_when_unchanged(monkeypatch):
    """本轮无场景变化时清除上一轮标记，避免信号永久挂着。"""
    import json as _json
    snap = {"scene": {"round": 8}, "present": [A], "relations": {},
            "actions": {}, "silent_rounds": {}, "secrets": [],
            "facts": [], "states": {}, "goals": {}, "ledger": [], "aux": [],
            "scene_shift": {"changed": True, "place": "旧地点", "time": "", "weather": ""}}
    payload = {"actions": {A: "沉默"}, "scene_shift": {"changed": False}}
    monkeypatch.setattr(director.llm, "complete",
                        lambda *a, **k: _json.dumps(payload, ensure_ascii=False))
    monkeypatch.setattr(director.memory, "load", lambda sid: snap)
    monkeypatch.setattr(director.memory, "save", lambda sid, s: None)
    monkeypatch.setattr(director.store, "list_characters", lambda: [])
    out = director.reflect("sid", "他沉默了很久。")
    assert "scene_shift" not in out
