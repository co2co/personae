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
#
# 实机依据（本地 27B，三组对照 ×3 临界场景）：
#   本条在场 vs 铁律⑧ 单独 → 处境锚定词 4→11、在场第三方提及 4→10（群像未被吃掉）；
#   vs 把技法硬编进铁律 → 后者仅在「指令明写性」的窄区间生效，另两轮为 0，
#   且抽象词翻 4 倍、正文暴涨 40%（挤占群像）。
_STANDARD_ENTRY_CONTENT = (
    "【本剧叙事标准，非背景设定，须逐条遵守】当两人之间的张力真正到位、剧情自然推进到"
    "亲密时刻时，须正面写实、具体到身体：不回避、不跳过、不用「他进入她」这类概括收尾，"
    "也不用「那根东西」「下身」「私密处」这类代称遮挡——直呼其名。心理一律通过身体反应"
    "写出，不直接下结论：不写「她很爽」「他不情愿」，写她如何僵住、他如何躲、事后谁先移开"
    "视线。动作与感受须有层次递进，从试探到失控到事后，而不是同一个动作反复重演；每一次"
    "推进都须有新的具体信息——身体的反应程度、谁主动谁被动、说出口的话与咽回去的话、"
    "以及这一刻新出现的具体细节，不得靠重复同一动作或同一句措辞充数。"
    "每一段亲密戏都必须锚定当前处境：这一空间里能被听见的具体风险、此刻还剩下多少时间或"
    "余地、以及这层关系里此刻最难逾越的那道界限。身体写得越具体，这份处境的张力越要保住"
    "——同时在场但不在这一段里的人，必须仍然有可能被写到，不能因为两个人关进了一间屋子，"
    "就让这出戏从其他人的世界里消失。"
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
