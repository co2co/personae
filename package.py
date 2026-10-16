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
import sys
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
# 不随分发包携带：会话状态/运行时状态、玩家私人设定。
# 口径（2026-10-15 simon 更改，替代 2026-10-04 的「方向 B」）：分发包随一份官方 demo 剧本，
# 该 demo 存放于 data/examples/（白名单，天然不被下方 data/characters、data/worlds 排除，
# 因前缀是 data/examples/… 而非 data/…）。用户私创/个人剧本仍在 data/characters、data/worlds，
# 二者整体排除，绝不可随分发泄漏。引擎 save_card/save_world 已 mkdir(exist_ok=True)，
# 用户导入时自动建目录，排除不影响可用性。
EXCLUDE_SUBPATHS = {
    "data/sessions",
    "data/state.json",
    "data/characters",   # 角色卡：用户私创/个人 DEMO，不随分发（官方 demo 在 data/examples/characters/）
    "data/worlds",       # 世界书：同上（官方 demo 在 data/examples/worlds/）
    "player-cast",       # 用户剧本：玩家设定
    # 注：运行展示截图（screenshots/ 与 screenshots-excluded/）已于 2026-10-09 整体挪到
    # 项目根，不再位于 engine/ 下，本 os.walk(ENGINE) 天然不会触及，故无需在此排除。
}

# 说明：开发类文档（DEVLOG / TODO / FACT-MEMO）已于 2026-10-08 移出引擎本体，
# 现存于 tests/（开发工作树），engine/ 仅保留面向用户的 README.md 与 INSTALL.md。
# 故此处不再需要它们各自的排除项——EXCLUDE_DIRS 已覆盖引擎内的一切子目录。
# 引擎面向任意剧本，任何剧本内容（角色名/关系/题材词）都不该出现在分发物里；
# 该约束现由 EXCLUDE_SUBPATHS 承担（data/characters、data/worlds、player-cast）。

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
    # 防御性排除：任何 backup_* 目录/文件都不得进分发包——备份含改动前旧源码，
    # 可能残留未洗白的本地路径/密钥，属分发红线（2026-10-12 实踩：backup 文件夹
    # 位于 engine/ 下被误打包，现加此规则并约定备份一律放项目根而非 engine/）。
    if any(p.startswith("backup_") for p in parts):
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
                        # fallback 段防御性洗白：v0.27.0 起已移除 LLM 降级机制，出厂 config
                        # 不再含 fallback 段；但升级用户的旧 config.json 可能仍残留该段
                        # （含本地 gguf 绝对路径/provider key），属分发红线，故遇残留一律清空。
                        fb = cfg.get("fallback")
                        if isinstance(fb, dict):
                            fb["base_url"] = ""
                            fb["api_key"] = ""
                            fb["model"] = ""
                        # 采样参数：连同 DEFAULTS 一起洗白。**直接从 llm.DEFAULTS 取真值**，
                        # 不在此处硬编码字面量——否则引擎调了默认值而这里没跟上，
                        # 新装用户就会拿到开发者机器上的旧值（v0.21.2 实踩：磁盘 temperature=1.0
                        # 被原样打进包，而出厂默认已是 0.85）。min_p 存 null 时也要写回真值。
                        # 注（v0.28.0）：repeat_penalty/repeat_last_n 已从采样参数降为
                        # llama.cpp 特化内部后备（不暴露给用户），故洗白白名单改为
                        # frequency_penalty/presence_penalty；遇旧 config 残留的 repeat_* 一律剔除。
                        for k in ("temperature", "top_p", "top_k", "min_p",
                                  "frequency_penalty", "presence_penalty", "max_tokens"):
                            if k in _ENGINE_DEFAULTS:
                                cfg[k] = _ENGINE_DEFAULTS[k]
                        # null/缺失一律剔除：setting() 虽已把 null 兜底成默认值，
                        # 但包里留 null 会让读包的人困惑，也让 config_view 回填出 null。
                        for k in ("temperature", "top_p", "top_k", "min_p",
                                  "frequency_penalty", "presence_penalty",
                                  "repeat_penalty", "repeat_last_n"):
                            if cfg.get(k) is None:
                                cfg.pop(k, None)
                        # 旧 config 残留的 llama.cpp 私有字段直接剔除，避免污染新装用户的默认态
                        for k in ("repeat_penalty", "repeat_last_n"):
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
    ap.add_argument("--skip-demo-check", action="store_true",
                    help="跳过「随包 demo 与运行态一致性」检查")
    args = ap.parse_args()

    # 守卫：真相源是作者源 dramas/。分发 zip 携带的 demo 与运行态必须都等于作者源。
    # 若不一致，说明改过作者源没 install，或实测改过运行态没 adopt——都会导致打出的
    # zip 行为与你设计稿不一致。先 install（或 adopt+install）再打包。
    if not args.skip_demo_check:
        sys.path.insert(0, str(ROOT / "scripts"))
        try:
            import sync_drama
            drama, divs = sync_drama.collect_divergences()
            if divs:
                print(f"✗ 打包中止：作者源/运行态/demo 三方不一致（剧本「{drama}」），共 {len(divs)} 处：")
                for d in divs:
                    print("   -", d)
                print("  → 先运行  python scripts/sync_drama.py install  铺开后再打包；"
                      "或 --skip-demo-check 强制跳过（不建议）。")
                sys.exit(1)
            print(f"✓ 作者源/运行态/随包 demo 三方一致（剧本「{drama}」）。")
        except SystemExit:
            print("⚠ 无法自动判定当前剧本（dramas/ 为空或多个），跳过一致性检查。")
        except Exception as e:
            print(f"⚠ 一致性检查异常：{e}，继续打包（不建议）。")

    out, n, bad = build(args.out)
    print(f"已生成 {out}（{n} 条目，{os.path.getsize(out)/1024:.1f} KB）")
    if bad:
        print("⚠ 不应出现于分发包的文件：", bad)
    else:
        print("排除项校验通过（无 venv/缓存/会话状态/tests 泄漏）。")
