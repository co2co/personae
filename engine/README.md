# 群像弈（Personae） · 引擎本体 / Engine

本目录是**纯引擎本体**：只含运行所需的一切，以及面向使用者的说明文档。安装步骤见 [`INSTALL.md`](INSTALL.md)（中文）/ [`INSTALL.en.md`](INSTALL.en.md)（English）。

This directory is the **engine proper**: everything needed to run it, plus user-facing documentation. For setup see [`INSTALL.md`](INSTALL.md) (Chinese) or [`INSTALL.en.md`](INSTALL.en.md) (English).

## 这是什么 / What This Is

群像弈是一个 Flask + 大模型驱动的**多角色关系沙盘**：把一组角色卡与一本世界书交给模型，引擎负责关系网、秘密状态、分场与终局判定，使用者只以「导演」身份向场景注入扰动，不登场、不扮演角色。

开发用的测试、打包脚本、作者态剧本源都不在包内。

Personae is a Flask + large-language-model driven **multi-character relationship sandbox**: give the model a cast of character cards and a worldbook, and the engine owns the relationship network, secret states, location staging, and ending detection, while the user only injects perturbations into the scene as an off-stage "director".

Developer tests, packaging scripts, and author-side drama sources are not shipped in the package.

## 技术栈 / Stack

| | |
|---|---|
| 后端 / Backend | Python 3.10+（推荐 3.12）· Flask 3 |
| 模型 / Model | 任意 OpenAI 兼容接口 / any OpenAI-compatible endpoint |
| 前端 / Frontend | 单页 `static/index.html`，原生 JS，无构建 / vanilla JS, no build step |
| 数据 / Data | 本地 JSON / JSONL 文件，无数据库 / local files, no database |

## 目录 / Layout

```text
engine/
├── app.py              entry point: routes + SSE streaming
├── director.py         clerk ledger: secret state machine / roster checks / location + state bookkeeping
├── world.py            worldbook scan (constant / depth / position / recursive)
├── prompter.py         layered prompt assembly
├── memory.py           sessions / snapshots / secret seeds
├── store.py            local file I/O for cards, worldbook, chats
├── llm.py              model backend (base_url / model / sampling params)
├── scene.py            scene-change resolution (pure rules; only the director's directive moves the scene)
├── data/
│   ├── characters/     character cards (open JSON format)
│   ├── worlds/         worldbooks (entry arrays)
│   ├── examples/       bundled demo drama, seeded on first run
│   └── config.json     ships with empty connection settings
├── static/             single-page frontend + worldbook manual (/docs/worldbook)
├── run.bat  install.bat  requirements.txt
├── README.md  INSTALL.md  INSTALL.en.md
└── VERSION             version
```

你创作的角色卡、世界书、会话记录，以及 `data/config.json` 里的连接信息，永远不会被打进分发包。

Your cards, worldbooks, and session records — along with the connection settings in `data/config.json` — are never packaged.

## 运行 / Run

```bash
cd engine
install.bat                      # 首次：建 venv 并装依赖 / first run: create venv, install deps
run.bat                          # http://127.0.0.1:5051
python app.py                    # http://127.0.0.1:5000
export PORT=8080 && python app.py   # 换端口 / custom port（cmd 用 set PORT=8080）
```

`run.bat` 固定 5051，端口被占用时先释放再启动；直接跑 `app.py` 默认 5000，端口由 `PORT` 环境变量决定。

`run.bat` pins port 5051 and frees it if occupied; running `app.py` directly defaults to 5000, with the port taken from the `PORT` environment variable.

## 再往上读 / Further Reading

- 完整项目说明、机制设计与界面截图 / full project docs and screenshots: <https://github.com/co2co/personae>（首页英文，顶部语言栏可切中文 / English homepage, language switch at the top）
- 世界书用法 / worldbook manual：启动引擎后浏览器打开 `/docs/worldbook`（serve it, then open `/docs/worldbook`）
- 版本 / version：见 `VERSION`
