# 测试单元（tests/）

群像弈（Personae）【暂定】的**开发工作树**目录，与引擎本体（`../engine/`）并列存放于项目根。
**仅供开发使用，分发引擎时不包含本目录。**

> **开发与本体隔离（2026-10-08 起）**：`engine/` 是纯引擎本体，只保留运行所需的一切
> + 面向使用者的 `README.md` / `INSTALL.md`。所有开发类文档收归本目录，
> `engine/` 内不再存放任何开发内容。
> **规约：新写开发类文档（开发日志、待办、设计备忘）一律放本目录，不要放 `engine/`。**

## 结构

```
tests/
├── DEVLOG.md           开发日志：架构决策与版本演进记录（开发类文档主入口）
├── TODO.md             待办与搁置项
├── FACT-MEMO.md        内部设计备忘
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

## 发版纪律（2026-10-31 simon 定）

**旧版分发包一律保留，不删、不覆盖、不合并**，全部躺在 `dist/` 里按版本号排列。

- 用途：出错时从旧包回溯取数——对照历史行为、复现旧问题、找回被回退或删改过的内容。`dist/` 里的每个 zip 都是一份可解压的历史快照。
- 唯一例外：明确作废的版本（如回退作废、从未发版的包）移入 `dist/_retired/`，**仍然保留**，只是与现行序列分开放。
- 配套约束：`dist/` 在 `.gitignore`、不进版本库，所以包本身不承担备份职责。代码与文档的追溯靠 git 对象（提交哈希 / tag），见 `DEVLOG.md` 顶部 tag 记录。
- 历史条目里出现过的「删除旧包，仅保留最新」是 2026-10-31 之前的旧做法，已在 `DEVLOG.md` 顶部标注废止；历史记录保留原貌，不回改。
