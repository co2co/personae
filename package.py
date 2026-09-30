#!/usr/bin/env python3
"""构建 ST-Lite 分发 zip：只打包 engine/（纯引擎本体），排除开发/运行时冗余。

分发原则：用户只需 engine/ 一份即可独立运作，不需要 tests/、venv、缓存与会话状态。
归档根目录为 `engine/`，与 engine/README.md 的运行说明一致（解压后 `cd engine && python app.py`）。

用法：
    python package.py                 # 生成 my-st-<VERSION>.zip
    python package.py --out foo.zip   # 指定输出名
"""

import argparse
import os
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENGINE = ROOT / "engine"

# 排除项（相对 engine/ 的路径）
EXCLUDE_DIRS = {".git", "venv", "__pycache__"}
EXCLUDE_SUBPATHS = {"data/sessions", "data/state.json"}


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
                arcname = os.path.relpath(full, ROOT).replace(os.sep, "/")  # zip 用正斜杠
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
