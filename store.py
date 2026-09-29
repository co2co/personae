"""数据层：角色卡、世界书、聊天记录。全部是本地 JSON / JSONL 文件，没有数据库。

目录结构（对应 SillyTavern 的 data/default-user/）：
    data/characters/<name>.json   角色卡
    data/worlds/<name>.json       世界书
    data/chats/<角色>/<会话>.jsonl 每行一条消息，第一行是会话头
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"


def _read_json(path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_characters():
    folder = DATA_DIR / "characters"
    return sorted(p.stem for p in folder.glob("*.json"))


def load_card(name):
    card = _read_json(DATA_DIR / "characters" / f"{name}.json")
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
    (folder / f"{name}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def delete_card(name):
    p = DATA_DIR / "characters" / f"{name}.json"
    if p.exists():
        p.unlink()


def list_worlds():
    folder = DATA_DIR / "worlds"
    return sorted(p.stem for p in folder.glob("*.json"))


def load_world_raw(name):
    return _read_json(DATA_DIR / "worlds" / f"{name}.json")


def load_world(name="demo"):
    data = _read_json(DATA_DIR / "worlds" / f"{name}.json")
    return (data or {}).get("entries", [])


def save_world(name, entries):
    """整份保存世界书（覆盖式）。entries 为条目数组。"""
    name = (name or "").strip()
    if not name:
        raise ValueError("世界名不能为空")
    folder = DATA_DIR / "worlds"
    folder.mkdir(parents=True, exist_ok=True)
    data = {"name": name, "entries": entries or []}
    (folder / f"{name}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def delete_world(name):
    """删除整份世界书。返回 True 表示文件已存在并删除，False 表示原本就不存在。"""
    name = (name or "").strip()
    if not name:
        raise ValueError("世界名不能为空")
    p = DATA_DIR / "worlds" / f"{name}.json"
    if not p.exists():
        return False
    p.unlink()
    return True


def worlds_referencing(name):
    """返回 world 字段指向该世界的角色卡名列表（用于删除前的引用保护）。"""
    return [c for c in list_characters()
            if (load_card(c) or {}).get("world") == name]


def chat_path(character, session="main"):
    folder = DATA_DIR / "chats" / character
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{session}.jsonl"


def load_chat(character, session="main"):
    """读取会话，跳过第一行会话头。"""
    path = chat_path(character, session)
    if not path.exists():
        return []
    messages = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        line = line.strip()
        if not line:
            continue
        if i == 0:
            continue
        messages.append(json.loads(line))
    return messages


def append_message(character, message, session="main"):
    """追加写一行。JSONL 的好处：崩溃最多丢最后一条，不会整文件损坏。"""
    path = chat_path(character, session)
    if not path.exists():
        path.write_text(json.dumps({"character": character, "session": session},
                                   ensure_ascii=False) + "\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(message, ensure_ascii=False) + "\n")


def rewrite_chat(character, messages, session="main"):
    """整体重写，用于删除消息或重新生成后同步。"""
    path = chat_path(character, session)
    lines = [json.dumps({"character": character, "session": session}, ensure_ascii=False)]
    lines.extend(json.dumps(m, ensure_ascii=False) for m in messages)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
