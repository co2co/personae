#!/usr/bin/env python3
"""构建 群像弈（Personae）分发 zip：只打包 engine/（纯引擎本体），排除开发/运行时冗余。

分发原则：用户只需 engine/ 一份即可独立运作，不需要 tests/、venv、缓存与会话状态。
归档根目录为 `engine/`，与 engine/README.md 的运行说明一致（解压后 `cd engine && python app.py`）。

用法：
    python package.py                 # 生成 personae-<VERSION>.zip
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
# 不随分发包携带：会话状态/运行时状态、玩家私人设定、任何剧本内容。
# 方向 B（2026-10-04 simon 裁定）：分发包不含任何示例剧本，首次运行需自行导入；
# 故 data/characters 与 data/worlds 整体排除（二者仅含用户私创/个人 DEMO，
# 绝不可随分发泄漏）。引擎 save_card/save_world 已 mkdir(exist_ok=True)，
# 用户导入时自动建目录，排除不影响可用性。
EXCLUDE_SUBPATHS = {
    "data/sessions",
    "data/state.json",
    "data/characters",   # 角色卡：用户私创/个人 DEMO，不随分发
    "data/worlds",       # 世界书：同上
    "player-cast",       # 用户剧本：玩家设定
}

# Windows 保留设备名（CON/PRN/AUX/NUL/COM1-9/LPT1-9）。
# 误把命令输出重定向到这些名（如 `... > nul`）时，会在工作树里生成同名垃圾文件：
# 既不该入库、也不该进分发包，且会让 os.path.relpath 抛
# "path is on mount '\\\\.\\nul'" 异常而中断打包。此处一律跳过。
RESERVED_WIN_NAMES = (
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)


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
    out_name = out_name or f"personae-{ver}.zip"
    out = ROOT / out_name
    n = 0
    bad = []
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for base, dirs, files in os.walk(ENGINE):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for f in files:
                if os.path.splitext(f)[0].upper() in RESERVED_WIN_NAMES:
                    continue  # 误重定向产生的保留名残留，跳过
                full = os.path.join(base, f)
                rel_engine = os.path.relpath(full, ENGINE)
                if _excluded(rel_engine):
                    continue
                if f.endswith((".log", ".bak")):
                    # 引擎运行日志不进分发 zip（可能含会话/调试内容）；
                    # .bak  likewise——data/config.local.bak 等本地配置备份含私人
                    # 模型绝对路径与 provider key，属分发红线，一律排除。
                    continue
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
    ap.add_argument("--out", help="输出文件名（默认 personae-<VERSION>.zip）")
    args = ap.parse_args()
    out, n, bad = build(args.out)
    print(f"已生成 {out}（{n} 条目，{os.path.getsize(out)/1024:.1f} KB）")
    if bad:
        print("⚠ 不应出现于分发包的文件：", bad)
    else:
        print("排除项校验通过（无 venv/缓存/会话状态/tests 泄漏）。")
