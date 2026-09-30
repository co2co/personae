# ST-Lite 开发日志

记录架构决策、待办与搁置项。非任务日志，按主题追加。

## 2026-09-30 秘密机制重构

### 已落地：秘密的归属 / 曝光路径 / 影响
- 快照 `secrets` 每条含：`owner`（归属角色）、`known_by`（知情实体集合，含「环境推手」与具体在场角色）、`exposures`（曝光路径日志 `[{by, via, round}]`）、`state`（潜伏 / 暴露，按 known_by 是否含在场角色重算）。
- 曝光路径两条：A1 环境推手主动查（关键词 + 信息获取动词）→ 记「环境推手」已知，不翻 in-world 状态；reflect 叙事揭露 → 由 LLM 输出 `secret_exposures[{owner, by}]`，把具体知情角色写入 known_by 并记路径。
- 影响：prompter 对 owner 注入「你的秘密已被 X 知晓」，对知情非 owner 角色注入「你已知 X 的秘密」，使秘密真实驱动后续推演（铁律②信息边界：只注入给确实知情者）。
- 「玩家」机制已于本轮彻底移除：affect.py / state.py 移入 `_bak_20260930/`，单角色路由 `/api/generate` `/api/message` `/api/state` `/api/persona` `/api/nsfw/confirm` `/api/state/reset` 删除；成年确认迁为系统设置 `adult_confirmed`（llm 配置），顶栏「确认已成年 / 重置」按钮移除，迁入系统设置面板。旧会话快照 loaded 时把 known_by 里的「玩家」归一为「环境推手」。

### 待办 / 搁置项

#### 世界级秘密（暂不实现，未来可能需要）
- 现状：世界书秘密条目必须绑定 `character` 才进快照（memory.py 种子 `e.get("secret") and e.get("character")` 门槛）。无 owner 的世界级秘密（如「这个小镇有个禁忌」）当前不进快照、不进爆发逻辑，只有编辑器预览能看到命中。
- 触发条件：当确实出现「不属于任何角色、却影响整个世界运转」的秘密需求时再实现。
- 实现方向：放开上述 `character` 门槛，允许 `character` 为空的秘密进快照（owner 记为空或「世界」），并为世界级秘密补曝光路径与呈现逻辑。

#### 全曝光状态（暂无方案，搁置）
- 现状：`state` 保留「全曝光」作为状态值（director._FULL 常量），但无任何代码会写入它——既无「暴露 → 全曝光」的升级规则，也无对应呈现。
- 搁置原因：尚未想清「全曝光」的语义与触发条件（是「所有在场角色皆知」还是「秘密内容被写进世界设定」？是否应泄漏给未在场角色？）。
- 待定：明确升级规则后再补，目前保持「潜伏 / 暴露」两态即可覆盖推演需求。

## 2026-09-30 版本控制

- 引入 git 版本控制，初始提交即 `v0.1`（git tag: `v0.1`，见 `VERSION` 文件）。
- 纳入跟踪：后端源码、前端 `static/index.html`、配置与脚本、`data`（角色 / 世界书 / config 等创作内容）、`player-cast/`、`DEVLOG.md`。
- 不纳入跟踪（见 `.gitignore`）：`venv/`、`__pycache__/`、临时工作副本（`*.bak-*`、`_bak_*/`）、打包备份（`*.zip`、`backups/`）、运行时会话状态（`data/sessions/`、`data/state.json`）。
- 临时工作副本（根目录与 `static/` 下 `*.bak-*`、`__pycache__/`）已清理；历史打包 `my-st-2026-09-29.zip` / `my-st-2026-09-30.zip` 与 `_bak_20260930/`（被移除的玩家机制文件）归档至 `backups/`。
- 当前版本打包备份：`my-st-v0.1.zip`。

## 2026-09-30 维护性清理（注释统一 + 死代码移除）

- app.py 顶部 docstring 改为准确描述现状：仅「创作管理接口 + 多角色沙盘接口」两类，旧单角色生成接口（/api/generate、/api/message、/api/state、/api/persona、/api/nsfw/confirm、/api/state/reset）已于 2026-09-30 移除，并注明「玩家」机制下线、成年确认迁为系统设置 `adult_confirmed`。NSFW 段「回写好感度」改为「回写快照（关系 / 目标 / 秘密揭露）」。
- app.py 区块注释「单角色（旧接口，保留）」改为「创作管理：角色卡 / 世界书 / 聊天 / 配置」——原下方为 /api/characters 等管理接口，并非旧单角色生成接口。
- memory.py 删除死代码 `bump_affection`（无任何调用方，旧单角色好感度机制已下线）。`py_compile` 校验通过。

## 2026-09-30 世界书机制复刻（constant / depth / position 三件套）

- 复刻酒馆 Lorebook 最核心三件套（递归扫描 recursive 留二期）：
  - `constant`：常量条目，不依赖关键词，每轮必注入，解决长文基础规则掉线。
  - `depth`：条目级扫描深度，只回看最近 N 条聊天匹配（默认取全局 `RECENT_FOR_SCAN=4`）。
  - `position`：插入位置 `before`（系统层/历史前，默认）与 `after`（对话历史之后、导演指令之前，独立 system 消息）。
- 改动：world.py 重写 `scan`（签名 `scan(entries, history, directive, default_depth, character, max_entries)`，history 改列表以支持条目级 depth）；app.py 的 `/api/act` 按 position 分组 `before_hits`/`after_hits` 并下传，test 路由改收 `history` 列表（兼容旧单串 text）；prompter.build_session 新增 `after_hits` 参数，after 段以独立 system 消息置于历史之后；前端 entryCard 增加 constant 复选框 / position 下拉 / depth 数字输入，collectWorldEntries 收集，test 预览改传 `history:[text]`。
- 向后兼容：老条目不写新字段则全部回退默认，行为不变；秘密条目（secret）仍由 app 层从命中剔除、不走世界设定段（前端 secret 勾选时隐藏常量/位置字段）。
- 验证：`py_compile` 通过；world.scan 单测（constant 必中 / depth 截断 / position 标记 / 向后兼容 / 禁用跳过 / directive 匹配）全过；端到端（test 路由 history+constant、prompter after 位置 system→user→system→user）全过。

## 2026-09-30 新建测试剧本「末日丧尸生存」

目的：替换旧家庭剧（home 世界 + 周家 5 卡），用单一封闭场景全面压测迭代后的引擎（尤其世界书三件套 + 秘密机制 + NSFW）。

### 清理
- 删除旧角色 5 张（周晓杰 / 周牧野 / 林梦雅 / 林泽宇 / 王三）、旧世界书 `home.json`、全部旧会话 `data/sessions/*`。

### 新内容
- 角色 5 张（均 `world: "末日"`，`nsfw.mode: on`）：老周（退伍/保安队长·主心骨）、林晚（急诊护士·偷偷怀孕）、阿杰（小混混·私藏物资）、苏曼（调查记者·寻女）、高洋（IT宅·隐瞒咬伤）。每人核心渴望 / 核心恐惧 / 性格 / 语言习惯各异，且全困于同一便利店后仓（逼仄空间制造张力）。
- 世界书 `末日.json` 13 条，刻意覆盖各机制作为测试样本：
  - constant×2（病毒法则 / 处境总则，每轮必注）
  - position=after×2（后仓布局 / 当下威胁，置历史之后）
  - position=before×2（末日时间线 / 尸群习性）
  - depth=10×1（城东庇护所传闻，远距命中对照）、depth=6×1（高洋监控习惯）
  - secret×5（5 角色各一条潜伏秘密：高洋咬伤 / 阿杰私藏 / 苏曼女儿 / 林晚怀孕 / 老周伪装，均带 `character` 与 `bottom_line`）
- 注意：世界书 `character` 字段在沙盘 act 路径不参与 scan 过滤（act 始终传 `character=None`），仅用于 secret 归属（memory.new 种子）；故非 secret 的 character 标签当前无运行期效果。

### 验证
- 临时脚本确认：5 卡 JSON 合法且 world 绑定正确；world.scan 空历史命中 2（constant 必中）、before/after 分组正确、depth=10 从远处命中而默认 depth 丢失、5 条 secret 种子归属 5 角色；脚本已清理。
- 系统级 NSFW 已开：`config.json` 第 11 行 `"adult_confirmed": true`（引擎读 `llm.setting("adult_confirmed")`）。无需改配置即可测试 NSFW。

## 2026-09-30 末日剧本端到端测试（真实 LLM: tencent/Hy4-preview）

驱动脚本 `drive_apoc_test.py`（位于 Claw 工作区，非仓库内）自动建会话并注入 8 轮扰动指令，结论：

### 通过
- 世界书三件套（确定性 scan 验证，不经 LLM）：constant×2 空历史必中；`after` 位置"当下威胁"在含"门外/尸群"时正确进 after 段、与 before 段分离；depth=10 条目在"城东/女儿"位于第 0 条、最近 4 条无关时仍命中（默认 depth=4 会丢失）。
- 秘密机制：快照 `secrets` 正确翻"暴露"并填充 `known_by`；暴露后通过 `_opp_from_secrets` 直接把机会等级顶到"满机会"。
- NSFW：adult_confirmed=true → unlocked 恒 True；intimate 随机会等级缩放；"满机会"回合模型确实写出越线/胁迫内容。
- 场景切换：含"夜深"触发时间推移，LLM 解析把在场缩为「老周+苏曼」，present 正确更新。
- 角色声线：五人语言习惯区分明显（老周命令式、阿杰痞、苏曼尖锐、林晚柔、高洋结巴），多说话人叙事连贯。

### 观察（待定，非必改）
- 秘密曝光偏早/偏激进：R1（仅分配守夜）后 高洋、阿杰 已被标"暴露"，疑似 `director.reflect` 的 `secret_exposures` 解析过松（或模型据角色卡 short_goal 自行发挥）。其副作用是 `_opp_from_secrets` 从 R2 起恒定"满机会"，掩盖了本应"半步"的轮次（如 R6 独处软弱本应半步）。
- 因 present 与模型发挥偶有出入（R7/R8 写了已离场角色），属模型对在场名单的忽略，非引擎缺陷。
- 建议（如需）：收紧 reflect 的 secret_exposures 判定——要求回复中同时出现「秘密内容」与「明确的信息获取/发现动作」才记曝光；或提高暴露所需的置信度。

## 2026-09-30 收紧 reflect 秘密曝光判定

针对上轮"秘密曝光偏激进"的观察，按约定落地：**LLM 报出的 `secret_exposures` 只有在本轮回复确实写出「秘密事实内容」+「明确的信息获取/发现动作」时才采信，否则视为误判丢弃。**

### 改动（director.py）
- 新增常量 `DISCOVERY_VERBS`：覆盖「观察者视觉/动作发现」与「持有者主动/无意泄露」两类路径（看见/发现/拆开/露出/识破/坦白/招了/说漏…）。
- 新增函数 `_reply_confirms_exposure(reply, secret, names)`：① 秘密内容信号 = 剔除人名后、长度>=2 的事实性触发词（secret.keys）出现在回复；② 明确的信息获取/发现动作 = 回复含任一 DISCOVERY_VERBS。两者皆满足才返回 True。
- `reflect` 的曝光循环：仅在 `_reply_confirms_exposure` 为 True 时调用 `_record_exposure`，否则跳过（视为 LLM 误判，不写快照、不翻状态）。

### 验证（真实 LLM 复跑 + 单轮诊断）
- 原投诉点 R1（仅分配守夜）复跑后全角色保持「潜伏」——修复生效。
- 单轮诊断（同指令、新会话）：回复既无"咬伤/感染"也无发现动词 → 高洋保持潜伏，证明校验在生效、非代码漏。
- 确认：模型若在回复里真写出发现情节（事实词+发现动词，如 R5 林晚拆绷带发现咬伤），按规则正确采信曝光；此前整轮跑里 R2 的曝光属模型随机性自插情节，非引擎缺陷。
- 配套：服务非 debug 模式，改 director.py 后需重启（已重启，新代码生效）。

## 2026-09-30 新增会话（剧本）管理接口

用户需要"放弃当前剧本"的入口。此前运行侧只有 new/snapshot/act，无列举/删除/切换；前端 SID 存于 JS 变量，无会话面板。

### 改动
- memory.py：新增 `list_sessions()`（列举全部会话，返回精简摘要：session/present/scene/round/intimacy_phase/updated，按更新时间倒序）与 `delete_session(sid)`（rmtree 整局目录，不存在返回 False）。顶部补 `import shutil`。
- app.py：新增 `GET /api/sessions`（列举）、`DELETE /api/session/<sid>`（删除，不存在 404）。
- 说明：本引擎无独立"剧本"实体，玩家所指"剧本"= 一个 session（cast+场景+世界书+演化状态）。删除 session 仅清运行时状态（data/sessions/<id>），角色卡与世界书等创作内容保留。切换/继续现有局直接用其 sid 调 `/api/act`（已支持任意 sid），无需新接口。

### 验证
- 重启服务后 `GET /api/sessions` 正确列出残留测试局；`DELETE` 后列表实时减少、返回 `{"deleted": sid}`；删不存在会话返回 404。三态全过。

## 2026-09-30 前端会话管理面板

配套上一项后端接口，给玩家在 UI 里管理"剧本"（会话）。

### 改动（static/index.html）
- 顶栏新增「会话」按钮（open-sessions），打开 modal 列出所有进行中的剧本。
- 新增 `#session-modal`：展示每局 会话 id / 回合 / 亲密阶段 / 更新时间 / 在场角色 / 场景，提供「继续」「放弃」两按钮。
- 逻辑：loadSessions / renderSessions / resumeSession / delSession。继续 = 拉快照 + 聊天历史（`GET /api/session/<sid>/chat`）渲染进对话区，恢复上下文；放弃 = 二次确认后 `DELETE`，若放弃的恰是当前局则退回开场。
- 后端补 `GET /api/session/<sid>/chat` 返回该局聊天历史（不存在 404），支撑"继续"时还原旧对话。

### 验证
- 后端：新建测试局→推进一轮→`/api/session/<sid>/chat` 正确返回 2 条（导演指令+角色回复）；列举/删除/404 三态早前已验。
- 前端：抽取内联脚本 `node --check` 语法通过；index.html 含 session-modal / open-sessions / resumeSession / delSession 等标记（grep 命中 9 处）。
- 测试局已清理，data/sessions 当前为空。

## 2026-09-30 优化角色库人设字段（清理更多字段中沙盘不适用的项）

用户要求：删除角色库「更多字段」下不注入推演、沙盘不适用的字段，避免困惑。

### 判定依据（prompter.build_session + app.py + memory.py 实际注入路径）
- 注入/适用（保留）：`world`（加载世界书）、`personality`（注入人设块）、`short_goal`（意图种子）、`relations`（关系网种子）
- 不注入且沙盘不适用（删除）：`system_prompt`（当前 build_session 根本不读取，旧标签"保存时自动补全"误导）、`scenario`（标注"沙盘当前不注入推演"）、`mes_example`（"单角色模式用，沙盘不使用"）、`first_mes`（"沙盘不使用"）

### 改动（static/index.html）
- 「更多字段」区删除 4 个字段 UI（system_prompt/scenario/mes_example/first_mes），更新 summary 文案为"可选；留空由系统自动生成"，并为保留字段补注入说明。
- 表单上方说明去掉"或不参与沙盘推演"字样（保留项均已参与）。
- `loadChar` 回填：移除 4 个废弃字段赋值。
- `char-new` 重置列表、保存 payload：移除 4 个废弃字段。
- 校验：grep 无残留引用；抽取内联脚本 `node --check` 语法通过。

### 数据清理
- 5 张角色卡（老周/林晚/阿杰/苏曼/高洋）删除上述 4 字段 + `post_history`（空字符串模板残留，不在任何表单/注入路径，顺手清除以统一数据模型），保留字段均不变。
- 仅需刷新浏览器即可生效（前端为静态文件，后端未改，服务无需重启）。

## 2026-10-01 世界书用户使用说明书

用户反映世界书上手有难度，要求在项目目录建一份带例子的使用说明。

### 产出
- 新建 `世界书使用说明.md`（项目根目录），覆盖：世界书概念 / 编辑器入口与基本操作 / 字段逐个讲解（keys、content、启用、优先级拖拽、常量 constant、位置 position、深度 depth、秘密 secret+character+bottom_line）/ 命中预览工具 / 与角色卡 world 字段关系 / 一份可直接照抄的完整示例世界书（5 条，覆盖全部机制）/ 常见坑与最佳实践 / 机制速查表。
- 文档严格对照当前实现：max_entries=8 硬上限、priority=100-idx*5、default_depth=4、constant 无视 keys/depth、position before/after 注入位置、secret 不进 prompt 而 seed 进快照（需填 character）、沙盘 act 传 character=None 故非秘密条目的 character 不参与过滤。
- 校验：文档内示例 JSON 用 json.loads 解析通过（5 条合法）。

## 2026-10-01 世界书说明书增强（走查章节 + 系统内链）

simon 批准两项：① 说明书补「从零建一个世界书」分步走查章节；② 系统设置面板加内链入口。

### 改动
- `世界书使用说明.md`：新增第八节「从零建一个世界书（末日剧本完整走查）」，以 apoc 末日剧本为例，从打开编辑器→常量打底→触发设定→秘密埋雷→排顺序→预览验证→保存→角色卡 world 指向→开局推演，8 步串成完整流程（含面板结构示意与走查小结流程图）。原"常见坑"顺延为九、"速查表"顺延为十；全文 一~十 编号连贯。
- `app.py`：新增 `GET /docs/worldbook`，用 `send_from_directory(ROOT, "世界书使用说明.md", mimetype="text/markdown; charset=utf-8")` 返回说明书源文件。
- `static/index.html`：系统设置（#sys-modal）新增「帮助文档」小节 + 链接 `<a href="/docs/worldbook" target="_blank">打开世界书使用说明（新窗口）</a>`。
- 验证：重启服务（task ZfGnJR）后 `/docs/worldbook` 返回 HTTP 200 且 body 为完整 Markdown；index 200。

## 2026-10-01 版本控制 v0.2（打包备份）

### 相较 v0.1 的增量（本次打包覆盖）
- 世界书机制复刻：constant / depth / position 三件套（world.py / app.py / prompter.py / 前端编辑器）。
- 收紧 reflect 秘密曝光判定（director.py：回复须同时含秘密事实+发现动作才记曝光）。
- 会话（剧本）管理：后端 list/delete/chat 接口 + 前端会话面板（顶栏「会话」按钮，继续/放弃）。
- 角色库人设字段清理：移除沙盘不适用的 system_prompt/scenario/mes_example/first_mes（+ 数据层 post_history）。
- 新建测试剧本「末日丧尸生存」：5 角色卡 + 13 条世界书（覆盖全部机制），替换旧家庭剧。
- 世界书用户使用说明书（世界书使用说明.md）：字段讲解 + 示例 + 走查章节；系统设置面板加内链入口（`GET /docs/worldbook`）。
- 维护性：app.py / memory.py 注释统一 + 死代码（bump_affection）移除。

### 打包与提交
- `VERSION` 升 `v0.2`；git 提交全量改动并打 tag `v0.2`。
- 打包备份：`my-st-v0.2.zip`，按 `.gitignore` 排除 `venv/`、`__pycache__/*`、`*.zip`、`backups/`、`data/sessions/`、`data/state.json`（仅源码 + 前端 + 配置 + 创作内容 data 角色/世界书/config）。

## 2026-10-01 迭代三方向：recursive 世界书 / present 校验 / 文档渲染+导入兼容

simon 拍板下一轮做 ① recursive 世界书 ② present 名单校验/后处理 ④ 文档渲染+角色卡导入兼容（跳过 ③ 自动化测试套件、⑤ 世界级秘密、⑥ 多模型切换）。

### ① recursive 世界书（#name# 引用拉入依赖条目）
- world.py：`scan` 新增 recursive 展开——条目 content 内 `#条目名#` 会把同名条目（需带 `name` 字段）自动拉入；BFS + visited（对象 id）防环，避免互相引用死循环。条目新增可选 `name` 字段；docstring 同步更新。
- 前端 `static/index.html`：entryCard 新增「条目名 name」输入框，collectWorldEntries 收集 `name`（无则 null）。
- 世界书使用说明.md：新增「§9 递归引用 name + #name#」，含例子与适用场景。
- 验证：单测通过（递归拉入 / 互相引用防环 / 无 name 老条目向后兼容）。

### ② present 名单校验/后处理（修 R7/R8 模型写出已离场角色）
- director.py：新增 `validate_present(reply, present, known_names)`，把非在场角色（含已离场者、环境推手）的"角色名："台词块（含续行）剥离，返回 (清洗文本, 是否违例)。names 按长度降序匹配避免短名前缀误命中。
- prompter.py：`build_session` 输出格式块新增「本轮在场角色：…」明确名单 + 硬禁令（只能写在场角色，严禁写未在场/环境推手）。
- app.py：`/api/act` 的 events() 改为先缓冲全文 → validate_present 清洗 → 按行流式回传校验后文本 → 存储/reflect → done 载荷新增 `present_violation` 字段（可观测）。
- 验证：单测通过（正常无违例 / 剥离非在场 / 续行整块移除 / 离场块前叙述行保留）；live act 集成确认 done 含 present_violation、reply 仅含在场角色。
- 注意：清洗为"整块移除"，若模型在离场角色块后紧接无归属叙述行，该叙述行也可能被一并移除（罕见，因 prompt 已硬禁未在场角色）；属已知小局限。

### ④ /docs/worldbook 渲染成网页 + 角色卡导入兼容性
- app.py：`/docs/worldbook` 改为返回渲染后的 HTML 页面（marked.js CDN 渲染 Markdown，带暗色样式；CDN 不可用时回退纯文本）。Markdown 经 `json.dumps` + `</` 转义安全嵌入脚本。系统设置面板内链不变。
- 角色卡导入兼容：前端 `loadChar` 拆出 `fillChar` 并 stash 原始卡 `_charOrig`；`char-save` payload 合并 `_charOrig` 中未识别字段（avatar/alternate_greetings/extensions/tags 等），避免从酒馆社区搬运时丢元数据；`char-new` 重置 `_charOrig`。新增「导入 JSON」按钮 + 隐藏 file input，读取本地 JSON 直接载入编辑器（未识别字段随保存保留）。
- 验证：docs 路由返回 text/html 且含 marked.min.js / id=content（不再回裸 md）；角色卡 API 往返确认 avatar/extensions/alternate_greetings/tags 均被原样保留。

## 2026-10-01 版本控制 v0.3（打包备份）

### 相较 v0.2 的增量（本次打包覆盖）
- recursive 世界书：`#条目名#` 引用拉入依赖条目（world.py / 前端 name 字段 / 说明书 §9）。
- present 名单校验/后处理：director.validate_present 剥离非在场角色台词；prompter 列出在场名单+硬禁；app.act 缓冲→清洗→按行流式→done 含 present_violation（修 R7/R8 模型写已离场角色）。
- /docs/worldbook 渲染成 marked.js HTML 页；角色卡导入兼容（char-save 保留未识别字段 + 「导入 JSON」按钮）。

### 打包与提交
- `VERSION` 升 `v0.3`；git 提交全量改动并打 tag `v0.3`。
- 打包备份：`my-st-v0.3.zip`，按 `.gitignore` 排除 `venv/`、`__pycache__/*`、`*.zip`、`backups/`、`data/sessions/`、`data/state.json`（仅源码 + 前端 + 配置 + 创作内容 data 角色/世界书/config + 说明书）。

## 2026-10-01 自动化测试套件（tests/）

simon 要求把临时驱动脚本固化为正式测试套件，并新增需求：走查过程以 markdown 存到项目专属测试文件夹，记录每次"你"发过去的环境扰动与引擎生成内容，直到剧本 ending。

### 结构（tests/）
- `pytest.ini`：`testpaths=tests`；`addopts=-m "not integration"`（默认只跑快测）；`integration`/`slow` 标记。
- `conftest.py`：把项目根加入 sys.path，使 test 能直接 import 引擎模块。
- `test_world_scan.py`：world.scan 确定性单测（constant 必中 / depth 远距命中 vs 默认丢失 / position 属性 / recursive 拉入+防环+禁用目标不拉 / 向后兼容 / 禁用跳过 / character 过滤）。不调 LLM。
- `test_director.py`：validate_present 四场景（无违例 / 剥离非在场+环境推手 / 续行整块移除 / 离场块前叙述保留）+ _reply_confirms_exposure 双信号门槛（事实+动作齐备才采信，人名从事实词剔除）。不调 LLM。
- `playthrough.py`：走查驱动库。复用引擎 HTTP API，按脚本化"环境扰动弧"（DEFAULT_ARC，末日剧本 8 步、末步 ending=True）建会话、逐轮 /api/act、解析 SSE 取 reply 与 done 载荷；`run_playthrough` 把每轮"环境扰动 + 引擎生成"写入 `tests/runs/<时间戳>_<剧本>.md`，直到 ending；默认跑完删会话（keep_session 可保留）。
- `run_playthrough.py`：独立运行入口（python tests/run_playthrough.py [--keep]）。
- `test_playthrough.py`：集成走查测试（标记 integration，服务不可达自动 skip）。
- `README.md`：套件说明与运行方式。
- `.gitignore`：新增 `tests/runs/`（生成的 markdown 日志非源码）。

### 验证
- 默认 `pytest`：15 passed, 1 deselected（integration 跳过）。
- `pytest -m integration`：1 passed（2m30s，8 轮真实 LLM 走查）；产物 `tests/runs/20261001_012147_末日丧尸生存.md`（5192 字节，含"环境扰动（导演 / 你）"+"引擎生成"每轮 + "## 结局"，结构正确）。
- venv 新增 dev 依赖 pytest 9.1.1（未在 requirements.txt 列，仅测试用）。

## 2026-10-01 项目结构重构：引擎本体 + 测试单元 双目录（A+B）

simon 提议：把引擎本体与测试单元分成两个并列目录，以 A+B 形式存于项目根；并在项目根、引擎、测试三处各放一份 README.md。

### 新结构
```
my-st/
├── engine/        A. 引擎本体（分发只需这一份）
│   ├── app.py / director.py / world.py / prompter.py / memory.py / store.py
│   ├── nsfw.py / llm.py / scene.py / hooks.py
│   ├── data/（角色卡/世界书/config）  static/index.html
│   ├── run.bat / install.bat / requirements.txt / VERSION
│   ├── DEVLOG.md / 世界书使用说明.md / README.md
├── tests/         B. 测试单元（开发用，不分发）
│   ├── conftest.py（把 ../engine 加入 sys.path）/ pytest.ini / README.md
│   ├── test_world_scan.py / test_director.py（确定性单测）
│   ├── playthrough.py / test_playthrough.py / run_playthrough.py
│   └── runs/（走查 markdown 日志，gitignore）
├── README.md      总说明（A+B 结构 + 运行/测试 + 分发说明）
└── *.zip / backups/（历史备份，gitignore）
```

### 改动要点
- 全部引擎文件/目录（含 static/data/player-cast）`git mv` 进 `engine/`（保留 git 历史）。
- `app.py` 用 `__file__`.parent 定位，移入子目录后 static/data 仍相对正确，无需改业务代码。
- `tests/conftest.py`：sys.path 从项目根改为 `../engine`（测试 import world/director 仍可用）。
- `run.bat` / `install.bat`：`cd` 目标由 `%ROOT%` 改为 `%ROOT%\engine`（venv 用绝对路径不受影响）。
- `.gitignore`：运行时路径加 `engine/` 前缀（`engine/data/sessions/`、`engine/data/state.json`），新增 `.pytest_cache/`；`tests/runs/`、`*.zip`、`backups/`、`venv/`、`__pycache__/` 维持。
- 三份 README：根 README（A+B 总览/快速开始/分发说明）、engine/README（引擎模块与机制）、tests/README（测试结构与运行）。

### 验证
- `engine/*.py` 全部 `py_compile` 通过；从 `engine/` 重启服务（task PhxoiZ）后 `/`、`/api/characters`、`/docs/worldbook` 均 200，5 角色正常加载。
- 默认 `pytest`：15 passed / 1 deselected（integration 跳过），conftest 正确指向 engine。
- git status：引擎文件均记为 R（重命名，历史保留）；`engine/data/state.json`、`tests/runs/`、`.pytest_cache/` 正确被忽略。

## 2026-10-01 版本控制 v0.4（A+B 结构 + 纯引擎分发）

### 结构变化
- 项目重构为 `engine/`（A，引擎本体）+ `tests/`（B，测试单元）双目录；根/引擎/测试三处各一份 README.md。
- 新增 `package.py`：固化"纯引擎分发"打包逻辑——只打 `engine/`，排除 `venv/`、`__pycache__/`、`engine/data/sessions/`、`engine/data/state.json`（不含 tests，不含运行时会话状态）。归档根为 `engine/`，与 README 运行说明一致。

### 相较 v0.3 的增量
- 项目结构 A+B 拆分与三份 README。
- 自动化测试套件（tests/）：确定性单测（world.scan / director）+ 走查模块（playthrough.py 落盘 markdown）+ 集成测试。
- 注：v0.4 的"增量"主要在前两轮（v0.3 已含 recursive 世界书 / present 校验 / 文档渲染 + 导入兼容）基础上的结构整理与测试固化。

### 打包与提交
- `VERSION` 升 `v0.4`；git 提交全量改动（含 A+B 结构、tests/、三份 README、package.py）并打 tag `v0.4`。
- 打包备份：`my-st-v0.4.zip`，由 `package.py` 生成，仅含 `engine/`（源码 + 前端 + 配置 + data 创作内容），排除 venv/__pycache__/会话状态/tests。

### v0.4 补丁：启动脚本改为位置无关（分发正确性修复）
- 原 `engine/run.bat`、`engine/install.bat` 把 `ROOT` 硬编码为 `D:\codes\my-st`、Python 路径硬编码为开发机绝对路径——分发到任何别的目录都会 `cd` 失败或指向错误位置，等于"解压即用"不成立。
- 修复：`run.bat` / `install.bat` 的 `ROOT` 改为 `%~dp0`（脚本自身所在目录），`VENV=%ROOT%venv`，`cd /d "%ROOT%"` 进入引擎目录；`install.bat` 的 Python 探测改为优先 `py -3`、其次 `python`（不再硬编码绝对路径）。
- 经"解压到空目录 → 起服务"端到端验证（见测试走查）：纯引擎 zip 解压到任意路径后，`run.bat` 能正确自定位并启动 Flask（5051 端口），首页/角色 API/世界书文档均 200。

### v0.4 补丁（续）：世界书说明书文件名改为 ASCII（分发健壮性）
- 端到端验证暴露：zip 内非 ASCII 文件名在被 legacy `unzip`（Git Bash / 类 Unix）解压时会按本地代码页解码成乱码；而 `app.py` 用字面量 `"世界书使用说明.md"` 读取该文档 → `FileNotFoundError` → `/docs/worldbook` 返回 500。
- 数据文件（`data/characters/*.json`、`data/worlds/*.json`）的**文件名即角色/世界名**（`store.list_characters` 用 `p.stem` 作名称、UI 也据此显示），不能改 ASCII，否则显示名变拼音；它们靠 `glob("*.json")` 加载，乱码仅影响显示名、不致命。
- 真正的代码硬引用只有这一处文档文件名，故将其重命名为 ASCII：`世界书使用说明.md` → `engine/worldbook-guide.md`，并同步改 `app.py` 读取、`README.md` / `engine/README.md` 目录树与引用。前端只链 `/docs/worldbook` 路由，不受影响。
- 效果：文档文件名变为 ASCII，任何解压工具都不会乱码，`/docs/worldbook` 对所有解压器鲁棒。数据文件的中文名在正常 Windows 解压（资源管理器 / 7-Zip）下保持原样，无误；仅用 legacy `unzip` 时显示名会乱码（不影响加载）。
- 注：此补丁不改引擎运行行为，`VERSION` 仍为 `v0.4`；如需重新打 tag 可升 `v0.4.1`。

## 2026-10-01 版本 v0.4.1（安装指南 + 分发补丁收口）

### 新增用户安装指南
- 新增 `engine/INSTALL.md`：面向**分发用户**的图文安装指南（系统要求 / 下载解压 / 依赖安装 / 启动 / 配置大模型 / 数据位置 / 常见问题 / 升级）。文件名用 ASCII，避免 legacy `unzip` 把中文名解成乱码（承接上一条教训）。
- 解压工具提醒写入指南：推荐 Windows 资源管理器「全部解压缩」或 7-Zip，勿用 Git Bash 的 `unzip`。
- 两份 README 目录树与引用同步加入 `INSTALL.md`；根 README 版本号更正为 v0.4.1。

### 版本收口
- `VERSION` 升 `v0.4.1`；重新打 tag `v0.4.1`，产出 `my-st-v0.4.1.zip`（`package.py` 按 `engine/VERSION` 自动命名）。
- v0.4 的两处分发补丁（run.bat/install.bat 位置无关、worldbook-guide.md 改 ASCII）随本次一并收口进 v0.4.1；引擎运行行为未变，纯分发健壮性 + 文档完善。

## 2026-10-01 补丁：修复 present 清空导致整段回复被剥空（测试误判通过的根因）

### 现象
- 集成走查（tests/runs/20261001_012147_末日丧尸生存.md）第 6/7/结局轮「引擎生成」全空，且 `present_violation=True`。测试却判 PASS——因为它只查 markdown 结构与 ending，没查每轮内容是否非空。
- 间歇性：重放时 LLM 偶尔正常（leave=[]），偶尔误填（leave=全员），故此前一度"看起来正常"。

### 根因
1. `scene.apply` 过度信任 LLM 的 `leave/arrive`：场景切换到"城东"时，LLM 偶发把"全员随世界转移"误填进 `leave`（把"离开旧地点"理解成每人离场），`leave` 覆盖全部在场者、`arrive` 为空 → `snap["present"]` 被清空。
2. `validate_present` 在 `present=[]` 时会把"任何角色都不在场"→ 全部台词块被剥离 → 整段回复变空，且误报违例。
3. 测试过松：只断言结构 + ending，放过了空回复。

### 修复
- `engine/scene.py`：新增安全网——`leave` 覆盖全部在场者且无 `arrive` 时，判定为"随世界一起移动"，忽略 `leave/arrive`；施加后名单若变空，回退为原名单。保证 `present` 永不为空。
- `engine/director.py`：`validate_present` 在 `present` 为空时原样返回、不报违例、不剥光（兜底，杜绝空白输出）。
- `tests/playthrough.py`：每轮记录 `present`；`tests/test_playthrough.py` 断言每轮「引擎生成」非空且 `present` 非空、且不出现 `[调用失败]`。
- 新增 `tests/test_scene.py` 确定性回归（monkeypatch LLM，模拟"leave=全员"危险响应，断言 present 不被清空；显式单人离场仍生效）；`tests/test_director.py` 补空 present 兜底测试。

### 验证
- 确定性单测 18/18 通过（含新增 3 项）。
- 重启引擎后跑 `pytest -m integration`（8 轮真实 LLM）：PASS，重生成的走查日志 8 轮均有内容（tests/runs/20261001_025830_末日丧尸生存.md）。
- 注：此为引擎行为修复，运行行为更健壮（不再因 LLM 误填清空白输出），但用户可见的剧情逻辑未变。VERSION 仍为 v0.4.1；若需干净 re-tag 可升 v0.4.2。

## 2026-10-01 版本 v0.4.2（present 清空回归收口）

- 将"present 清空导致整段回复被剥空"的引擎修复（scene.apply 安全网 + validate_present 兜底）与走查测试收紧（每轮内容非空 + present 非空断言 + 确定性回归）随本次收口进 v0.4.2。
- `VERSION` 升 `v0.4.2`；重新打 tag `v0.4.2`，产出 `my-st-v0.4.2.zip`（package.py 按 VERSION 自动命名，27 条目）。旧 `my-st-v0.4.1.zip` 删除，仅保留最新。
- 引擎运行行为不变；纯健壮性补丁（防 LLM 误填 leave 清空在场名单、防 present 为空时剥光回复）。

## 2026-10-01 测试套件补强：NSFW 支持度验证

- 发现：主走查（末日求生弧）机会等级虽到「满机会」，但扰动指令从不把角色推进到私密情境，引擎即便强令越线也无从落笔；且 `test_playthrough` 从未断言 NSFW，导致 NSFW 支持度完全未被验证（与"空输出被放过"同类盲区）。
- `tests/test_nsfw.py`（新增，确定性）：锁死 `nsfw.resolve_session` 门控——未确认成年强制受限、满机会=intimate 且提示词含「越线」、override off 压制、override on 不绕过年龄硬门禁。
- `tests/test_director.py` 补 3 项确定性回归：`_opp_from_secrets`（把柄胁迫→满机会）、`_opp_from_relations`（强/中信号）、`_opp_from_history`（近期身体接触仅升温、半步上限）。
- `tests/playthrough.py`：新增独立 `NSFW_ARC`（2 人私密脆弱情境，强驱动满机会）+ `NSFW_CAST`/`NSFW_SCENE`；每轮记录 `nsfw` 判定；markdown 增加 `NSFW=解锁/受限` 标记。
- `tests/test_playthrough.py`：新增 `test_nsfw_arc_produces_intimate_content`（integration）— 断言至少一轮 `intimate=True` 且生成内容含身体亲密接触标记（BODY_MID/BODY_STRONG），并复用以非空的回归护栏。
- 验证：确定性单测 28/28 通过（2 集成默认跳过）；`pytest -m integration -k nsfw` 真实 LLM 跑通，3 轮均 `NSFW=解锁（满机会）`，生成贴耳/压向/唇贴/搂紧/喘息等强亲密叙事（tests/runs/20261001_031540_NSFW验证.md）。
- 纯测试改动，`tests/` 不进分发 zip，故不升版本、不重打 zip。
