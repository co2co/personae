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
    """全版把柄消除：仅改 holders、known_by 不变；holders 清空时状态回落潜伏。"""
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
    # D 失去 -> holders 空 -> 回落潜伏
    assert director._release_handle(s, D, "", 8) is True
    assert s["holders"] == []
    assert s["state"] == "潜伏"
    # 不持有该把柄的人 -> 无变更
    assert director._release_handle(s, "角色戊", "", 9) is False


def test_record_exposure_adds_holder():
    """全版：曝光同时写入 known_by 与 holders；state 基于 holders。"""
    s = {"owner": A, "known_by": []}
    director._record_exposure(s, B, "叙事揭露", 3)
    assert B in s["known_by"] and B in s["holders"]
    assert s["state"] == "暴露"


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
