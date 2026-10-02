# ST-Lite（my-st）· 项目总览

基于 SilkyTavern 思路精简而来的**多角色关系沙盘**引擎——Flask + 本地/云端大模型驱动的
剧情推演工具，自带世界书、秘密机制、关系网演化与 NSFW 尺度控制。

## 目录结构（A + B）

本项目采用「**引擎本体（A） + 测试单元（B）**」双目录并列存放：

```
my-st/                      ← 项目根
├── engine/                 ← A. 引擎本体（分发时用户只需这一份）
│   ├── app.py              后端入口（路由 + SSE 流式转发）
│   ├── director.py         导演简报 + 秘密曝光 + 机会等级 + present 校验
│   ├── world.py            世界书（constant / depth / position / recursive）
│   ├── prompter.py         提示词组装（分层注入）
│   ├── memory.py           会话 / 快照 / 秘密种子
│   ├── store.py            角色卡 / 世界书 / 聊天 本地 JSON 存储
│   ├── nsfw.py  llm.py  scene.py  hooks.py
│   ├── data/               创作内容（角色卡 / 世界书 / config）
│   ├── static/index.html   单页前端
│   ├── run.bat  install.bat  requirements.txt  VERSION
│   ├── INSTALL.md          安装指南（见 engine/INSTALL.md）
│   ├── DEVLOG.md           开发日志（架构决策 / 版本记录）
│   ├── worldbook-guide.md  世界书用户手册（原“世界书使用说明”）
│   └── README.md           引擎说明（见 engine/README.md）
├── tests/                  ← B. 测试单元（开发用，不分发）
│   ├── test_world_scan.py   world.scan 确定性单测
│   ├── test_director.py     director 确定性单测
│   ├── playthrough.py      走查驱动库（落盘 markdown）
│   ├── test_playthrough.py  集成走查（标记 integration）
│   ├── run_playthrough.py   独立走查入口
│   ├── conftest.py  pytest.ini  README.md
│   └── runs/               走查生成的 markdown 日志（gitignore）
└── README.md               ← 本文件
```

> 历史打包与备份留在根目录 `*.zip`、`backups/`（均 gitignore）。

## 快速开始

**跑引擎**（进入 `engine/`）：

```bash
cd engine
python app.py          # 默认 http://127.0.0.1:5000
# 或双击 engine/run.bat（默认端口 5051；首次需先 engine/install.bat 装依赖）
```

打开浏览器访问对应地址即可使用（角色库 / 世界书 / 会话 / 系统设置四个面板）。

**跑测试**（在项目根）：

```bash
pytest                              # 快测（确定性单测，不调 LLM）
pytest -m integration              # 完整走查 + 落盘 markdown（需引擎在运行 + 真实 LLM）
python tests/run_playthrough.py     # 不依赖 pytest，直接跑一局走查并保存 markdown
```

## 分发说明

用户只需 **`engine/`** 这一份即可独立运作；`tests/` 是开发期测试单元，分发时排除。
打包脚本应只包含 `engine/` 及其创作内容（`data/`、前端、`config`），排除 `venv/`、`__pycache__/`、
运行时会话状态（`engine/data/sessions/`、`engine/data/state.json`）与测试相关文件。

## 版本

当前版本见 `engine/VERSION`（v0.7.1）。各版本备份 zip 与提交记录见 `engine/DEVLOG.md`。
