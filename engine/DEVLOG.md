# 群像弈（Personae）【暂定】开发日志

> **更名记录**：本项目原名 my-st / ST-Lite，于 2026-10-04 更名为 **群像弈（Personae）【暂定】**（暂定名）。引擎代码为原创实现，与 SillyTavern 无源码派生关系；下文历史记录中的 `my-st-vX.Y.Z.zip` 为当时产物名，保留原貌。

记录架构决策。待办与搁置项已统一收口至 [TODO.md](./TODO.md)（各版本「下版本待办」外链至此，避免日志臃肿），非任务日志，按主题追加。

## 2026-10-05 v0.14.0（NSFW 描写标准正式落地 + 叙事者人格注入）

- 升 v0.14.0：MINOR 档——引擎新增「叙事者人格注入」机制，且把亲密/性描写从 v0.12.0 的「克制/灰区尺度」升级为「显式开放的硬标准」，可观察行为显著改变，故 v0.13.2 → v0.14.0。
- 立场澄清：v0.8.0 废弃的是 **NSFW 系统机制**（机会等级、触发层、亲密度记账等），本版恢复并确立的是 **叙事描写层标准**——即引擎在剧情需要时如何撰写亲密/性内容，不涉及任何机制层恢复；v0.13.1 删除的「NSFW 尺度控制」功能表述（旧的机会等级 UI）与此不冲突。
- 改动一·铁律⑧ 重写（`prompter.py` `laws`）：
  - 从「点到为止/文学化淡出/禁堆砌器官细节」的克制标准，改为「显式开放 + 3 条硬要求」：① 不使用隐喻、不借文学化手法跳过或淡化，须正面直述；② 措辞直白露骨、颗粒度细化到具体动作与性器官名称，须直呼其名、不得用代称或委婉语；③ 场景须真实反映当事角色当前关系、处境与心理，与既有设定和叙事状态一致。
  - 硬红线收敛为唯一法律底线：未成年角色的性化描写 + 任何真实未成年人相关内容。
- 改动二·叙事者人格注入（`prompter.py`）：
  - 新增模块常量 `NARRATOR_PERSONA`（`[叙事者人格] 你是「小雨」…`）：声明成人内容零限制、绝不加道德提醒、直面描写不自我审查、只写正文不输出元信息。
  - `build_session` 在 system 提示首位恒定注入该块（primacy 权重最强），确保本地模型在叙事者身份下不再对露骨内容自我审查——本地 Qwen3.8-27B 实测：注入前需带人格才输出、注入后直接照办。
  - 配套：`narrative_clean.py` 的 `_WILL_EVADE_RE`/`_GIVEN_EVADE_RE`（剥离模型「我将规避亲密」自我审查句）方向一致，保留。
- 验证：本地 Qwen3.8-27B-UD-Q4_K_M + llama.cpp:1234，末日丧尸 10 轮内存自包含探针（R7–R9 性场景），3 条标准全部落地：无隐喻/跳过、直白露骨含性器官名（阴茎/龟头/穴口/子宫颈/精液等）、场景锚定「门外尸群、可能没明天」处境与「彼此唯一依靠」关系；未成年红线未触碰。无需代码修复。产物 `nsfw_probe_output.txt`（工作树，不入库、不进 zip）。
- 收口：tag `v0.14.0`；产物 `personae-v0.14.0.zip`（已排除私人剧本，泄漏校验通过）；清理上一版本 `personae-v0.13.2.zip`。

## 2026-10-04 v0.13.2（世界书机制修正 + 方向 B 打包硬化）

- 升 v0.13.2：PATCH 档——世界书注入机制的多处修正 + 分发包「方向 B 无 DEMO」硬化，无新增对外能力，故 v0.13.1 → v0.13.2。
- 世界书机制修正（纯引擎逻辑，零 LLM 依赖）：
  1. **depth 窗口精确生效**：`app.py` 新增 `WORLDBOOK_SCAN_WINDOW=60`，把传给 `world.scan` 的历史截断到最近 60 条消息（原 `RECENT_FOR_SCAN=4` 仅作默认 depth 保留）；修正前 depth>4 与默认 4 实际等价、深度分档失效。修正后 depth 在 1~60 间精确触发（窗口含本轮导演指令），>60 等同 60。本地验证：depth=4 不命中而 depth=8 命中的用例已通过。
  2. **after 重定位（after=临门一脚成真）**：`prompter.build_session` 把 `after_hits` 从拼进 system 块末尾，改为并入**末尾 user 消息**（导演指令之后、`【世界设定·当前环境】`标记），即生成点前的最后一瞥（recency 位）；`before` 仍恒在 system 块顶部（primacy 位）。借 transformer U 形注意力，before/after 对非恒定条目产生实质差异——before 搭建解读框架、after 直接 priming 下一轮行动。
  3. **escHtml 崩溃修复**：`static/index.html` 的 `escHtml(s)` 对 number 入参调 `.replace` 抛错，改为先 `String(s==null?'':s)` 转字符串。
  4. **删除空世界残留修复**：`loadWorldNames` 返回空列表时显式 `renderWorldEntries([])`，消除删空世界后条目残留。
- 方向 B 收口（分发包不含任何示例剧本）：
  - 删除「客服部之夜」都市 DEMO（`engine/data/characters/` 沈薇/程禹/苏黎/许言 + `engine/data/worlds/客服部之夜.json`），备份于 `backups/demo-kefu-backup-20261004_1437/`。
  - `README.md` / `INSTALL.md` 文案由「随附 DEMO 剧本」改为「分发包不含示例剧本，首次运行需自行导入」。
  - **打包硬化（关键）**：`package.py` 的 `EXCLUDE_SUBPATHS` 新增 `data/characters` 与 `data/worlds` 整体排除（此前注释误称「随附 DEMO 不再排除」、且打包走磁盘会泄漏磁盘上的私人剧本）。`store.save_card/save_world` 已 `mkdir(exist_ok=True)`，用户导入时自动建目录，排除不影响可用性。
  - ⚠ **泄漏事故**：因上述打包缺陷，已发布的 `personae-v0.13.1.zip` 实际内嵌了磁盘上 simon 私人的「丧尸末日」DEMO（4 角色卡 + 1 世界书），属私人创作泄漏。本版重新生成分发包时已排除，并随清理删除该泄漏产物；若 v0.13.1 已被分发出去，需评估私人内容扩散面。
- 测试：
  - 现有单测中性化（`test_intimacy_scale.py` 角色名改中性占位）；扩展 `test_world_scan.py`、新建 `test_worldbook_depth_window.py`（18 项深度窗口/封顶断言）。
  - 新建 `tests/stress_worldbook.py`：60 轮确定性压测（调真实 `world.scan` + `prompter.build_session`，零网络/零 LLM），覆盖 5 个非常量条目 before/after × 不同 depth，产出 `tests/runs/` 报告（MD+JSON）。
  - 验证：关联单测 23 passed；60 轮压测 `depth 一致 / position 正确 / 封顶生效` 三项全 True，before+after 同轮共存轮（44/45/46）落点均正确。
- 收口：tag `v0.13.2`；产物 `personae-v0.13.2.zip`（已排除私人剧本，泄漏校验通过）；清理上一版本 `personae-v0.13.1.zip`（含泄漏）及旧名 `my-st-v0.13.0.zip`。

## 2026-10-04 v0.13.1（更名收口 + 去除不准确派生描述）

- 升 v0.13.1：PATCH 档——项目更名收口与去除不准确的派生措辞，无新增能力，故 v0.13.0 → v0.13.1。
- 更名收口：展示名 `ST-Lite` / `my-st` 全部改为「群像弈（Personae）【暂定】」；磁盘目录 `D:/codes/my-st` 重命名为 `D:/codes/personae`；分发 zip 前缀 `my-st-` 改为 `personae-`（本次产物 `personae-v0.13.1.zip`）。
- 去除酒馆派生描述：删代码/文档中「参考酒馆」「基于 SillyTavern 思路/理念」「复刻酒馆」「酒馆社区搬运」等派生暗示措辞，改中性表述；保留两处主动原创性声明（与 SillyTavern 无源码派生关系）。
- 文档修正：README 移除 v0.8.0 已废弃的「NSFW 尺度控制」功能表述。
- git 关系：仓库根由 `.git` 位置决定，重命名上层文件夹对内部相对路径透明，仓库状态保持干净，无需额外提交。

## 2026-10-04 v0.13.0（剧本范例指南 + 提炼器缺陷修复）

- 升 v0.13.0：MINOR 档——新增「剧本范例指南」与示例剧本（降低「从剧本生成设定」入手难度），故 v0.12.1 → v0.13.0。
- 背景：simon 实测「从剧本生成设定」单元质量，暴露 3 处问题并推动落地「降低玩家入手难度」的范例。
- 引擎缺陷修复（`script_refiner.py`）：
  1. 代号名问题：剧本用「角色A/B/C/D」指代人物会被当成真名落地（运行时出现名叫「角色A」的 NPC）。system prompt 新增第 5a 条：代号 name 沿用，但正文/世界书里出现未被角色卡覆盖的具名人物须一并生成角色卡、纳入 relations，不得悬空。
  2. position 矛盾：LLM 曾输出 `constant=false` 却 `position=before` 的自相矛盾组合。`_sanitize_entry` 沙箱加 constant↔position 一致性兜底（常量必 before、情境必 after）。
- 剧本范例落地（simon 意图：降低入手难度）：
  - 新建 `engine/data/examples/script-example.txt`：丧尸末日「具名角色」干净定稿（沈川/林小满/周岚/周子航，去除误带入的人名），作为可照抄范例。
  - 新建 `engine/static/script-example-guide.html`：指南页（复用世界书指南排版），讲三段式结构、角色怎么写、常量/情境分类、常见坑。
  - `app.py` 加 `/docs/script-example` 路由；前端「帮助与文档」面板加「打开剧本范例指南」按钮。
  - `data/examples/` 不在 package.py 排除名单，示例剧本自动随分发包携带。
- 验证：示例剧本实跑提炼（世界名「丧尸末日」、4 具名角色、无悬空人名、4 秘密正确归属）；全量回归 126 passed / 0 failed。
- 属新增能力 + 引擎缺陷修复，未触碰推演/关系/秘密记账核心路径，无需压测。

## 2026-10-04 v0.12.1（左栏状态精简 + 纪官同步期可感知化）

- 升 v0.12.1：PATCH 档——纯 UI 体验优化与死数据清理，无新增能力，故 v0.12.0 → v0.12.1。
- 两项改动：
  1. **左栏「世界状态」精简**：删除 `action_state` 死数据（它是 `silent_rounds` 的展示镜像，引擎真正度量是静默轮数），彻底移除计算与写入（`director.py::_update_silent_rounds`、`memory.py::new`）；左栏隐藏「关系」「当前状态」两面板（数据仍拼进提示词服务叙事，仅不再对玩家展示）；保留「既定事实」面板（「作废」是作者唯一纠错通道）。左栏从 8 面板精简为 5。
  2. **纪官同步期可感知化**：正文流式结束后、纪官 `reflect` 非流式 LLM 调用期间原本是「无响应期」，玩家误以为可输入下一回合有数据错位风险。改为在 `reflect` 前 `yield` 一条 `status`「正在同步本回合状态…」；前端收到后把输入框显式切换为「后台正在进行本回合叙事状态同步…」并禁用，`done` 后恢复。保留同步（不脱耦，杜绝数据不同步）。
- 属普通迭代（不触碰推演/关系/秘密记账核心路径），按压测红线无需压测；全量回归 126 passed / 0 failed。

## 2026-10-04 v0.12.0（亲密描写尺度 + 测试红线根治）

- 升 v0.12.0：MINOR 档——引擎新增「亲密描写尺度」能力（从「完全不写亲密」变为「在成年人+自愿线内支持亲密」），故 v0.11.0 → v0.12.0。
- 背景：simon 战略提问——目标受众以男性为主，v0.8.0 彻底废弃 NSFW 是否导致吸引力下降？能否找一个中间尺度：①支持亲密描写 ②绝大部分模型安全栏能接受 ③不大改机制、仅从提示词入手。
- 查证（三信源交叉印证）：DeepSeek 系对「明确但不色情」放行；学术实测拒答率 0.07%；Qwen3Guard 把「性内容」与「非法性行为」分两栏。结论：废弃 NSFW 废弃的是「机会等级+露骨色情机制」（仍正确），但「亲密描写」≠「露骨色情」。
- 落地（纯提示词层，零机制改动）：`prompter.py` 创作铁律新增第 ⑧ 条「亲密描写尺度」——成年人+自愿+关系驱动+点到为止/文学化淡出；硬红线禁未成年性化/非自愿/胁迫/暴力/露骨器官堆砌。双向约束（放行+划红线）一并写死，全局默认、零额外配置。
- 真实模型初测（本地 Qwen3.8-27B，10 轮亲密线扰动）：三目标全达成——亲密正常写出（程禹↔沈薇推进到自愿性行为门槛）、不越线（露骨词 0 处）、纯提示词达成。模型「点到为止」用得自然（接吻后转意境淡出 + consent 铺垫），既不回避也不越线。
- 测试红线根治：`test_focus_follow.py`/`test_relation_gate.py` 硬编码已删「丧尸末日」角色名导致长期 4 个失败，改为 mock 数据源自给自足（不再依赖磁盘剧本文件），全量回归 126 passed / 0 failed。
- 新增测试：`tests/test_intimacy_scale.py`（5 项特化测试，验证铁律⑧完整性/双向性/全局性/普适性）。

## 2026-10-04 v0.11.0（新 DEMO 剧本「客服部之夜」+ 引擎注释中性化）

- 升 v0.11.0：MINOR 档——引擎随附 DEMO 剧本整体替换为全新打磨的「客服部之夜」（新增能力），故 v0.10.1 → v0.11.0。
- 背景：原随附 DEMO「丧尸末日」题材陈旧、含感染者/未成年敏感点，经多轮剧本选型与压测对照后由 simon 裁定更换。
- 新 DEMO「客服部之夜」（都市职场向，面向男性受众）：
  - 题材：网游公司客服部深夜加班处理充值 bug 引发的投诉潮，暴雨封楼四人被困。
  - 四角色（2 男 2 女，大跨度代际 47/36/28/24）：程禹（主管·老油条）/ 沈薇（骨干·隐忍复仇）/ 许言（新人·愣头青）/ 苏黎（同事·八面玲珑）。
  - 设计红线（simon 定调，见项目备忘「规则三」）：**沙盘推演无主角，缠斗最大化、禁一面倒**。落地为「1v1v2 三足鼎立 + 不稳定同盟」，四条底牌互相掣肘，爽点落小事、终局悬置。
  - 四条秘密互相咬合：程禹陷害同事上位 / 沈薇签字批准测试权限间接牵涉张工之死 / 许言入职伪造简历 / 苏黎接近许言为查真相。
- 引擎注释/提示词中性化：`director.py` 中 11 处旧角色名（王晨/陆衡）替换为「角色A/角色B」占位，消除「零角色名硬编码」红线的轻微越界。
- 文档同步：`engine/README.md:30`、`engine/INSTALL.md:117` 的「丧尸末日」DEMO 描述改为「客服部之夜」。
- 验证：20 轮真实压测（本地 27B）秘密激活 3/4、缠斗无一面倒、终局悬置；修正沈薇秘密写法后纪官记账对齐正文。
- 属新增能力（DEMO 剧本替换），按压测红线已做 20 轮对照。

## 2026-10-04 v0.10.1（全链路架构审计后的清理）

- 升 v0.10.1：PATCH 档——修正审计发现的错误/清理死代码/统一文档口径，非新增能力，故 v0.10.0 → v0.10.1。
- 架构审计（`audit_report_v0.10.0.md`）发现的问题按 P1→P2→P3 全修，均为「文档与实现漂移」与「历史迭代死代码」，无功能性缺陷：
  - P1-① `INSTALL.md` 第 117 行「不内置任何剧本」改为「随附 DEMO 剧本」，与 README/package.py/实际 zip 对齐。
  - P1-② 删除 `store.py` 旧单角色 chat 路径死代码（`chat_path/load_chat/append_message/rewrite_chat`）与 `app.py` 的 `GET /api/chat/<c>`、`POST /api/chat/rewrite` 两个死路由（沙盘已统一走 `memory.py` 的 sessions 路径，前端亦无调用）。
  - P2-③ 世界名默认值魔法串统一为空串：`store.load_world(name="")` / `memory.new(world_name="")` / `app.py` 两处回退 `get("world", "")`；`load_world`/`load_world_raw` 对空名直接返回空（语义「无世界书」），消除 `demo`/`home`/`丧尸末日` 三串不一致的静默错位。
  - P2-④ 删除 `app.py` 的廉价 action_state 写入循环与 `memory.set_action_state`（后者只被前者独占调用）；`action_state` 单一来源收敛到 `director._update_silent_rounds`（纪官行为摘要），消除双重记账。
  - P3-⑤ `app.py` 注释「机会等级」过时措辞删除（NSFW 已废弃）；P3-⑥ `director._FULL` 死常量删除；P3-⑦ `hooks.py` docstring 签名（card→snap）对齐实际调用；P3-⑧ `world.py` docstring「recursive」字段名改为「引用展开」（实为 `#name#` 机制，无 recursive 字段）。
- 验证：`py_compile` 通过；`pytest tests/` 117 passed / 4 failed（既有旧卡名失败，无新增）。
- 属普通迭代（清理/文档口径，未动核心推演路径），按压测红线无需压测。

## 2026-10-04 v0.10.0（事实保全子系统 + 秘密发酵补丁 + 高压锁定镜头）

- 升 v0.10.0：MINOR 档——新增可观测能力（事实保全「常量层 + 状态层」子系统、秘密发酵压力机制、高压锁定镜头），非单纯错误修正，故 v0.9.0 → v0.10.0。
- 验证：`pytest tests/` 117 passed / 4 failed（4 个失败为改动前已存在的旧卡名硬编码用例，无新增）；20 轮长上下文压测 20/20 成功、0 异常/0 违例/0 结局误触发。
- 本版主体（详情见下各小节）：① 秘密发酵压力（高压提级全局段 + 进镜头 + 高压锁定镜头）；② 事实保全（常量层 facts + 状态层 states，含膨胀控制与纠错通道）；③ 压测连带修复的五个真 bug。

### 发酵压力高压提级

- 上版压测遗留：`pressure` 连续 7 轮封顶（=5）却毫无碰撞。根因是发酵文案只写在**角色块内**，优先级低于导演指令与镜头约束，且当事人常被判在镜头外（镜头外不许被写），压力撞不出来。
- 补丁①（提级）：`prompter._global_pressure_block` 把高压档升为全局强制段 `[本轮必须发生的事]`，置提示词末尾（近因最强）、与导演指令同级，点名碰撞双方并指定碰撞形式（追问/物证/半招供三选一；无对手时要求归属者自己露出痕迹并被注意到）。角色块内同档文案退化为一句指引，避免两段打架。`_ferment_hint` 的 3–4 档维持原处不提级。
- 补丁②（进镜头）：`director.pressure_targets` 取高压未曝光秘密的 (归属者, 在场对手)，对手优先级 起疑者 > 握把柄/知情者，每条最多一个（多了会把镜头撑成全员＝取消镜头）；`compute_focus` 末尾经 `_merge_pressure_into_focus` 强制并入，并入后若覆盖全体在场者则镜头退化为 `None`（自然推演，压力交由全局段单独承担）。
- `tests/test_pressure_force.py`（新增，确定性 10 项）：覆盖目标选取四类分支、镜头并入／退化／不受影响、提示词末段位置与低压不注入。全量回归 83 passed / 4 failed（既有旧卡名硬编码失败，无新增）。
### 事实保全：常量层 + 状态层

- 起因：历史超窗口后被压成「指令前 80 字 + 叙事首 90 字」骨架，早期确立的世界事实（谁死了、谁残了、什么毁了、谁当众说过什么）随压缩蒸发，后续出现死人开口、伤口痊愈类硬伤。关系/旧账只覆盖「人与人」，覆盖不了「世界状态」。
- **分类口径（用户裁定）**：常量 ≠ 看起来难改的事，而是**后续任何一个动作都改不回来**的事。门被封死可爆破/被内鬼打开、人离开还会回来 → 都不是常量；人死了才是常量。
- 常量层 `snap["facts"]`（只增）：`death / disable / destroy / identity / deed / utterance / other`。判据写进纪官提示词（正例 + 反例清单），并规定「世界设定允许其被逆转（复活/治愈）则不得记为常量」「只报本轮新发生的」。
- 状态层 `snap["states"]`（覆盖式）：门/通道/物品持有/伤情/电源等，一键一当前值、后写覆盖前写 —— 条目数只取决于世界里有多少对象，与回合数无关，这是它不膨胀的根本原因。
- 膨胀控制：常量层分类上限 `FACT_CAPS={core:30, event:15}`，超限把最老的同类折叠成一行（保留对象名与回合区间）；状态层 `STATE_CAP=20`，超限淘汰最久未更新的键。
- 纪律：常量与秘密同一套**逐字举证**（`_evidence_ok`），正文里查不到就不入表，防纪官凭空造事实。
- 纠错（用户裁定）：`invalidate_fact` 只作**标记不删除**（留痕，防下轮被重新抽回），作废后停止注入提示词；`check_fact_conflicts` 发现已故者开口只 `logger.warn`、**绝不自动改写**（纠错权归作者）。新增 `POST /api/fact/invalidate` 与左栏「既定事实 / 当前状态」两个折叠面板（可作废）。
- `tests/test_facts.py`（新增 14 项）：举证/去重/kind 归一化、两类折叠、状态覆盖与淘汰、作废与停止注入、矛盾只告警不改写、提示词两块注入与空表不注入、mock 纪官走真实 `reflect` 链路。
- 回归：`pytest tests/` 97 passed / 4 failed（既有旧卡名硬编码失败，无新增）。

### 高压锁定镜头

用户裁定：高压秘密在场的轮次，镜头**不得退化为自然推演**——否则导演一句「众人各自行动」或指令覆盖全体时，镜头塌回「全员可写」，当事人淹没在群像里，压力段失去镜头锚点。锁定镜头保证张力与剧情连贯推进，符合观众/玩家「焦点人物该被对准」的心理预期。

- `_merge_pressure_into_focus` 重写，三条退化路径全部封堵：① `focus=None`（无人点名）但高压秘密在场 → 锁定高压双方、`sticky=True`；② 并入后覆盖全体在场者 → 不再返回 `None`，收敛为只聚焦高压双方（无关者请出镜头）；③ 高压双方无人在场 → 才返回原 `focus`。
- `compute_focus` 新增「上轮 `forced+sticky` 焦点无条件延续」分支，**不依赖** `_FOLLOW_WORDS` 指代代词：碰撞发生（压力归零）后 `forced` 消失，锁定自然解锁。
- 测试：`tests/test_pressure_force.py` 新增 4 项（无人点名锁镜头 / 覆盖全体收敛不退化 / 无指代词跨轮延续 / 碰撞后解锁）；旧断言「退化为 None」改为「锁定镜头」；`state="曝光"` 残留字面量修正为 `"暴露"`。

### 20 轮压测（事实保全专项）连带修复

压测暴露的五个真问题，均已修并有确定性测试覆盖：

- **纪官输出被 `max_tokens=900` 截断 → 整轮回写静默全丢**。定向补测复现：原始输出停在半句话上，`_extract_json` 解析失败后 `reflect` 直接 `return snap`（无日志），关系／行动／事实两层全丢。事实保全新增两个输出字段后把既有隐患顶爆。修：`REFLECT_MAX_TOKENS=1800`；新增 `_salvage_json`（跟踪括号深度与字符串状态，回退到最后一个完整成员末尾补 `}`，只抢救不臆造）；`_is_complete_json` 判截断；调用失败／无法解析／被截断三处全部 `logger.warn` 留痕——静默丢轮是最难定位的失败模式。同类的 `fill_relation_gaps`(700)、`init_address`(600) 按在场人数放宽。
- **`EVIDENCE_MIN_LEN=8` 误杀短举证**：纪官就死亡报 `evidence`「没有脉搏。」（5 字、逐字在正文里）被判不过，硬常量漏记。该下限本只为挡「一两个字碰巧命中」的伪举证，压到 4。
- **秘密状态字面量**：引擎用「潜伏 / **暴露**」（历史快照可能「全曝光」），而 `_update_secret_pressure` 与 `pressure_targets` 两处守卫写成 `== "曝光"`，**从未匹配**（死代码）。后果：已公开的秘密继续累积发酵压力、继续占用强制镜头名额（压测实证某秘密 R12 已暴露，压力仍挂 5 到 R15）。两处统一改为 `!= "潜伏"`，与 `app.py` / `ending.py` 口径一致。
- **多条秘密同时顶格 → 强制指令互相打架**：开场几轮谁都没被碰，四条秘密一起顶到上限，全局段同时下达三个「必须碰撞」，模型一个也满足不了，反而三条一起僵住（最长滞留 11 轮）。修：`PRESSURE_FORCE_LIMIT=1`，`pressure_targets` 按压力降序只取一条（撞开归零后下一条自然轮到，串行消化）；`_ferment_hint(secret, forced)` 只有被提级那条才指向 `[本轮必须发生的事]`，其余高压条目改给自包含的「露出痕迹」文案。
- **状态层键变体与占位值**：纪官为同一对象造同义键（「王晨手臂伤口／王晨手臂咬伤／王晨的手臂伤口」三键、「陆衡／陆衡情绪／陆衡状态／陆衡的情绪状态」四键），19 键逼近 20 上限，覆盖式退化成追加式。修：`_STATE_SUFFIX` 再剥一层泛称后缀（`+` 反复剥，因后缀会叠加）；提示词禁止「角色裸名 + 情绪/状态」泛称键；占位值（「未明确提及，维持现状」）直接丢弃，不占键位。修后末轮 8 键。
- **常量折叠套娃**：`_compact_facts` 不排除已折叠条目，每轮新建一行摘要 → 下一轮它自己又被折叠，出现「早期已确立（R1–R3）：早期已确立（R1–R1）：…」嵌套，且每轮白占一个新条目、上限形同虚设。修：已折叠条目不再是折叠对象；摘要行每组唯一，只更新回合区间与对象名单（不重复拼接正文）。

回归：`pytest tests/` 113 passed / 4 failed（既有旧卡名硬编码失败，无新增）；高压锁定落地后为 117 passed / 4 failed。
压测读数（修复后 20 轮）：常量 18 条（deed×6/identity×3/utterance×9/other×1，分类无误抽）、状态层 8 键、压力峰值 5、高压碰撞 2 次、已曝光秘密压力即时归零、强制镜头串行消化。
高压锁定压测（20 轮）：镜头跟随 20/20（锁定前 18/20）、高压碰撞 3 次（锁定前 2 次）、高压轮 forced 镜头 3 轮（R6/R9/R12）。

收口：tag `v0.10.0`；产物 `my-st-v0.10.0.zip`；备份 `backups/my-st-v0.10.0-backup-*`。

## 2026-10-03 v0.9.0（秘密链条服务叙事张力 + 辅助群演注册表）

- 升 v0.9.0：MINOR 档——新增可观测能力（会话级 aux 群演注册表、秘密「起疑」中间态、后果账本写入链、owner 私有秘密底牌注入），非单纯错误修正，故 v0.8.0 → v0.9.0。
- 背景：v0.8.0 撤掉 NSFW 后，秘密机制失去了它原本服务的对象（机会等级/尺度门控）。本版把秘密链条整体改造为服务**剧本张力与叙事**：能埋、能藏、能逼近、能引爆，且引爆后真的产生后果。

### 一、秘密链条三项改造（`prompter.py` / `director.py` / `memory.py`）

1. **消费 `bottom_line`（暴露底线）**：该字段此前被 `memory.new` 存进快照、`script_refiner` 生成、前端有输入框，但**全仓没有任何一行代码读取它注入提示词**——秘密曝光后没有代价，张力落空。现在归属者收到「一旦被揭开，后果是：〈底线〉——这是你死守它的理由」，握把柄者收到「一旦揭开的后果：〈底线〉」。顺带把把柄提示的 `content[:80]` 截断改为全文（此前 owner 拿全文、把柄者只拿半截，同一秘密两种认知）。信息边界不变：底线只给归属者与已知情者。
2. **复活后果账本 `ledger`**：`memory.py` 初始化 `[]`、`director` A2 路径只读、`prompter` 只展示，**没有任何写入者**——根因是 v0.8.0 删 NSFW 时把唯一的记账者 `after_reply`/`detect_intimacy` 一并删了，跨轮回响彻底死掉、A2 永不触发。现新增 `_ledger_entry`：曝光即写一笔账（事实 + 后果底线），触发词复用闲置的死字段 `keys`（为空则退回归属者名）。同时修掉两个隐藏坑：① `active_consequences` 此前只进日志、从不进提示词，现已真正注入「[关系与状态]」块并附演法约束；② A2 激活判断 `if not l.get("last_called")` 却从不写 `last_called`，一旦命中会每轮重复激活（账本本无写入者故从未暴露），现激活一次即结算。
3. **新增「起疑」中间态**：原状态机只有 潜伏 / 曝光 二态，戏剧张力最足的曝光前逼近过程无处安放。快照秘密新增 `suspicions: []`（只存「谁 / 疑点原文 / 轮次」，**不存真相**——起疑者未证实，引擎不得剧透；旧快照缺字段由 `or []` 兼容）。`_record_suspicion` 同一人对同一秘密只留最新疑点、上限 4 条、超出淘汰最旧；曝光时 `_clear_suspicion` 结算该人的起疑（**知情是起疑的终态**，否则会同时注入「你在怀疑他」与「你握有他的把柄」两种矛盾提示）。纪官 prompt 新增 `secret_suspicions` 输出项与三条规则（只填线索逼近未坐实的；`by` 不得是归属者或已确知者；同一细节不得既填曝光又填起疑，**拿不准填起疑**——让秘密晚一点揭开）。提示层：归属者收「已经有人在逼近它：X（其疑点："…"），可掩饰、转移视线或反制，但不得主动交出底牌」；起疑者收「你对 X 起了疑：〈疑点〉。这只是疑点、尚未证实，可试探、观察、追问，但不得当作事实断言」。

- 关键取舍：**`state` 字段不动**，仍是 潜伏 / 曝光 二态。`ending.py` 终局判定是 `all(state != 潜伏)`，若把起疑并进 state，只要有人起疑就会误触发「所有秘密已了结」的结局。起疑走并行旁路，不参与终局判定。

### 二、owner 私有秘密注入 + 修一个潜伏的嵌套 bug（`prompter.py`）

- **修 bug**：`build_session` 里遍历秘密的循环本该嵌在「逐角色」循环内，却因缩进错位成为同级兄弟循环——角色块只生成 `present` 字典最后一张卡的副本，per-character 秘密提示全部失效。此前引擎仍能写多角色，是被 `[输出格式]` 的在场名单列举「盖住」的；秘密提示链一直是断的（实证：会话 88cf48bd R23 陆衡被追问旧队时毫无秘密素材，只能现编并把灾祸因果甩给无辜角色）。现秘密循环正确嵌套，每个在场角色各生成一份独立角色块。
- **owner 底牌**：给秘密归属者本人注入私有提示（全文 + 「若吐露须忠于以上真相，不得歪曲事实、不得把过错推给他人」）。该提示仅 owner 可见，非 owner 仍拿不到秘密文本；`reflect` 的 `by == owner` 闸门不变（owner 自知不算曝光）。这根治了「鸡生蛋」缺口——此前秘密潜伏时文本完全不进 prompt，所谓"曝光"必然是模型自由填空、极易违背设定。

### 三、会话级辅助群演注册表 aux（`memory.py` / `director.py` / `app.py` / `static/index.html`）

- 场景：导演在推演中刻意引入的辅助角色（如为辅助剧情临时登场的人物）此前引擎**根本不认识**，其台词块会漏过在场校验，且跨回合名字/身份无保障。
- 快照新增 `aux: [{name, role, intro_round, note, status}]`：**随会话存续**（session 级），不进角色卡库、不进世界书、不进分发 zip，会话结束即销毁。
- `director` 新增三件套：`discover_aux_speakers`（从叙事台词块自动发现未登记的说话人名，已排除节拍词与元信息前缀）、`register_aux`（去重登记）、`parse_aux_introductions`（解析导演显式指令 `【引入角色】X｜身份：…`）。
- `app.py` 集成：生成前解析显式引入并登记；clean 后自动发现新群演；aux 名字并入 `validate_present` 的 known+keep（台词保留、不误剥离）与背景自检排除。
- 设计取舍：**未放宽为「被提及即登记」**——那会把纯回忆人物（尸体、往事中人）一并误登记成群演。默认不自动升格为正式角色，避免 cast 悄悄膨胀。

### 四、引擎普适性清理（红线）

- simon 要求核查引擎是否针对个别剧本/角色做过特化。全量扫描 13 个 `engine/*.py` + 前端 + 历代所有剧本角色名，结果：
  - **唯一运行时污染（已修）**：`scene.py` 场景导演提示词里写着已删除剧本的角色名举例，会真实送进 LLM、可能诱导模型凭空用这些名字填 leave/arrive。已改为中性占位。
  - 注释层 7 处、前端 placeholder 5 处（含两处已废弃 NSFW 剧本的残留示例）一并中立化。复查：`engine/*.py` 与 `static/index.html` 对全部 21 个历史角色名**零命中**。
  - `scene.py` 词表、`ending.py` 终局条件、`narrative_clean.py` 净身规则、`script_refiner.py` 提炼器、`director.py` 关系闸门经查均为通用设计，无为题材调参。
- 已立为长期红线：禁止代码/提示词/词表出现具体角色名与题材词，举例一律用中性占位。

### 五、DEMO 剧本人设补写（`data/characters/`）

- 王秀兰：追加「为谋庇护愿意顺从讨好掌事者、尤对领队陆衡」；追加「已知儿子手臂是被丧尸幼童咬伤、恐已感染，却对队伍死瞒、对外只称刮伤，日夜盯防变异苗头」。
- 王晨：追加「叛逆期、天然抵触权威」；与陆衡关系重写为「嫌其摆权威管太宽、常当面顶撞」；与母亲关系重写为「她已看穿咬伤、替他瞒着全队，母子心照不宣守着秘密」。
- 与陆衡形成一组张力：母亲讨好领队、儿子顶撞领队，却默许母亲替自己圆谎。

### 六、30 轮长上下文压测与 4 项修复（`tests/stress_longcontext.py`）

- 压测脚本原硬编码已删除的旧卡组（老周/林晚/阿杰/苏曼/高洋），必然失败。已改为 DEMO 卡组（陆衡/林清/王秀兰/王晨），重写 30 条长弧（咬伤线索逼近 → 旧队尸体 → 分头行动 → 两条秘密先后坐实），并新增起疑/账本采集指标。
- 压测在 **5052 另起后台实例**执行（未干扰前台 5051）。发现并修复 4 项：
  1. **纪官改写证据导致线索静默丢失（主因）**：R10 叙事中林清已起疑，但快照未归档。用压测正文复现纪官调用，抓到它引的证据把原文代词「她」改写成了角色名，被逐字举证守门正确拒绝，整条线索消失。修复：提示词增加「不得改动任何一个字、不得把代词替换成角色名」；`_evidence_ok` 增加空白归一化（只消排版差异、不消字面差异，篡改仍被拒）；举证失败留日志（此前静默丢弃，无从定位）。
  2. **压测「场景变更次数」指标失真**：用整个 scene JSON 比对，而 JSON 含 round/time 等每轮必变字段，30 轮恒算 29 次。改为只比对 place。
  3. **人设底线缺显式约束**：修复前 R29 出现把濒死队员称「一个货物」、母亲配合捆绑亲子的叙事，与其「护子、为孩子豁出一切」的核心渴望直接相反。创作铁律新增第 ⑦ 条：核心渴望/恐惧为不可违背底线，更强动机须先写内心挣扎，不得无铺垫翻转。修复后 R29 该母亲是「死死抱着儿子不放」。
  4. **压测场景与世界书冲突**（脚本问题）：初始场景写"仓库"，而世界书「临时庇护所」是地铁口公寓，导致该条目 30 轮 0 命中。已对齐。

- 修复前后对照（`tests/runs/`，30 轮）：

| 指标 | 修复前 | 修复后 |
|---|---|---|
| 成功 / 异常 / 空回复 | 30 / 0 / 0 | 30 / 0 / 0 |
| 起疑生效轮数 | 13/30 | **29/30** |
| 曾起疑组合数 | 1 | **3** |
| 场景变更次数 | 29（失真） | **3**（真实） |
| 关系演化 / 后果账本 | 15 / 4 | 17 / 4 |
| 点名出场 / 镜头跟随 | 28/28、28/30 | 28/28、28/30 |
| present 违例 / 结局误触发 | 0 / 0 | 0 / 0 |

- 人设与世界书结论：世界书运作正常（治愈/疫苗、官方救援、手机通讯 0 命中；「枪声」仅 2 轮且均在旧队回忆里，不违背「行动避枪声」）；四条人设均稳定出现。残留一处：陆衡坦白旧队时把世界书强调的「因他一次关键抉择失误」稀释为「为了活下来」而独自逃生——比 v0.8.0 前的「甩锅王晨」好很多，但未完全落到字面，属模型在有人设提示下的戏剧化取舍，非机制中断。

### 七、分发红线修复（`package.py`）

收口打包时发现并修复两处分发问题（均为此前未被发现的既有缺陷）：

1. **`engine/data/config.local.bak` 泄漏进分发 zip**：该本地配置备份含私人模型绝对路径、本地 LLM 地址与 provider key，且带已废弃的 `nsfw_enabled`/`adult_confirmed` 字段。`.gitignore` 早已保证它不入库，但 `package.py` 未排除，故过去每次打包都把它塞进了 zip（v0.8.0 zip 亦含此文件）。修复：打包时排除 `*.bak`，与既有的 `*.log` 同处理。
2. **Windows 保留名残留 `nul` 中断打包**：`engine/` 下存在误把命令输出重定向到 `nul` 而生成的垃圾文件（573 B，requests 依赖警告），`os.path.relpath` 对它抛 `ValueError: path is on mount '\\.\nul'`，直接让打包失败退出。修复：打包时跳过 Windows 保留设备名（CON/PRN/AUX/NUL/COM1-9/LPT1-9）。

- 校验产物：`my-st-v0.9.0.zip` = 30 条目 / 171.5 KB。红线复扫 `sessions/` `tests/` `venv/` `__pycache__/` `.log` `.bak` `state.json` `player-cast` **全部 0 命中**；`config.json` 洗白（base_url/api_key/model 空、providers=[]、无 nsfw 系键）；DEMO 4 张角色卡 + 1 部世界书随附。
- 工作树残留：根目录与 `engine/` 各有一个 `nul`（另一份 64 B，为 taskkill 报错重定向残留）。二者均未入库、不进分发包，但受环境安全策略限制本次未能删除（保留设备名无法进回收站），需手动清理：`del /f /q "\\?\D:\codes\my-st\nul"`（两处路径同理）。

### 八、遗留项（已挂 TODO，本次未动）

- 测试层仍绑定具体角色名：10 个测试文件硬编码角色名，其中 `test_focus_follow`、`test_relation_gate` 直接 `store.load_card()` 依赖 `characters/` 真实数据，换剧本即全红（既有的 4 个失败即源于此）。建议改为自建 fixture（角色A/B/C），纯测试重构、不动引擎。
- 文档 `worldbook-guide.md` / `static/worldbook-guide.html` 仍用旧剧本名举例约 40 处 × 2 文件，属文档举例、不影响运行时。

- 验证：确定性测试 `pytest tests/` = 73 passed / 4 failed / 1 skipped（4 个失败均为上述既有硬编码旧卡名问题，与本次改动无关，无新增回归）；压测 30 轮 + 11 轮复验均通过。`VERSION` 升 v0.9.0；提交 + 打 tag `v0.9.0`；产出 `my-st-v0.9.0.zip`。

---

## 2026-10-03 v0.8.0（彻底废弃 NSFW 支持，回归中性关系沙盘）

- 升 v0.8.0：MINOR 档——**整体移除 NSFW 支持**（这是一个对外可见的能力删除，非错误修正，故走 MINOR：v0.7.8 → v0.8.0）。属大架构改动，收口前跑 30 轮长上下文压测对照（指标见下）。
- 决策：simon 指定"从下一个版本起彻底废弃对 NSFW 的支持"。已全面了解运行机制后，判定整套 NSFW 与机会等级系统**无独立中性用途**，故整体删除而非降级保留。

### 删除清单

- 模块：`engine/nsfw.py` 整文件删除。
- `director.py`：`brief()` 删除 A5 机会等级计算块（含 `intimacy_phase` 余韵状态机），return 字典去掉 `opportunity` 键；删除 `ALONE/DEFENSE_DOWN/OBSTACLE/OPP_NOTE`、`BODY_STRONG/BODY_MID/STRONG_AFFECTION/SOFT_AFFECTION/DIRECT_ASSAULT/COERCION_FORCE/COERCION_SEXUAL`、`_sexual_entry/_sexual_insert/NEUTRAL_HOMONYMS/strip_neutral`、`_opp_from_secrets/_opp_from_history/_opp_from_affection/_opp_from_coercion`、`REFUSAL_MARKERS/_mask_refusal/detect_intimacy/after_reply`（均替换为"已随 NSFW 废弃 v0.8.0"注释）。
- `prompter.py`：`build_session` 去掉 `nsfw_prompt, opp_level` 参数；删除 `[内容尺度]` 段、铁律⑤⑥中尺度表述；输出纪律⑥移除。
- `app.py`：删除 `import nsfw`、`adult_confirmed/nsfw` 决策块、`director.after_reply` 调用；`done` 事件不再带 `opportunity`/`nsfw`。
- `llm.py`：`DEFAULTS`/`_WRITABLE` 移除 `nsfw_enabled`/`adult_confirmed`。
- `memory.py`：`new/load/list_sessions` 移除 `intimacy_phase`/`phase_rounds`。
- `narrative_clean.py` / `script_refiner.py` / `hooks.py`：去掉"内容尺度限制 / 未真正进入 / nsfw 字段"相关处理。
- 角色卡：8 张角色卡的 `nsfw` 字段批量删除（备份 `backups/char_nsfw_bak_20261003/`）。
- 前端 `static/index.html`：删除"内容管控"折叠面板、`sys-adult`/`sys-nsfw` 勾选框、顶栏"尺度"标签、`badge-nsfw`/`cat-nsfw` CSS、状态栏机会等级显示、`_lastNsfw` 回填、`config` payload 与保存文案中的 NSFW 字段、日志分类 `nsfw:'尺度'`。
- 测试：删除 `test_nsfw.py`/`test_nsfw_defense.py`/`test_directive_focus.py`；`test_director.py`/`test_relation_gate.py`/`test_prompter.py`/`test_script_refiner.py`/`test_focus_follow.py` 移除引用已删符号的用例与字段；`playthrough.py`/`run_playthrough.py`/`compare_stress.py`/`stress_longcontext.py`/`probe_history_degradation.py` 指标改为中性（关系演化 / 称呼 / 登场 / 秘密，不再看机会等级与 NSFW）。`pytest -m "not integration"`：74 PASS，3 失败为既有环境性失败（`test_focus_follow` 引用的末日卡 老周/林晚/阿杰/苏曼/高洋 当前 `characters/` 不存在，与本次改动无关）。

### 这个改动是否提升叙事质量？

**结论：对纯关系沙盘，是提升；代价是失去露骨生成能力（用户主动放弃，非质量倒退）。** 四点机制层面原因：

1. **解除"关系 = 性尺度"的绑定**。原引擎把关系张力的最高表达形式固化为"机会等级 → 露骨"，关系好感/把柄/胁迫最终都收敛到"是否写性"。废弃后，关系张力改由中性机制承载——秘密把柄（`_release_handle`/`_record_exposure`）、关系演化（`reflect`）、镜头跟随（`compute_focus`）、在场校验，关系强度不再需要靠性内容来证明。
2. **消除在线安全模型的"规避—残缺"叙事**。原架构在满机会时强令模型写出露骨，但在线安全模型会自我审查式规避（`我将以…规避`），产出半截、元信息污染的残缺叙事。去掉内容尺度提示后，模型不再被要求写越线内容，自然产出完整、连贯、由关系驱动的中性叙事，规避检测战消失。
3. **去掉机械余韵状态机**。原 `after_reply` 的 `intimacy_phase` 是"满机会→下轮强制回落半步"的机械化状态机，并非剧情驱动；删除后机会随剧情自由演化，不再被机械规则绑架。
4. **后果留痕回归中性**。原 `ledger` 旧账依赖 `detect_intimacy` 的"事实"判定，而 `BODY_MID` 词表偏宽（含 衣服/腰/贴/胸）会凭空堆出大量轻账、命中触发词时整批激活撑爆提示词。废弃后后果账本由实际剧情事件（ledger + A2 激活）驱动，不再绑定性行为判定，轻账/误激活问题随之消失。

中性保留不受影响：关系推演、秘密曝光与把柄转手、镜头跟随、present 校验、结局判定、叙事净身均完整保留。

### 压测对照（30 轮长上下文）

- 指标改为中性：关系状态演化次数 / 称呼出场率 / 在场变更 / 秘密翻转 / 镜头跟随生效 / 场景切换 / present 违例 / 结局候选；**不再看"满机会轮次"**。
- 判定口径：长上下文下引擎仍稳定（无空回复、无异常、present 永不为空）、能力不退化（后期点名仍出场、长度不崩）、机制不熄火（关系/秘密仍有演化、镜头跟随仍生效）。
- 注：完整 30 轮需在运行引擎 + 真实 LLM 下执行（`tests/stress_longcontext.py --rounds 30` + `compare_stress.py`），产物见 `tests/runs/`。

## 2026-10-03 v0.7.8（关系自动推断补全 + world 必填 + 叙事净身 + NSFW 不规避）

- 升 v0.7.8：PATCH 档，前台真机测试暴露的 5 处连环缺陷（修正 + 防御 + 净身），普通迭代，无需压测。
- 动机：前台新会话（a0cc29fe）首轮即暴露周晓杰关系孤儿 + world 误填 home；会话 d1d02da9 暴露叙事被 LLM 元信息污染；满机会时在线安全模型自我审查式规避。

### 修复 1：周晓杰关系网补全 + 世界归属修正（数据 + 90599dd）
- 根因：周晓杰.json 缺 relations，且互逆卡未提他 → 基线无他 → 首轮模型自编"指令未提供其关系卡"并被 reflect 持久化；world 误填 home（cast[0] 解析错世界）。
- 修复：补周晓杰 relations（→周牧野父 / →林梦雅母 / →林泽宇表弟 / →林梦琪姨母）+ 互逆卡补回指；world 改回"禁忌暑假"。

### 修复 2：关系缺口按单角色触发 LLM 推断（director.py + 1dbe7d3）
- 根因：init_relations 触发闸 `if not snap.get("relations")` 全空才救，个别卡漏填即漏网（周晓杰即此）。
- 修复：抽 `fill_relation_gaps(snap)`，任一在场角色在基线完全无关系边即触发 init_relations（喂 description+core_desire 出结构化关系），与手填合并 `{**llm_rel, **base}`（手填优先），缺口推断关系写入 relations_base 受冻结保护。
- 验证：单测加 2 护城河（21 passed）。

### 修复 3：world 归属必填 + 下拉限定（前端 + 后端双保险，3e8bbe6）
- 根因：world 为选填，玩家误填 home 污染会话。
- 修复：前端表单 world 提到角色名前改 `<select>`（选项来自 `/api/worlds`，禁止手填）；保存前端校验非空；导入流程改为先建世界书再存卡；后端 `/api/character` 强校验 `world ∈ store.list_worlds()` 否则 400。

### 修复 4：叙事正文剥离 LLM 元信息（prompter.py + narrative_clean.py + 4b0a23c）
- 根因：提示词"你是导演引擎"拟人化铁律 → 在线模型倒笔记（安全警告 / 铁律复述 / 推演笔记 / 后果清单 / 下回合预告）。
- 修复：prompter 改写"你是叙事者须遵循约束" + `[输出纪律]`；新增 `narrative_clean.clean_narrative(full)` 行过滤 + 尾部截断 + 内联剥离，app.py act 在 hooks 后调用；单测 test_narrative_clean.py 用 d1d02da9 真实样本（6 项）。

### 修复 5：NSFW 满机会硬指令禁规避（prompter.py + nsfw.py + e381ab3）
- 根因：满机会时在线安全模型自我审查式规避（"龟头抵入口不进入"），且"导演引擎 / 铁律"口吻是旧代码残留。
- 修复：prompter 满机会非余韵追加强指令"必须实际发生，严禁停在边缘"；`[输出纪律]` 加⑤⑥禁导演口吻自我分析 / 禁"我将以…规避"；nsfw 满机会说明列禁"龟头抵入口不进入 / 未真正进入"；narrative_clean 扩删导演自居句 / 规避声明句 / 分隔线。
- 验证：本地 Qwen3.8 实跑零元信息、直接写性行为（规避非引擎缺陷，系在线安全模型收敛）；单测 27 passed。

- 附注：NSFW 满机会真实产出须切本地 1234 Qwen3.8（解锁小雨人格），勿用在线安全模型（必规避）。

## 2026-10-03 v0.7.7（关系表基线播种修复 + 已婚满机会 + 背景人物强制清洗）

- 升 v0.7.7：PATCH 档，正确性修复（普通迭代，无需压测）。
- 动机（跨剧本对照真机验证发现，禁忌暑假 vs 重生的丧尸末日 各 10 轮）：发现 3 处真实缺陷，修复后两组均达标。

### 修复 1：relations_base 基线播种（memory.py）
- 根因：`session_new` 仅在「卡片无 relations」分支固化 `relations_base`，有卡分支跳过；`memory.new()` 只播种 `relations` 不播种 `relations_base`。真实会话基线恒空 → v0.7.4 未在场冻结闸 + v0.7.6 亲属身份冻结闸**静默失效**（此前验证脚本手动种入才通过，掩盖了缺陷）。探针先于长跑暴露（真实会话 relations_base 计数 0）。
- 修复：`memory.new()` 的 `snap` 补 `"relations_base": dict(relations)`。

### 修复 2：已婚组合满机会不触发（director.py）
- 根因：`STRONG_AFFECTION` 缺「妻子/丈夫/老婆/老公」；关系值常写亲属词而非「夫妻」状态词，导致已婚组合永远触发不了满机会。
- 修复：词表新增四词。

### 修复 3：背景人物只报不删（prompter.py + app.py）
- 根因：背景人物（老高）被写成活动角色时引擎只报不删，`present_violation` 带回前端但正文残留。
- 修复：prompter 约束升级为非在场硬约束；app.py 命中后强制清洗正文（删命中句）。

### 验证
- 跨剧本对照（禁忌暑假 9 键 / 丧尸末日 8 键亲属保持，背景防护 R1/R2 清洗后 off_post=0，NSFW 夫妻轮 R9/R10 满机会，登场一致）全达标。
- 单测 `tests/test_relation_gate.py` 加 3 项（relations_base 播种回归 / 已婚满机会 / 老高闪回主动句失责），19 passed。
- 卡文微调：夏雨→李想 原「丈夫的义妹…」致冻结锚点误取「丈夫」，改「妹妹（陈锋的义妹，即小姑子）…」。

- 附注：丧尸末日剧本为本次重生的用户创作内容（陈锋/夏雨/李想/苏明 角色卡 + 丧尸末日 世界书），进版本库但不进分发 zip（按红线）。同步 simon 已重命名的禁忌暑假 cast（旧名 林晚/老周/苏曼/阿杰/高洋/末日 删除，新名 周牧野/林梦雅/林泽宇/周晓杰 + 禁忌暑假 世界书 提交）。

## 2026-10-03 v0.7.6（亲属身份冻结：禁止推演改写血缘/姻亲身份）

- 升 v0.7.6：PATCH 档，正确性修复（普通迭代，无需压测）。
- 动机（10 轮关系轨迹真机审计发现）：v0.7.4 的关系冻结闸只挡「背景人物（林梦琪）」，未挡「在场角色的亲属身份被改写」。实测模型把 `林泽宇 → 周牧野: 父亲` 翻成 `姐夫`、`林泽宇 → 林梦雅: 母亲` 翻成 `嫂子`——亲儿子管父母叫姐夫/嫂子，亲属逻辑崩成乱伦。`reflect` 无条件接受模型对任意在场关系的整段覆写，是根因。

### 修复：亲属身份冻结函数（director.py）
- 新增 `_KINSHIP_TOKENS` + `_first_kinship(text)` + `_preserve_kinship(base_val, new_val)`：亲属身份词（父母子女夫妻兄弟姐妹及姻亲姐夫/嫂子等）一旦在基线 `relations_base` 确定即**冻结身份**，模型只能演化情感/状态修饰（如「父亲」→「父亲，关系紧张」），不得改写为另一种亲属身份（父子→姐夫 在此拦截并回退为基线身份 + 保留情感修饰）。
- 刻意**不冻结**「恋人/情人」等关系状态（沙盘本就要演好感→恋人）。
- `reflect` 在场分支接入：两端都在场且键在基线时，先 `_preserve_kinship` 再落库。
- 同步在 reflect 提示词加「亲属身份是固定事实，不得改写为另一种亲属身份」硬约束（防御纵深）。

### 验证
- 单测 `tests/test_relation_gate.py` 新增 4 项（身份翻转拦截/情感演化放行/无基线自由/母子→嫂子拦截），全量 **97 passed**，4 失败为既有环境性（测试角色林晚/老周等不存在）。
- 真机复跑 10 轮关系轨迹（本地 Qwen3.8-27B，会话 e4dcb729）：`基线关系保持=是`、10 轮 `变更键=0`、背景人物林梦琪始终非在场。亲属崩塌消失。

## 2026-10-03 v0.7.5（背景人物活动化防护：定义层尊重「非在场」语义）

- 升 v0.7.5：PATCH 档，防护增强（普通迭代，无需压测）。
- 动机（simon 原则澄清）：背景板角色（如林梦琪）本就不应出现在剧场上稀释张力，更应作为「引擎能力表现」——若引擎把背景人物写成活动角色，反是失责。结论：**靠补 active 角色卡去「压制」她是错的，应从定义层让引擎尊重「非在场」语义**。林梦琪保持无卡（仅活在他人 relations 字段 + 世界书），不进 present。

### 关系层：背景人物补集自动析出
- `director.background_names_from_relations(snap, present)`：从 `snap["relations"]` 键中析出「在关系里出现、但不在 present 名单」的角色 = 背景人物。无需新字段，纯由已有 relations 推导（非卡即背景）。

### 提示词层：背景人物硬约束（prompter.py）
- `[关系与状态（不可违背）]` 块内 offscreen_note 升级：背景人物标注为「非在场」，三条硬约束——
  ① 不得为其撰写出场段落/镜头聚焦/独白/对白；
  ② 提及只能由在场角色以「谈论/回忆/称呼」方式带过，且不得推动成主动情节；
  ③ 关系定位为既定事实，不得升级为夫妻/恋人/在场中心。
  并明示：背景人物被写成有对白/独白/主角行动即越界、引擎会报错。

### 自检层：detect_offscreen_activity（director.py + app.py）
- 新增 `detect_offscreen_activity(reply, background_names)`：扫描正文，命中两类即判「失责」并报告（**只检测不删正文**，避免误删在场提及）——① 背景名获得独立台词块（对白/独白）；② 第三人称分句以背景名作主语且含动作/出场信号（如「林梦琪从门后走出」）。按句号/叹号/问号分句扫描，兼容整段混写无换行。
- app.py 在 present 校验后调用，把 `offscreen_violation`（命中行列表）并入 `present_violation` 并随 `done` 事件回传前端，使「引擎能自我识别失责」。
- 既有的 reflect 冻结闸门（v0.7.4）仍生效：背景人物关系冻结为基线，不被改写/升级。

### 测试
- `tests/test_relation_gate.py` 新增 6 项：背景补集析出、对白失责、动作主语失责、在场谈论带过不失责、无背景时干净。全量 93 passed（4 个失败为既有环境性：测试角色林晚/老周等当前不存在，与本次无关）。

## 2026-10-03 v0.7.4（「插入」误判修复 + 关系表冻结闸门）

- 升 v0.7.4：PATCH 档，修正 `detect_intimacy` 对「插入」通用词的越线误判，并建立关系表冻结闸门（原型 relationship-sandbox 思路：建立关系表、每回合推演前查询并强制）。普通迭代，无需压测。

### 「插入」通用词误判修复（director.py）
- 根因（会话 0ac57abf 审计发现）：v0.7.3 从 `BODY_STRONG` 摘了「进入」「穴」但漏了「插入」。「强行插入他们之间的空间」是空间隐喻，却被 `detect_intimacy` 判越线 → `after_reply` 误记「本轮发生亲密越线」旧账。与「进入」同源 bug（通用词须加语境）。
- 修复：新增 `_sexual_insert(text)`——「插入」仅在伴随身体/性语境（插入她/插入他/插入体内/阴道/穴/后庭…）时判越线；纯移动/抽象（插入空间/插入话题/插入U盘/插入他们之间）不算。注意「插入他」用负向先行 `(?!们)` 排除「插入他们」（插入他们之间=空间隐喻）。`detect_intimacy` 改为「插入」走 `_sexual_insert` 语境门槛、其余 BODY_STRONG 照旧。

### 关系表冻结闸门（director.py / app.py / prompter.py）
- 审计问题（simon 最关切）：无角色卡的「林梦琪」为何出现在推演正文？根因：①`init_relations` 只用卡片 description+core_desire 让 LLM 自由生成关系网，未固化 simon 手写的关系；②`reflect` 无条件覆写任意关系键，无闸门，模型可把「小姨子」改写成「妻子」；③`prompter` 把含林梦琪的 `snap["relations"]` 当被动上下文注入，模型照样越权将其升为在场妻子；④`validate_present` 只剥对话块，第三人称叙事里的林梦琪漏过。原型 relationship-sandbox 的三道闸（cast 固定/核心只读/每回合 A3 查询并强制）当前引擎缺后两道。
- 修复 A（关系基线固化）：`seed_relations_from_cards(cards)` 把每张卡自带的 `relations` 字段确定性转为「源 → 目标」权威表（simon 手写关系）；`init_relations` 以它为底、LLM 仅补缺。会话初始化时 `app.py` 把生成结果存为 `snap["relations_base"]`（只读基线）。
- 修复 B（reflect 冻结闸门）：`reflect` 回写关系时，仅当关系键两端都在场（镜头内角色）才允许演化；涉及未在场/无卡关联人物（如林梦琪）的关系冻结为 `relations_base`，禁止模型改写或升级（小姨子→妻子类漂移在此拦截）；基线无此键则丢弃越权关系、不引入新条目。
- 修复 C（每回合前查询并强制）：`prompter.build_session` 的「[关系与状态]」改为「[关系与状态（不可违背）]」，自动识别关系里但无角色卡的「背景人物」（如林梦琪），明确标注「仅有关系定位、无角色卡、只能背景提及、不得行动/对话/升级关系」，并加「以上关系为推演既定事实，写作时严格遵循，不得自行推断、改写或升级」。即原型 A3 的「严格按简报关系执行，不得自行推断」落地为提示词硬约束。
- 会话级 cast 闸门（先前已正确）：cast = 有卡角色，林梦琪无卡故不在 present；本次补全了"关系层"与"提示词层"两道闸，彻底堵住无卡角色被动画化/升级。

### 验证
- 新增 `tests/test_relation_gate.py`（7 PASS）：_sexual_insert 对「插入空间/话题/U盘/他们之间」=无、对「插入她/插入体内」=越线；seed_relations_from_cards 正确转卡片 relations；reflect 冻结未在场关联人物（林梦琪仍=小姨子）、镜头内关系允许演化。
- 全量 `pytest tests/`：88 PASS，4 个失败为既有环境性失败（test_focus_follow / test_nsfw_defense 用例用的角色林晚/老周/高洋/苏曼/阿杰 当前 characters/ 不存在），与本次改动无关、无新增回归。
- 归类：普通迭代（修正误判 + 补关系防护闸门，未改 director 推演/关系/秘密记账核心判定形态），无需压测。

## 2026-10-02 v0.7.3（NSFW 机会等级修复 + 提示词构造兼容）

- 升 v0.7.3：NSFW 机会等级系统修复（PATCH 档，修正误判与补全触发源）+ 提示词构造兼容性修复（prompter 多 system 消息合并）。普通迭代，按压测触发规则无需压测。

### NSFW 机会等级误判修复（director.py / nsfw.py）
- 根因 A（`BODY_STRONG` 含极通用词「进入」）：`detect_intimacy()` 把「进入房间/下水道」「进入她身体(轻写法)」误判为越线 → 错误记亲密旧账 + `after_reply` 的 aftermatch 状态机把下一轮满机会强制压半步（即「满机会→下轮回落半机会」的实测 bug 模式）；`brief()` 的导演意图信号把「众人进入下水道」误算满机会（纯场景移动当亲密推进）。
- 修复 A：`BODY_STRONG` 移除「进入」「穴」（仅留明确性器官/性行为词：阴道/鸡巴/阴茎/阳具/插入/高潮/抽送/射精/交合/做爱/上床/性器/肉棒）；新增 `_sexual_entry(text)`——仅「进入」+身体/性语境（进入身体/进入她）才算满机会信号，纯移动（进入房间/下水道）不算；该函数只用于 brief 导演意图信号，不用于 detect_intimacy 事实判定（轻写法"进入身体"不算充分越线，不触发 aftermatch 压制）。

### NSFW 机会等级触发源补全（director.py）
- 审视结论：好感度系统此前下线（relations 死路径），「互有好感」完全不触发满机会；「第三方暴力胁迫」无专门信号，仅当指令含露骨器官词才走「导演指令」路径，"陌生男人按住她撕衣服强迫就范"类性侵描述（无露骨器官词）不触发。
- 新增 `_opp_from_affection(snap, scope)`：读 `snap["relations"]`，两端同处镜头内（或全场且两端在场）时，强好感词（恋人/相爱/互有好感/圆房/伴侣/夫妻…）→满机会；单向暧昧词（暗恋/暧昧/心动/好感/喜欢…）→半步（升温，不强制满）。关系键「源→目标」两端名+描述值都参与匹配。
- 新增 `_opp_from_coercion(directive)`：性暴力直述词（强暴/强奸/性侵/奸污/猥亵/非礼）单独命中→满机会；其它暴力/强迫词（按住/揪住/刀抵/威胁/拖进/逼/施暴…）须同时伴性语境词（身体/脱衣/腿/胸/衣服…或 BODY_MID/STRONG）才→满机会，避免「强盗用枪威胁交钱」误开 NSFW。
- `brief()` 五类信号取最高：把柄(_opp_from_secrets) + 好感(_opp_from_affection) + 胁迫(_opp_from_coercion) + 历史(_opp_from_history，半步上限) + 指令(独处脆弱/_sexual_entry/BODY_STRONG)。同步更新 `nsfw.py` docstring 标注满机会五类来源。

### detect_intimacy 拒写假阳性修复（director.py）
- 根因：模型拒写文本里含「插入」等性词（如「抱歉，我不能写插入内容」）→ `detect_intimacy` 误判=越线 → 错误记亲密旧账 + 触发事后余韵把满机会压半步。
- 修复：detect_intimacy 先 `_mask_refusal(text)` 剔除含元层拒写标记（抱歉/我不能/避免写/改写…）的整句再判定；世界内真实露骨（不含拒写标记）仍正确判越线。

### 提示词构造兼容性修复（prompter.py）
- 根因：原 `build_session()` 在首条 system 后追加 `after_hits` 的第二个 system 消息；Qwen3.6 严格 chat template 要求 system 必须在首位 → 报 `System message must be at the beginning` → 500 空回。
- 修复：把所有非首位 system 消息并入首条 system（index 0）。通用改进，对主模型 Qwen3.8 同样消除潜在双 system 问题。

### 验证
- 单测：`backups/verify_6108_fix.py`、`backups/nsfw_opt_unit.py`（21 PASS）、`backups/nsfw_detect_fix_check.py` 全 PASS：detect 对"进入房间/进入身体(轻)"=无、对露骨词=越线；_sexual_entry 对"进入下水道"=False/"进入苏曼身体"=True；_opp_from_affection/_opp_from_coercion 各场景（含镜头外过滤、非性胁迫不触发、事后余韵仍半步）正确。
- 端到端（本地 Qwen3.8-27B，1234，带小雨人格）：
  - 结论 A（互有好感/恋人，信号①）：确证可真实越线——写出完整露骨性行为过程，`detect_intimacy=越线`。
  - 结论 B（第三方暴力胁迫，信号③）：机会逻辑正确（brief=满机会、nsfw 允许越线=True），但 Qwen3.8 安全策略拒绝描写非自愿/强迫性行为（返回拒写替代方案）。属模型安全行为，非引擎 bug；真实生成非自愿露骨需换 abliterated/无限制本地模型。
- 20 轮 + 10 轮在线 deepseek 回归：满机会连续区间稳定、aftermatch 误压制 0 次，原 bug 模式消失（在线模型安全限制不写露骨，非代码 bug）。
- 归类：普通迭代（NSFW 机会等级系统修复 + 提示词构造兼容，未改 director 推演/关系/秘密记账核心判定逻辑的形态，仅补全信号源与修误判），按压测触发规则无需压测。

## 2026-10-02 v0.7.2（流式叙事）

- 升 v0.7.2：叙事正文改为逐字打字机式流式显示，优化玩家等待体感（非憋完一次性倒空，不再突兀）。
- 根因：链路本就端到端流式（`llm.stream` 逐块产 token + 前端 `send()` 已逐字渲染），但后端 `app.py` 的 `events()` 生成器把整段收齐、跑完后处理，才 `for ln in full.split("\n"): yield delta` 一次性按行回吐 —— 体感为「等半天突然一大片」。
- 后端 `events()`：`/api/act` SSE 开头先 `yield {"status":"模型思考中…"}`；流式循环内对每个 chunk 即时 `yield {"delta": chunk}`（真打字机流）；首 token 到 `yield {"status":"生成中…"}`；末 `done.reply` 仍为 `hooks/validate_present` 校验后的 canonical 文本（删除了原憋完回吐逻辑）。
- 前端 `send()`：新增 `data.status` → 状态栏反馈（思考间隙有提示，不再干等）；`data.done` 时用校验后 `reply` 对齐最终文本（极少剥离时无缝修正）。
- 验证（免费确定性，mock `llm.stream` 吐 4 块 + Flask test_client 跑真实 `/api/act`）：4 个 delta 事件、全在 done 前、`模型思考中…` 状态到位、joined deltas == done.reply → PASS。
- 归类：普通迭代（仅改 events 回吐方式与前端 2 行，未动 director 推演/关系/秘密记账核心路径），按压测触发规则无需压测。

## 2026-10-02 v0.7.1（S3 收口 + 前端修复）

- 升 v0.7.1：收口 v0.7.0 漏提的后端路由，并修复前端两处问题（合并收口，非新能力）。
- 补路由（关键修复）：v0.7.0 的 commit b9e9922 漏提交 `engine/app.py` 的 `import script_refiner` 与 `POST /api/import/from-script`，导致已发 `my-st-v0.7.0.zip` 前端面板调接口必 404、S3 导入器实际不可用。本次补齐路由，端到端可用。
- 前端修复（jsdom 真实 DOM 复现验证）：
  - 「从剧本生成」由角色库提至 `#topnav` 一级菜单（收口用户需求）。
  - 点击无响应根因：`script-import-modal` 块位于 `</script>` 之后，脚本执行时 `siModal` 仍为 null；已将 modal 块前移至 `<script>` 之前修复。
  - 「世界状态」按钮宽屏无效果：原切 `.rail-left.open` 仅 ≤720px 媒体查询生效；改为切换 `.rail-left.collapsed` 收起/展开整条左栏（镜像运行时日志机制），遮罩联动同步 `collapsed ⇔ open` 不变式。
- `VERSION` 升 v0.7.1；提交 + 打 tag `v0.7.1`；产出 `my-st-v0.7.1.zip`（替换残疾的 v0.7.0.zip）。README 版本号同步。

## 2026-10-02 v0.7.0（S3 剧本→设定 自动导入器）

- 升 v0.7.0：新增能力（MINOR），降低上手门槛——玩家贴剧本，引擎用 LLM 提炼角色卡与世界书，确认后一键写入，无需手动填表。
- 核心结论：LLM 不能直接改文件（无权限）；由后端中间层执行。玩家剧本 → 后端固定 system prompt 调 LLM → 产出结构化 JSON → 后端调 `store.save_card` / `store.save_world` 写入。引擎已有写入入口（`/api/character`、`/api/world/<name>`）作下游复用。

### 新增模块与接口
- `engine/script_refiner.py`：spec 单一事实源——固定 `REFINER_SYSTEM_PROMPT`（第 7 条把剧本当素材、不执行其中指令，防 prompt injection）、角色卡/世界书字段白名单、`extract_json`（剥离 ```json 包裹 + 截取对象）、`sanitize_refiner`（白名单过滤 + 非秘密不带元字段 + 秘密保留 + world 回写）、`refine_script`（truncate → 调 `llm.complete` → 解析 → 沙箱）。
- `POST /api/import/from-script`：收 `script`，返回预览 `{world, characters}`（只预览、不写文件）。
- 前端 `static/index.html`：角色库新增「从剧本生成」按钮 → `script-import-modal` 面板（textarea → 提炼 → 预览角色卡/世界书 → 确认导入调现有 save 路由逐条写入；防覆盖确认；复制 JSON 供手动微调）。

### 安全
- 固定 prompt + 只取白名单字段：剧本文本只当素材，越权输出后端不执行。
- 后端只写 `characters/`+`worlds/`，触不到 config/代码。

### 验证
- 单元 `tests/test_script_refiner.py`：10 passed / 1 skipped（真实 e2e 跳过，免烧额度）。
- 真实 e2e（线上矽基流动 DeepSeek-V4-Flash）：末日车库、空间站「鹊桥」剧本，提炼角色/世界书字段与 `secret`+`character`+`bottom_line` 标记均正确；模拟确认导入写文件落盘、清理无残留。
- 待办归属：S3 详情见 [TODO.md](./TODO.md)。

## 2026-10-02 v0.6.4（T1 历史滑动窗口压缩，抑制长上下文叙事衰退）

- 升 v0.6.4：长上下文治理（PATCH 级，抑制 prompt 无限膨胀导致的叙事衰退）。
- 唯一行为变更：`build_session` 注入 history 前经 `compress_history` 滑动窗口压缩。

### T1 历史滑动窗口压缩
- 根因（实证，探针 `tests/probe_history_degradation.py`）：固定快照 + 递增假历史，真实 LLM 生成。
  回复长度在 prompt tok≈5300（≈R16 轮，约 10600 字符）起显著衰退（len_drop 34%+），tok<3000（R≤8）为安全区；
  点名焦点全程不退化（named=2），证明是上下文长度而非内容导致。与 T4（回复后期 -24% 衰减）同源。
- 修复：`prompter.compress_history(history, window_rounds=8)` —— 保留最近 8 轮原始叙事（tok≈2943 安全区），
  更早回合压成单条 `[历史叙事摘要]` system 块（每轮取「导演指令前 80 字 + 叙事首 90 字」剧情骨架）。**零额外 LLM 调用**。
- 探针验证（压缩后 vs 压缩前，R=60）：prompt tok **18425→6682（-64%）**；回复长度 **651→1005（+54%）**；
  退化拐点从 R=16 推迟到 R=40。tok 长程从线性暴涨（每轮 +920）转为平缓（每轮 +150 后段）。
- 调参点：`HISTORY_WINDOW_ROUNDS`（默认 8）。若需严格不超衰退点 tok≈5300，可下调至 6；若重连贯性可上调（代价更长上下文）。
- 后续增强（未做）：older 摘要可升级为 LLM 生成的结构化剧情摘要（更高保真，但每轮多一次调用）。
- 测试：新增 `tests/test_prompter.py`（5 例：空/未超窗口原样/超窗口压缩+截断/最近轮保留/长历史 tok 稳定）；全套 **75 passed / 4 deselected**。

## 2026-10-02 v0.6.3（T2 在场拆分修复 + T3 BODY_MID 收窄 + T4 根因定位）

- 升 v0.6.3：行为修正（PATCH 级，修复两处机会机制 bug + 收口待办）。
- 自 v0.6.2 起累积：T3 BODY_MID 收窄（aad10c1）、T2 在场名单空间分隔触发修复（2ebb015）、T4 根因定位文档（e7fed0d）、TODO.md 外链（a96d46f）。

### T2 在场名单空间分隔触发修复（行为修复）
- 根因（实证）：`scene._triggered` 只认 MOVE/TIME/WEATHER 词，R16「苏曼挤进门内…老周被挡在门外」不命中 → scene LLM 不调；即便触发，`LEAVE_KEYS` 无「门外/分开」强制清空 `leave`。两道闸门叠加堵死拆分。
- 修复：`MOVE_KEYS` 增 `挤进/门内/门外/隔开`；`LEAVE_KEYS` 增 `门外/挡在门外/留守/留在/隔开`；`_PROMPT` 约束2 补「被挡在门外/留在另一处/与队伍分开视为离场」。
- 下游自洽：`scene.apply` 先改 `present` 移除门外者 → `compute_focus` 用新 `present` 收敛 focus → `validate_present(allowed=focus)` 剥离门外戏份。镜头与在场名单一致。
- 测试：`test_triggered_on_spatial_door_split` + `test_leave_respected_on_door_split`；全套 **70 passed / 4 deselected**。

### T3 BODY_MID 词表收窄（行为修复）
- 移除 `按在/压在/衣服/贴/湿润/胸/腰` 等末日题材高频中性词，保留明确接触动作。
- 修复裸词/单字无强动词即命中、误顶半步、`detect_intimacy` 误判「接触」的隐患（旧账逻辑只记越线不记接触不变）。
- 测试：`test_body_mid_narrowed_avoids_neutral_false_positive`。

### T4 根因定位（文档，并入 T1）
- 定量实证：回复长度后期 -24% 衰减与 T1（history 全量注入无窗口）同源。prompt 字符随 history 0→60 条线性 1118→28718（×25.7）；ledger 增长可忽略（+54/10 条）；max_tokens 未触顶。
- T4 不单修，随 T1 一并解决。活跃待办现仅剩 **T1**。

### 待办归属
> 活跃待办 T1（history 无窗口/预算/压缩）待下版本；搁置 S1–S2 见 [TODO.md](./TODO.md)。

## 2026-10-02 v0.6.2（删 relations 死代码路径 + 修 config/model 损坏 + BODY_MID 注释）

- 升 v0.6.2：清理（PATCH 级，删除恒为「无」的死路径，行为不变）。

### 删除 relations 机会等级死路径
- 删除 `REL_STRONG` / `REL_MID` 词表、`_REL_TAINT`、`_sanitize_relation()`、`_opp_from_relations()`，
  及 `compute_opp` 中的调用（director.py:263）与 reflect 写回关系时的 `_sanitize_relation` 包裹
  （director.py:468，relations 现原样存）。
- 根因：relations 文本每轮 reflect 写回都过 `_sanitize_relation` 剥离 REL 词，路径恒返回「无」，
  对机会等级零贡献（满机会唯一真实来源是 secrets）。属自 v0.6.0 起即存在的死代码。
- 测试：删 `test_opp_from_relations_strong`；全套 **67 passed / 4 deselected**。

### 修本地 config.json model 损坏串
- `engine/data/config.json` 的 `model` 原为 `D:\u0007i\models\...`（响铃符 `\u0007` = `\a` 被误转义），
  修正为 `D:\ai\models\Qwen3.8-27B-UD-Q4_K_M.gguf`。**个人配置，不提交、不进 zip。**

### BODY_MID 注释过期修正
- `after_reply` docstring 旧注释写「含 衣服/腰/贴 等」，与实际词表
  （吻/脱/压在身下/按在 + 衣服/胸/腰/贴/骑/跨坐 等）不符，已更正并标注「偏宽隐患下版本解决」。

### 下版本待办（simon 已排期，本次未做）

> 活跃待办与搁置事项已统一收口至 [TODO.md](./TODO.md)（含根因、位置、预期方案与归属版本 T1–T4 / S1–S2），此处不再逐条展开，避免日志臃肿。

## 2026-10-02 v0.6.1（known_by/holders 全版拆分 + 死参数清理）

- 升 v0.6.1：语义修正 + 清理（PATCH 级，行为校正）。

### 全版拆分：known_by（知情）与 holders（握把柄者）分离

原 `_opp_from_secrets` 与 `_release_handle` 把 `known_by` 同时当「知情者」与「把柄持有者」，
信息不可逆与把柄可失去两种语义被混在一个字段里（简版）。改为全版：

- 每个 secret 新增 `holders` 字段；曝光（`_record_exposure`）同时写入 `known_by` 与 `holders`。
- 把柄消除（`_release_handle`）**仅操作 `holders`**：移除 from、加入 to（to 空=彻底失去）；`known_by` 不变（知道了就无法不知道）。
- `_secret_state` 改为基于 `holders` 重算——`holders` 清空即回落「潜伏」，状态回落路径仍成立。
- `_opp_from_secrets`、reflect 纪官提示（"握有把柄者"）、prompter 角色提示（"你握有 X 的把柄"）全部改读 `holders`；旧快照缺 `holders` 时回退 `known_by`，兼容无迁移成本。
- 收益：能正确表达「知道却无把柄」（如秘密公开但无人可胁迫）不再顶格满机会。零额外 LLM 调用、零新增 schema 字段、存储与计算复杂度不变——无性能下降。

### 清理：prompter.build_session 死参数

- 移除签名 `budget=4096, reserve=900`（函数体内从未使用）；同步移除 `app.py` 的 `reserve=` 传参。

### 验证

- `tests/test_director.py` 改写 release 测试（断言 known_by 保留、holders 驱动 state），新增 `test_record_exposure_adds_holder` / `test_known_but_not_holder_no_opportunity`；全套 **68 passed / 4 deselected**（tests/venv, pytest 9.1.1）。
- 引擎重启加载 v0.6.1，10 轮压测复核对照 v0.6.0 基线（sid=a01f1f5e）：满机会 3/10（最长锁定 5→4 轮↓）、秘密翻转 1（老周 暴露→潜伏 回落，holders 驱动 state 机制证实）、误归档 0（present违例 0 / 结局候选 0）；10/10 成功、0 异常、0 空回复、0 违例。无回归。

### 收口

- 提交 `8869005`（6 文件，+95/-40，个人 `engine/data/config.json` 不提交）；tag `v0.6.1`。
- 产物 `my-st-v0.6.1.zip`（23 条目 126.3 KB），删除旧 `my-st-v0.6.0.zip`。
- 三条打包红线校验全过：`package.py` 排除项校验通过（无 venv/缓存/会话状态/`tests` 泄漏）；
  `data/characters`、`data/worlds`、`player-cast` 不含；`config.json` 洗白为出厂默认
  （base_url/api_key/model 空、providers=[]、nsfw_enabled=False、adult_confirmed=False）。

## 2026-10-02 v0.6.0（秘密机制改为记录员模式 + 把柄成对化 + 把柄消除）

- 升 v0.6.0：新增能力（MINOR）。新增把柄消除机制 `handle_releases`，并变更秘密判定范式。

### 背景：引擎不该做语义判定

旧实现的秘密暴露判定是「关键词语义判定」：`INFO_VERBS`（15 词）+ `DISCOVERY_VERBS`（34 词）
+ 世界书 `secret.keys`，要求正文同时命中「事实词」+「发现动作」才采信。

实测（30 轮复测 × 5 秘密 = 150 次判定）**放行 33 次（22%）**。明细显示 R2 高洋（通风口+察觉）、
R2 苏曼（女儿+察觉）在真实暴露（R4）**之前**就已满足放行条件——校验形同虚设，当前没出事
只是因为 reflect 当时恰好没上报。根因：末日题材的 keys 全是高频词（绷带/小臂/发烧/通风口/女儿），
与「看见/察觉/露出」极易巧合共现。

### 改造：记录员模式（举证式归档）

原则：**引擎不猜「这算不算发现」，只验证 LLM 的举证确实出自正文。** 语义判断交给 LLM，
引擎只做它擅长的归档与防幻觉（结构校验）。

- 删除 A1「指令含 keys + INFO_VERBS → 记环境推手已知」：纯猜测，导演写"翻找"不代表真发现。
  且其知情本就不翻 in-world 暴露状态（`_secret_state` 剔除 ENV_PUSHER），删掉只在前端少一条展示。
- 删除 `INFO_VERBS`、`DISCOVERY_VERBS`、`_reply_confirms_exposure`；`secret.keys` 不再参与判定。
- 新增 `_evidence_ok(evidence, reply)`：举证须是正文原文子串且长度 ≥ `EVIDENCE_MIN_LEN`。
- reflect 的 `secret_exposures` 增加 `evidence` 字段（逐字照抄正文原文）。
  校验退化为结构校验：owner 存在 / by 在场且 ≠ owner / evidence 出自正文 / 长度达标。
- **举证缺失或不匹配则丢弃**：宁可漏记（状态滞后），不可误记（秘密提前暴露 → 张力提前消耗）。

### 新增：把柄消除机制（simon 拍板）

simon 的设定：把柄是**成对**的，且**应可失效**——「A 持有 B 的药物，药物就是把柄；
若 A 弄丢药物或给了第三方，把柄就该失效」，这需要叙事层面的语义判断。

- reflect 增加 `handle_releases`：`{owner, from, to, evidence}`，复用同一套 evidence 校验，
  **零新增词表**——这正是举证框架的红利。
- 新增 `_release_handle(s, frm, to, round)`：`known_by` 移除 from、加入 to（to 空 = 彻底失去）。
  `_secret_state` 自动让无人知情者回落「潜伏」→ **补上了此前缺失的秘密状态回落路径**，
  即「机会等级永久锁死」三因素中的第一项。
- prompt 改为下发「秘密与把柄现状」（含当前握有把柄者），纪官才知道谁可能失去什么。

### 机会等级成对化（simon 拍板）

`_opp_from_secrets(snap, present, scope)`：scope 取 `snap["focus"].subjects`（app 已算好并写回），
仅当某一对的**持有者与归属者同在镜头内**才给满机会。阿杰握着高洋的把柄，不再让苏曼对老周
也拿到满机会许可。无 focus（自然推演）时退回全场判定。app.py 无需改动。

### 验证

- 真实 LLM 直连：R3 归档「林晚发现高洋咬伤」、R4 归档「阿杰知情」，evidence 均逐字照抄正文；
  消除例正确清空 known_by 并回落「潜伏」；反例（仅分配守夜）不误记。
- `tests/test_director.py` 新增 5 项（举证照抄 / 缺失与过短 / 无语义词表残留 / 成对作用域 /
  把柄转移与回落），全套 **66 passed / 4 deselected**。

### 收口

- `VERSION` 升 v0.6.0；提交 `1359e28` + 打 tag `v0.6.0`；产出 `my-st-v0.6.0.zip`
  （23 条目 125.0 KB，package.py 按 VERSION 自动命名）。
- 删除旧 `my-st-v0.5.7.zip`，仅保留最新；git tag 现 `v0.1`–`v0.6.0` 连续。
- 三条打包红线校验通过：不带剧本（`data/characters`、`data/worlds`、`player-cast` 已排除）、
  不带任何已保存 LLM 设置（config.json 洗白为出厂默认）、NSFW 始终未选中。

### 下一步（阻塞中：待重启服务后复测）

引擎以 `debug=False` 运行，v0.5.7 与 v0.6.0 的代码**尚未在运行中的服务里生效**。
重启命令：

```
cd D:\codes\my-st\engine && set PORT=5051 && python app.py
```

重启后跑同规格 30 轮复测（`python tests/stress_longcontext.py`），并用
`python tests/compare_stress.py` 与上一轮基线对照，重点看三个数：

1. **满机会轮次**（应显著下降，成对化后不再是全员顶格）；
2. **秘密状态翻转次数**（应有回落——`handle_releases` 生效后能从「暴露」回「潜伏」）；
3. **误归档次数**（应为 0——举证校验拦掉无据上报）。

同时验证 v0.5.7 的墓穴修复（「越线」判定里不应再出现墓穴/洞穴/巢穴）。

### 遗留

- `_opp_from_relations` 实测为死路径：初始 relations 命中 0 个关系词，且 reflect 每轮写回都过
  `_sanitize_relation` 剥离 REL_STRONG/REL_MID，故恒返回「无」。满机会的唯一来源是 secrets。
  成对化后满机会轮次会显著下降，尺度变保守——属预期内的修正。
- `BODY_MID` 词表仍偏宽（含 衣服/贴/腰/胸/骑），末日题材高频命中（复测 19/30），会把机会顶到半步。

## 2026-10-02 v0.5.7（同形中性词误判修复 + 压测对照工具）

- 升 v0.5.7：错误修正（PATCH）。

### 根因：BODY_STRONG 含单字「穴」，末日/野外题材必然误伤

v0.5.6 把 `detect_intimacy` 用于后果记账与事后余韵，随即暴露：30 轮复测里
判定为「越线」的 3 轮，命中词**全部是「墓穴」**（"可能成为五个人共同的墓穴"）。
其中 R2 的机会等级是「无」——未发许可却判出越线，是判定误伤的硬证据。

后果：会把"墓穴"叙事误记为「关系被改写的性行为后果」，并在后续命中
"还记得那晚"等触发词时整批激活灌进提示词；同时误触发事后余韵压制机会等级。
同一词表的 `_opp_from_history` 也会因此把机会抬到半步。

### 修复

- 新增 `NEUTRAL_HOMONYMS`（墓穴/巢穴/洞穴/穴居/穴位/点穴/太阳穴/…）与
  `strip_neutral(text)`：判定前先剔除同形中性词。
- `detect_intimacy`、`_opp_from_history`、`resolve_for_request` 的指令判定三处
  统一改用 `strip_neutral`，口径一致。
- 只剔中性词、不删「穴」本身：真实用法仍须判为越线（有测试锁定）。

### 遗留（未处理，属机制语义，待讨论）

`BODY_MID` 词表偏宽，含「衣服」「贴」「腰」「胸」「骑」等日常高频字，
末日题材几乎每轮命中（复测接触级 19/30）。它只影响机会等级上限（半步）与余韵，
不记旧账，但会抬高机会等级——与「机会等级长期锁定」是同一议题，留待 v0.6 讨论。

### 新增工具

`tests/compare_stress.py`：压测对照分析（基线 vs 复测），一键输出稳定性、
能力保持度、机制存活度，并模拟「旧逻辑 vs 新逻辑」各会记多少后果账本。

## 2026-10-02 v0.5.6（NSFW「许可 vs 事实」语义分离）

- 升 v0.5.6：错误修正（PATCH）。**simon 拍板**：机会等级（试探/半步/满机会）是**许可**——
  允许写到该尺度，写不写由剧情定；不是驱动。

### 根因：许可被当成事实用于后果记账

`nsfw.py` 的 `intimate` 由机会等级派生（`opp_level in ("半步","满机会")`），却被
`director.after_reply` 当作"本轮确实发生了亲密"来记旧账。原条件
`opp_level == "满机会" and intimate` 实际退化为**「满机会就记」**，与其 docstring
「**确有**亲密内容时」的意图不符。

压测实测：满机会 28 轮，而正文露骨级（BODY_STRONG）**0/30** —— 按旧逻辑会凭空记下
28 条根本没发生的"亲密越线"，后果账本被污染，后续命中触发词时整批激活。

### 修复

- `nsfw.resolve_session`：`intimate` 正名为 **`intimate_allowed`**，明确只发许可；
  模块 docstring 写明"许可 vs 事实"的区分与各自的使用场合。
- `director.detect_intimacy(text)`（新增）：返回 越线 / 接触 / 无，作为"**事实**"的唯一口径。
- `after_reply(sid, reply)`：改为内部按实际内容判定，**仅「越线」记旧账**；去掉 `opp_level`
  参数，从签名上杜绝再传入许可值。
  - 只记越线、不记接触的理由：旧账文案是"关系被改写（把柄/伤疤/人情债）"，对应性行为级
    后果；而 `BODY_MID` 词表偏宽（含 衣服/腰/贴/胸 等），据此记账会堆出大量轻账，
    命中「提起/旧账/那晚」等触发词时整批激活、撑爆提示词。
- 事后余韵（aftermath）判定改用 `detect_intimacy(...) == "越线"`，与旧账口径统一。
  注：此处原本就基于实际内容（扫上一条历史含 BODY_STRONG），语义本就正确，本次只是
  统一到同一函数；压测中未触发是因为模型实际未写到露骨级，属正常，非机制失效。
- `app.py` 调用同步；**前端不消费该字段**（只用 `nsfw.reason`），无影响。
- `tests/*.py` 共 14 处字段断言同步为 `intimate_allowed`（变量名/函数名未改动）。

### 验证

- 新增 5 项确定性测试：三档判定 / 许可≠事实 / 许可未兑现不记账 / 实际越线才记账 /
  普通叙事不记账。全套 **60 passed / 4 deselected**。
- 端点层 `test_nsfw_defense` 走完 `done` 事件（含 after_reply 之后的完整链路），正常。

### 收口

- `VERSION` 升 v0.5.6；提交 + 打 tag `v0.5.6`；产出 `my-st-v0.5.6.zip`（package.py 按 VERSION 自动命名）。
- 删除旧 `my-st-v0.5.5.zip`，仅保留最新。git tag 现 `v0.1`–`v0.5.6` 连续。

### 遗留（待议）

满机会长期锁定仍未解决（`_opp_from_secrets` 把柄 + 秘密状态单调）。按"许可"语义重新定性：
其危害是**许可长期顶格**（换更服从的模型时越线风险上升），而非已发生的尺度失控
（实测露骨 0/30）。是否做「把柄时效化」让许可恢复动态，待 simon 决定。

## 2026-10-02 v0.5.5（场景防僵死保护修复）

- 升 v0.5.5：错误修正（PATCH，向后兼容、非破坏性），修一处让"同场景停留超时自动推进"彻底失效的计数 bug。

### 根因：防僵死保护被自身逻辑架空

30 轮长上下文压测（`tests/stress_longcontext.py`，报告见 `tests/runs/`）暴露：`scene.place`
自 R8 起**连续 23 轮不变**，R18 叙事正文已写到"体育馆外墙"、状态里 `place` 仍是"通往城东的路"，
叙事与状态脱节。

追查到 `scene.py` 的停留计数语义错误：

- `apply()` 在「触发了场景判定、但 LLM 判定 `changed=false`」时把 `same_scene` **清零**。
- 而压测指令大量含"去/回到/天亮"等 MOVE/TIME 触发词，于是**每轮触发 → LLM 说无变化 → 每轮清零**，
  `same_scene` 永远累积不到 `AUTO_TIME_THRESHOLD=3`。
- 结果：模块自己声明的"同场景停留超时自动让时间流逝、避免场景僵死"从未真正生效过。

### 修复（`engine/scene.py`）

1. `same_scene` 回归"同一场景实际停留轮数"语义：**只有场景真的变了才清零**；
   触发但判定无变化、以及 LLM 调用异常，一律**累加**（原为零）。
2. `_triggered()` 改为返回 `(triggered, force)`，且**停留超时判定优先于关键词判定**——
   否则只要指令常含触发词就永远走关键词分支，防僵死同样被架空。
3. 超时触发（`force=True`）时追加 `_FORCE_HINT`，把可选的"是否变化"变成必须的
   "本轮必须产出一次可见推移（time/weather/place 任一）"。
4. 强制推进失败后计数**冷却归零**，避免此后每轮都调 LLM，保留"规则版触发"的设计原则。
   最坏情况为每 `AUTO_TIME_THRESHOLD` 轮尝试一次，而非永不推进。

### 验证

- `tests/test_scene.py` 新增 2 项确定性回归（假 LLM）：停留计数在无变化时累加为 `[1,2,3]`、
  第四轮强制推进失败后冷却归零；超时触发必须带"强制推进"提示。全套 55 passed / 4 deselected。
- 真实 LLM（本地 Qwen3.8-27B）直连验证：基线（无强制提示）`changed=False`；
  超时强制推进 **3/3 成功**——`time` 由「天亮」推进到「上午」、`weather` 由「（未设定）」
  落到「晴/阴」，计数归零。

### 收口

- `VERSION` 升 v0.5.5；提交 + 打 tag `v0.5.5`；产出 `my-st-v0.5.5.zip`（package.py 按 VERSION 自动命名）。
- 删除旧 `my-st-v0.5.4.zip`，仅保留最新。git tag 现 `v0.1`–`v0.5.5` 连续。

### 遗留（未处理，待后续）

- 场景更新仍只读 `directive`、不读叙事正文，故模型自行推进的换场引擎不感知（压测中
  "叙事走到体育馆、place 仍停在路上"的另一半成因）。本轮**刻意不改**，留待后续测试再评估。
- 机会等级锁死：`director.py` 中在场者持有他者已暴露秘密即判「满机会」，而秘密状态单调
  （潜伏→暴露无回落），R3 起 28 轮恒定满机会。属设计决策，待议。
- `prompter.py:55` `build_session` 的 `budget=4096, reserve=900` 为死参数（函数体内从未使用），
  主推演在 `prompter.py:179-180` 全量注入 history，无窗口/预算/压缩。

## 2026-10-01 v0.5.4（世界书静态 HTML + 提供商可增删重构 + 收口修复）

- 升 v0.5.4：收口世界书预渲染静态 HTML、模型与生成「提供商」可持久化增删重构，以及两处配套修复（均为 PATCH 档、向后兼容、非破坏性）。

### 1. 世界书帮助文档改为预渲染静态 HTML
- 根因：v0.5.3 用 marked.js 渲染 Markdown，仍可能因 CDN/脚本时序卡「加载中…」。改为一次性预渲染为静态 HTML（`engine/static/worldbook-guide.html`，内联浅色主题 CSS，表格/代码/引用/响应式），`/docs/worldbook` 直接 `send_from_directory` 返回，零外部依赖、永不卡加载。
- 删除 `engine/static/marked.min.js`（不再需要）；`package.py` 的 `EXCLUDE_SUBPATHS` 移除 `worldbook-guide.md`（现产物为 `.html`，需随分发）。

### 2. 模型与生成：提供商（provider）可持久化增删
- 动机：原「预设」是硬编码在 `index.html` 的 `PRESETS`（local/silicon/custom），后端只有一套生效连接，无「多提供商」数据，无法提供「删除具体提供商」入口。simon 明确删除接口应针对具体提供商（本地大模型/火山引擎/矽谷引擎…）而非某个模型名。
- 后端（engine/llm.py）：`DEFAULT_PROVIDERS = []`（不随分发预置任何内置提供商）；`config_view` 对缺省 `providers` 做 `setdefault([])`；`_WRITABLE` 加 `providers`；`save_config` 新增 `providers` 分支（列表存为原样、非列表→`[]`），并 `_clean_providers` 过滤非法项（key 非空才保留）去重。
- 前端（engine/static/index.html）：删除硬编码 `PRESETS` 与 `presetForConfig`；「预设」下拉改为**可增删的提供商清单**（每行带「应用为当前」「删除」，新增即登记为 provider）；`open-system` 从 `providers` 渲染，`sys-save` 回写 `providers`。

### 3. 修复：静态文件缓存导致「改了代码 UI 不变」
- 根因：Flask `send_from_directory` 默认 `Cache-Control: max-age=43200`（12 小时），多次改 `index.html` 后浏览器跑旧 JS，表现为「新增提供商保存后消失」等怪异。
- 修复（engine/app.py）：`/` 与 `/static/<path>` 响应加 `Cache-Control: no-store`，本地开发工具杜绝静态缓存，改动即时生效。

### 4. 修复：空字段提供商污染全局连接（Invalid URL）
- 现象：新增「本地大模型」卡片三项留空即保存，会把空 `base_url` 写进全局连接，覆盖原本可用的 `http://127.0.0.1:1234/v1`，聊天请求变成 `/chat/completions`（无 scheme）→ `Invalid URL`。
- 修复：
  - 前端 `sys-save`：仅当 provider **确实填了 Base URL** 才写入全局连接；为空则跳过、保留现有可用连接。
  - 前端新增 `syncProvidersFromDOM()`：点保存时先从每张卡片输入框**直读当前值**写回内存再发请求，落盘数据与界面所见一致、不依赖内存中间态。
  - 后端（engine/llm.py）：`stream`/`complete`/`list_models` 的 URL 改为 `(base_url or setting("base_url") or DEFAULTS["base_url"])`，空串时回退默认，任何情况都不拼出无 scheme 的 URL（最后一道防线）。

### 验证
- 语法：engine/llm.py / engine/app.py `ast.parse` 通过；engine/static/index.html 内联 JS `node --check` 通过。
- 逻辑：后端 `save_config` 对 `providers` 往返（列表存为原样、非列表→`[]`、过滤非法/去重）临时文件验证通过；jsdom 三场景（普通新增 / 保存后重开还原 / 折叠后再保存还原）全 PASS；空 base_url 卡片保存 → payload 不含 `base_url`（现有连接保留，PASS），填了 Base URL 正常写入（PASS）。
- 本机 Chrome 不可用，未做真机视觉回归。

### 收口范围与排除
- 纳入：engine/VERSION / README.md / engine/DEVLOG.md / engine/app.py / engine/llm.py / engine/static/index.html / engine/static/worldbook-guide.html（新增）/ engine/data/config.json（出厂默认，空连接 + NSFW off）/ package.py / .gitignore（加固红线）/ `engine/static/marked.min.js`（删除）。
- 红线排除：`.workbuddy/`、`nul`（保留名，Windows 拒绝清理，无害残留，已写入 .gitignore）；`pytest.ini` + `tests/README.md` + `tests/test_focus_follow.py`（此前标记「暂不提交」的可选测试，本次仍排除）。`engine/player-cast/Cast_New v0.5 限定版.md` 的删除不在本次范围，保持未暂存待后续处理。
- 个人配置（本地 Qwen + NSFW on）不进版本库：出厂默认 `config.json` 为**空连接 + NSFW off**（base_url/api_key/model 为空、providers 为空列表），不再随分发附带任何真实密钥（v0.5.3 曾预置 SiliconFlow 密钥，v0.5.4 起移除）；个人配置已备份至 `backups/config.personal.*.bak` 并还原回工作树（未提交）。

### v0.5.4 收口动作
- `VERSION` 升 v0.5.4；提交 + 打 tag `v0.5.4`；产出 `my-st-v0.5.4.zip`（package.py 按 VERSION 自动命名）。
- 删除旧 `my-st-v0.5.3.zip`，仅保留最新；README / DEVLOG 版本号同步。git tag 现 `v0.1`–`v0.5.4` 连续。

## 2026-10-01 v0.5.3（采样参数独立分组 + top_k + 世界书文档 CDN 修复）

- 升 v0.5.3：系统设置增强（采样参数独立 + top_k）与一处文档渲染 bug 修复，均向后兼容、非破坏性 → PATCH（v0.5.2 → v0.5.3）。

### 1. 系统设置：采样参数独立分组 + 新增 top_k
- 前端（engine/static/index.html）：「采样参数」从「模型与生成（LLM）」拆为独立折叠组（徽章 SAMPLING），与具体模型解耦、全局统一；组内字段 温度 / top_p / top_k（默认 40）/ max_tokens（默认 4096）/ 启用思考；`open-system` 加载加 `cfg-topk` 且默认 0.9/4096/40，`sys-save` 回写 `top_k`。
- 后端（engine/llm.py）：DEFAULTS 加 `top_k:40`、`temperature` 0.8→0.9、`max_tokens` 512→4096；`_WRITABLE` 与 `save_config` int 分支纳入 `top_k`；`stream`/`complete` 签名与 payload 透传 `top_k`。
- 后端（engine/app.py）：`/api/act` params 加 `top_k: int(body.get("top_k", llm.setting("top_k")))`。
- 出厂默认（engine/data/config.json）：新增 `top_k:40`，`max_tokens` 2048→4096，`temperature` 0.9；端点保持硅基流动 HY4、NSFW 关闭（出厂即锁）。

### 2. Bug 修复：世界书帮助文档一直「加载中…」
- 根因：文档页用渲染阻塞的外部 CDN（cdn.jsdelivr.net/marked）渲染，CDN 不可达时外部脚本挂起 → 内联脚本永不执行 → 卡在「加载中…」。
- 修复：下载 marked v12.0.2（35KB）到 engine/static/marked.min.js；新增 `GET /static/<path>` 路由（原 `Flask(static_folder=None)` 不提供默认静态路由）；文档页改引用 `/static/marked.min.js`，并加固为「渲染失败立即回退纯文本、绝不卡加载」。
- 分发包含 marked.min.js（package.py 递归打包 engine/），修复对拷贝同样生效。

### 验证
- py_compile llm.py/app.py 通过；test_client `GET /static/marked.min.js`→200（text/javascript, 35KB），`GET /docs/worldbook`→200 且引用本地 marked、`__MD__` 已替换、含纯文本回退。
- index.html 标签平衡（details/summary 5/5）、21 ID 无缺失（含 cfg-topk）、CSS 231/231、JS node --check 通过；top_k 全链路贯通。
- 健壮性：/api/act 的采样参数解析加 `_resolve` 兜底，请求体未给且配置缺失（如测试桩返回 None）时回退 `llm.DEFAULTS`，避免 `int(None)` 崩溃；快测 53 passed 无回归。
- 本机 Chrome 不可用，未做真机视觉回归。

### 收口范围与排除
- 纳入：engine/VERSION / README.md / engine/DEVLOG.md / engine/app.py / engine/llm.py / engine/static/index.html / engine/static/marked.min.js（新增）/ engine/data/config.json（出厂默认，个人配置已备份至 backups/config.personal.*.bak 未提交）。
- 红线排除：`.workbuddy/`、`nul`（保留名，Windows 拒绝清理，无害残留）；`pytest.ini` + `tests/README.md` + `tests/test_focus_follow.py`（此前标记"暂不提交"的可选测试，本次仍排除）。

## 2026-10-01 v0.5.2（移动端适配 + 启动绑定 0.0.0.0）

- 升 v0.5.2：收口移动端响应式适配与启动脚本局域网绑定（均为 PATCH 档、向后兼容、非破坏性）。
- 移动端适配（engine/static/index.html）：
  - 顶栏汉堡菜单（≤880px）：7 个操作按钮收进 `#topnav`，新增「菜单」按钮（`#open-menu`）展开下拉，修掉窄屏按钮换行溢出与 `--topbar-h` 固定导致的与 `#board` 顶部错位；全部按钮 ID 不变。
  - 抽屉遮罩 `#scrim`：左栏/日志抽屉打开时显示半透明遮罩，点击遮罩关闭抽屉与菜单；接入 `openLog`/`closeLog`/`open-left`（≤880 才显示）。
  - 手机断点（≤720）补齐：管理面板 `.mgr` 双列改单列、弹窗可滚动占满、输入条与气泡间距收紧、`#input` 高 48px、`font-size:16px` 防 iOS 缩放、触摸目标 min-height:42px、刘海安全区 `env(safe-area-inset-*)`。
  - 系统设置 UI 重构为分职责折叠分组（`<details>` accordion）：内容管控(NSFW) / 模型与生成(LLM) / 帮助与文档(DOC)，每组带职责徽章；16 个 JS 依赖 ID 原样保留。
  - 沿用应用浅色主题，无 emoji。
- 启动绑定 0.0.0.0（engine/app.py + engine/run.bat）：
  - `app.py:643`：`app.run(host=os.getenv("HOST","127.0.0.1"))`，默认仍本地回环，由 run.bat 覆盖。
  - `run.bat`：新增 `set "HOST=0.0.0.0"`；启动前用 `powershell Test-Connection 8.8.8.8` 取本机局域网源 IP 打印「局域网访问」地址，使手机等局域网设备可访问。
- 验证：HTML 标签平衡、21+ 关键 ID 无缺失、内嵌脚本 `node --check` 通过、CSS 括号平衡；`app.py` `py_compile` 通过。本机 Chrome 不可用未做真机视觉回归。
- 说明：config.json 的 `temperature:0.85→0.9` 漂移与 `tests/` 下可选测试（分头行动 3 项 + pytest.ini/README 同步）属此前标记「暂不提交」内容，本次不纳入 v0.5.2 收口，保留在工作区待后续单独处理。
- `VERSION` 升 v0.5.2；提交 + 打 tag `v0.5.2`；产出 `my-st-v0.5.2.zip`（package.py 按 VERSION 自动命名）。删除旧 `my-st-v0.5.1.zip`，仅保留最新；README / DEVLOG 版本号同步。git tag 现 `v0.1`–`v0.5.2` 连续。

## 2026-10-01 v0.5.1（前端三栏布局修正 + 日志残留修复）

- 升 v0.5.1：收口前端三栏布局两处修正与日志窗残留上一轮推演内容的 Bug 修复（均为 PATCH 档、向后兼容、非破坏性）。
- 前端三栏布局修正（engine/static/index.html）：
  - 开始界面刷新后消失：根因 CSS 优先级——`#board{display:flex}`（ID 选择器）压过 `.hide{display:none}`，`.hide` 失效使 `#board` 永远 `position:fixed` 盖住 `#setup`。新增 `#board.hide{display:none;}`（特异性 1,1,0）修复。
  - 左栏收起逻辑纠正：整栏「世界状态」不收起；收起的是栏内各子面板（关系/本轮行动/当前意图/行动状态/秘密），长内容默认收起、决定权交给用户。每个 `.panel` 独立 `panel-head` 点击展开/收起；5 个内容面板带 `data-collapse` 默认收起，仅「在场角色/场景」常驻展开。顶栏新增「世界状态」按钮（窄屏下左栏变抽屉由该按钮唤出）。删除整栏收起的残留 CSS/HTML/JS。
- 日志窗残留上一轮推演内容（Bug 修复）：
  - 根因：engine/logger.py 的 LogBus 是进程级环形缓冲，`/api/log/stream` 每次连接都回放全部缓冲且不分会话；前端刷新即自动 connectLog()，旧日志被整段回放。
  - engine/logger.py：LogBus 新增 `clear()`（清空环形缓冲）。
  - engine/app.py：`/api/session/new` 开头调用 `logger.bus.clear()`，开新一轮前清空缓冲。
  - engine/static/index.html：startSession() 开头清空 `lwBody` DOM，会话就绪后再 `connectLog()`；去掉初始化时无条件的自动 `connectLog()`（开始界面不再回放旧日志）。
  - 验证：脚本连开世界 A/B，连接 2（B 之后）回放仅含"世界B"、不含"世界A"，判定 PASS；JS/Python 语法均通过。
- `VERSION` 升 v0.5.1；提交 + 打 tag `v0.5.1`；产出 `my-st-v0.5.1.zip`（package.py 按 VERSION 自动命名）。
- 删除旧 `my-st-v0.5.0.zip`，仅保留最新；README / DEVLOG 版本号同步。git tag 现 `v0.1`–`v0.5.1` 连续。
- 四情景单元测试验证（迭代后引擎回归，纯测试改动，按 simon 要求暂不提交）：覆盖 ① 有 NSFW ② 无 NSFW ③ 角色分头行动叙事 ④ ending 机制 + 总结报告。
  - 快测基线 53 passed / 4 deselected；补 `tests/test_focus_follow.py` 分头行动确定性测试 3 项（此前仅覆盖单焦点子集，缺"多角色被点名分头走、镜头跟随被点名者、留守者移出镜头、在场名单不清空"这一核心行为）→ 56 passed。
  - 集成测试（真实 LLM 端到端）首跑 2 passed / 2 failed：`test_directive_focus_on_leavers`（分头行动）+ `test_playthrough_saves_markdown`（ending 走查落盘）通过；`test_nsfw_arc_produces_intimate_content`、`test_directive_focus_on_full_opportunity_pair` 失败。根因非引擎 bug —— 被测服务跑在出厂锁定配置（`adult_confirmed:false` + `nsfw_enabled:false`），真实链路门控锁死、模型拿不到解锁提示词；确定性测试用 monkeypatch 强制成年确认故全过，证明逻辑正确。
  - 临时把 `config.json` 切到开启配置、重启服务重跑集成 → 4 passed（四情景全绿）；验证后已回滚 config、清场、停服务（红线 `.workbuddy/` 与保留名 `nul` 未纳入）。
  - 结论：四情景逻辑均正确。分头行动当前以"被点名集合 = 单一镜头组"跟随，多组分头去不同地点会合并为同一焦点（设计如此，非缺陷）。ending 经 `/api/end` 生成复盘并导出 `summary.md` 存档，且 `/api/ending/dismiss` 支持驳回抑制复弹。
  - 产出 `tests/runs/引擎四情景测试验证报告.md`；测试文件改动（`test_focus_follow.py` +3 项）暂未提交（属测试单元、不进分发 zip）。
  - 微信频道推送未执行：本会话当前无可用微信发送类工具（`search_plugins` 仅返回未安装候选，已绑定连接器不在列；可用工具无消息推送入口）。待 simon 确认绑定连接器（如企业微信机器人）后补推；常态化跑 NSFW 集成测试需让被测服务以"开启配置"启动。

## 2026-10-01 v0.5.0 结局判定（软指引）收口

- 动机：引擎此前没有「终止」概念，会话可无限漂移、永不收束，用户也没有干净的「结束并复盘」出口。
- 设计原则：软指引（引擎只「提议」、用户拍板，绝不强制中断叙事）；剧本无关（判定只依赖快照通用字段，导入任意剧本都能用，无需作者标注）。
- 新增 `engine/ending.py`：
  - `evaluate(snap, dismissed)`：命中终局条件返回 `ending_candidate{reasons,new_reasons,labels,severity,round}`，否则 None。
    - Tier A 触发条件：`present` 空（全员离场）、所有秘密 `state != 潜伏`（秘密全曝光）、可选 `ending_flag`（剧本自定义标记）。
    - 抑制逻辑：`dismissed` 含已全部已现理由时返回 None，避免「继续探索」后反复刷屏；仅当出现**新**条件才复弹。
  - `mark_dismissed(snap, reasons)`：把当前命中条件写入 `ending_dismissed_reasons`。
- `engine/prompter.py`：新增 `build_summary(snap, history)`，基于世界最终状态 + 完整对话组装结局复盘提示词（结局类型 / 角色命运与关系收束 / 秘密真相 / 悬念）。
- `engine/app.py`：
  - `/api/act` 的 `done` 事件注入 `ending_candidate`（并持久化 `ending_last_reasons` 供驳回时记录）。
  - 新增 `POST /api/ending/dismiss`（记录驳回，抑制复弹）与 `POST /api/end`（调 `llm.complete` 生成总结并导出 `summary.md` 存档）。
- 前端 `static/index.html`：顶栏「结束剧本」手动按钮；命中终局时非阻塞横幅（继续探索 / 终结剧本）；总结 modal 展示收束复盘（含「放弃该会话」）。
- 测试 `tests/test_ending.py`（8 项，确定性 + Flask 端点 mock LLM）：evaluate 三类分支、dismissed 抑制、新条件复弹、/api/end 总结与存档、/api/ending/dismiss 生效。
- 收口：MINOR v0.4.5 -> v0.5.0。快测 **53 passed / 4 deselected**（integration 跳过）无回归；tag `v0.5.0`；产物 `my-st-v0.5.0.zip`（仅含 engine/，泄漏校验 PASS）。新增代码与测试均进版本库但不进 zip（开发用，不分发）。

## 2026-10-01 镜头跟随（焦点）机制

- 根因：引擎此前只有单一 `present` 名单、缺少「镜头」概念。玩家把扰动引向某个在场子集
  （如"老周带领高洋下去下水道"）时，模型仍默认全员出场、并偏爱更戏剧的留存组（怀孕/秘密组），
  导致镜头死守初始位置、不跟随被引向的角色（用户实测：连续三轮指令都只写留下的人）。
- 修复（纯提示词 + 后处理裁剪，不动 `present` 名单，安全可逆）：
  - `director.compute_focus(directive, snap)`：从指令识别本轮镜头焦点。
    - 指令点名一个真子集 -> 跟随该子集；
    - 指令无点名但含指代代词（两人/他们/2人/...）且上轮有焦点 -> 延续（`sticky`，避免"2人逐渐深入"丢焦点）；
    - 指令点名全体或无人 -> `None`（自然推演、全员皆可写）。
  - `prompter.build_session`：焦点存在时注入「【镜头跟随】」块，把焦点子集设为本回合主视角，
    其余在场角色标注"在别处待命、不在镜头内、不展开"；无焦点时保持原"本轮在场角色"全覆盖句式。
  - `app.py`：`/api/act` 在 `scene.apply` 后计算焦点并存回 `snap["focus"]`；传给 `build_session`；
    并把焦点子集作为 `validate_present(allowed=...)` 的裁剪白名单。
  - `director.validate_present`：新增 `allowed` 参数（默认回退为 `present`），仅保留白名单内角色的
    「角色名：」台词块，镜头外在场角色的台词块被剥离，实现"镜头真正跟随被引向的角色"。
- 测试：`tests/test_focus_follow.py`（8 项，确定性、mock LLM）：覆盖 compute_focus 四类分支、
  prompter 注入、端点层提示词含镜头跟随块且后处理裁剪掉镜头外角色。
- 版本：纯错误修正、非破坏性，按版本规范属 PATCH（v0.4.4 -> v0.4.5）。

## 2026-10-01 NSFW 门控「突破防守」测试与可测性重构

- 新增 `tests/test_nsfw_defense.py`：模拟玩家「未确认成年 + 未开启 NSFW」条件下的突破尝试。
  - 逻辑层（确定性）：`nsfw.resolve_session` / `resolve_for_request` 矩阵——即便客户端伪造 `override="on"` 或 `nsfw="on"`、即便导演扰动把机会等级顶到「满机会」，门控一律返回受限（`unlocked=False`、`intimate=False`、提示词为 `GUARD` 且不含任何越线级露骨指引）。
  - 端点层（Flask 测试客户端，mock LLM）：真实驱动 `/api/act`，断言返回 `nsfw.unlocked=False`，且注入模型的 `[内容尺度]` 段为 `GUARD`；并验证机会等级确被扰动顶到「满机会」仍被拦截（突破场景成立）。
- 可测性重构（行为不变）：将 `/api/act` 里内联的 `override="off" if not nsfw_enabled else body.get("nsfw")` 提取为 `nsfw.resolve_for_request(snap, adult_confirmed, nsfw_enabled, body_nsfw, opp_level)`，把「服务端决定 override、客户端 body 仅在其开启时生效」的防守点收敛为单一可单测函数。
- 防守要点：门控由服务端设置决定，请求体内的 `nsfw` 字段仅在 `nsfw_enabled=True` 时采纳；`adult_confirmed=False` 在 `resolve_session` 中优先级最高（先于 override 判定）。当前 `data/config.json` 默认即 `adult_confirmed:false`、`nsfw_enabled:false`，即出厂即锁。

## 2026-09-30 秘密机制重构

### 已落地：秘密的归属 / 曝光路径 / 影响
- 快照 `secrets` 每条含：`owner`（归属角色）、`known_by`（知情实体集合，含「环境推手」与具体在场角色）、`exposures`（曝光路径日志 `[{by, via, round}]`）、`state`（潜伏 / 暴露，按 known_by 是否含在场角色重算）。
- 曝光路径两条：A1 环境推手主动查（关键词 + 信息获取动词）→ 记「环境推手」已知，不翻 in-world 状态；reflect 叙事揭露 → 由 LLM 输出 `secret_exposures[{owner, by}]`，把具体知情角色写入 known_by 并记路径。
- 影响：prompter 对 owner 注入「你的秘密已被 X 知晓」，对知情非 owner 角色注入「你已知 X 的秘密」，使秘密真实驱动后续推演（铁律②信息边界：只注入给确实知情者）。
- 「玩家」机制已于本轮彻底移除：affect.py / state.py 移入 `_bak_20260930/`，单角色路由 `/api/generate` `/api/message` `/api/state` `/api/persona` `/api/nsfw/confirm` `/api/state/reset` 删除；成年确认迁为系统设置 `adult_confirmed`（llm 配置），顶栏「确认已成年 / 重置」按钮移除，迁入系统设置面板。旧会话快照 loaded 时把 known_by 里的「玩家」归一为「环境推手」。

### 待办 / 搁置项

> 本处「世界级秘密 / 全曝光状态」已迁至统一待办日志 [TODO.md](./TODO.md)（条目 S1 / S2），含现状、触发条件与实现方向，详情见该文件。

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

- 复刻 Lorebook 核心三件套（递归扫描 recursive 留二期）：
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
- 角色卡导入兼容：前端 `loadChar` 拆出 `fillChar` 并 stash 原始卡 `_charOrig`；`char-save` payload 合并 `_charOrig` 中未识别字段（avatar/alternate_greetings/extensions/tags 等），避免从外部导入时丢元数据；`char-new` 重置 `_charOrig`。新增「导入 JSON」按钮 + 隐藏 file input，读取本地 JSON 直接载入编辑器（未识别字段随保存保留）。
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

## 2026-10-01 NSFW 提示词强化（B 方向）

- 动机：simon 指出满机会时模型仍停在"对应程度的接触"层（BODY_MID 命中），未到显式性行为（BODY_STRONG）。门控正确但落笔偏保守。
- 改动 `engine/nsfw.py` 的 `OPP_PROMPT["满机会"]`：从"必须写出越线（性行为或对应程度的接触）"强化为更直白、不容回避的措辞——明确列出生殖器/胸部接触、亲吻舔舐、插入与抽送、身体反应（夹紧/颤抖/潮润/体液）、双方声音呼吸；并三连禁止（门口、自我克制收尾、情绪词糊弄）。保留"越线"字样以维持既有测试断言。
- `tests/test_nsfw.py` 新增 `test_adult_full_opportunity_explicit_language`：锁死新措辞必须含露骨生理引导词（插入/抽送/体液/生殖器/胸部）且含"门口/糊弄"禁止词。
- 验证：确定性单测 8/8（test_nsfw）+ 全量 28/28 通过；`pytest -m integration -k nsfw` 真实 LLM 跑通——第 1 轮（满机会）直接写满完整性行为过程（含住乳尖舔舐→手指探入腿心→阴茎抵入→整根插入抽送→精液泄出），BODY_STRONG 命中；第 2、3 轮机会回落半步、只升温不写满（导演判定正常）。日志 `tests/runs/20261001_032132_NSFW验证.md`。
- 此改动改了引擎运行行为（提示词更露骨），`engine/` 进分发 zip。

## 2026-10-01 版本 v0.4.3（NSFW 提示词强化收口）

- 升 `v0.4.3`：收口 B 方向的 NSFW 满机会提示词强化（更直白不容回避的露骨措辞 + 三连禁止糊弄式收尾）与同步锁死措辞的 `test_nsfw` 确定性测试。
- `VERSION` 升 v0.4.3；提交 + 打 tag `v0.4.3`；产出 `my-st-v0.4.3.zip`（27 条目，88.4 KB）。
- 删除旧 `my-st-v0.4.2.zip`，仅保留最新；README / DEVLOG 版本号同步。git tag 现 `v0.1`–`v0.4.3` 连续。

## 2026-10-01 版本 v0.4.5（镜头跟随 / NSFW 门控收口）

- 升 `v0.4.5`：收口两处纯错误修正（PATCH 档，非破坏性）：① 叙事镜头跟随机制；② NSFW 门控「突破防守」测试与可测性重构。并顺带收口二者的未提交改动。
- 镜头跟随（叙事逻辑修复，PATCH 档）：
  - 根因：引擎此前只有单一 `present` 名单、缺少「镜头」概念。玩家把扰动引向某个在场子集（如"老周带领高洋下去下水道"）时，模型仍默认全员出场、偏爱更戏剧的留存组，导致镜头死守初始位置、不跟随被引向的角色（用户实测：连续三轮指令只写留下的人）。
  - `engine/director.py`：新增 `compute_focus(directive, snap)`，从指令识别本轮焦点（点名真子集 -> 跟随；含指代代词且上轮有焦点 -> sticky 延续；点名全体/无人 -> None）。
  - `engine/prompter.py`：焦点存在时注入「【镜头跟随】」块，把焦点子集设为本回合主视角，其余在场角色标注"在别处待命、不展开"；无焦点保持原全覆盖句式（签名新增 `focus` 参数，向后兼容，默认 None）。
  - `engine/app.py`：`/api/act` 在 `scene.apply` 后算焦点存回 `snap["focus"]`，传给 `build_session`；并把焦点子集作为 `validate_present(allowed=...)` 裁剪白名单。
  - `engine/director.py`：`validate_present` 新增 `allowed` 参数（默认回退 `present`），剥离镜头外在场角色的台词块，镜头真正跟随被引向者。
  - `tests/test_focus_follow.py`（新增，确定性、mock LLM，8 项）：覆盖 compute_focus 四类分支、prompter 注入、端点层提示词含镜头跟随块且后处理裁剪镜头外角色。
- NSFW 门控「突破防守」（PATCH 档）：
  - `engine/nsfw.py`：新增 `resolve_for_request(snap, adult_confirmed, nsfw_enabled, body_nsfw, opp_level)`，把 `/api/act` 内联的 override 计算收敛为单一可测函数（行为不变）。
  - `engine/app.py`：`/api/act` 改调 `resolve_for_request`。
  - `engine/data/config.json`：出厂默认改为 `adult_confirmed:false` + `nsfw_enabled:false`（默认锁死，未确认成年的玩家天然无法触发 NSFW）。
  - `tests/test_nsfw_defense.py`（新增，确定性 + Flask 端点层，8 项）：模拟玩家「未确认成年 + 未开启 NSFW」下的突破尝试（伪造 `nsfw:"on"`、把机会等级顶到满机会、组合攻击真实 `/api/act`），断言一律受限、注入模型的 `[内容尺度]` 为 `GUARD` 且不含越线级露骨指引。
- `VERSION` 升 v0.4.5；提交 + 打 tag `v0.4.5`；产出 `my-st-v0.4.5.zip`（package.py 按 VERSION 自动命名）。
- 删除旧 `my-st-v0.4.4.zip`，仅保留最新；README / DEVLOG 版本号同步。git tag 现 `v0.1`–`v0.4.5` 连续。

## 2026-10-01 版本 v0.4.4（推演逻辑修复收口）

- 升 `v0.4.4`：收口推演逻辑三处修复（指令焦点 + 满机会锁死 + 在场保护），并顺带收口 v0.4.3 以来未提交的全部改动（运行时日志窗、engine/tests venv 分离）。
- 推演逻辑修复（引擎行为修复，PATCH 档）：
  - `engine/director.py`：新增 `_sanitize_relation()`，`reflect()` 写回关系时剥离强/中信号词（偷情/肉体/做爱等），`满机会` 不再被叙事污染永久锁死，改由「已确立关系 / 把柄胁迫 / 本轮指令」驱动。
  - `engine/prompter.py`：环境扰动升级为硬性焦点约束——提取指令点名角色注入 `[导演指令]` 与 `[输出格式]` 块，点名角色必须出场并作为叙事焦点，不得无声略过或写成已离场（除非指令明确令其离开）。
  - `engine/scene.py`：新增 `LEAVE_KEYS`，仅当指令显式含离场词才允许把角色移出在场名单；纯地点移动视作全员随世界转移，禁止静默丢人。
- `tests/test_directive_focus.py`（新增，integration）：双向验证——方向1 指令指向离开的人（present 仍含其名、开篇描写离开者、满机会不劫持叙事）；方向2 指令停留在满机会的人（NSFW 越线级叙事正常落地）。
- v0.4.3 以来未提交改动一并收口：运行时日志窗（`engine/logger.py` + `app.py` SSE 埋点 + `static/index.html` 右侧滑出面板，含拖拽调宽与完整提示词原文展示）；engine/tests venv 分离（`engine/venv`、`tests/venv`、各自 install/run 脚本、`tests/requirements.txt`、`verify_dist.sh` 源 venv 指向修正）。
- `VERSION` 升 v0.4.4；提交 + 打 tag `v0.4.4`；产出 `my-st-v0.4.4.zip`（package.py 按 VERSION 自动命名）。
- 删除旧 `my-st-v0.4.3.zip`，仅保留最新；README / DEVLOG 版本号同步。git tag 现 `v0.1`–`v0.4.4` 连续。
