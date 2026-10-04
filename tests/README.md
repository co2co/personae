# 测试单元（tests/）

群像弈（Personae）【暂定】的自动化测试目录，与引擎本体（`../engine/`）并列存放于项目根。
**仅供开发使用，分发引擎时不包含本目录。**

## 结构

```
tests/
├── conftest.py         把 ../engine 加入 sys.path，使测试能 import 引擎模块
├── pytest.ini          testpaths=tests；默认 -m "not integration"（只跑快测）
├── test_world_scan.py  world.scan 确定性单测（不调 LLM）
├── test_director.py    director 确定性单测（不调 LLM）
├── test_focus_follow.py 镜头跟随（焦点）机制测试：compute_focus 焦点识别 + prompter 注入 + 端点层裁剪（确定性，mock LLM）
├── test_ending.py       结局判定（软指引）测试：evaluate 三类分支 + dismissed 抑制 + /api/end 总结存档 + /api/ending/dismiss（确定性 + Flask 端点，mock LLM）
├── playthrough.py      走查驱动库：按"环境扰动弧"调引擎 API 逐轮推进，
│                       把每轮「你发的环境扰动」+「引擎生成」写入 runs/
├── test_playthrough.py 集成走查测试（标记 integration，服务不可达自动 skip）
├── run_playthrough.py  独立运行入口（python tests/run_playthrough.py）
└── runs/               走查生成的 markdown 日志（gitignore，非源码）
```

## 运行

> 前置：测试虚拟环境 `tests/venv` 已建好（双击 `tests/install.bat`）。
> 测试 venv 与引擎 venv（`engine/venv`）**完全独立**，改测试依赖不会污染引擎运行环境，反之亦然。

方式一：双击脚本（推荐，自动用 `tests/venv`）

- `tests/run_tests.bat` —— 快测（确定性单测，不调 LLM，秒级）
- `tests/run_tests.bat -m integration` —— 完整走查（需引擎在运行 + 真实 LLM）
- `tests/run_playthrough.bat` —— 不依赖 pytest，直接跑一局走查并落盘
- `tests/run_playthrough.bat --keep` —— 跑完保留会话（可在 UI 继续）

方式二：命令行（在 `tests/` 下用 `tests/venv` 的 python）

```bash
tests/venv/Scripts/python.exe -m pytest                  # 快测
tests/venv/Scripts/python.exe -m pytest -m integration   # 完整走查
tests/venv/Scripts/python.exe run_playthrough.py --keep  # 走查落盘
```

## 说明

- 确定性单测覆盖 `world.scan`（constant / depth / position / recursive 防环 / 向后兼容 /
  character 过滤）与 `director`（validate_present 四类场景、_reply_confirms_exposure
  双信号门槛）——这些不触碰大模型，跑得飞快、结果稳定。
- 集成走查（`test_playthrough.py` / `playthrough.py`）通过引擎 HTTP API 驱动一整轮剧情，
  把每轮**你（导演）发过去的环境扰动**与**引擎生成的内容**写入
  `runs/<时间戳>_<剧本>.md`，直到剧本 ending（弧末标记）。这是回归与"看实际推演效果"的入口。
- 走查弧剧本在 `playthrough.py` 的 `DEFAULT_ARC`（末日丧尸生存，8 步），可按需改写。

## 落盘格式

`runs/<时间戳>_<剧本>.md` 每轮包含：

- **环境扰动（导演 / 你）**：本次注入的扰动指令
- **引擎生成**：对应回合并发的叙事
- 结尾以 `## 结局` 标记剧本 ending，并附 present 违例 / 备注等观察信息。
