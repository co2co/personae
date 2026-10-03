#!/usr/bin/env python3
"""构建 ST-Lite 分发 zip：只打包 engine/（纯引擎本体），排除开发/运行时冗余。

分发原则：用户只需 engine/ 一份即可独立运作，不需要 tests/、venv、缓存与会话状态。
归档根目录为 `engine/`，与 engine/README.md 的运行说明一致（解压后 `cd engine && python app.py`）。

用法：
    python package.py                 # 生成 my-st-<VERSION>.zip
    python package.py --out foo.zip   # 指定输出名
"""

import argparse
import json
import os
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENGINE = ROOT / "engine"

# 排除项（相对 engine/ 的路径）
EXCLUDE_DIRS = {".git", "venv", "__pycache__"}
# 不随分发包携带：会话状态/运行时状态、玩家私人设定。
# 注：自 v0.8.0 起，引擎随附「丧尸末日」DEMO 剧本（角色卡 + 世界书），
# 位于 data/characters 与 data/worlds，作为公开示例一并分发，故不再排除二者；
# 如需排除私人剧本，请仅删除对应文件而非整目录。
EXCLUDE_SUBPATHS = {
    "data/sessions",
    "data/state.json",
    "player-cast",       # 用户剧本：玩家设定
}


def _version():
    p = ENGINE / "VERSION"
    return p.read_text(encoding="utf-8").strip() if p.exists() else "dev"


def _excluded(rel_engine):
    rel = rel_engine.replace(os.sep, "/")  # 跨平台：统一为正斜杠
    parts = rel.split("/")
    if parts[0] in EXCLUDE_DIRS:
        return True
    for sp in EXCLUDE_SUBPATHS:
        if rel == sp or rel.startswith(sp + "/"):
            return True
    return False


def build(out_name=None):
    ver = _version()
    out_name = out_name or f"my-st-{ver}.zip"
    out = ROOT / out_name
    n = 0
    bad = []
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for base, dirs, files in os.walk(ENGINE):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for f in files:
                full = os.path.join(base, f)
                rel_engine = os.path.relpath(full, ENGINE)
                if _excluded(rel_engine):
                    continue
                if f.endswith(".log"):
                    continue  # 引擎运行日志不进分发 zip（可能含会话/调试内容）
                arcname = os.path.relpath(full, ROOT).replace(os.sep, "/")  # zip 用正斜杠
                if rel_engine.replace(os.sep, "/") == "data/config.json":
                    # 分发 zip 不得携带个人 config（本地模型路径/连接）；洗白为出厂默认再归档，工作树不动
                    try:
                        cfg = json.loads(Path(full).read_text(encoding="utf-8"))
                        cfg["base_url"] = ""
                        cfg["api_key"] = ""
                        cfg["model"] = ""
                        cfg["providers"] = []
                        z.writestr(arcname, json.dumps(cfg, ensure_ascii=False, indent=2))
                    except Exception:
                        z.write(full, arcname)
                    n += 1
                    continue
                z.write(full, arcname)
                n += 1
                if any(x in arcname for x in ("venv/", "__pycache__/", "data/sessions", "tests/")):
                    bad.append(arcname)
    return out, n, bad


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="打包 engine/ 为分发 zip")
    ap.add_argument("--out", help="输出文件名（默认 my-st-<VERSION>.zip）")
    args = ap.parse_args()
    out, n, bad = build(args.out)
    print(f"已生成 {out}（{n} 条目，{os.path.getsize(out)/1024:.1f} KB）")
    if bad:
        print("⚠ 不应出现于分发包的文件：", bad)
    else:
        print("排除项校验通过（无 venv/缓存/会话状态/tests 泄漏）。")
