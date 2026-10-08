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

# 采样参数的出厂真值，直接取自引擎的 DEFAULTS（不硬编码字面量到打包脚本里）。
# 用 importlib 从文件加载而非 import llm：llm 依赖 requests，缺依赖时打包仍须能跑。
def _load_engine_defaults():
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_pkg_llm", ENGINE / "llm.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)          # llm 只在函数内读 CONFIG_FILE，加载期无副作用
        return dict(mod.DEFAULTS)
    except Exception:
        return {}


_ENGINE_DEFAULTS = _load_engine_defaults()

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

# 内部设计备忘：不随分发（写给开发者复装用，用户不需要也不该看到已移除机制的细节）
EXCLUDE_FILES = {
    "FACT-MEMO.md",
    # 开发日志 / 待办：含私人剧本的具体角色名、关系与题材词（引擎普适性红线：
    # 引擎面向任意剧本，这些名字一个都不该出现在分发物里）。与 FACT-MEMO 同理，
    # 属只留工作树的内部文档。engine/README.md 中对二者的引用已同步改为不随包提供。
    "DEVLOG.md",
    "TODO.md",
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
    if rel in EXCLUDE_FILES:
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
                        # fallback 段：本地兜底模型的 base_url/model 是个人机器布局
                        # （如 D:\ai\models\*.gguf），属分发红线。清空 base_url 即
                        # 「未启用降级」，是出厂默认（_fallback_config() 见空即返回 None）。
                        fb = cfg.get("fallback")
                        if isinstance(fb, dict):
                            fb["base_url"] = ""
                            fb["api_key"] = ""
                            fb["model"] = ""
                        # 采样参数：连同 DEFAULTS 一起洗白。**直接从 llm.DEFAULTS 取真值**，
                        # 不在此处硬编码字面量——否则引擎调了默认值而这里没跟上，
                        # 新装用户就会拿到开发者机器上的旧值（v0.21.2 实踩：磁盘 temperature=1.0
                        # 被原样打进包，而出厂默认已是 0.85）。min_p 存 null 时也要写回真值。
                        for k in ("temperature", "top_p", "top_k", "min_p",
                                  "repeat_penalty", "repeat_last_n", "max_tokens"):
                            if k in _ENGINE_DEFAULTS:
                                cfg[k] = _ENGINE_DEFAULTS[k]
                        # null/缺失一律剔除：setting() 虽已把 null 兜底成默认值，
                        # 但包里留 null 会让读包的人困惑，也让 config_view 回填出 null。
                        for k in ("temperature", "top_p", "top_k", "min_p",
                                  "repeat_penalty", "repeat_last_n"):
                            if cfg.get(k) is None:
                                cfg.pop(k, None)
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
