# 引擎本体（engine/）

群像弈（Personae）【暂定】的核心——一个 Flask 服务，用大模型驱动**多角色关系沙盘**的剧情推演。
基于开放的角色卡 / 世界书设计思路精简而来，去掉了插件体系、多用户、
TTS/图生图等冗余，保留了最关键的：多角色沙盘、世界书、秘密机制、关系网演化。

## 技术栈

- 后端：Python 3.12 + Flask 3
- 模型：OpenAI 兼容接口（默认对接本地推理服务如 llama.cpp / Qwen 系列；亦可接任意云端 OpenAI 兼容服务）
- 前端：单页 `static/index.html`（原生 JS，无构建步骤）
- 数据：本地 JSON / JSONL，无数据库

## 目录

```
engine/
├── app.py          服务入口：路由 + SSE 流式转发（创作管理 + 多角色沙盘两类接口）
├── director.py     导演简报：秘密状态机 / present 名单校验 / 关系与镜头推断
├── world.py        世界书 scan（constant / depth / position / recursive）
├── prompter.py     提示词分层组装
├── memory.py       会话 / 快照 / 秘密种子 / 行动状态
├── store.py        角色卡 / 世界书 / 聊天 的本地文件读写
├── llm.py          后端接入（base_url / model / 采样参数）
├── scene.py        场景自动切换（时间 / 天气 / 在场名单）
├── hooks.py        钩子（prompt_ready / message_received）
├── data/
│   ├── characters/ 角色卡（开放格式 JSON，含核心渴望/恐惧/关系种子等）
│   ├── worlds/     世界书（条目数组：keys/content/constant/position/depth/name/secret）
│   └── config.json 系统配置（出厂为空连接）；分发包不含示例剧本，首次运行需自行导入角色卡/世界书，玩家设定（player-cast）不随分发提供
├── static/index.html  单页前端
├── static/worldbook-guide.html  世界书用户手册（由 `/docs/worldbook` 提供）
├── run.bat         启动（默认端口 5051；先 install.bat）
├── install.bat     建 venv + pip 装 requirements.txt
├── requirements.txt  Flask / requests
├── INSTALL.md        安装指南（面向分发用户，先看这个）
└── VERSION         版本号
```

> 本目录是**纯引擎本体**：只含运行所需的一切，以及面向使用者的说明文档。
> 开发类文档（开发日志 `DEVLOG.md`、待办 `TODO.md`、内部备忘 `FACT-MEMO.md`）
> **已移出本目录**，存放于开发工作树 `tests/`，不随分发包提供
> （内含具体剧本的角色名与题材词，属引擎普适性红线）。

## 运行

**首次部署请先读 `INSTALL.md`（安装指南）。**

```bash
cd engine
python app.py          # 默认 http://127.0.0.1:5000
# 或双击 run.bat（端口 5051；首次需先运行 install.bat 创建 venv 并装依赖）
```

浏览器打开对应地址。顶部四个面板：

- **角色库**：新建 / 编辑 / 删除角色卡（或「导入 JSON」从外部导入，未识别字段保留）
- **世界书**：编辑世界书条目（`/docs/worldbook` 有完整使用说明）
- **会话**：列出 / 继续 / 放弃进行中的剧本（会话）
- **系统设置**：模型与生成（LLM 后端设置），以及世界书说明书内链

## 核心机制速览

- **世界书**：关键词命中注入；`constant` 每轮必注；`depth` 条目级扫描深度；
  `position` 注入位置（before 系统层 / after 历史后）；`#name#` 递归拉入依赖条目。
- **秘密机制**：每个秘密绑定 `owner`（角色），初始「潜伏」；剧情真写出"发现动作 + 事实"
  才翻「暴露」，并驱动后续博弈。
- **关系网 / 目标**：由 director 在每轮 reflect 中从叙事回写（actions / goals / relations）。
- **present 校验**：生成后剥离非在场角色（含已离场者、环境推手）的台词块，避免出戏。

世界书用法见浏览器 `/docs/worldbook`（由 `static/worldbook-guide.html` 提供）；版本演进与架构决策见开发工作树 `tests/DEVLOG.md`（不随分发提供）。
