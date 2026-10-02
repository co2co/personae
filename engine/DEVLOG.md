# ST-Lite 开发日志

记录架构决策。待办与搁置项已统一收口至 [TODO.md](./TODO.md)（各版本「下版本待办」外链至此，避免日志臃肿），非任务日志，按主题追加。

## 2026-10-02 v0.7.0（S3 剧本→设定 自动导入器）

- 升 v0.7.0：新增能力（MINOR），降低酒馆入门门槛——玩家贴剧本，引擎用 LLM 提炼角色卡与世界书，确认后一键写入，无需手动填表。
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
