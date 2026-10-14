"""关系表与关系冻结测试（会话 0ac57abf 审计驱动的修复）。

覆盖：
  1. 角色卡 relations 字段可确定性地构建权威关系基线（seed_relations_from_cards）。
  2. reflect 冻结未在场/无卡关联人物的关系，禁止模型改写或升级（小姨子->妻子类漂移拦截）。
"""

import json
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

import director  # noqa: E402
import memory  # noqa: E402


# ---------------------------------------------------------------------------
# 0. relations_base 必须由 memory.new 一并固化（v0.7.7 修复）
# ---------------------------------------------------------------------------

def test_memory_new_seeds_relations_base(monkeypatch):
    """真实会话（卡片自带 relations）必须固化 relations_base。

    回归护城河：v0.7.4/v0.7.6 的「未在场冻结」「亲属身份冻结」都以 relations_base
    为唯一可信源；若 memory.new 不固化，真实会话（卡片有 relations 时跳过 app.py
    固化分支）会让 relations_base 为空，两道闸静默失效。

    卡片与世界书用内存 mock 提供，不依赖磁盘文件。
    """
    cards = {
        "角色甲": {"name": "角色甲", "relations": {"角色乙": "妻子"},
                "core_desire": "", "core_fear": "", "short_goal": ""},
        "角色乙": {"name": "角色乙", "relations": {"角色甲": "丈夫"},
                "core_desire": "", "core_fear": "", "short_goal": ""},
    }
    monkeypatch.setattr(memory.store, "load_card", lambda name: cards[name])
    monkeypatch.setattr(memory.store, "load_world", lambda name: [])
    sid = memory.new(["角色甲", "角色乙"], scene_place="安全屋", world_name="测试世界")
    try:
        snap = memory.load(sid)
        rel = snap.get("relations", {})
        base = snap.get("relations_base", {})
        assert rel, "relations 不应为空"
        assert base, "relations_base 不应为空（v0.7.7 修复点）"
        assert base == rel, "relations_base 应与 seeded relations 一致"
        # 亲属身份键应在基线中
        assert director._first_kinship(base.get("角色甲 → 角色乙", "")) == "妻子"
    finally:
        import shutil
        from pathlib import Path
        d = Path(memory.SESS_DIR) / sid if not str(memory.SESS_DIR).endswith(sid) else None
        # 直接按 sid 定位会话目录并清理
        root = Path(memory.SESS_DIR)
        target = root / sid
        if target.exists():
            shutil.rmtree(target)


# ---------------------------------------------------------------------------
# 1. 卡片 relations -> 权威基线
# ---------------------------------------------------------------------------

def test_seed_relations_from_cards():
    cards = {
        "角色甲": {"relations": {"角色乙": "丈夫", "角色丙": "妹妹", "角色丁": "侄子"}},
        "角色乙": {"relations": {"角色甲": "妻子", "角色丙": "小姨子"}},
    }
    base = director.seed_relations_from_cards(cards)
    assert base.get("角色甲 → 角色丙") == "妹妹"
    assert base.get("角色乙 → 角色丙") == "小姨子"
    assert base.get("角色甲 → 角色乙") == "丈夫"


# ---------------------------------------------------------------------------
# 3. reflect 冻结未在场关联人物关系
# ---------------------------------------------------------------------------

def test_reflect_freezes_offscreen_relation(monkeypatch):
    """模型试图把未在场/无卡的角色丙升为「妻子」，必须被冻结为基线小姨子；
    镜头内（角色乙/角色甲 都在场）的关系允许演化。"""
    def fake_complete(messages, **kwargs):
        return json.dumps({
            "relations": {
                "角色乙 → 角色丙": "妻子，占有欲强烈",
                "角色乙 → 角色甲": "妻子，关系紧张（镜头内演化）",
            },
            "actions": {}, "goals": {},
        }, ensure_ascii=False)
    monkeypatch.setattr(director.llm, "complete", fake_complete)

    snap = {
        "present": ["角色乙", "角色甲"],
        "relations": {"角色乙 → 角色丙": "小姨子", "角色乙 → 角色甲": "妻子"},
        "relations_base": {"角色乙 → 角色丙": "小姨子", "角色乙 → 角色甲": "妻子"},
        "secrets": [], "goals": {}, "actions": {}, "ledger": [],
    }
    monkeypatch.setattr(director.memory, "load", lambda sid: snap)
    monkeypatch.setattr(director.memory, "save", lambda sid, s: None)

    director.reflect("sid-x", "角色乙握了握角色甲的手")

    # 未在场关联人物：冻结为基线，不得升级为妻子
    assert snap["relations"]["角色乙 → 角色丙"] == "小姨子", snap["relations"]
    # 镜头内角色：关系允许随剧情演化
    assert snap["relations"]["角色乙 → 角色甲"] == "妻子，关系紧张（镜头内演化）"


# ---------------------------------------------------------------------------
# 4. 背景人物活动化自检（simon 验收：引擎把背景人物写成活动角色即失责）
# ---------------------------------------------------------------------------

def test_background_names_excludes_present():
    """relations 里出现但不在在场名单的角色 = 背景人物（如角色丙）。"""
    snap = {"present": ["角色乙", "角色甲"],
            "relations": {"角色乙 → 角色丙": "小姨子",
                          "角色甲 → 角色丙": "妹妹",
                          "角色乙 → 角色甲": "妻子"}}
    offs = director.background_names_from_relations(snap, snap["present"])
    assert offs == ["角色丙"]


def test_offscreen_dialogue_flagged():
    """背景人物获得独立台词块（对白/独白）-> 失责。"""
    offs = ["角色丙"]
    reply = "角色乙看着窗外。\n角色丙：其实我早就知道了，姐夫。\n角色甲叹了口气。"
    viol, hits = director.detect_offscreen_activity(reply, offs)
    assert viol is True
    assert any("角色丙" in h for h in hits)


def test_offscreen_action_subject_flagged():
    """第三人称里背景人物作主语且有动作 -> 失责（如「角色丙从门后走出」）。"""
    offs = ["角色丙"]
    reply = "角色乙沉默不语。角色丙从门后走出，静静望着二人。角色甲握紧了手。"
    viol, hits = director.detect_offscreen_activity(reply, offs)
    assert viol is True
    assert any(h.startswith("角色丙") for h in hits)


def test_offscreen_mentioned_by_present_ok():
    """在场角色以谈论方式带过背景人物 -> 不失责（允许的背景提及）。"""
    offs = ["角色丙"]
    reply = "角色甲低声说：我妹妹梦琪最近总一个人待着，怪让人担心的。角色乙点点头。"
    viol, hits = director.detect_offscreen_activity(reply, offs)
    assert viol is False, hits


def test_offscreen_no_background_clean():
    """无背景人物时自检直接通过。"""
    viol, hits = director.detect_offscreen_activity("角色乙走了出去。", [])
    assert viol is False and hits == []


def test_preserve_kinship_blocks_identity_flip():
    """亲属身份冻结：父亲被模型改写成姐夫时，应回退为父亲、保留情感修饰。"""
    corrected = director._preserve_kinship("父亲", "姐夫，挑衅者/主动方")
    assert corrected.startswith("父亲"), corrected
    assert "挑衅者" in corrected, corrected


def test_preserve_kinship_allows_emotional_evolution():
    """亲属身份一致时，允许情感/状态修饰演化（父亲 -> 父亲，关系紧张）。"""
    corrected = director._preserve_kinship("父亲，关系紧张", "父亲，关系彻底破裂")
    assert corrected == "父亲，关系彻底破裂", corrected


def test_preserve_kinship_no_baseline_free():
    """基线无亲属身份词时（如同事），模型可自由定义关系身份。"""
    corrected = director._preserve_kinship("同事", "恋人，暗通款曲")
    assert corrected == "恋人，暗通款曲", corrected


def test_preserve_kinship_mother_sister_in_law_blocked():
    """母亲被改写成嫂子时，应回退为母亲。"""
    corrected = director._preserve_kinship("母亲", "嫂子，复杂情感萌芽")
    assert corrected.startswith("母亲"), corrected


# --- 亲属身份冻结的误判防护（v0.15.x 修复）---

def test_kinship_single_char_tokens_removed():
    """词表不得含单字身份词。

    单字（母/子/夫/弟…）在中文里几乎只作长词碎片（母子/母性/夫人/兄弟）出现，
    早期版本收录导致「以A母子的生死为筹码」被当成对 B 的身份声明「子」，
    冻结机制反过来把模型写对的「妻子」改坏成「子，关系紧张」。
    """
    assert not [t for t in director._KINSHIP_TOKENS if len(t) == 1], \
        "身份词表混入单字词：%s" % [t for t in director._KINSHIP_TOKENS if len(t) == 1]


def test_kinship_covers_common_relations():
    """词表须覆盖中国亲属称谓里的常见缺项（v0.18.6 补词守护）。

    回归事故：姨父/姑父/堂表兄弟姐妹/侄女外甥女/岳父岳母/继子女养子女等都不在表，
    作者在 relations_kinship 里显式声明了也会被 seed_kinship_from_cards 静默丢弃——
    声明形同虚设，且无任何报错（该函数对非法词静默 return），极难排查。
    """
    must = [
        # 姨父 /姑父 / 舅妈（母系亲属的配偶，原表完全缺失）
        "姨父", "姨母", "姑父", "姑母", "舅妈", "舅母",
        # 父系伯叔
        "伯父", "伯母", "叔父", "叔母", "婶婶",
        # 堂表兄弟姐妹
        "堂兄", "堂弟", "堂姐", "堂妹", "堂哥",
        "表兄", "表弟", "表姐", "表妹", "表哥",
        # 侄辈女系
        "侄女", "外甥女", "外孙", "外孙女",
        # 核心姻亲长辈
        "岳父", "岳母", "亲家", "亲家公", "亲家母",
        # 继嗣 / 收养
        "继子", "继女", "养子", "养女", "义父", "义母",
        # 高祖辈
        "曾祖父", "曾祖母", "外祖父", "外祖母",
        # 妻子的姐妹（成年向剧本高频设定）
        "小姨子", "大姨子",
    ]
    missing = [k for k in must if k not in director._KINSHIP_TOKENS]
    assert not missing, "词表缺失常见亲属词：%s" % missing


def test_kinship_excludes_social_relations():
    """社会关系词一律不得进冻结表（守护沙盘的「关系演化」核心能力）。

    本引擎的主功能就是关系演化——同事→恋人、下属上位、房东变盟友都是要演的东西。
    一旦把「同事」写进表，_preserve_kinship 会把模型写对的「恋人」拉回「同事」，
    等于从机制上关掉引擎的主要功能（守护用例见
    test_preserve_kinship_no_baseline_free）。
    职业/称谓类词另有一重风险：在中文里大量作状语与口语称呼（「领导在场」）。
    """
    forbidden = [
        "同事", "邻居", "房东", "租客", "队友", "同学", "朋友", "熟人",
        "医生", "老师", "领导", "上司", "下属", "老板", "员工", "客户",
        "恋人", "情人", "暧昧", "追求者",
        # 作量词/口语称呼，极易误判
        "大哥", "小弟", "大爷", "大妈", "师傅", "姑娘", "小姐", "先生",
    ]
    bad = [t for t in forbidden if t in director._KINSHIP_TOKENS]
    assert not bad, "社会关系/关系状态词混入冻结表：%s" % bad


def test_kinship_new_tokens_detected_as_declaration():
    """新补的词必须能被句首声明规则识别（否则补了也白补）。"""
    cases = [
        ("姨父：妻子的姐姐的丈夫，一直照顾这个家", "姨父"),
        ("堂哥：从小一起长大，感情很深", "堂哥"),
        ("表姐：偶尔来串门，性子温和", "表姐"),
        ("岳父：威严的长辈，从不过问家事", "岳父"),
        ("继女：后来成了这个家的人", "继女"),
        ("侄女", "侄女"),
        ("小姨子，一直住在娘家", "小姨子"),
    ]
    for v, expect in cases:
        got = director._first_kinship(v)
        assert got == expect, "新词 %r 未被识别为身份声明（实得 %r）" % (expect, got)


def test_kinship_new_tokens_freeze_against_identity_flip():
    """新补词的冻结生效：模型把姨父写成姐夫/叔叔，须拉回基准身份。"""
    corrected = director._preserve_kinship("姨父，一直照顾她", "姐夫，挑衅者", declared="姨父")
    assert corrected.startswith("姨父"), corrected
    assert "挑衅者" in corrected, corrected
    # 无显式声明时，走句首基准推断
    assert director._preserve_kinship("堂哥：一起长大", "表弟，暗中较劲").startswith("堂哥")


def test_kinship_new_tokens_no_narrative_false_positive():
    """新补词不得在叙述句里误判为身份声明（补词不能削弱原有的误判防护）。"""
    narrative = [
        "以她的堂兄弟姐妹的处境为筹码",
        "对其岳母的扶持的回答是不屑一顾",
        "他不敢戳破「曾祖父大概率已过世」的真相",
        "唯一念想的亲家母",                # 修饰语位置，句首非身份词
        "养子她不敢承认这件事",            # 身份词后无分隔符
    ]
    for v in narrative:
        assert director._first_kinship(v) is None, \
            "新补词在叙述句里被误判：%r -> %r" % (v, director._first_kinship(v))


def test_kinship_social_relation_still_evolves():
    """社会关系演化能力不受词表变化影响（同事仍可变成恋人）。"""
    assert director._preserve_kinship("同事", "恋人，暗通款曲") == "恋人，暗通款曲"
    assert director._preserve_kinship("房东", "房东太太，主动示好") == "房东太太，主动示好"


def test_kinship_not_inferred_from_narrative_midtext():
    """身份词出现在叙述句中间不得判为身份声明。

    句中的身份词常指第三方（如「她不敢戳破父亲已死」里的父亲是别处的人），
    据此冻结会把关系改坏。只认句首声明。
    """
    narrative_cases = [
        "以她的母子的生死为筹码",           # 「母子」非身份声明
        "对其扶持的回答是不屑一顾",          # 无身份词
        "他不敢戳破「父亲大概率已死」的真相",   # 引号内第三方
        "唯一念想的儿子",                   # 修饰语位置
        "母亲她不敢承认这件事",              # 身份词后无分隔符
    ]
    for v in narrative_cases:
        assert director._first_kinship(v) is None, \
            "叙述句被误判为身份声明：%r -> %r" % (v, director._first_kinship(v))


def test_kinship_explicit_declaration_forms():
    """句首身份声明（含裸身份词）必须被识别，否则冻结机制形同虚设。"""
    assert director._first_kinship("母亲：她不敢承认") == "母亲"
    assert director._first_kinship("父亲，严厉") == "父亲"
    assert director._first_kinship("儿子，唯一的念想") == "儿子"
    assert director._first_kinship("父亲") == "父亲"     # 裸身份词
    assert director._first_kinship("母亲") == "母亲"


def test_preserve_kinship_narrative_baseline_does_not_freeze():
    """基线是叙述句（未显式声明身份）→ 放行，不得把模型写对的身份改坏。"""
    baseline = "对其扶持的回答是不屑一顾，对母亲的选择既鄙夷又无可奈何"
    assert director._preserve_kinship(baseline, "妻子，暗中结盟") == "妻子，暗中结盟"


def test_seed_kinship_from_cards_explicit():
    """作者用 relations_kinship 显式声明的血缘身份应被提取。"""
    cards = {
        "角色甲": {"relations": {"角色乙": "唯一的念想"},
                "relations_kinship": {"角色乙": "母亲"}},
        "角色乙": {"relations": {"角色甲": "唯一的对手"},
                "relations_kinship": {"角色甲": "儿子"}},
    }
    got = director.seed_kinship_from_cards(cards)
    assert got == {"角色甲 → 角色乙": "母亲", "角色乙 → 角色甲": "儿子"}, got


def test_seed_kinship_ignores_non_kinship_words():
    """非法身份词（同事/恋人等非亲属）不进血缘表——非亲属关系不该被冻结。"""
    cards = {"角色甲": {"relations": {"角色乙": "同事"},
                       "relations_kinship": {"角色乙": "同事"}}}
    assert director.seed_kinship_from_cards(cards) == {}


def test_preserve_kinship_declared_overrides_baseline():
    """显式声明优先于描述句推断：模型漂移按声明的身份拉回。"""
    baseline = "唯一的念想，对儿子坚持寻父的执念既心痛又恐惧"   # 句中「儿子」不是身份声明
    assert director._first_kinship(baseline) is None, "前置条件：句中身份词不应被识别"
    corrected = director._preserve_kinship(baseline, "妻子，讨好", declared="母亲")
    assert corrected == "母亲，讨好", corrected


def test_preserve_kinship_declared_allows_emotional_evolution():
    """显式声明身份一致时，仍允许情感/状态修饰演化。"""
    corrected = director._preserve_kinship("唯一的念想", "母亲，关系紧张", declared="母亲")
    assert corrected == "母亲，关系紧张", corrected


def test_preserve_kinship_declared_overrides_model_wrong_identity():
    """显式声明为「母亲」时，模型写「儿子」属身份漂移，须拉回「母亲」并保留修饰。"""
    corrected = director._preserve_kinship("唯一的念想", "儿子，复杂情感萌芽", declared="母亲")
    assert corrected == "母亲，复杂情感萌芽", corrected


def test_offscreen_flashback_action_detected():
    """背景人物在闪回里成为主动主语（角色丙笑/角色丙塞糖）应被判失责。

    复现跨剧本对照验证中的真实失责样本。
    """
    offs = ["角色丙"]
    reply = ("角色甲望着墙角的旧照片。角色丙笑的样子浮上心头。"
             "角色丙每次出完任务回来，都从兜里摸出一颗水果糖，塞进她手心里。")
    viol, hits = director.detect_offscreen_activity(reply, offs)
    assert viol is True, hits
    assert any(h.startswith("角色丙") for h in hits)


# ---------------------------------------------------------------------------
# 5. 关系缺口自动推断（漏网 bug 修复）
# ---------------------------------------------------------------------------

def test_fill_relation_gaps_infers_for_uncovered(monkeypatch):
    """缺口补全：在场角色在基线中完全无关系边时，应触发纪官推断并写回 relations/relations_base。

    复现该漏网 bug 的修复逻辑——旧版仅在「全部卡的 relations 合并为空」时才推断，
    导致「大部分有、个别缺」（子卡空且不被父母提及）漏网。
    """
    def fake_init(cards):
        return {
            "子 → 父": "父亲", "子 → 母": "母亲",
            "父 → 子": "儿子", "母 → 子": "儿子",
            "父 → 母": "妻子", "母 → 父": "丈夫",
        }
    monkeypatch.setattr(director, "init_relations", fake_init)
    monkeypatch.setattr(director.store, "load_card", lambda n: {"name": n, "relations": {}})

    snap = {
        "present": ["父", "母", "子"],
        # 基线只含父母互指，子完全无边的（= 原始漏网条件）
        "relations": {"父 → 母": "妻子", "母 → 父": "丈夫"},
        "relations_base": {"父 → 母": "妻子", "母 → 父": "丈夫"},
    }
    gap = director.fill_relation_gaps(snap)
    assert gap == ["子"], gap
    # 推断关系写回 relations 与冻结基线
    assert snap["relations"].get("子 → 父") == "父亲", snap["relations"]
    assert snap["relations_base"].get("子 → 母") == "母亲", snap["relations_base"]
    # 手填基线边保留
    assert snap["relations"].get("父 → 母") == "妻子"


def test_fill_relation_gaps_skips_when_complete(monkeypatch):
    """手填齐全（无缺口）时不触发任何 LLM 推断，零开销。"""
    called = {"n": 0}
    def fake_init(cards):
        called["n"] += 1
        return {"x → y": "z"}
    monkeypatch.setattr(director, "init_relations", fake_init)
    monkeypatch.setattr(director.store, "load_card", lambda n: {"name": n, "relations": {}})

    snap = {
        "present": ["角色乙", "角色甲"],
        "relations": {"角色乙 → 角色甲": "妻子", "角色甲 → 角色乙": "丈夫"},
        "relations_base": {"角色乙 → 角色甲": "妻子", "角色甲 → 角色乙": "丈夫"},
    }
    gap = director.fill_relation_gaps(snap)
    assert gap == [], gap
    assert called["n"] == 0, "齐全卡不应调用推断"
    assert snap["relations"] == {"角色乙 → 角色甲": "妻子", "角色甲 → 角色乙": "丈夫"}



# ---------------------------------------------------------------------------
# 背景人物名单推导（v0.17.2 修复：有独立角色卡 / 已登记群演不是背景人物）
# ---------------------------------------------------------------------------

def test_background_excludes_carded_characters(monkeypatch):
    """有独立角色卡的角色即便本轮不在场名单，也不算背景人物。

    真实事故：某位有独立角色卡、全程在演的角色，却被 relations↔present 的
    集合差划成背景，导致其正常戏份被 detect_offscreen_activity 整句删除
    （27 字长句被删到只剩「。」）。背景人物的定义是「store 不收录者」。
    """
    monkeypatch.setattr(director.store, "list_characters",
                        lambda: ["角色甲", "角色丙"])
    snap = {"relations": {"角色甲 → 角色丙": "妹妹", "角色甲 → 角色戊": "邻居"},
            "present": ["角色甲"]}
    offs = director.background_names_from_relations(snap, ["角色甲"])
    assert offs == ["角色戊"], offs


def test_background_accepts_extra_known(monkeypatch):
    """extra_known 用于复用调用方已算好的名单，避免重复扫盘。"""
    monkeypatch.setattr(director.store, "list_characters", lambda: [])
    snap = {"relations": {"角色甲 → 角色戊": "邻居"}, "present": ["角色甲"]}
    assert director.background_names_from_relations(snap, ["角色甲"]) == ["角色戊"]
    assert director.background_names_from_relations(
        snap, ["角色甲"], extra_known=["角色戊", "角色甲"]) == []


def test_scene_trigger_uses_director_signal(monkeypatch):
    """纪官的 scene_shift 信号触发场景导演，补上关键词表枚举不完的洞。

    零额外 LLM 成本：reflect 本来就每轮都跑，只是把它的语义判断并联进来。
    """
    import scene
    snap = {"scene": {"same_scene": 0}}
    # 无关键词、无超时、无纪官信号 -> 不触发
    assert scene._triggered("他走向窗边，沉默地望着外面。", snap) == (False, False)
    # 有纪官信号 -> 触发（非 force）
    snap["scene_shift"] = {"changed": True, "place": "楼道", "time": "", "weather": ""}
    assert scene._triggered("他走向窗边，沉默地望着外面。", snap) == (True, False)
    # 停留超时优先，返回 force
    snap["scene"]["same_scene"] = 3
    assert scene._triggered("他走向窗边。", snap) == (True, True)


def test_scene_shift_consumed_once(monkeypatch):
    """纪官信号用后即清，避免同一次上报反复触发、每轮都调场景 LLM。"""
    import scene
    calls = []
    monkeypatch.setattr(scene.llm, "complete", lambda *a, **k: calls.append(1) or "{}")
    monkeypatch.setattr(scene.store, "list_characters", lambda: ["角色甲"])
    snap = {"scene": {"same_scene": 0, "place": "客厅", "time": "清晨", "weather": ""},
            "present": ["角色甲"], "goals": {},
            "scene_shift": {"changed": True, "place": "楼道", "time": "", "weather": ""}}
    scene.apply("sid", "他望着窗外。", snap)
    assert "scene_shift" not in snap, "信号必须被消费掉"
