"""服务层：只做路由和流式转发，业务逻辑全在其余模块里。

    python app.py   然后打开 http://127.0.0.1:5000

两类接口：
    创作管理（角色卡 / 世界书 / 聊天 / 配置）：/api/characters、/api/world、/api/config 等
    多角色沙盘（核心）：/api/session/new、/api/act、/api/snapshot

注：旧版单角色生成接口（/api/generate、/api/message、/api/state、/api/persona、
/api/nsfw/confirm、/api/state/reset）已于 2026-09-30 移除，「玩家」机制一并下线，
成年确认迁为系统设置 adult_confirmed。详见 DEVLOG.md。

生成流程里 NSFW 的位置：
    读角色卡 -> nsfw.resolve* 决定尺度 -> prompter 把尺度说明插进固定段
    -> 发请求 -> 回写快照（关系 / 目标 / 秘密揭露）-> 必要时记旧账
"""

import json
import os
import queue
import re
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory, stream_with_context

import director
import scene
import hooks
import llm
import logger
import memory
import nsfw
import prompter
import store
import world as world_mod
import ending
import script_refiner

ROOT = Path(__file__).parent
app = Flask(__name__, static_folder=None)

RECENT_FOR_SCAN = 4


def speaker_segment(text, name, others):
    """从多说话人回复里提取 name 的台词段落。

    格式约定为「角色名：台词」（见 prompter.build_session）。遇到其他角色的
    「X：」开头行即停止收集。找不到则返回空串，调用方应回退到整段回复。
    """
    head = name + "："
    stops = [o + "：" for o in others]
    out, active = [], False
    for ln in text.split("\n"):
        if ln.startswith(head):
            active = True
            out.append(ln[len(head):].lstrip())
        elif active:
            if any(ln.startswith(p) for p in stops):
                break
            out.append(ln)
    return "\n".join(out).strip()


def _scene_change_payload(changed, prop, snap):
    """把场景切换结果整理成前端可读的结构。changed 必为 True。"""
    prop = prop or {}
    return {
        "changed": True,
        "place": snap["scene"].get("place", ""),
        "time": snap["scene"].get("time", ""),
        "leave": prop.get("leave", []),
        "arrive": prop.get("arrive", []),
        "reason": prop.get("reason", ""),
    }


def _worldbook_meta(entries, before_hits, after_hits, secret_hits):
    """整理世界书命中明细，供日志窗结构化展示（常量 / before / after / 排除秘密）。

    让高级用户直观核对：每条设定是否被正确安放到了预期位置（常量每轮必注入、
    before 进系统层、after 进历史之后、秘密条目被排除不进 prompt）。
    """

    def _summ(e):
        return {
            "name": e.get("name") or "",
            "keys": e.get("keys") or [],
            "summary": (e.get("content", "") or "").strip().replace("\n", " ")[:80],
        }

    constants = [e for e in entries if e.get("enabled", True) and e.get("constant")]
    return {
        "total": len(entries),
        "constants": [_summ(e) for e in constants],
        "before": [_summ(e) for e in before_hits],
        "after": [_summ(e) for e in after_hits],
        "secret_excluded": [_summ(e) for e in secret_hits],
    }


# ----------------------------------------------------------------------------
# 前端页面（根路径直接返回场景板）
# ----------------------------------------------------------------------------

@app.get("/")
def index():
    # 本地单用户开发工具：禁用缓存，确保改完 index.html 后浏览器立即拿到最新版，
    # 避免「前端改了但 UI 行为仍是旧的」这类缓存导致的假性 bug。
    r = send_from_directory(ROOT / "static", "index.html")
    r.headers["Cache-Control"] = "no-store"
    return r


@app.get("/static/<path:filename>")
def static_files(filename):
    # 引擎关闭了默认 static 服务（static_folder=None），此处按需提供本地静态资源，
    # 避免世界书文档依赖外部 CDN 而卡在「加载中…」。
    # 同样禁用缓存，保证修复/改动即时生效。
    r = send_from_directory(ROOT / "static", filename)
    r.headers["Cache-Control"] = "no-store"
    return r


@app.get("/docs/worldbook")
def worldbook_doc():
    """返回预渲染的世界书使用说明静态页（构建时由 Markdown 渲染，零 JS 依赖）。"""
    return send_from_directory(ROOT / "static", "worldbook-guide.html")



# ----------------------------------------------------------------------------
# 创作管理：角色卡 / 世界书 / 聊天 / 配置
# ----------------------------------------------------------------------------

@app.get("/api/characters")
def characters():
    return jsonify(store.list_characters())


# ----------------------------------------------------------------------------
# 初始化流程：角色卡 / 世界书管理（参考酒馆的 Character / Lorebook 入口）
# ----------------------------------------------------------------------------
@app.get("/api/character/<name>")
def get_character(name):
    try:
        return jsonify(store.load_card(name))
    except FileNotFoundError:
        return jsonify({"error": f"角色卡不存在: {name}"}), 404


@app.post("/api/character")
def save_character():
    body = request.get_json(force=True)
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name 不能为空"}), 400
    try:
        store.save_card(name, body)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"ok": True, "name": name})


@app.delete("/api/character/<name>")
def delete_character(name):
    store.delete_card(name)
    return jsonify({"ok": True})


@app.get("/api/worlds")
def worlds():
    return jsonify(store.list_worlds())


@app.get("/api/world/<name>")
def get_world(name):
    data = store.load_world_raw(name)
    if data is None:
        return jsonify({"error": f"世界不存在: {name}"}), 404
    return jsonify(data)


@app.post("/api/world/<name>")
def save_world_route(name):
    body = request.get_json(force=True)
    try:
        store.save_world(name, body.get("entries", []))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"ok": True, "name": name})


@app.post("/api/import/from-script")
def import_from_script():
    """剧本→设定 提炼预览（S3 大工程）。

    玩家贴剧本 -> 后端固定 prompt 调 LLM -> 解析 + 白名单沙箱 -> 返回预览。
    只预览、不写文件；确认导入由前端调现有 /api/character 与 /api/world/<name> 执行。
    """
    body = request.get_json(force=True) or {}
    script = (body.get("script") or "").strip()
    if not script:
        return jsonify({"error": "剧本内容不能为空"}), 400
    world_name = (body.get("world_name") or "").strip() or None
    try:
        result = script_refiner.refine_script(script, world_name=world_name)
    except Exception as exc:
        return jsonify({"error": f"提炼失败：{exc}"}), 400
    return jsonify({"ok": True, **result})


@app.post("/api/world/<name>/test")
def test_world(name):
    """命中预览：用 world.scan 对给定历史返回会注入的条目（含秘密标记）。

    服务两件事：① 编辑器里实时看触发词 / 常量是否 fire；② 调引擎时核对世界书覆盖。
    history 为文本列表（最近若干条聊天）；也兼容旧式单串 text。
    """
    body = request.get_json(force=True)
    entries = body.get("entries")
    if entries is None:
        entries = store.load_world(name)
    history = body.get("history")
    if history is None:
        history = [body.get("text", "")]
    directive = body.get("directive", "")
    hits = world_mod.scan(entries, history, directive=directive, character=None)
    return jsonify({"hits": hits, "total": len(entries)})


@app.delete("/api/world/<name>")
def delete_world_route(name):
    name = (name or "").strip()
    if not name:
        return jsonify({"error": "世界名不能为空"}), 400
    body = request.get_json(silent=True) or {}
    referenced = store.worlds_referencing(name)
    # 仍有角色卡绑定此世界时，需前端二次确认，避免误删后开局丢失设定
    if referenced and not body.get("confirm"):
        return jsonify({"ok": False, "referenced": referenced,
                        "error": "该世界仍被角色卡引用，需确认后强制删除"})
    try:
        removed = store.delete_world(name)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400
    if not removed:
        return jsonify({"ok": False, "error": "世界不存在"}), 404
    return jsonify({"ok": True, "name": name, "referenced": referenced})


@app.get("/api/chat/<character>")
def get_chat(character):
    session = request.args.get("session", "main")
    return jsonify(store.load_chat(character, session))


@app.post("/api/chat/rewrite")
def rewrite():
    body = request.get_json(force=True)
    store.rewrite_chat(body["character"], body["messages"], body.get("session", "main"))
    return jsonify({"ok": True})


@app.get("/api/config")
def get_config():
    return jsonify(llm.config_view())


@app.post("/api/config")
def post_config():
    """保存后端设置，立即生效（llm 每次请求重读 config.json）。"""
    body = request.get_json(force=True)
    return jsonify(llm.save_config(body))


@app.post("/api/config/test")
def test_config():
    """测试后端连通性，返回模型列表或错误。"""
    body = request.get_json(force=True)
    try:
        models = llm.list_models(body.get("base_url"), body.get("api_key"))
        return jsonify({"ok": True, "models": models})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)})




# ----------------------------------------------------------------------------
# 运行时日志（SSE）：前端「运行时日志」窗订阅，打开时连接、关闭时断开
# ----------------------------------------------------------------------------

@app.get("/api/log/stream")
def log_stream():
    """以 SSE 推送结构化日志。新连入时先回放最近一段缓冲，再实时推送。"""
    def gen():
        q, back = logger.bus.subscribe_with_backlog()
        try:
            for e in back:
                yield "data: " + json.dumps(e, ensure_ascii=False) + "\n\n"
            while True:
                try:
                    e = q.get(timeout=15)
                    yield "data: " + json.dumps(e, ensure_ascii=False) + "\n\n"
                except queue.Empty:
                    yield ": ping\n\n"
        finally:
            logger.bus.unsubscribe(q)
    return Response(stream_with_context(gen()), mimetype="text/event-stream")


# ----------------------------------------------------------------------------
# 多角色沙盘（新接口）
# ----------------------------------------------------------------------------

@app.post("/api/session/new")
def session_new():
    logger.bus.clear()  # 新一轮推演：清空日志缓冲，避免上一轮内容被日志窗回放
    body = request.get_json(force=True)
    all_chars = store.list_characters()
    # 环境推手不作为角色入场；cast 为同场角色卡列表（默认全部）
    cast = body.get("cast") or list(all_chars)
    # 安全网：去重、剔除不存在的卡，避免在场名单错乱/重复
    cast = [c for c in dict.fromkeys(cast) if c in all_chars]
    if not cast:
        logger.warn("session", "开局失败：未选择任何在场角色")
        return jsonify({"error": "至少需要选择一个在场角色"}), 400
    scene = body.get("scene", "")
    # 世界名取首个在场角色的世界（与 /api/act 加载 lore 的逻辑保持一致），
    # 否则秘密种子会永远从默认 "home" 生成，与 lore 世界错位
    world_name = store.load_card(cast[0]).get("world", "home") if cast else "home"
    try:
        sid = memory.new(cast, scene_place=scene, world_name=world_name)
    except Exception as exc:
        logger.error("session", "创建会话失败：" + repr(exc))
        return jsonify({"error": str(exc)}), 500
    logger.info("session", "开启新会话：" + sid + " ｜ 在场 " + "、".join(cast)
                + " ｜ 世界 " + world_name + (" ｜ 开场 " + scene if scene else ""))
    # 角色卡未提供初始关系时，由系统根据同场角色自动生成关系网写入快照
    snap = memory.load(sid)
    if not snap.get("relations"):
        cards = {c: store.load_card(c) for c in snap["present"]}
        gen = director.init_relations(cards)
        if gen:
            snap["relations"] = gen
            # 固化权威关系基线：后续 reflect 只允许镜头内角色演化关系，
            # 未在场/无卡关联人物（如林梦琪）的关系冻结为此基线，杜绝漂移
            snap["relations_base"] = dict(gen)
            memory.save(sid, snap)
            logger.info("director", "自动生成初始关系网：" + str(len(gen)) + " 条（已固化 relations_base）")
        else:
            # 回退：同场角色两两互为“互相认识”，保证引擎有最小关系网可用
            fallback = {}
            for a in snap["present"]:
                for b in snap["present"]:
                    if a != b:
                        fallback[f"{a} → {b}"] = "同处一个场景，互相认识"
            snap["relations"] = fallback
            snap["relations_base"] = dict(fallback)
            memory.save(sid, snap)
            logger.info("director", "关系自动生成失败，回退为全互相认识")
    logger.success("session", "会话就绪：" + sid)
    return jsonify({"session": sid, "snapshot": memory.load(sid)})


@app.get("/api/snapshot")
def get_snapshot():
    sid = request.args.get("session")
    snap = memory.load(sid) if sid else None
    return jsonify(snap or {})


@app.get("/api/sessions")
def list_sessions_route():
    """列举全部会话（玩家侧"剧本管理"入口）：返回 id / 在场 / 场景 / 回合 / 状态。"""
    return jsonify(memory.list_sessions())


@app.delete("/api/session/<sid>")
def delete_session_route(sid):
    """删除一局会话（玩家放弃当前剧本）。不存在返回 404。"""
    if memory.delete_session(sid):
        return jsonify({"deleted": sid})
    return jsonify({"error": "会话不存在"}), 404


@app.get("/api/session/<sid>/chat")
def session_chat_route(sid):
    """返回某局会话的聊天历史（继续剧本时前端渲染旧对话）。不存在返回 404。"""
    if not (memory.SESS_DIR / sid).exists():
        return jsonify({"error": "会话不存在"}), 404
    return jsonify(memory.load_chat(sid))


@app.post("/api/act")
def act():
    body = request.get_json(force=True)
    sid = body.get("session")
    directive = (body.get("input") or "").strip()   # 环境推手注入的扰动指令
    try:
        snap = memory.load(sid)
    except Exception as exc:
        logger.error("error", "读取会话失败：" + repr(exc))
        return jsonify({"error": str(exc)}), 500
    if not snap:
        logger.warn("session", "指令发往不存在的会话：" + str(sid))
        return jsonify({"error": "会话不存在"}), 404

    logger.info("session", "收到导演扰动：" + (directive or "（无，自然推演）"))
    try:
        # 场景自动切换：生成前先决定，使新场景/天气进入提示词；同时更新在场名单
        scene_changed, scene_prop = scene.apply(sid, directive, snap)
        # 镜头跟随：玩家把扰动引向某子集时，镜头跟随该子集，其余在场者视为镜头外
        focus = director.compute_focus(directive, snap)
        snap["focus"] = focus
        memory.save(sid, snap)
        present = snap["present"]                  # 全部为 NPC，环境推手不在场
        cards_present = {c: store.load_card(c) for c in present}

        # 导演简报（含秘密状态更新、回合数、机会等级）
        brief, snap = director.brief(sid, directive)
        logger.info("director", "导演简报：回合 R" + str(brief["round"]) + " ｜ 机会等级 " + brief["opportunity"]
                    + (" ｜ 新揭露秘密：" + "、".join(brief["revealed_secrets"]) if brief["revealed_secrets"] else "")
                    + (" ｜ 激活旧账 " + str(len(brief["active_consequences"])) + " 条" if brief["active_consequences"] else ""))

        # 场景切换日志
        if scene_changed and scene_prop:
            logger.info("scene", "场景切换 → " + (scene_prop.get("place", "") or "")
                        + ("（" + (scene_prop.get("time", "") or "时间未明") + "）" if scene_prop.get("place") or scene_prop.get("time") else "")
                        + (" ｜ 天气 " + scene_prop["weather"] if scene_prop.get("weather") else "")
                        + (" ｜ " + "、".join(scene_prop.get("leave", [])) + " 离开" if scene_prop.get("leave") else "")
                        + (" ｜ " + "、".join(scene_prop.get("arrive", [])) + " 到场" if scene_prop.get("arrive") else ""))
        else:
            logger.debug("scene", "场景无变化，沿用当前场景")

        # 世界书：剔除潜伏秘密条目（秘密不进 prompt，只在角色块里按已知状态提示）
        world_name = cards_present[present[0]].get("world") if present else "home"
        entries = store.load_world(world_name)
        history = [m.get("content", "") for m in memory.load_chat(sid)[-RECENT_FOR_SCAN:]]
        hits_all = world_mod.scan(entries, history, directive=directive,
                                 default_depth=RECENT_FOR_SCAN, character=None)
        world_hits = [e for e in hits_all if not e.get("secret")]
        before_hits = [e for e in world_hits if e.get("position", "before") == "before"]
        after_hits = [e for e in world_hits if e.get("position", "before") == "after"]
        secret_hits = [e for e in hits_all if e.get("secret")]

        wb_meta = _worldbook_meta(entries, before_hits, after_hits, secret_hits)
        logger.info("worldbook",
                    "世界书「" + world_name + "」扫描 " + str(wb_meta["total"]) + " 条："
                    "常量 " + str(len(wb_meta["constants"]))
                    + " ｜ before 命中 " + str(len(wb_meta["before"]))
                    + " ｜ after 命中 " + str(len(wb_meta["after"]))
                    + " ｜ 排除秘密 " + str(len(wb_meta["secret_excluded"])) + "（不注入 prompt）",
                    meta=wb_meta)

        # NSFW：尺度由“成年确认 + 本轮机会等级”驱动（回归原版机制，不再用好感度阈值）
        # 服务端门控：override 由设置决定，客户端 body 里的 nsfw 仅在 nsfw_enabled 时生效；
        # 未确认成年 / 未开启 NSFW 即便伪造 nsfw="on" 也无法突破（见 tests/test_nsfw_defense.py）
        adult = llm.setting("adult_confirmed")
        decision = nsfw.resolve_for_request(
            snap, adult, llm.setting("nsfw_enabled"), body.get("nsfw"), brief["opportunity"])
        logger.info("nsfw", "尺度：" + ("开放" if decision["unlocked"] else "受限") + "（" + decision["reason"] + "）")

        history = memory.load_chat(sid)
        messages = prompter.build_session(
            cards_present, directive, before_hits, snap,
            decision["prompt"], brief["opportunity"], history=history,
            after_hits=after_hits,
            focus=focus,
        )
        messages = hooks.emit("prompt_ready", messages=messages, snap=snap)["messages"]
        tok = sum(prompter.count_tokens(m.get("content", "")) for m in messages)
        # 计算世界书落点标注：before 命中全部进首条 system 段；after 命中进独立的「[世界设定·续]」段。
        # 高级用户可据此逐段核对世界书到底插进了哪一段。
        prompt_ann = {}
        if before_hits and messages:
            prompt_ann[0] = "世界书·before"
        for i, m in enumerate(messages):
            if (m.get("content") or "").startswith("[世界设定·续]"):
                prompt_ann[i] = "世界书·after"
        logger.info("prompt", "组装提示词：" + str(len(messages)) + " 段 ｜ 约 " + str(tok) + " token"
                    + "（系统层 " + str(1 + len(before_hits)) + " ｜ after " + str(len(after_hits))
                    + " ｜ 历史 " + str(len(history)) + "）",
                    meta={"full": {"messages": messages, "annotations": prompt_ann}})
    except Exception as exc:
        logger.error("error", "生成流程准备阶段异常：" + repr(exc))
        return jsonify({"error": str(exc)}), 500

    def _resolve(name, raw):
        # 请求体未给时回退配置；配置缺失（如测试桩返回 None）再回退代码默认值，避免 int(None) 崩溃
        v = raw if raw is not None else llm.setting(name)
        return v if v is not None else llm.DEFAULTS[name]

    params = {
        "temperature": float(_resolve("temperature", body.get("temperature"))),
        "top_p": float(_resolve("top_p", body.get("top_p"))),
        "top_k": int(_resolve("top_k", body.get("top_k"))),
        "max_tokens": int(_resolve("max_tokens", body.get("max_tokens"))),
    }

    def events():
        reply_text = []
        model = llm.setting("model")
        logger.info("model", "远程模型开始生成（" + str(model) + "）…")
        # 实时流式：首 token 抵达前先发「思考中」状态，避免玩家干等无反馈
        yield "data: " + json.dumps({"status": "模型思考中…"}, ensure_ascii=False) + "\n\n"
        first = True
        try:
            for chunk in llm.stream(messages, **params):
                if first:
                    first = False
                    logger.success("model", "首 token 已到达，模型正在输出…")
                    yield "data: " + json.dumps({"status": "生成中…"}, ensure_ascii=False) + "\n\n"
                reply_text.append(chunk)
                # 逐块即时回传，前端逐字追加渲染（打字机效果），不再憋完一次性倒空
                yield "data: " + json.dumps({"delta": chunk}, ensure_ascii=False) + "\n\n"
        except Exception as exc:
            logger.error("model", "模型流异常：" + repr(exc))
            yield "data: " + json.dumps({"error": str(exc)}, ensure_ascii=False) + "\n\n"
            return

        full = "".join(reply_text)
        logger.info("model", "模型输出完成，共 " + str(len(full)) + " 字")
        result = hooks.emit("message_received", reply=full, snap=snap)
        full = result["reply"]
        # present 名单校验/后处理：剥离非在场角色（含已离场者、环境推手）的台词块；
        # 若本轮有镜头焦点，则按焦点子集裁剪，使镜头真正跟随被引向的角色，其余在场者不展开
        known = store.list_characters()
        focus_subjects = focus["subjects"] if focus else None
        full, present_violation = director.validate_present(
            full, present, known, allowed=focus_subjects)
        if present_violation:
            logger.warn("model", "在场校验：剥离了非在场角色的台词块（已自动清洗）")
        else:
            logger.info("model", "在场校验通过：仅含在场角色台词")
        # 背景人物活动化自检：无独立角色卡、仅关系事实的角色若被写成对白/独白/主角行动，
        # 属引擎失责（simon 验收标准）。仅检测不删正文，结果向前端报告。
        offscreens = director.background_names_from_relations(snap, present)
        off_viol, off_hits = director.detect_offscreen_activity(full, offscreens)
        if off_viol:
            present_violation = True
            logger.warn("model", "背景人物活动化自检失责：" + "；".join(off_hits[:3])
                        + ("…" if len(off_hits) > 3 else ""))
        else:
            logger.info("model", "背景人物自检通过："
                        + ("、".join(offscreens) + " 保持背景" if offscreens else "无背景人物"))
        # 注：原始 token 已实时流式回传，此处不再回吐整段以免重复；
        # 校验后的 canonical 文本经末尾 done.reply 回传，前端据此对齐（极少剥离时无缝修正）。

        memory.append_chat(sid, {"role": "user", "content": "【导演指令】" + directive})
        memory.append_chat(sid, {"role": "assistant", "content": full})

        # 行动状态（廉价启发）：本轮正文里出现的角色 = 主动，未出现 = 无行动
        for c in present:
            memory.set_action_state(sid, c, "主动" if c in full else "无行动")
        director.after_reply(sid, full)
        # 状态机回写：把本轮推演产生的后果（关系/目标/秘密揭露）落回快照
        director.reflect(sid, full)
        snap_now = memory.load(sid)
        exposed = [s for s in snap_now.get("secrets", []) if s.get("state") != "潜伏"]
        logger.info("director", "状态回写完成：关系 " + str(len(snap_now.get("relations", {}))) + " 条"
                    + " ｜ 本轮行动 " + str(len(snap_now.get("actions", {}))) + " 条"
                    + " ｜ 已暴露秘密 " + str(len(exposed)) + " 条")

        # 结局判定（软指引，非强制）：命中终局条件则向客户端提议是否终结当前会话
        candidate = ending.evaluate(snap_now, snap_now.get("ending_dismissed_reasons"))
        snap_now["ending_last_reasons"] = (candidate or {}).get("reasons", [])
        memory.save(sid, snap_now)
        if candidate:
            logger.info("ending", "命中终局条件：" + "、".join(candidate["labels"])
                        + " ｜ 已向客户端提议是否终结")
        else:
            logger.debug("ending", "未命中终局条件，继续推演")

        yield "data: " + json.dumps({
            "done": True,
            "reply": full,
            "present_violation": present_violation,
            "offscreen_violation": off_hits,
            "opportunity": brief["opportunity"],
            "nsfw": decision,
            "scene_change": _scene_change_payload(scene_changed, scene_prop, snap)
                            if scene_changed else None,
            "ending_candidate": candidate,
            "snapshot": snap_now,
        }, ensure_ascii=False) + "\n\n"
        logger.success("system", "本轮推演完成（R" + str(brief["round"]) + "）")

    return Response(stream_with_context(events()), mimetype="text/event-stream")


@app.post("/api/ending/dismiss")
def ending_dismiss():
    """用户点"继续探索"：把当前命中的终局条件记入快照，后续除非出现新条件不再弹提示。"""
    body = request.get_json(force=True)
    sid = body.get("session")
    snap = memory.load(sid) if sid else None
    if not snap:
        return jsonify({"error": "会话不存在"}), 404
    ending.mark_dismissed(snap, snap.get("ending_last_reasons", []))
    memory.save(sid, snap)
    logger.info("ending", "用户选择继续探索，已抑制终局提示（新条件出现前不再弹出）")
    return jsonify({"ok": True})


@app.post("/api/end")
def end_session():
    """终结当前会话：基于世界最终状态与对话生成剧本总结（非流式），并导出 markdown 存档。

    软指引的一部分：引擎不主动终结，仅在用户显式选择"终结剧本"（手动按钮或终局提示）时调用。
    """
    body = request.get_json(force=True)
    sid = body.get("session")
    snap = memory.load(sid) if sid else None
    if not snap:
        return jsonify({"error": "会话不存在"}), 404
    history = memory.load_chat(sid)
    try:
        messages = prompter.build_summary(snap, history)
        summary = llm.complete(messages, max_tokens=900, temperature=0.7, timeout=120)
    except Exception as exc:
        logger.error("ending", "总结生成失败：" + repr(exc))
        return jsonify({"error": str(exc)}), 500

    # 导出 markdown 存档（玩家侧可下载/留档；不影响会话删除）
    exported = False
    try:
        out = memory.SESS_DIR / sid / "summary.md"
        out.write_text("# 剧本总结\n\n" + summary.strip() + "\n", encoding="utf-8")
        exported = True
    except Exception as exc:
        logger.warn("ending", "总结 markdown 导出失败（不影响返回）：" + repr(exc))

    logger.success("ending", "会话 " + sid + " 已生成剧本总结（" + str(len(summary)) + " 字"
                            + (" ｜ 已导出 summary.md" if exported else "") + "）")
    return jsonify({
        "summary": summary,
        "exported": exported,
        "present": snap.get("present", []),
        "round": (snap.get("scene") or {}).get("round", 0),
    })


if __name__ == "__main__":
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "5000")),
            debug=os.getenv("FLASK_DEBUG", "0") == "1")
