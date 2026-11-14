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

    list_characters / list_worlds 每轮被 director（开场加载、在场校验）调用，
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


# 世界书只装作者设定：引擎不再向世界书播种任何条目（2026-11-14 撤净「引擎默认条目」层）。
#
# 撤掉的机制：save_world 首次创建 / import_drama 时插入引擎自带的「写法示范·常驻」条目，
# 并以 origin="engine" 标来源，前端据此分区、加徽标、挂「恢复默认」端点。撤它的直接
# 证据是装配实测：整份提示词里没有第二处在约束篇幅与节奏（字数/篇幅/长度 计数均为 0），
# 这条示范是唯一的具体范例，又挂在 system 尾部并带「照着它的风格与节奏写」的命令，
# 于是它示范的「一人一句 + 静止收束」就成了每轮正文的事实长度与事实节奏。出厂示范受
# 普适性红线限制只能用「角色甲/角色乙」占位，示范得出形状、示范不出张力，改写正文救不回。
#
# 不留标记字段：引擎读写都不看 origin，既有磁盘剧本里残留的 origin="engine" 无害，
# 前端下次保存会自然抹掉。作者想给本剧一个写法锚点，正路是在本剧世界书自建一条 demo
# 条目（few-shot 通道保留，分流见 world.py）。

# 亲密/性内容的尺度**不由引擎出厂预设**（2026-10-21 首发下架，对齐 v0.29.0；
# 2026-10-23 为引擎优化工作临时再下架，完成后重新上架）。
# 引擎不再随新建 / 导入剧本播种「亲密描写标准」世界书条目——尺度完全交回各剧本的
# 世界书与剧情推进决定。既有磁盘剧本里的同名条目原样保留（引擎改动只影响今后的播种，
# 不回填、不清理旧条目）；作者想给某剧本加亲密写法标准，正路是在本剧世界书里自建一条。


# ---- 写法示范：引擎侧不再提供任何条目（实况）----
#
# 两份示范档都已撤净：世界书常驻档（引擎播种的 demo 条目）与会话快照开局档
# （session_new 写入 snap.opening_demo、首轮 act 注入一次）都在 2026-11-14 撤除。
# 撤除理由与「出厂示范受普适性红线限制只能用占位角色，示范得出形状、示范不出张力」
# 这条限制，见上方「引擎不再向世界书播种任何条目」注释。正文形式改用小说体散文，
# 引擎不再给一份「照着写」的样本。
#
# 作者想给本剧一个写法锚点，正路是在本剧世界书自建一条 demo 条目——那时它是剧本
# 资产，不是引擎副本。demo / first_round 分流通道保留（分流见 world.py），
# first_round 条目仍只在首轮注入。


def save_world(name, entries):
    """整份保存世界书（覆盖式）。entries 为条目数组，引擎原样覆盖写入、不插入任何条目。

    引擎不播种条目：2026-11-14 撤净「引擎默认条目」层（写法示范·常驻不再自动播种），
    亲密尺度自 2026-10-21 起同样不播种（对齐 v0.29.0）。新建与覆盖写都是纯覆盖，
    作者给什么存什么；既有磁盘剧本里的旧条目原样保留，不清理、不回填。
    """
    name = (name or "").strip()
    if not name:
        raise ValueError("世界名不能为空")
    folder = DATA_DIR / "worlds"
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / f"{name}.json"
    entries = list(entries or [])
    data = {"name": name, "entries": entries}
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    _invalidate(p)
    return name


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


# ----------------------------------------------------------------------------
# 剧本包模板（统一 JSON 规范）：一个剧本 = 一本世界书 + 该剧本全部角色
# ----------------------------------------------------------------------------
# 引擎所有「剧本的导入 / 导出」一律基于本模板，不再各自拼结构——
# 备份剧本、恢复剧本、将来任何导入导出脚本都读写同一形状，便于高效管理与版本演化。
#
# 模板形状（顶层是对象，不是裸数组）：
#   {
#     "schema": "personae.drama",      # SCHEMA_ID，固定标识，区分本模板与其它 JSON
#     "schema_version": 1,             # SCHEMA_VERSION，结构版本，将来改形状时 +1
#     "drama": "<剧本名>",             # 剧本名（= 世界书文件名 / 角色卡 world 值）
#     "exported_at": "<ISO8601 本地时间>","exported_by": "personae/<版本>",
#     "world":  { "name": "<剧本名>", "entries": [ ...世界书条目... ] },
#     "characters": [ ...角色卡（每张一个完整对象，字段同 data/characters/*.json）... ]
#   }
#
# 字段约定：
#   - world 即 data/worlds/<剧本名>.json 的原始对象（{name, entries}），逐字照搬。
#   - characters 收录 world 字段 == <剧本名> 的全部角色卡；卡内 world 一律以
#     drama 字段为准（导入时强制对齐目标剧本名，防止 world 错位加载错世界）。
#   - 角色卡里引擎未识别的扩展字段（avatar / alternate_greetings / extensions 等）
#     随卡原样保留——导入不丢元数据（与前端角色保存的保留策略一致）。
#
# 普适性红线：本规范只描述「剧本包」这一通用形状，不含任何具体剧本名、
# 角色名或题材词；exported_by 的版本号来自 engine/VERSION，是引擎事实非剧本设定。
SCHEMA_ID = "personae.drama"
SCHEMA_VERSION = 1

# 模板里属于「结构元信息」的顶层字段：校验与导入时要剥掉，只保留剧本内容。
_SCHEMA_META_KEYS = ("schema", "schema_version", "drama", "exported_at", "exported_by")


def _engine_version():
    """读 engine/VERSION 取当前版本号（如 v0.28.2）；缺失时返回 "unknown"。

    exported_by 用「personae/<版本>」标记，便于日后追溯某份剧本包由哪个引擎版本导出。
    读文件不 import，避免为这点事引入循环依赖。
    """
    try:
        v = (DATA_DIR.parent / "VERSION").read_text(encoding="utf-8").strip()
        return v or "unknown"
    except OSError:
        return "unknown"


def _drama_characters(name):
    """该剧本全部角色卡（world == name），按角色名升序，逐张完整对象。"""
    out = []
    for cname in list_characters():
        try:
            card = load_card(cname)
        except FileNotFoundError:
            continue
        if (card.get("world", "") or "").strip() == name:
            out.append(card)
    out.sort(key=lambda c: (c.get("name", "") or ""))
    return out


def export_drama(name):
    """把一个剧本（世界书 + 其全部角色）导出为统一模板对象（内存，不写盘）。

    返回 dict，路由层直接 jsonify 即可。剧本（世界书）不存在时返回 None。
    """
    name = (name or "").strip()
    if not name:
        raise ValueError("剧本名不能为空")
    world_raw = load_world_raw(name)
    if world_raw is None:
        return None
    from datetime import datetime
    tpl = {
        "schema": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "drama": name,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "exported_by": "personae/" + _engine_version(),
        "world": world_raw,
        "characters": _drama_characters(name),
    }
    return tpl


def import_drama(name, template):
    """把一个统一模板对象导入为目标剧本（覆盖写世界书 + 重建角色卡）。

    参数：
      name      目标剧本名（落盘用的世界书文件名 / 角色卡 world 值）。
      template  模板对象（export_drama 的形状，或旧版无 schema 字段的裸 {world, characters}）。

    行为：
      - 模板里 world 的 name 与 characters 里每张卡的 world 一律以 `name` 为准，
        强制对齐目标剧本名，杜绝 world 错位（与 /api/character 的世界存在性校验同向）。
      - 世界书整份覆盖写（走 save_world）：引擎不补种任何条目，模板里有什么就存什么。
      - 角色卡按模板里的名单整份重建：模板内有的按模板写、world 对齐 name；
        模板里没列、但当前已归属 name 的多余角色卡会被删除（恢复=精确还原，不留残卡）。
        其它剧本的角色一律不碰。
    返回 {ok, name, world_entries, imported, deleted}。
    """
    name = (name or "").strip()
    if not name:
        raise ValueError("剧本名不能为空")
    if not isinstance(template, dict):
        raise ValueError("模板必须是一个 JSON 对象")
    # 结构校验：至少要有 world 或 characters 之一，否则是空壳 / 不是剧本包
    world = template.get("world")
    chars = template.get("characters")
    if not isinstance(world, dict) and not isinstance(chars, list):
        raise ValueError("模板缺少 world / characters 字段，不是合法剧本包")

    world_entries = (world or {}).get("entries") or []
    cards = chars if isinstance(chars, list) else []

    # 1) 世界书：整份覆盖写，name 对齐目标剧本名（save_world 内部会把 name 落进文件）。
    store_entries = list(world_entries)
    save_world(name, store_entries)

    # 2) 角色卡：模板内名单整份重建，world 强制对齐 name。
    imported = []
    template_names = set()
    for card in cards:
        if not isinstance(card, dict):
            continue
        cname = (card.get("name", "") or "").strip()
        if not cname:
            continue
        data = dict(card)
        data["name"] = cname
        data["world"] = name  # 强制对齐目标剧本名，防 world 错位
        save_card(cname, data)
        template_names.add(cname)
        imported.append(cname)

    # 3) 删除「当前归属 name 但不在模板里」的多余卡（精确恢复）；其它剧本不碰。
    deleted = []
    for cname in list_characters():
        try:
            card = load_card(cname)
        except FileNotFoundError:
            continue
        if (card.get("world", "") or "").strip() == name and cname not in template_names:
            if delete_card(cname):
                deleted.append(cname)

    return {
        "ok": True,
        "name": name,
        "world_entries": len(store_entries),
        "imported": imported,
        "deleted": deleted,
    }


def delete_drama(name):
    """删除一个剧本 = 整份世界书 + 该剧本全部角色卡（world == name）。

    与 export_drama / import_drama 同属「剧本」概念：删剧本不是只删世界书、
    把角色卡留成无归属的孤儿，而是世界书与角色一并清掉，保持磁盘干净。

    返回 {ok, name, world_removed, characters_deleted}；世界书与角色都不存在
    （原本就没这个剧本）时返回 None，由路由层据此回 404。
    """
    name = (name or "").strip()
    if not name:
        raise ValueError("剧本名不能为空")
    world_removed = delete_world(name)
    deleted = [c for c in worlds_referencing(name) if delete_card(c)]
    if not world_removed and not deleted:
        return None
    return {
        "ok": True,
        "name": name,
        "world_removed": world_removed,
        "characters_deleted": deleted,
    }
