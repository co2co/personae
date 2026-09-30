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
import re
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory, stream_with_context

import director
import scene
import hooks
import llm
import memory
import nsfw
import prompter
import store
import world as world_mod

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


# ----------------------------------------------------------------------------
# 前端页面（根路径直接返回场景板）
# ----------------------------------------------------------------------------

@app.get("/")
def index():
    return send_from_directory(ROOT / "static", "index.html")


@app.get("/docs/worldbook")
def worldbook_doc():
    """返回世界书使用说明书（Markdown 源文件，供「系统设置」内链在新窗口打开）。"""
    return send_from_directory(ROOT, "世界书使用说明.md",
                               mimetype="text/markdown; charset=utf-8")


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
# 多角色沙盘（新接口）
# ----------------------------------------------------------------------------

@app.post("/api/session/new")
def session_new():
    body = request.get_json(force=True)
    all_chars = store.list_characters()
    # 环境推手不作为角色入场；cast 为同场角色卡列表（默认全部）
    cast = body.get("cast") or list(all_chars)
    # 安全网：去重、剔除不存在的卡，避免在场名单错乱/重复
    cast = [c for c in dict.fromkeys(cast) if c in all_chars]
    if not cast:
        return jsonify({"error": "至少需要选择一个在场角色"}), 400
    scene = body.get("scene", "")
    # 世界名取首个在场角色的世界（与 /api/act 加载 lore 的逻辑保持一致），
    # 否则秘密种子会永远从默认 "home" 生成，与 lore 世界错位
    world_name = store.load_card(cast[0]).get("world", "home") if cast else "home"
    sid = memory.new(cast, scene_place=scene, world_name=world_name)
    # 角色卡未提供初始关系时，由系统根据同场角色自动生成关系网写入快照
    snap = memory.load(sid)
    if not snap.get("relations"):
        cards = {c: store.load_card(c) for c in snap["present"]}
        gen = director.init_relations(cards)
        if gen:
            snap["relations"] = gen
            memory.save(sid, snap)
        else:
            # 回退：同场角色两两互为“互相认识”，保证引擎有最小关系网可用
            fallback = {}
            for a in snap["present"]:
                for b in snap["present"]:
                    if a != b:
                        fallback[f"{a} → {b}"] = "同处一个场景，互相认识"
            snap["relations"] = fallback
            memory.save(sid, snap)
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
    directive = body.get("input", "")          # 环境推手注入的扰动指令
    snap = memory.load(sid)
    if not snap:
        return jsonify({"error": "会话不存在"}), 404

    # 场景自动切换：生成前先决定，使新场景/天气进入提示词；同时更新在场名单
    scene_changed, scene_prop = scene.apply(sid, directive, snap)
    memory.save(sid, snap)
    present = snap["present"]                  # 全部为 NPC，环境推手不在场
    cards_present = {c: store.load_card(c) for c in present}

    # 导演简报（含秘密状态更新、回合数、机会等级）
    brief, snap = director.brief(sid, directive)

    # 世界书：剔除潜伏秘密条目（秘密不进 prompt，只在角色块里按已知状态提示）
    world_name = cards_present[present[0]].get("world") if present else "home"
    entries = store.load_world(world_name)
    history = [m.get("content", "") for m in memory.load_chat(sid)[-RECENT_FOR_SCAN:]]
    hits_all = world_mod.scan(entries, history, directive=directive,
                             default_depth=RECENT_FOR_SCAN, character=None)
    world_hits = [e for e in hits_all if not e.get("secret")]
    before_hits = [e for e in world_hits if e.get("position", "before") == "before"]
    after_hits = [e for e in world_hits if e.get("position", "before") == "after"]

    # NSFW：尺度由“成年确认 + 本轮机会等级”驱动（回归原版机制，不再用好感度阈值）
    adult = llm.setting("adult_confirmed")
    decision = nsfw.resolve_session(snap, adult, brief["opportunity"],
                                    override="off" if not llm.setting("nsfw_enabled") else body.get("nsfw"))

    history = memory.load_chat(sid)
    messages = prompter.build_session(
        cards_present, directive, before_hits, snap,
        decision["prompt"], brief["opportunity"], history=history,
        after_hits=after_hits,
        reserve=int(body.get("max_tokens", llm.setting("max_tokens"))) + 200,
    )
    messages = hooks.emit("prompt_ready", messages=messages, snap=snap)["messages"]

    params = {
        "temperature": float(body.get("temperature", llm.setting("temperature"))),
        "top_p": float(body.get("top_p", llm.setting("top_p"))),
        "max_tokens": int(body.get("max_tokens", llm.setting("max_tokens"))),
    }

    def events():
        reply_text = []
        try:
            for chunk in llm.stream(messages, **params):
                reply_text.append(chunk)
                yield "data: " + json.dumps({"delta": chunk}, ensure_ascii=False) + "\n\n"
        except Exception as exc:
            yield "data: " + json.dumps({"error": str(exc)}, ensure_ascii=False) + "\n\n"
            return

        full = "".join(reply_text)
        result = hooks.emit("message_received", reply=full, snap=snap)
        full = result["reply"]
        memory.append_chat(sid, {"role": "user", "content": "【导演指令】" + directive})
        memory.append_chat(sid, {"role": "assistant", "content": full})

        # 行动状态（廉价启发）：本轮正文里出现的角色 = 主动，未出现 = 无行动
        for c in present:
            memory.set_action_state(sid, c, "主动" if c in full else "无行动")
        director.after_reply(sid, full, brief["opportunity"], decision["intimate"])
        # 状态机回写：把本轮推演产生的后果（关系/目标/秘密揭露）落回快照
        director.reflect(sid, full)

        yield "data: " + json.dumps({
            "done": True,
            "reply": full,
            "opportunity": brief["opportunity"],
            "nsfw": decision,
            "scene_change": _scene_change_payload(scene_changed, scene_prop, snap)
                            if scene_changed else None,
            "snapshot": memory.load(sid),
        }, ensure_ascii=False) + "\n\n"

    return Response(stream_with_context(events()), mimetype="text/event-stream")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")),
            debug=os.getenv("FLASK_DEBUG", "0") == "1")
