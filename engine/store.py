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


STANDARD_ENTRY_NAME = "亲密描写标准"

# 条目来源标记：引擎默认供给 vs 作者自写。
#
# 为什么需要它：世界书同时承载「剧本设定」与「注入调度」（position/depth/priority/
# constant/enabled 五维控制），而两条引擎默认条目（亲密描写标准、写法示范·常驻）由
# save_world / import_drama 播种进用户数据文件，在 UI 里与作者自写条目长得一模一样——
# 用户无法判断「这条是系统的还是我写的」「删了会不会被补回来」。origin 让来源在数据层
# 可见，前端据此分区、标注、提供恢复入口。
#
# 语义边界：origin 记的是**播种来源**，不是「内容是否原文」。作者改写默认条目内容后
# 仍是 origin="engine"（可改可关），只有删除后由作者重写的同名条目才退回无标记。
ORIGIN_ENGINE = "engine"

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
#   ——长 prompt 的常见失效点就是把末尾的要求丢掉。当前为**六分层**（写多实 /
#   怎么落笔 / 心理怎么带 / 节奏 / 处境锚点 / 如何收束）。第二层落笔处带器官词
#   **正反措辞示例**（禁「探到底」「贯穿」式概括，示范直呼其名），第四层带抽插
#   **防复读**反面示例。器官词与「抽插/高潮」在此都是**反面/示范用法**（禁概括、
#   防重复充数），不是正向配额或阶段达成表——不重犯 v0.14.x「字数/频率/阶段表」的硬指标坍缩。
#
# 时机层职责（何时写 / 未到位不硬写）已**移交铁律⑧**（prompter._LAW8_DEFAULT 的
#   「当叙事推进到亲密场景时…」正向门槛 + 「叙事尚未推进到亲密时刻前，不得…硬写」
#   反向约束，v0.24.2 补齐）。本条只保留**写法技法**，标题首行「非亲密戏时直接跳过」
#   是轻量提醒，不承担触发判定——避免本条与铁律⑧ 在时机层重复约束。
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
    "【本剧亲密与性行为描写标准，须逐条遵守，非亲密戏时直接跳过】\n"
    "以下各条不是建议，写到亲密戏时必须逐条执行。\n"
    "一、写多实\n"
    "既不回避也不跳过，用足该写的那一段。若已越界，须把该发生的写完——"
    "衣物如何解、谁先伸手、哪一步是谁主动、身体在什么位置被怎样对待，都写出来，"
    "不靠一句「继而」带过，不在将入未入之际收束。\n"
    "二、怎么落笔\n"
    "落笔必须落在身体上，具体到部位和动作。"
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
    "三、心理怎么带\n"
    "心理一律通过身体反应写出，不直接下结论。"
    "不写「她很爽」「他不情愿」「她爱他」，写她如何僵住、呼吸如何乱、"
    "他如何躲开视线、事后谁先移开眼睛。\n"
    "情话与内心独白只在身体已经说过之后补一句，且只补一句。"
    "禁止用大段情色内心独白或「感觉像……」的比喻堆砌来填充篇幅。"
    "身体已经表达过的，嘴和脑子不必再说第二遍。\n"
    "四、节奏\n"
    "必须有层次：试探 → 越界 → 失控 → 事后。\n"
    "每一次推进都要带来新的具体信息，而不是同一动作的重复描述。"
    "新信息包括但不限于：身体反应程度的变化、主动/被动的转换、说出口与咽回去的话、"
    "处境风险的即时提醒、关系里此刻最难逾越的那道界限被触碰或暂时跨越。\n"
    "事前犹豫、事后避开眼睛，各写一次即可。"
    "不得靠重复同一抽插动作或同一句措辞充数。"
    "如果一段里连续三次都在写「他用力抽插、她叫出声」，就是节奏失败。\n"
    "五、不能丢的（处境锚点）\n"
    "每一段亲密戏都必须始终锚定当前处境：\n"
    "- 这个空间里能被听见/看见的具体风险\n"
    "- 此刻还剩多少时间或余地\n"
    "- 这层关系里此刻最难逾越的那道界限\n"
    "- 同时在场但不在这一段里的人，必须仍然有「被写到」的可能\n"
    "身体写得越具体，这些非性的处境张力越要保住。"
    "如果两个人关进一间屋子后，整段就只剩他们两个人的身体，"
    "而其他人的世界、时间压力、被发现的风险全部消失，就是失败。\n"
    "六、如何收束\n"
    "事后必须回到人物与处境，而不是停在高潮余韵里。"
    "写清楚：谁先动、谁先穿衣服/整理、谁先说话或故意不说话、"
    "这一刻关系有没有发生不可逆的改变、外部世界的压力有没有重新压回来。"
    "高潮不是终点，人物带着这场性回到原来的世界才是终点。"
)


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
        "origin": ORIGIN_ENGINE,
    }


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


def _has_standard_entry(entries):
    return any((e or {}).get("name") == STANDARD_ENTRY_NAME for e in (entries or []))


def _has_standard_example(entries):
    return any((e or {}).get("name") == STANDARD_EXAMPLE_NAME for e in (entries or []))


def restore_default_entries(name):
    """补回被删除的引擎默认条目（只补缺失，不覆盖已存在的同名条目）。

    为什么只补不覆盖：用户可能按自己的口味改过「亲密描写标准」或把「写法示范·常驻」
    换成本剧角色（高氏王朝就是这么用的）。一键重置为出厂内容等于静默销毁作者的修改，
    与「可改可关」的设计相悖。需要重置某条时，先删除它再点恢复，路径显式可控。

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

    if _has_standard_entry(entries):
        present.append(STANDARD_ENTRY_NAME)
    else:
        entries.insert(0, _standard_entry())
        added.append(STANDARD_ENTRY_NAME)

    if _has_standard_example(entries):
        present.append(STANDARD_EXAMPLE_NAME)
    else:
        # 紧跟标准条目（与 save_world 首次播种的顺序一致，保持文件可读性；
        # 展示顺序最终由 priority 决定，位置不影响注入）。
        pos = 0
        for i, e in enumerate(entries):
            if (e or {}).get("name") == STANDARD_ENTRY_NAME:
                pos = i + 1
                break
        entries.insert(pos, _standard_example_entry())
        added.append(STANDARD_EXAMPLE_NAME)

    if added:
        out = dict(raw)
        out["entries"] = entries
        p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        _invalidate(p)

    return {"added": added, "present": present}


def save_world(name, entries):
    """整份保存世界书（覆盖式）。entries 为条目数组。

    新建世界时（该世界此前不存在）自动播种两条默认条目：
      - _STANDARD_ENTRY「亲密描写标准」：叙事技法标准，措辞全中性、不含任何剧本
        专名与题材词，对任意剧本都成立，故随每个新世界出厂即激活。用户可整条删除
        或改写，删除后本函数不会再补（只对「首次创建」播种，不做每次保存的强制回填），
        也可 enabled=false 停用。详见 _STANDARD_ENTRY 注释。
      - _standard_example_entry「写法示范·常驻」：中性 few-shot 示范（酒馆 example
        messages），让「玩家不写示范也能每轮有范例可循」。同样只对首次创建播种，
        删除后不强制回填。
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
        # 置于首位：前端 collectWorldEntries 按列表序重算 priority（index 0 → 100），
        # 而 world.scan 是按 priority 降序截断 max_entries——放首位才能保证
        # 「每世界多一条 constant」不会把该世界的其它设定挤出配额。
        if not _has_standard_entry(entries):
            entries.insert(0, _standard_entry())
        # 常驻写法示范紧随其后（demo 条目不占 max_entries 配额，但保持靠前利于渲染顺序）
        if not _has_standard_example(entries):
            entries.insert(1, _standard_example_entry())
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
    # 导入时补种两条引擎默认条目（若模板未自带）：亲密描写标准是叙事技法基线，
    # 写法示范·常驻是每轮范例——导入一个没带它们的剧本包，也该拿到与新建剧本
    # 同样的出厂供给。save_world 只在「首次创建」时播种，导入覆盖写已存在的剧本
    # 不会触发，故在此显式补，且两条待遇一致（旧版只补示范，导致导入的剧本包
    # 可能永远没有亲密描写标准）。
    if not _has_standard_entry(store_entries):
        store_entries.insert(0, _standard_entry())
    if not _has_standard_example(store_entries):
        pos = next((i + 1 for i, e in enumerate(store_entries)
                    if (e or {}).get("name") == STANDARD_ENTRY_NAME), 0)
        store_entries.insert(pos, _standard_example_entry())
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
