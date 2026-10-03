"""独立运行走查并落盘 markdown（无需 pytest）。

用法：
    python tests/run_playthrough.py
    python tests/run_playthrough.py --base http://127.0.0.1:5000 --keep
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import playthrough


def main():
    ap = argparse.ArgumentParser(description="跑一整轮 ST-Lite 走查并保存 markdown")
    ap.add_argument("--base", default=playthrough.BASE_DEFAULT, help="引擎基地址")
    ap.add_argument("--keep", action="store_true", help="跑完保留会话（可在 UI 继续）")
    args = ap.parse_args()

    path, rounds = playthrough.run_playthrough(
        base_url=args.base, keep_session=args.keep)
    print("走查完成，已保存：", path)
    print(f"共 {len(rounds)} 轮：")
    for i, r in enumerate(rounds, 1):
        tag = "【结局】" if r["ending"] else f"第{i}轮"
        print(f"  {tag} 违例={r['present_violation']} 字数={len(r['reply'])}")


if __name__ == "__main__":
    main()
