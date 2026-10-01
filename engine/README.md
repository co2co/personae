# 引擎本体（engine/）

ST-Lite 的核心——一个 Flask 服务，用大模型驱动**多角色关系沙盘**的剧情推演。
基于 SilkyTavern 的开放角色卡 / 世界书思路精简而来，去掉了插件体系、多用户、
TTS/图生图等冗余，保留了最关键的：多角色沙盘、世界书、秘密机制、关系网演化、NSFW 尺度。

## 技术栈

- 后端：Python 3.12 + Flask 3
- 模型：OpenAI 兼容接口（默认对接 SiliconFlow `tencent/Hy4-preview`；亦可接本地 llama.cpp / Qwen 代理）
- 前端：单页 `static/index.html`（原生 JS，无构建步骤）
- 数据：本地 JSON / JSONL，无数据库

## 目录

```
engine/
├── app.py          服务入口：路由 + SSE 流式转发（创作管理 + 多角色沙盘两类接口）
├── director.py     导演简报：秘密状态机 / 机会等级 / present 名单校验
├── world.py        世界书 scan（constant / depth / position / recursive）
├── prompter.py     提示词分层组装
├── memory.py       会话 / 快照 / 秘密种子 / 行动状态
├── store.py        角色卡 / 世界书 / 聊天 的本地文件读写
├── nsfw.py         尺度 resolve（系统级 adult_confirmed + 本轮机会等级驱动）
├── llm.py          后端接入（base_url / model / 采样参数）
├── scene.py        场景自动切换（时间 / 天气 / 在场名单）
├── hooks.py        钩子（prompt_ready / message_received）
├── data/
│   ├── characters/ 角色卡（开放格式 JSON，含核心渴望/恐惧/关系种子等）
│   ├── worlds/     世界书（条目数组：keys/content/constant/position/depth/name/secret）
│   └── config.json 系统配置（出厂为空连接 + NSFW 关闭；角色卡/世界书/玩家设定目录不随分发包提供，首次运行后自行添加）
├── static/index.html  单页前端
├── run.bat         启动（默认端口 5051；先 install.bat）
├── install.bat     建 venv + pip 装 requirements.txt
├── requirements.txt  Flask / requests
├── INSTALL.md        安装指南（面向分发用户，先看这个）
├── VERSION         版本号
├── DEVLOG.md       开发日志（架构决策 + 版本记录，必读）
└── worldbook-guide.md  世界书用户手册（含例子与走查）
```

## 运行

**首次部署请先读 `INSTALL.md`（安装指南）。**

```bash
cd engine
python app.py          # 默认 http://127.0.0.1:5000
# 或双击 run.bat（端口 5051；首次需先运行 install.bat 创建 venv 并装依赖）
```

浏览器打开对应地址。顶部四个面板：

- **角色库**：新建 / 编辑 / 删除角色卡（或「导入 JSON」从酒馆社区搬运，未识别字段保留）
- **世界书**：编辑世界书条目（`/docs/worldbook` 有完整使用说明）
- **会话**：列出 / 继续 / 放弃进行中的剧本（会话）
- **系统设置**：模型 / NSFW / 成年确认，以及世界书说明书内链

## 核心机制速览

- **世界书**：关键词命中注入；`constant` 每轮必注；`depth` 条目级扫描深度；
  `position` 注入位置（before 系统层 / after 历史后）；`#name#` 递归拉入依赖条目。
- **秘密机制**：每个秘密绑定 `owner`（角色），初始「潜伏」；剧情真写出"发现动作 + 事实"
  才翻「暴露」，并驱动后续博弈。
- **关系网 / 目标**：由 director 在每轮 reflect 中从叙事回写（actions / goals / relations）。
- **NSFW 尺度**：系统级 `adult_confirmed` 解锁；每轮机会等级（试探/半步/满机会）由
  关系把柄 / 指令 / 历史综合决定，驱动 `prompter` 的尺度提示。
- **present 校验**：生成后剥离非在场角色（含已离场者、环境推手）的台词块，避免出戏。

详细的版本演进、架构决策与待办见 `DEVLOG.md`；世界书用法见 `worldbook-guide.md`。
