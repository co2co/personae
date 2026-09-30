import sys
from pathlib import Path

# 让 tests/ 下的测试能直接 import 引擎模块（world / director 等）。
# 引擎本体位于项目根的 engine/ 目录，加入 sys.path 即可。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))
