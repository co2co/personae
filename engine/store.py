"""数据层：角色卡、世界书。全部是本地 JSON 文件，没有数据库。

目录结构：
    data/characters/<name>.json   角色卡
    data/worlds/<name>.json       世界书

注：会话（聊天记录）不在此模块，统一由 memory.py 管理（data/sessions/<sid>/chat.jsonl）。
"""

import json
import shutil
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
EXAMPLES_DIR = DATA_DIR / "examples"

# 进程级只读缓存：角色卡与世界书在会话内基本不变，但每轮推演会被反复
# load_card / load_world 读盘（app.py 每轮为在场角色逐张 load、director 反复
# load_characters/load_world）。带 mtime 校验的缓存：命中时比对文件修改时间，
# 变了就重读、没变直接用内存——既省掉每轮磁盘 IO 与 JSON 解析，又不漏掉
# 运行期导入/编辑新卡新世界的变化（长上下文后期尤其明显）。
_cache = {}


def _cached_read(path):
    p = str(path)
    try:
        mtime = path.stat().st_mtime if path.exists() else None
    except OSError:
        mtime = None
    hit = _cache.get(p)
    if hit is not None and hit["mtime"] == mtime:
        return hit["data"]
    data = _read_json(path)
    _cache[p] = {"mtime": mtime, "data": data}
    return data


def _invalidate(path):
    _cache.pop(str(path), None)
    # 同时失效其所在目录的列表签名缓存，否则新增/删除卡或世界后
    # list_characters / list_worlds 仍返回旧名单（签名是「文件名+mtime」快照）。
    _cache.pop(("listing", str(path.parent)), None)


def _read_json(path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _seed_examples():
    """首次运行（无任何私人剧本时）从 examples/ 播种官方 demo。

    仅当 characters/ 或 worlds/ 目录为空时才复制，且按名去重、不覆盖用户已有文件。
    demo 是出厂预置，用户导入/新建私人剧本后目录不再为空，此后不再播种。
    """
    if not EXAMPLES_DIR.exists():
        return
    for kind in ("characters", "worlds"):
        src = EXAMPLES_DIR / kind
        dst = DATA_DIR / kind
        if not src.is_dir():
            continue
        dst.mkdir(parents=True, exist_ok=True)
        # 目录已有任意内容（哪怕只剩 1 个文件）即视为「已播种 / 已有私人剧本」，
        # 整份跳过。此前按文件逐个补缺，会把用户已删除的 demo 从 examples 重新拷回，
        # 导致「删除角色」下一秒又被播种、看起来删除失效。
        if any(dst.glob("*.json")):
            continue
        for f in src.glob("*.json"):
            shutil.copyfile(f, dst / f.name)


def list_characters():
    _seed_examples()
    return _cached_listing(DATA_DIR / "characters")


def list_characters_by_world(world_name):
    """列出归属于指定世界书的所有角色名（升序）。

    开场界面「先选世界 → 再列该世界的角色」用这个：角色卡的 world 字段是它与
    世界书的唯一归属键（见 save_world 的世界存在性校验），所以按 world 精确过滤。
    卡未声明 world 或指向已不存在的世界书时归入「未归属」（world 为空），
    不静默丢弃——否则玩家会以为角色凭空消失了。
    """
    world_name = (world_name or "").strip()
    out = []
    for name in list_characters():
        try:
            w = (load_card(name) or {}).get("world", "") or ""
        except FileNotFoundError:
            continue
        if w == world_name:
            out.append(name)
    return out


def unassigned_characters():
    """未声明 world / world 指向已不存在世界书的角色名（开场界面给出修复指引）。"""
    valid = set(list_worlds())
    out = []
    for name in list_characters():
        try:
            w = (load_card(name) or {}).get("world", "") or ""
        except FileNotFoundError:
            continue
        if w not in valid:
            out.append(name)
    return out


def _cached_listing(folder):
    """带签名的目录列表缓存：以「文件名 + mtime」签名做键，文件集合变化才重扫。

    list_characters / list_worlds 每轮被 director（背景人物判定、群演排除）调用，
    逐轮 glob 目录 + stat 属于无谓开销；签名缓存把重复扫目录压成一次。
    """
    folder.mkdir(parents=True, exist_ok=True)
    sig = tuple(sorted((p.stem, p.stat().st_mtime) for p in folder.glob("*.json")))
    key = ("listing", str(folder))
    hit = _cache.get(key)
    if hit is not None and hit["sig"] == sig:
        return hit["names"]
    names = sorted(s for s, _ in sig)
    _cache[key] = {"sig": sig, "names": names}
    return names


def load_card(name):
    card = _cached_read(DATA_DIR / "characters" / f"{name}.json")
    if card is None:
        raise FileNotFoundError(f"角色卡不存在: {name}")
    return card


def save_card(name, card):
    """新建或覆盖角色卡。name 同时作为文件名与卡内 name 字段。"""
    name = (name or "").strip()
    if not name:
        raise ValueError("角色名不能为空")
    folder = DATA_DIR / "characters"
    folder.mkdir(parents=True, exist_ok=True)
    data = dict(card)
    data["name"] = name
    p = folder / f"{name}.json"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    _invalidate(p)


def delete_card(name):
    """删除角色卡文件。返回 True 表示文件存在并已删除，False 表示原本就不存在。

    未删除必须显式返回 False（而非静默 return），否则上层路由无法区分
    「真删了」与「名字对不上磁盘文件名、其实没删到」，会向前端误报删除成功。
    """
    name = (name or "").strip()
    if not name:
        return False
    p = DATA_DIR / "characters" / f"{name}.json"
    if not p.exists():
        return False
    p.unlink()
    _invalidate(p)
    return True


def list_worlds():
    _seed_examples()
    return _cached_listing(DATA_DIR / "worlds")


def load_world_raw(name):
    name = (name or "").strip()
    if not name:
        return None
    return _cached_read(DATA_DIR / "worlds" / f"{name}.json")


def load_world(name=""):
    """按名加载世界书条目。空名或无此世界时返回空列表（语义：没有世界书，不报错）。"""
    name = (name or "").strip()
    if not name:
        return []
    data = _cached_read(DATA_DIR / "worlds" / f"{name}.json")
    return (data or {}).get("entries", [])


STANDARD_ENTRY_NAME = "亲密描写标准"

# 出厂随每个新世界播种的世界书条目：亲密/性描写的**叙事技法标准**。
#
# 为什么放在世界书而不是引擎铁律：
#   引擎铁律⑧ 恒定在 system 块约 39% 处，其后压着数百字才到生成点，长上下文下
#   权重被稀释；而 position=after 的常量条目落在**末尾 user 消息**（生成点前最后一瞥），
#   近因权重最强。同样的文本换个位置，实测效果差别显著。
#
# 为什么是「技法标准」而不是「尺度档位」：
#   本条不含任何具体尺度预设（不规定器官词、不规定字数、不规定必须到哪一步），
#   只约束「到了亲密时刻该怎么写」，何时生效完全交给剧情判断——因此对任意剧本
#   都成立，不会把某个剧本的走向锁死。措辞全中性，不含专名与题材词（普适性红线）。
#   作者想要更露骨时的正路是在**本剧本自己的世界书里另加一条**，不是改引擎（零代码）。
#
# 为什么用「一/二/三…」分层而不是散文串接：
#   指令型长文本分条后模型更容易逐条对照执行，且不易漏掉末尾几条（处境锚点、如何收束）
#   ——长 prompt 的常见失效点就是把末尾的要求丢掉。本版由六分层扩为**七分层**：
#   新增「七、如何收束」（事后回到人物与处境，高潮不是终点），第三层落笔处补了
#   器官词**正反措辞示例**（禁「探到底」「贯穿」式概括，示范直呼其名），第五层补了
#   抽插**防复读**反面示例。器官词与「抽插/高潮」在此都是**反面/示范用法**（禁概括、
#   防重复充数），不是正向配额或阶段达成表——不重犯 v0.14.x「字数/频率/阶段表」的硬指标坍缩。
#
# 实机依据（本地 27B，四组对照 × 临界场景）：
#   本条在场 vs 铁律⑧ 单独 → 处境锚定词 4→11、在场第三方提及 4→10（群像未被吃掉）；
#   vs 把技法硬编进铁律 → 后者仅在「指令明写性」的窄区间生效，另两轮为 0，
#   且抽象词翻 4 倍、正文暴涨 40%（挤占群像）。
#   跨题材（古代宫廷权谋 / 深空殖民站科幻 / 当代小镇伦理 / 末世生存）四类剧本各跑
#   2组×3 场景：零整段复读、零器官词，非亲密轮不硬写。
#   注：复读（描写/台词句被写两遍）在「仅本条、零其他条」的配置下也出现过两次，
#   属模型长输出末尾的句式回卷，**不是冗余指令互相强化**——故此处不做去冗余化处理，
#   保留全部有效要求。
_STANDARD_ENTRY_CONTENT = (
    "【本剧亲密与性描写标准，须逐条遵守】\n"
    "以下各条不是建议，写到亲密戏时必须逐条执行。\n"
    "一、何时写\n"
    "由剧情与角色关系自然驱动。当两人之间的张力真正到位、剧情自然推进到亲密时刻，"
    "才写；未到位就不要硬写。\n"
    "二、写多实\n"
    "既不回避也不跳过，用足该写的那一段。若已越界，须把该发生的写完——"
    "衣物如何解、谁先伸手、哪一步是谁主动、身体在什么位置被怎样对待，都写出来，"
    "不靠一句「继而」带过，不在将入未入之际收束。\n"
    "三、怎么落笔\n"
    "落笔必须落在身体上，具体到部位与动作。"
    "禁止概括收尾（「两人衣衫尽褪」「他进入了她」），"
    "禁止代称遮挡（「那根东西」「下身」「私密处」「那处」等）。直呼其名。\n"
    "示例：\n"
    "- 不是「他的手终于探到了底，掌心抵住了那片湿润的热度」，"
    "而是「他的手指分开她的阴唇，指腹直接按上她已经湿透的阴蒂」。\n"
    "- 不是「他猛地挺腰，彻底贯穿了她」，"
    "而是「他抓住她的腰往下一按，整根阴茎一下插到底，龟头顶到了她子宫口」。\n"
    "同时：身体写得再具体，也不能让整段只剩下身体。"
    "每推进一个明确的性动作，必须同步带出至少一项非性信息"
    "（处境风险、人物情绪通过身体的泄露、关系里的主动/被动/犹豫、时间压力等）。\n"
    "四、心理怎么带\n"
    "心理一律通过身体反应写出，不直接下结论。"
    "不写「她很爽」「他不情愿」「她爱他」，写她如何僵住、呼吸如何乱、"
    "他如何躲开视线、事后谁先移开眼睛。\n"
    "情话与内心独白只在身体已经说过之后补一句，且只补一句。"
    "禁止用大段情色内心独白或「感觉像……」的比喻堆砌来填充篇幅。"
    "身体已经表达过的，嘴和脑子不必再说第二遍。\n"
    "五、节奏\n"
    "必须有层次：试探 → 越界 → 失控 → 事后。\n"
    "每一次推进都要带来新的具体信息，而不是同一动作的重复描述。"
    "新信息包括但不限于：身体反应程度的变化、主动/被动的转换、说出口与咽回去的话、"
    "处境风险的即时提醒、关系里此刻最难逾越的那道界限被触碰或暂时跨越。\n"
    "事前犹豫、事后避开眼睛，各写一次即可。"
    "不得靠重复同一抽插动作或同一句措辞充数。"
    "如果一段里连续三次都在写「他用力抽插、她叫出声」，就是节奏失败。\n"
    "六、不能丢的（处境锚点）\n"
    "每一段亲密戏都必须始终锚定当前处境：\n"
    "- 这个空间里能被听见/看见的具体风险\n"
    "- 此刻还剩多少时间或余地\n"
    "- 这层关系里此刻最难逾越的那道界限\n"
    "- 同时在场但不在这一段里的人，必须仍然有「被写到」的可能\n"
    "身体写得越具体，这些非性的处境张力越要保住。"
    "如果两个人关进一间屋子后，整段就只剩他们两个人的身体，"
    "而其他人的世界、时间压力、被发现的风险全部消失，就是失败。\n"
    "七、如何收束\n"
    "事后必须回到人物与处境，而不是停在高潮余韵里。"
    "写清楚：谁先动、谁先穿衣服/整理、谁先说话或故意不说话、"
    "这一刻关系有没有发生不可逆的改变、外部世界的压力有没有重新压回来。"
    "高潮不是终点，人物带着这场性回到原来的世界才是终点。"
)


def _standard_entry():
    return {
        "name": STANDARD_ENTRY_NAME,
        "keys": [],
        "content": _STANDARD_ENTRY_CONTENT,
        "priority": 100,
        "enabled": True,
        "constant": True,
        "position": "after",
        "depth": None,
        "secret": False,
    }


def _has_standard_entry(entries):
    return any((e or {}).get("name") == STANDARD_ENTRY_NAME for e in (entries or []))


def save_world(name, entries):
    """整份保存世界书（覆盖式）。entries 为条目数组。

    新建世界时（该世界此前不存在）自动播种 _STANDARD_ENTRY「亲密描写标准」——
    它是**叙事技法标准**而非内容设定，措辞全中性、不含任何剧本专名与题材词，
    对任意剧本都成立，故随每个新世界出厂即激活。用户可整条删除或改写，
    删除后本函数不会再补（只对「首次创建」播种，不做每次保存的强制回填），
    也可 enabled=false 停用。详见 _STANDARD_ENTRY 注释。
    """
    name = (name or "").strip()
    if not name:
        raise ValueError("世界名不能为空")
    folder = DATA_DIR / "worlds"
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / f"{name}.json"
    entries = list(entries or [])
    if not p.exists() and not _has_standard_entry(entries):
        # 置于首位：前端 collectWorldEntries 按列表序重算 priority（index 0 → 100），
        # 而 world.scan 是按 priority 降序截断 max_entries——放首位才能保证
        # 「每世界多一条 constant」不会把该世界的其它设定挤出配额。
        entries.insert(0, _standard_entry())
    data = {"name": name, "entries": entries}
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    _invalidate(p)


def delete_world(name):
    """删除整份世界书。返回 True 表示文件已存在并删除，False 表示原本就不存在。"""
    name = (name or "").strip()
    if not name:
        raise ValueError("世界名不能为空")
    p = DATA_DIR / "worlds" / f"{name}.json"
    if not p.exists():
        return False
    p.unlink()
    _invalidate(p)
    return True


def worlds_referencing(name):
    """返回 world 字段指向该世界的角色卡名列表（用于删除前的引用保护）。"""
    return [c for c in list_characters()
            if (load_card(c) or {}).get("world") == name]
