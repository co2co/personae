"""「亲密描写标准」出厂播种条（确定性，不碰磁盘真实 data/）。

契约（simon 2026-10-08 拍板，本版为**七分层强化版**）：
  1. 每个**新建**的世界书默认自带该条且处于激活状态（constant=true、enabled=true）。
  2. position=after —— 落末尾 user 消息（生成点前最后一瞥），不是 system 块中段。
  3. 措辞全中性：不含任何剧本专名、角色名、题材词（引擎普适性红线）。
  4. 不规定**数量配额**与**正向阶段达成表**：不得含字数配额、频率配额、
     「前戏→…」必达清单。（本版第三层**刻意**用器官词作正反措辞示例、
     第五层用「抽插」作防复读反面示例——这些是技法示范，不是正向配额，
     故不再禁止器官词本身，只锁死字数/频率/阶段达成三类真正的坍缩诱因。）
  5. 用户主权：可在编辑器里整条删除或改写，删掉后保存**不得复活**；
     自带同名条时不得被覆盖。
  6. 置首位：前端 collectWorldEntries 按列表序重算 priority（index 0 → 100），
     而 world.scan 按 priority 降序截断 max_entries——放首位才能保证
     「每世界多一条 constant」不把该世界的其它设定挤出注入配额。
  7. 末端法律底线（未成年）不在本条重复——由 prompter 铁律⑧ 恒定兜底
     （铁律⑧ 在 system 块注入，与本条并存、不互斥）。

另附：铁律⑧ 不变的守护——本条是「加强」不是「替代」，两条并存。
"""
import re
import sys
from pathlib import Path

import pytest

ENGINE = Path(__file__).resolve().parent.parent / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

import store  # noqa: E402
import world as world_mod  # noqa: E402
import prompter  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_store(tmp_path, monkeypatch):
    data = tmp_path / "data"
    (data / "characters").mkdir(parents=True)
    (data / "worlds").mkdir(parents=True)
    monkeypatch.setattr(store, "DATA_DIR", data)
    monkeypatch.setattr(store, "EXAMPLES_DIR", data / "examples")
    store._cache.clear()
    yield data
    store._cache.clear()


def _std(entries):
    return next(e for e in entries if e.get("name") == store.STANDARD_ENTRY_NAME)


# ---- 1. 出厂播种 --------------------------------------------------------

def test_new_world_seeds_standard_entry(_isolated_store):
    store.save_world("新世界", [{"keys": ["a"], "content": "用户条目"}])
    ents = store.load_world("新世界")
    assert len(ents) == 2
    assert _std(ents)["content"] == store._STANDARD_ENTRY_CONTENT


def test_standard_entry_is_active_and_after_position(_isolated_store):
    """激活状态 + position=after（落末尾 user 消息，近因权重最强）。"""
    store.save_world("新世界", [])
    e = _std(store.load_world("新世界"))
    assert e["enabled"] is True
    assert e["constant"] is True
    assert e["position"] == "after"
    assert e["secret"] is False
    assert e["keys"] == []          # 常量条目，关键词不参与判定
    assert e["depth"] is None


def test_standard_entry_is_first(_isolated_store):
    """置首位：priority 100 让它不被该世界的其它条目挤出 max_entries 配额。"""
    store.save_world("新世界", [{"keys": ["a"], "content": "用户条目"}])
    assert store.load_world("新世界")[0]["name"] == store.STANDARD_ENTRY_NAME


# ---- 2. 用户主权 --------------------------------------------------------

def test_standard_entry_not_duplicated_on_resave(_isolated_store):
    """二次保存不得重复播种。"""
    store.save_world("新世界", [{"keys": ["a"], "content": "用户条目"}])
    ents = store.load_world("新世界")
    store.save_world("新世界", ents)
    store.save_world("新世界", store.load_world("新世界"))
    names = [e.get("name") for e in store.load_world("新世界")]
    assert names.count(store.STANDARD_ENTRY_NAME) == 1


def test_user_deletion_is_respected(_isolated_store):
    """用户主动删掉该条后保存 → 不得复活（只对首次创建播种）。"""
    store.save_world("新世界", [{"keys": ["a"], "content": "用户条目"}])
    kept = [e for e in store.load_world("新世界")
            if e.get("name") != store.STANDARD_ENTRY_NAME]
    store.save_world("新世界", kept)
    ents = store.load_world("新世界")
    assert len(ents) == 1
    assert store.STANDARD_ENTRY_NAME not in [e.get("name") for e in ents]


def test_user_own_same_named_entry_not_overwritten(_isolated_store):
    """自带同名条（自行改写过）→ 引擎不得覆盖其内容。"""
    custom = {"name": store.STANDARD_ENTRY_NAME, "keys": [], "content": "我自己写的标准",
              "constant": True, "position": "after", "enabled": True}
    store.save_world("新世界", [custom])
    assert _std(store.load_world("新世界"))["content"] == "我自己写的标准"


def test_user_can_disable_by_enabled_false(_isolated_store):
    """enabled=false 是「停用而不删除」的正规开关，须被 load 原样尊重。"""
    store.save_world("新世界", [])
    ents = store.load_world("新世界")
    for e in ents:
        if e.get("name") == store.STANDARD_ENTRY_NAME:
            e["enabled"] = False
    store.save_world("新世界", ents)
    assert _std(store.load_world("新世界"))["enabled"] is False


# ---- 3. 普适性红线（引擎不为任何剧本/题材定尺度） ------------------------

BANNED_LORE = [
    # 角色名 / 专名（中性占位与典型中文人名，一律禁止）
    "角色甲", "角色乙", "角色丙", "角色丁", "小明", "阿强",
    "李医生", "老王", "小姐", "太太",
    # 题材词
    "丧尸", "末日", "避难所", "荒岛", "宫廷", "修真",
]


def test_standard_entry_lore_neutral():
    content = store._STANDARD_ENTRY_CONTENT
    for w in BANNED_LORE:
        assert w not in content, "标准条出现剧本专名/题材词：%s" % w


def test_standard_entry_no_scale_presets():
    """不得规定**数量配额**与**正向阶段达成表**（v0.14.x 坍缩的真凶）。

    本版第三层刻意用器官词作**正反措辞示例**、第五层用「抽插」作**防复读反面
    示例**——这些是技法示范（禁概括、防重复充数），不是正向配额或必达指标，
    故不再禁止器官词/抽插本身。真正锁死的是三类会诱发模型「为凑数而坍缩」的
    硬指标：字数区间配额、每 N 字频率配额、前戏→…必达阶段表。
    """
    content = store._STANDARD_ENTRY_CONTENT
    # 字数区间配额（如「500-800 字」）
    assert not re.search(r"\d+\s*[-~]\s*\d+\s*字", content), "出现字数区间配额"
    # 每 N 字频率配额（如「每 200 字」）
    assert not re.search(r"每\s*\d+\s*[-~]?\s*\d*\s*字", content), "出现每 N 字配额"
    # 正向阶段达成表（前戏→插入→高潮 的必达清单）
    assert "前戏" not in content, "出现必达阶段表（前戏）"


def test_standard_entry_keeps_core_technique_directions():
    """七分层强化版须完整保留经实测有效的全部技法方向。

    本版由六分层扩为七分层：新增「七、如何收束」（事后回到人物与处境），
    第三层落笔处补器官词正反措辞示例，第五层补抽插防复读反面示例。
    分层是为了让模型逐条对照执行、不易漏掉末尾几条（处境锚点、如何收束）。
    """
    c = store._STANDARD_ENTRY_CONTENT
    # 一、何时写（触发门槛：未到位不硬写）
    assert "何时写" in c
    assert "未到位就不要硬写" in c
    # 二、写多实（「不省略 / 不收束」独立层）
    assert "写多实" in c
    assert "既不回避也不跳过" in c
    assert "把该发生的写完" in c
    assert "不在将入未入之际收束" in c
    # 三、怎么落笔（落身体上 + 禁概括 + 禁代称 + 器官词正反示例）
    assert "落笔必须落在身体上" in c
    assert "代称" in c
    assert "衣衫尽褪" in c                          # 禁概括收尾
    assert "那根东西" in c                           # 禁代称示例
    assert "阴唇" in c and "阴蒂" in c               # 直呼其名的正反示例
    # 四、心理怎么带
    assert "身体反应" in c
    assert "情话与内心独白" in c
    assert "只补一句" in c                           # 情话限量
    # 五、节奏 + 防复读（层次 + 每次新信息 + 事前事后各一次 + 抽插反面示例）
    assert "失控" in c and "试探" in c               # 试探→越界→失控→事后
    assert "新的具体信息" in c
    assert "不得靠重复" in c
    assert "各写一次即可" in c                       # 事前/事后各一次
    assert "抽插" in c                               # 防复读反面示例
    # 六、不能丢的（处境锚点）
    assert "锚定" in c
    assert "处境锚点" in c
    assert "在场" in c
    # 七、如何收束（事后回到人物与处境）
    assert "如何收束" in c
    assert "高潮不是终点" in c


def test_standard_entry_has_seven_numbered_layers():
    """七分层编号齐全且有序——分层执行是强化版的关键设计。"""
    c = store._STANDARD_ENTRY_CONTENT
    for n in ("一、何时写", "二、写多实", "三、怎么落笔",
              "四、心理怎么带", "五、节奏", "六、不能丢的", "七、如何收束"):
        assert n in c, "缺少分层：%s" % n
    # 法律底线不在本条重复（由铁律⑧ 兜底），此处不得再出现"硬红线"
    assert "硬红线" not in c, "本版已把未成年硬红线移交给铁律⑧，本条不应再带"
    # 分层顺序不可乱（模型按序逐条执行）
    pos = [c.index(n) for n in ("一、何时写", "二、写多实", "三、怎么落笔",
                              "四、心理怎么带", "五、节奏", "六、不能丢的",
                              "七、如何收束")]
    assert pos == sorted(pos), "分层顺序错乱"


# ---- 4. 落点验证：必须进 prompt 且在末尾 ---------------------------------

def test_standard_entry_lands_in_prompt_tail(_isolated_store):
    """端到端：新建世界的该条须落在 messages 的**末尾 user 消息**里。"""
    store.save_world("新世界", [])
    cards = {"角色甲": {"name": "角色甲"}, "角色乙": {"name": "角色乙"}}
    snap = {"scene": {"round": 1, "place": "某处", "time": "夜", "weather": ""},
            "relations": {}, "ledger": [], "secrets": [], "goals": {},
            "present": ["角色甲", "角色乙"], "address": {}}
    ents = store.load_world("新世界")
    hits = world_mod.scan(ents, [], directive="本轮扰动", max_entries=8)
    after = [e for e in hits if e.get("position") == "after" and not e.get("secret")]
    msgs = prompter.build_session(cards, "本轮扰动", [], snap, history=[], after_hits=after)
    assert store._STANDARD_ENTRY_CONTENT in msgs[-1]["content"], "标准条未落在末尾 user 消息"
    assert store._STANDARD_ENTRY_CONTENT not in msgs[0]["content"], "标准条不应落在 system 块"


def test_standard_entry_does_not_eat_quota(_isolated_store):
    """配额回归：7 条用户条目 + 1 条标准条时，全部 8 条仍进 prompt（8/8 零丢弃）。"""
    user = [{"keys": ["k%d" % i], "content": "用户条目%d" % i} for i in range(7)]
    store.save_world("新世界", user)
    ents = store.load_world("新世界")
    assert len(ents) == 8
    hits = world_mod.scan(ents, ["k0 k1 k2 k3 k4 k5 k6"], max_entries=8)
    assert len([h for h in hits if not h.get("secret")]) == 8, "有条目被挤出配额"
