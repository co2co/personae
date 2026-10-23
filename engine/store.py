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


# 条目来源标记：引擎默认供给 vs 作者自写。
#
# 为什么需要它：世界书同时承载「剧本设定」与「注入调度」（position/depth/priority/
# constant/enabled 五维控制），而引擎默认条目（写法示范·常驻）由 save_world /
# import_drama 播种进用户数据文件，在 UI 里与作者自写条目长得一模一样——
# 用户无法判断「这条是系统的还是我写的」「删了会不会被补回来」。origin 让来源在数据层
# 可见，前端据此分区、标注、提供恢复入口。
#
# 语义边界：origin 记的是**播种来源**，不是「内容是否原文」。作者改写默认条目内容后
# 仍是 origin="engine"（可改可关），只有删除后由作者重写的同名条目才退回无标记。
ORIGIN_ENGINE = "engine"

# 亲密/性内容的尺度**不由引擎出厂预设**（2026-10-21 首发下架，simon 裁决，对齐 v0.29.0；
# 2026-10-23 为引擎优化工作临时再下架，完成后重新上架）。
# 引擎不再随新建 / 导入剧本播种「亲密描写标准」世界书条目——尺度完全交回各剧本的
# 世界书与剧情推进决定。既有磁盘剧本里的同名条目原样保留（引擎改动只影响今后的播种，
# 不回填、不清理旧条目）；作者想给某剧本加亲密写法标准，正路是在本剧世界书里自建一条。
# 回滚蓝本（唯一权威）：git tag `nsfw-on-v2.1.7`（→ 提交 a6e1280），
# _STANDARD_ENTRY_CONTENT（六分层 + 器官词正反示例）在该 tag 的 engine/store.py 内。
# 重新上架：git checkout nsfw-on-v2.1.7 -- <13文件>，清单见 DEVLOG 2026-10-23 条目。
# 注：早期使用的目录快照 _backup_offshelf_nsfw_* 已于 2026-10-23 晚手工清理，勿再引用。


# ---- 写法示范（few-shot，对标酒馆 first message / example messages）----
#
# 引擎内置两份中性示范，让任何剧本无需作者手写也能直接开局：
#   1. FIRST_ROUND_DEMO（开局示范）：由 session_new 静默写入快照，首轮 act 注入一次。
#   2. STANDARD_EXAMPLE_ENTRY（常驻示范）：作为世界书条目，在创建剧本与导入剧本时自动播种。
#
# 两份示范措辞全中性、不含任何剧本专名与题材词（普适性红线），用「角色甲/角色乙」
# 这类占位，任何剧本都可直接用；作者想换成贴合本剧风格的示范，可整条改写或删除。

FIRST_ROUND_DEMO_NAME = "写法示范·开局"
_FIRST_ROUND_DEMO = (
    "本剧开局的写法（多说话人叙事，可用「角色名：」标注说话人，动作与叙事穿插推进）：\n"
    "角色甲抬起头，灯影在脸上晃了晃，才慢慢看向来人。\n"
    "角色甲：这么晚了，还赶路？\n"
    "角色乙把肩上的雪抖落，往炭火边挪了半步。\n"
    "角色乙：赶不赶，都得找个地方落脚。\n"
    "堂里安静了一瞬，只有炭火哔剥地响。两人各怀各的心事，谁也没先挑破那半句没出口的话。"

)

STANDARD_EXAMPLE_NAME = "写法示范·常驻"
_STANDARD_EXAMPLE_CONTENT = (
    "写法常驻示范（多说话人叙事，角色台词以「角色名：」起段，动作与旁白穿插）：\n"
    "角色甲把手里那卷纸往桌上一搁，没抬头。\n"
    "角色甲：这事，还有谁知道？\n"
    "角色乙端茶的手停了一下。\n"
    "角色乙：该知道的，都知道了。\n"
    "屋里静了一瞬，谁也没接谁的话，只有茶盏落桌那一声，脆得像是敲在鼓面上。"

)


def _standard_example_entry():
    """常驻写法示范条目（酒馆 example messages）：demo 标志 + 非 first_round，每轮注入。"""
    return {
        "name": STANDARD_EXAMPLE_NAME,
        "keys": [],
        "content": _STANDARD_EXAMPLE_CONTENT,
        "priority": 60,
        "enabled": True,
        "constant": False,
        "position": "before",
        "depth": None,
        "secret": False,
        "demo": True,
        "first_round": False,
        "origin": ORIGIN_ENGINE,
    }


def _has_standard_example(entries):
    return any((e or {}).get("name") == STANDARD_EXAMPLE_NAME for e in (entries or []))


def restore_default_entries(name):
    """补回被删除的引擎默认条目（只补缺失，不覆盖已存在的同名条目）。

    2026-10-21 下架亲密尺度后，引擎出厂条目只剩「写法示范·常驻」一条
    （「亲密描写标准」不再由引擎播种，见上方注释）。

    为什么只补不覆盖：用户可能把「写法示范·常驻」换成本剧角色（高氏王朝就是这么用
    的）。一键重置为出厂内容等于静默销毁作者的修改，与「可改可关」的设计相悖。
    需要重置某条时，先删除它再点恢复，路径显式可控。

    返回 {"added": [...], "present": [...]}；剧本不存在返回 None。
    """
    name = (name or "").strip()
    if not name:
        raise ValueError("剧本名不能为空")
    p = DATA_DIR / "worlds" / f"{name}.json"
    raw = load_world_raw(name)
    if raw is None:
        return None

    entries = list(raw.get("entries") or [])
    added, present = [], []

    if _has_standard_example(entries):
        present.append(STANDARD_EXAMPLE_NAME)
    else:
        # 插入位置只决定它在世界书列表里的初始位置；注入先后由 priority 决定
        # （本条目 priority=60，见 _standard_example_entry）。
        # 2026-10-23 起前端保存不再按列表序重算 priority，故这里插到首位不会
        # 把它顶成最高优先级——两者已解耦。
        entries.insert(0, _standard_example_entry())
        added.append(STANDARD_EXAMPLE_NAME)

    if added:
        out = dict(raw)
        out["entries"] = entries
        p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        _invalidate(p)

    return {"added": added, "present": present}


def save_world(name, entries):
    """整份保存世界书（覆盖式）。entries 为条目数组。

    新建世界时（该世界此前不存在）自动播种一条默认条目：
      - _standard_example_entry「写法示范·常驻」：中性 few-shot 示范（酒馆 example
        messages），让「玩家不写示范也能每轮有范例可循」。只对首次创建播种，
        删除后不强制回填。

    亲密/性内容的尺度**不由引擎播种**（2026-10-21 下架，对齐 v0.29.0）：此前随新世界
    播种的「亲密描写标准」条目已移除，尺度完全交回各剧本的世界书与剧情推进决定。
    """
    name = (name or "").strip()
    if not name:
        raise ValueError("世界名不能为空")
    folder = DATA_DIR / "worlds"
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / f"{name}.json"
    entries = list(entries or [])
    first_create = not p.exists()
    if first_create:
        # 插入位置只决定初始列表位置；priority 由条目自带（60），不受位置影响。
        # demo 条目不占 max_entries 配额。前端保存已不改写 priority（2026-10-23）。
        if not _has_standard_example(entries):
            entries.insert(0, _standard_example_entry())
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
      - 世界书整份覆盖写（走 save_world，会自动为新世界播种标准条目）。
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
    # 导入时补种引擎默认条目（若模板未自带）：写法示范·常驻是每轮范例。
    # save_world 只在「首次创建」时播种，导入覆盖写已存在的剧本不会触发，故在此显式补。
    # 亲密尺度不由引擎播种（2026-10-21 下架，对齐 v0.29.0），故不再补「亲密描写标准」。
    if not _has_standard_example(store_entries):
        store_entries.insert(0, _standard_example_entry())
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
