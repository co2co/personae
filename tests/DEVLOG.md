# 群像弈（Personae）【暂定】开发日志

> **更名记录**：本项目原名 my-st / ST-Lite，于 2026-10-04 更名为 **群像弈（Personae）【暂定】**（暂定名）。引擎代码为原创实现，与 SillyTavern 无源码派生关系；下文历史记录中的 `my-st-vX.Y.Z.zip` 为当时产物名，保留原貌。

记录架构决策。待办与搁置项已统一收口至 [TODO.md](./TODO.md)（各版本「下版本待办」外链至此，避免日志臃肿），非任务日志，按主题追加。

> **tag 记录（2026-10-21 补，2026-10-23 续）**：`v2.0.0` 发版当日漏打 tag，已补至 `d726911`。`v2.0.1` / `v2.0.2` 是同日连续 PATCH 迭代，改动交织在 `index.html` 同一批行里（v2.0.2 重构掉了 v2.0.1 的说明条与按钮，反推不出真实的 v2.0.1 界面），故合并为提交 `c8b2db0` 且无独立 tag。当前 tag 序列：`v1.2.3` → `v2.0.0` → `v2.1.0` → `v2.1.1` → `v2.1.2` → `v2.1.3` → `v2.1.4` → `v2.1.5` → `v2.1.6` → `v2.1.7` → `v2.1.8` → `v2.1.9` → `v2.1.10` → `v2.2.0`（v2.0.1/v2.0.2 合并无独立 tag；v2.1.4 同一次提交含 NSFW 下架 + P0 注入审计两项，故 DEVLOG 拆成两条目共用一个版本号；**v2.1.11~13 与 v2.1.11 号段因 2026-10-30/31 两次回退从未发版，tag 已删腾位**，回退前工作保全在分支 `keep/v2.1.13` → `5bf1d84`、`keep/v2.1.12` → `dea891b`）。
> **锚点 tag（2026-10-23 补）**：`nsfw-on-v2.1.7` → `a6e1280`（v2.1.7 重新上架 NSFW 的原子提交）。它不是版本发布 tag，只作 NSFW-ON 态的持久锚点：`git checkout nsfw-on-v2.1.7 -- <13文件>` 即可重新上架，不受将来 rebase / 历史重写影响。**勿删**。
> **发版纪律修订（2026-10-31 补）**：旧版分发包改为**一律保留**，`dist/` 全量归档、不再清理（作废版移 `dist/_retired/`，同样保留）。下文历史条目里的「删除旧包，仅保留最新」是彼时做法，已废止，原文不回改。理由：出错时能从旧包回溯取数。细则见 `tests/README.md`「发版纪律」。

---

## 2026-11-12 版本 v2.5.0（发版记账：执笔写手落地）

> 版本号取 MINOR。判据：新增用户可见能力面（系统设置「执笔写手」面板 + `config.json` 新增 `writer` 字段 + 新端点 `GET /api/writer`），数据文件形状未变（角色卡 / 世界书 / 会话 JSON 照旧，旧会话可继续读），作者侧只多了一个可选面板，故不用 MAJOR 也不用 PATCH。

- 本版包含两个提交：`149f27c`（执笔写手落地，含 20 项守护测试）与 `1279b4d`（引擎注释去掉对未入库实验分支的直接点名，纯注释）。开发过程记录见上一条「执笔写手落地」条目。
- VERSION：`engine/VERSION` `v2.4.0` → `v2.5.0`。tag `v2.5.0` 打在本发版记账提交上（另一条本地发布线用带后缀的号段，两边不顶包）。
- 测试：`tests\venv\Scripts\python.exe -m pytest -q -p no:cacheprovider` → **325 passed / 1 skipped / 1 deselected**，退出码 0。本轮起点基线 305 passed / 1 skipped / 1 deselected（同命令改前实测），净 +20 = `tests/test_writer_persona.py` [实测]。
- 分发包：`dist/personae-v2.5.0.zip`（32 条目，229.6 KB / 235,116 字节，sha256 前 16 位 `3ece6aec7e1e28a9`），命令 `python package.py --skip-demo-check`。
  - 为什么仍要跳守卫：本机 `dramas/` 里的作者源与 master 的随包 demo 不是同一份剧本，`scripts/sync_drama.py check` 会拿那份剧本比对并报差异，`install` 更会把不相干的数据写进入库 demo。故不 install、只跳守卫，改以包内校验代替。
  - 包内校验（读 zip，实测）：条目 32 项；无 `data/characters|worlds|sessions`、无 `venv`/`tests`/`__pycache__` 泄漏；`engine/data/config.json` 已洗白（`base_url`/`model` 空、`providers: []`、采样参数取自 `llm.DEFAULTS`、**无 `writer` 键**——用户自述属个人创作内容，缺该字段时 `writer_cfg()` 自动回退出厂写手）；随包 demo = 世界书 1 本 21 条（引擎默认条目仅「写法示范·常驻」一条，写手不进世界书）+ 角色卡 6 张；`engine/VERSION` = v2.5.0。
  - 泄漏扫描（实测）：包内文本零命中实验剧本名与其角色名；`sk-local` 是 `llm.DEFAULTS` 的出厂占位密钥，非真实密钥。
- 旧包纪律：本轮首次构建的 v2.5.0 包（含未脱敏注释）不删除，移入 `dist/_retired/personae-v2.5.0-pre-scrub.zip`，随后重建正式包；`dist/` 原有各包一律保留，未覆盖任何旧包。
- 脱敏（本轮新增内容）：新增提交内零命中实验分支名、个人路径与个人信息；另清掉两处历史注释里对未入库分支的直接点名（`engine/app.py` 闭包遮蔽教训、`engine/prompter.py` 尺度措辞归属）。**遗留待裁**：`engine/app.py` 2 处、`engine/director.py` 10 处「旧尺度机制已随 v0.8.0 整体废弃」一类历史说明，以及一条同名旧路由名残留——这些讲的是本引擎自己的功能沿革、不是分支指向，是否一并中性化等 simon 定（先例见同日「措辞清理」条目）。
- 外部动作：master 与本条 tag 已推送至 `origin`（本条目随该次推送入库）；GitHub Release 未创建，等 simon 定。

---

## 2026-11-12 执笔写手落地 master：投递位锁 system 头部，编辑入口回「系统设置」（已随 v2.5.0 发版）

> 触发：simon 裁决——写手这条系统人设放 system prompt 更合适，按该投递位落地；编辑位置放回「系统设置」菜单（它最初就在那里）。
> 承载位取舍的依据是同一条措辞换位置的对照实测，探针件不入库。

- **先更正一条前提**：master 上**此前并没有写手**，谈不上「迁移」——2026-11-09 引擎瘦身条目当时就明写了「写手在 master 上本就不存在，不新建、不回填」。本轮是**新建并按已验证的形态定形**，不是搬运。
- **形态选定（存储层与投递层分开定）**：写手正文存 `data/config.json` 的 `writer` 字段（编辑入口在系统设置，保存即生效不重启），投递位固定在 system 提示词**第一块**。承载位对照实测（探针件未入库）：同一条措辞恒定进 system 头部（装配约 3% 处）稳定生效，整块挪进末尾 user（约 76% 处、仍标「强制」）后同一批场景 4 次里 3 次失效——投递层决定接不接受，位置是放大器。故 ① 寄 system 中段与 ② 寄世界书引擎条目都不取，取 ③ 恒定进 system 头部 + 正文存 config。
- **引擎落点**：`prompter` 新增写手段（`WRITER_LIMIT` 4000 / `WRITER_NAME_LIMIT` 60、`WRITER_GUARD`、`DEFAULT_WRITER` 群像向出厂写手、`WRITER_PRESETS` 五模板、`writer_cfg` / `writer_block` / `writer_view`），`build_session` 起手即 `blocks = [writer_block()]`，先于 `[世界设定]` 与 `[导演指令]`。写手只进正文这一条通道：`director.reflect`（纪官回写）与 `build_summary`（结局总结）不引用它，写成静态守卫。
- **存储与路由**：`llm._WRITABLE` 增 `writer`，`save_config` 只留 `name`/`content` 两字段并按上限截断（延迟 import 取 prompter 的上限，避免绕依赖环）；新增 `GET /api/writer` 下发设置页视图（当前值 + 上限 + 模板 + 出厂默认）。
- **前端**：系统设置新增「执笔写手」折叠面板（名称 / 自述带字数计数、五模板一键套用、恢复默认、实际注入内容预览），`sys-save` payload 携带 `writer`；面板文案同步补 i18n 词条与正则模板（`执笔写手` / 模板名 / `N / M 字` 计数 / 模板套用提示），中英两态都有词可查。面板不给出任何「改投递位」的控件——位置是引擎红线，不交给用户。
- **两条承载约定 + 一处加强**：
  - ① 出厂正文取中性群像写手，**零尺度措辞**——尺度自 2026-10-21 起不由引擎预设，测试里加了「出厂写手不含尺度/器官/性字样」的哨兵守着这条。
  - ② `WRITER_GUARD` 自带一句冲突裁决（写手只管怎么写，后文铁律含未成年红线恒定生效）。这类容错句会带一点措辞稀释，但未成年红线是不可让渡的边界，宁稀释也不撤。
  - ③ `sys-save` 只在 `/api/writer` 拉取成功时才带 `writer` 字段。面板没加载出来（输入框是空的）时宁可原样保留盘上写手，也不能把用户自述当「已被清空」覆盖掉。
- **打包红线**：`package.py` config 洗白段 `cfg.pop("writer")`。实测（临时包，用后即删、未进 `dist/`）：包 32 条目 229.2 KB，包内 `engine/data/config.json` 键集为 `api_key/base_url/enable_thinking/frequency_penalty/max_tokens/min_p/model/presence_penalty/providers/temperature/top_k/top_p`，无 `writer`；包内不含该字段时 `writer_cfg()` 自动回退出厂写手，新装用户拿到默认写手 [实测 来源:`package.py --out $env:TEMP\\personae-writer-check.zip --skip-demo-check` + 读 zip 内 config]。
- **测试**：新增 `tests/test_writer_persona.py` 20 项（恒在与回落 / 投递位第一块 / 不被当环境资料投末尾 / 不进纪官与总结通道 / 落盘截断与免重启生效 / 视图形状 / `/api/writer` 路由 / 世界书不播种 / 未成年红线哨兵 / 零尺度哨兵 / 出厂写手普适性 / 前端入口绑定）。`tests/venv/Scripts/python.exe -m pytest -q -p no:cacheprovider` → **325 passed / 1 skipped / 1 deselected**，退出码 0；改前基线 305 passed / 1 skipped / 1 deselected（同命令，本轮改前实测），净 +20 即本文件 [实测]。`test_universality` 的 `ALLOW_FILES` 加白本测试文件（其普适性断言正当引用黑名单词）。
- **文档**：`README.md` / `README.en.md` 顶部面板清单补「执笔写手」；`engine/INSTALL.md` / `engine/INSTALL.en.md` §6 新增「执笔写手」小节（留空回落、不可关闭、免重启、不进分发包）。
- **版本**：本条目不 bump `engine/VERSION`、不打包、不打 tag；发版另立条目（同日 v2.5.0 发版记账）。新增用户可见能力面（系统设置新面板 + config 新字段），按 v2.4.0 的定级口径取 MINOR。
- **遗留（待裁）**：① 投递位增益在本分支未做同口径 A/B 复测，本轮是把既有对照实测的结论落成形态并加守卫；要复现须另跑探针（探针件不入库）。② 写手是**全局**人设，跨剧本共用一位；若将来要「一个剧本一位写手」，得另开按世界书的存储与回落规则，本轮不做也不预留半套。

---

## 2026-11-12 全库清除第三方原型衍生暗示措辞（仅注释/文档，无机制改动）

> 触发：simon 指出仓库内的第三方原型产品名（西方 LLM 角色扮演前端）措辞会让人误以为本项目派生自该实现。引擎为原创实现，表述不应留这类指向。

- **口径**：一律去掉出处指向，改述行为与形态。概念层改名：`first message` → 「开场示范」，`example messages` → 「常驻示范」；「三段式」不再挂产品名，直称「动作 / 对白 / 散文」三段式；「Persona 写法」不再挂产品名，直称通行写法。落到 `engine/world.py`、`engine/store.py`、`engine/app.py`、`engine/static/worldbook-guide.html`、`tests/test_world_scan.py`、`tests/test_standard_example.py` 与本日志全部历史条目。
- **保留项**：`README.md` / `README.en.md` 与本文顶部更名记录中的主动原创性声明（明确与第三方前端无源码派生关系）——这三处是消歧义的正向声明，删除反而增加误会，故留。
- **验证**：中文产品名与 `Tavern` 全库零命中（`git grep`），第三方产品名仅剩上述三处声明。pytest **305 passed / 1 skipped / 1 deselected**，exit 0 [实测 来源:`engine/venv/Scripts/python.exe -m pytest -q`]。
- **版本**：注释与文档改动，不改 `engine/VERSION`（仍 v2.4.0），不打包。遗留：`v0.13.1` 的**注释式 tag 说明**（远端 tag 对象）尚无中性表述版本，改 tag 需删旧重建；本地未入库研究文档（`outputs/`、`scripts/_probe_*`）亦仍含旧措辞，待 simon 定夺。

---


> 触发：simon 决定把 nsfw 支线独立成库（本地 `D:\codes\personae-nsfw`，不配远端）。拆分前先把 nsfw 侧与 NSFW 无关的修复回流 master，否则分家后同类 bug 要两边各修一遍，且失去对照物。逐条裁决如下，只搬适用项，不为「回流」而搬。

- **✅ `284b1b7` → 本提交**：`llm.save_config` 同一 `base_url` 上换量化也作废重取 + 前端「测试连接」模型下拉预选值回写。master 同缺陷存在：旧写法只在 `base_url` 变化时 `pop("model")`，而自动取模型只在 `model` 为空时触发，后端已不提供旧值时永远修不掉；前端下拉预选首项却不写回，实测界面显示 A、落盘还是 B。`git cherry-pick -n` 后 `engine/llm.py` / `engine/static/index.html` / `tests/test_llm_repeat_penalty.py` 三处自动合并无冲突，DEVLOG 冲突按「master 自己记账」丢弃 nsfw 侧文本。pytest **298 → 302 passed**（+4 条），1 skipped，exit 0 [实测 来源:回流前后同命令各跑一次]。
- **❌ 订正一条前判：`init_relations` 的 NameError 不需要回流。** 上一轮 22d39fc 的提交信息写它是「与 master 同源的潜伏缺陷、master 未落地」，实测不成立：`master:engine/director.py:586-587` 早已是 `len(cards_present)` 并带说明注释，即 `91af241` 已含此修，补齐方是 nsfw 而非 master。该文件不再动。
- **❌ `c4537c4` 不整体回流**：混合提交（拒答净身后自动重试 + 出厂写手措辞去禁区枚举 + NSFW demo 卡），拆开搬运等于替 master 决定「模型整条拒答该不该自动重试」，那是独立的语义决策，不属通用修复。留 nsfw 侧。
- **❌ `7f0881b` 包名分支后缀不回流**：它是「两条发布线共用同一 VERSION 导致顶包」的补丁，支线独立后该前提消失。留在 nsfw 历史上，新库里撤除（连带 `tests/test_package_naming.py` 的 `-nsfw` 断言）。
- **❌ `cc1504b` / `d952bca` / `22d39fc` / `7284909` 无回流价值**：`git cherry -v nsfw master` 中 `b20a15c` 已 patch 等价标 `-`，其余三件 master 已有自己的实现（引擎瘦身 `255c333`、死键与 kinship 清理 `91af241`）。
- **✅ `_generate_once` 参数化 + `tests/test_generate_stream.py` → 后续提交**：master 的 `events()` 只读不写 `messages`（实测 grep：`messages` 在 `events()` 内仅出现一次，`app.py:729` 作读用），那条 NameError 在 master 上属潜伏而非已爆；但闭包读提示词是同一类坑，且 master **完全没有覆盖 `/api/act` 流式回路的测试**——探针只调 `prompter` + `llm.complete`，`app.py` 整段是盲区。移植口径：`_generate_once(cur_params, box)` → `(cur_params, box, msgs)`，`llm.stream(msgs, ...)`，调用点显式传 `messages`；nsfw 原版四条里**撤掉 `test_refusal_retry_reassembles_with_reason`**（master 无拒答重试分支，不带 nsfw 的产品语义），保留 HTTP 回归 + 两条静态护栏，共三条。
  - 移植中撞出一处 API 分叉，值得记：`/api/act` 的入参字段 master 读 `body["input"]`（`app.py:624`），nsfw 读 `body["directive"]`。测试按 master 口径写，并在注释里点明，别再照抄 nsfw 版。
  - 护栏鉴别力单独验过（不落盘，内存变异）：把 `app.py` 改回出错形态（去掉 `msgs` 参数 + 恢复 `llm.stream(messages` + 在 `events()` 内插入 `messages = _assemble(...)`）后，两条静态护栏同时 FAIL，现形为 `current events=PASS sig=PASS / buggy events=FAIL sig=FAIL`，exit 0 [实测 来源:verify_guards.py]。
  - pytest **302 → 305 passed**（+3），exit 0 [实测 来源:回流前后同命令各跑一次]。
- **✅ `.gitignore` 收编 `tests/_resync*` → 同批最后一个提交**：master 只收编了 `tests/_probe*`（`.gitignore:44`），本次回流当场就撞见 `tests/_resync_engine_defaults.py` 以未跟踪垃圾形态出现在 `git status` 里。收编后复核：`git status` 不再列该文件、`git check-ignore -v` 命中 `.gitignore:50`，且已跟踪的 `tests/_frontend_binding_check.js` 仍在跟踪列表内（ignore 不作用于已跟踪件）[实测 来源:git status + git check-ignore -v + git ls-files]。

---

## 2026-11-09 清理补记（发版同日：死键与失效字段裁净 + `cc1504b` 回填 master + retag）

> 触发：simon 裁定两条——「`cc1504b` 还没进 master，要回填」「遗留死键与失效字段仍在原处等裁，清掉」。
> 仍属 v2.4.0 号段（未 push，`VERSION` 不再 bump，tag 重打见末条）。

- **回填 nsfw 侧提交**：`git cherry-pick -x cc1504b` → `b20a15c`（`.gitignore` 补 `.tmp-pytest-*/` 兜底 + `tests/EVALUATION.md` 381 行 v1 深度评估标准入库）。回填前全文扫过：无 NSFW 正文、无密钥与个人信息，内容是证据体系方法论加文献条目；`package.py` 排除 `tests/`，不进分发包。就地补一条 2026-11-09 勘误：该文档 §0「本机解释器路径已失效」不成立，是执行沙箱拒绝启动该路径，不是环境损坏。
- **清 `budget` 死键**：入库版 `engine/data/config.json` 删 `"budget": 4096`。引擎零读取方——`llm.DEFAULTS` 与 `_WRITABLE` 都不含该键（实测 grep 全仓 `engine/`、`package.py`、`tests/` 无 Python 消费方）。该文件在开发机带 `assume-unchanged`（`git ls-files -v` 显 `h`），故走 git plumbing 清提交态：`hash-object -w` 造新 blob（194→176 字节）+ `update-index --cacheinfo`，事后重新 `--assume-unchanged`；工作区那份本地运行配置（providers / 模型绝对路径）一字未动。分发包侧 `package.py` 洗白本就剔除该键，用户侧无变化。
- **撤 kinship 层（`relations_base` / `kinship_base` / `relations_kinship` / `_KINSHIP_TOKENS`）**：
  - `memory.new` 不再读角色卡 `relations_kinship`、不再写快照 `relations_base` 与 `kinship_base`（净 −19 行）。
  - `director` 删 `seed_kinship_from_cards` 与 `_KINSHIP_TOKENS` 词表（含 60 行词表注释与两条自检 assert）；`fill_relation_gaps` 不再回写 `relations_base`。
  - demo 6 张角色卡删 `relations_kinship` 字段。信息不丢：陆沉↔陆芷的「父亲 / 女儿」在两卡 `relations` 描述句里本就写着（「他的女儿」「父亲。她认得他脚步声的节拍」）。
  - 判据：v2.4.0 撤掉关系回写后，两道冻结闸已一并删除，这条链只剩「落盘、无消费方」；前端卡表已知字段集（`index.html` 的 `KNOWN` 白名单）从不认这个键，作者填了既不显示也不生效——留着等于教作者去用一个死字段。
  - 兼容性：老快照、老角色卡带这些键不报错（读取方全撤，多余键被忽略），未做数据迁移。属可选字段收缩，不另开版本号。
  - 措辞去悬空引用：`README.md` / `README.en.md`「名册与分场」条去掉「亲缘 / kinship」；`index.html` 名册注释同改。
- **顺带修一条潜伏缺陷（主动审查发现）**：`director.init_relations` 的额度行写作 `len(present)`，而本函数没有 `present` 这个局部名、模块层也没有该全局 [静态检查 依据:`symtable` 旧版 director.py——`init_relations` 自由引用 `present`，模块层无名为 `present` 的赋值]，`NameError` 被外层 `except Exception: pass` 吞掉。后果：**「关系缺口推断」自那次改动起从未真正调用模型**，只返回卡片手填的部分；既有 `fill_relation_gaps` 用例把 `init_relations` 整个 mock 掉，所以这条静默失效在测试里完全看不见。修：额度口径改 `len(cards_present)`；新增 `test_init_relations_actually_calls_llm`（断言模型确实被调一次，旧代码必挂）与 `test_init_relations_card_relations_win_over_llm`（手填不被模型覆盖）锁死。
  - 行为变化提示：新建会话时若名册里有人完全无关系边，现在会真的发起一次 `init_relations` 调用（此前永远不发）。导演指令与手填齐全的剧本仍零开销。
- 测试：`tests\venv\Scripts\python.exe -m pytest -q -p no:cacheprovider` → **298 passed / 1 skipped / 1 deselected**，退出码 0。同日改前 301 passed [实测]，净 −3 = 删 5 条词表/血缘用例、新增 2 条缺口推断用例。
- tag 与包：`v2.4.0` 重打到清理后的 HEAD（`git tag -f`），使 tag 内容 = 分发包内容；旧 tag 未 push，无外部影响。清理版 `dist/personae-v2.4.0.zip` 按「旧包一律保留」移入 `dist/_retired/personae-v2.4.0-pre-cleanup.zip`，重新打包并复验。

---

## 2026-11-09 版本 v2.4.0（发版记账：引擎瘦身移植 master 落地）

> 版本号取 MINOR。判据：数据文件形状未变（角色卡 / 世界书 / 会话 JSON 结构照旧，旧会话可继续读），
> 但运行时能力面与快照语义对外收缩（快照不再有 `goals` / `actions` / `silent_rounds`；关系不再回写；
> 镜头跟随、提醒机器、场景导演 LLM 调用整条撤除）。作者侧需要自己接管镜头与尺度措辞，
> 属能力面变化而非单纯修 bug，故不用 PATCH。若 simon 按 v2.1.4「机制下架放在 2.1.x 内」旧例
> 想降成 PATCH，改 `engine/VERSION` 与本条标题即可（未 push，可改）。

- 兑现同日「2026-11-09 架构：引擎瘦身移植到 master」条目：提交 `255c333`，`codex/engine-slim` → `master` 快进合并（`merge --ff-only`，无 merge commit）。回滚锚点 tag `checkpoint-pre-slim-master-20261109` → `d860515` 保留。
- VERSION：`v2.3.0` → `v2.4.0`。tag `v2.4.0` 打在本发版记账提交上（不再重演 v2.0.0 漏打 tag 补录）。
- 未做的外部动作：`git push`、GitHub Release 均未执行（`origin/master` 仍停在 `d860515`，本地 master ahead 1）。分发包已出但对外发布等 simon。
- 测试：`tests\venv\Scripts\python.exe -m pytest -q`（= 双击 `tests/run_tests.bat`）→ **301 passed / 1 skipped / 1 deselected**，退出码 0。改前 master 基线 381 passed 见上一条目的实测记录。
- 测试环境重建：`tests/venv` 由本机 Python 3.12.10 重建，pip 26.3 / pytest 9.2.0 / Flask 3.1.3 / requests 2.34.2（= `tests/requirements.txt`）。旧 venv 移到 `backup/venv-tests-pre-rebuild-20261109`（31.2 MB，gitignore 内，可回滚）。**更正一条判断**：旧 venv 并非损坏——`pyvenv.cfg` 的 `home` 所指 `Python312` 仍在盘上，先前 `Unable to create process using …Python312\python.exe` 是执行沙箱拒绝启动该解释器路径所致。本轮仍重建，是为了让 venv 位置与 `tests/install.bat`、`tests/requirements.txt` 三方对齐、可复现；结论口径改为「venv 位置重建 + 依赖刷新」，不是「修复损坏环境」。
- 分发包：`dist/personae-v2.4.0.zip`（32 条目，224.8 KB），命令 `python package.py --skip-demo-check`。
  - 为什么必须跳守卫：本机作者源 `dramas/` 目前只有 nsfw 分支的「深夜寄宿」，master 的随包 demo 是「终局曙光」。`scripts/sync_drama.py check` 会锁定「深夜寄宿」并报 8 处差异（demo 世界书缺失、4 张 demo 卡缺失、运行态 6 张卡多余、demo 6 张卡在作者源没有）。**此时 `install` 会把 NSFW 剧本数据写进 master 的入库 demo**，属分发红线，故不 install、只跳守卫。
  - 以包内校验代替守卫（实测，脚本读 zip）：条目 32 项、无 `data/characters|worlds|sessions`、无 `venv/__pycache__/tests`、无「深夜寄宿」及其角色卡（周晓杰 / 周牧野 / 林梦雅 / 林泽宇）残留；`engine/data/config.json` 已洗白（`base_url` / `api_key` / `model` 空、`providers: []`，采样参数取自 `llm.DEFAULTS`，`budget` 死键随洗白自然消失）；随包 demo 世界书 = 「终局曙光」21 条，含新增作者条目「叙事纪律·镜头轮换」（`constant=true` / priority 84 / `origin` 空＝作者条目）；demo 角色卡 6 张（林晚晚 / 苏梅 / 赵铁 / 陆沉 / 陆芷 / 顾言）；`engine/VERSION` = v2.4.0；`hooks.py` 已不在包内。
  - 覆盖风险核对：`dist/` 下此前只有 `personae-v2.3.0-nsfw.zip` 与 `personae-v2.3.0-nsfw-slim.zip`，无 `personae-v2.3.0.zip`，本次新包未覆盖任何旧包（旧包一律保留纪律不破）。
- 遗留（发版后待裁）：`engine/data/config.json`（工作区那份）里的 `budget` 死键仍未清——该文件在开发机带 `assume-unchanged` 位（`git ls-files -v` 显 `h`），清它要在提交态改 blob 并会牵动本地运行配置；分发包侧已由 `package.py` 洗白自动剔除，不影响用户。另：`relations_base` / `kinship_base` 与角色卡 `relations_kinship` 在关系回写撤除后只剩落盘无消费方，去留等裁决。**［已结：同日「清理补记」条目两项都清了，工作区那份本地配置照旧不动。］**
- 若要 master 的 `sync_drama` 守卫恢复可用，需要把「终局曙光」的作者源放回 `dramas/`（`dramas/` 不入库，本机只有 nsfw 作者源）。

---

## 2026-11-09 架构：引擎瘦身移植到 master（三档全执行，与 nsfw 分支 7284909 同源裁决）

> 回滚锚点：tag `checkpoint-pre-slim-master-20261109` → `d860515`（v2.3.0 发版后的 master HEAD）。
> 未 bump VERSION，未发版；`dist/` 无新包。

- 来源与口径：nsfw 分支 2026-11-08 的瘦身（提交 `7284909`）搬到 master。移植前先核对——`engine/director.py`、`scene.py`、`memory.py`、`ending.py`、`hooks.py` 在 master 与 nsfw 改前（`f24bbde`）字节相同，nsfw 只多出铁律⑧、写手、亲密条目三块；因此 27 个改动文件里 19 个（含全部控制层与 15 个测试文件）可原样落 master，仅 `prompter.py`、`narrative_clean.py`、`index.html`、`store.py` 四处按 master 口径手工校正。
- 第一性原理（沿用 nsfw 侧立下的两条纪律）：① 引擎只描述世界与角色，不注入「必须发生什么」；② 引擎可以标注模型输出，不得删改正文。此前几乎每段防御代码都挂着一条「某次真实会话事故」注释，逐次打补丁长出来，本轮回到权限与预算重新估。
- 拆控制层（三档之三）：`scene.py` 重写为纯规则 `resolve(snap, directive)`，删场景导演 LLM 调用与 `AUTO_TIME_THRESHOLD` 强制推时间；删镜头跟随（`compute_focus`、「本回合主镜头」注入、镜头外 goal 抑制）与 `validate_present` 的 `allowed` 台词裁剪（保留剥名册外角色）；删提醒机器（秘密发酵、久未登场 `stale_cast_block`/`STALE_*`、`pressure` 分档加压、`silent_rounds` 累加与前端角标）；反照抄重生成改为只告警不重写；一轮 = 1 次生成 + 1 次纪官记账。
- 纪官 9 字段 → 5 项簿记：只留 `secret_exposures` / `secret_suspicions` / `handle_releases` / `location_updates` / `state_updates`；删 `relations` / `actions` / `goals` / `scene_shift` / `secret_touches` 及关系冻结闸与 `_preserve_kinship` 系列。语义变更：快照不再有 `goals`，开局意图由 prompter 直读角色卡 `short_goal`（「开局意图（作者设定）」，留空则不给）。旧快照的 `goals` / `actions` / `silent_rounds` 自此无读取方，未做迁移。
- 下沉作者层（三档之二）：`prompter._NARRATIVE_DISCIPLINE`（104 字镜头轮换纪律）从引擎层删除，唯一承载位改为世界书——随包 demo「终局曙光」新增作者条目「叙事纪律·镜头轮换」（constant / before / priority 84），并加 `test_example_drama_carries_lens_discipline` 锁住接盘方，防「引擎不再说、也没人接」。称呼速查仍只在建局时推一次。
- 死代码（三档之一）：删 `engine/hooks.py`（全仓 0 监听者）与两处 `hooks.emit`；`ending.py` 只留 `secrets_resolved`（`all_left` 自 v2.1.0 起 `present` 永不收缩，条件永不命中）；`narrative_clean` 只留元标题外移 / 尾部截断 / 分隔线 / 引擎自述四类正则（`场景[：:]`、行首编号、`我将/鉴于` 整句删除全部撤除，它们清的是已不存在的旧提示失败形态，代价是吞正常台词与编号行）。
- **master 口径校正（不跟 nsfw 的四件事）**：① 「己、法律底线」未成年红线留在引擎层 `_LAWS_PREFIX`，恒定注入、不可由世界书覆盖（nsfw 删了，master 不删），`tests/test_narrative_discipline.py` 重写为「引擎不再立法 + 红线仍在」双断言；② 铁律⑧ / 写手 / 「亲密描写标准」在 master 上本就不存在（2026-10-21 下架），不新建、不回填，尺度措辞本轮零新增；③ `llm.py` 五级参数协商链不动——master 面向外部任意云网关，`test_llm_primary_only.py` / `test_llm_repeat_penalty.py` 是它的守护；④ 前端 i18n 撤掉只剩词典残留的死键（`到场` / `离开`）与 nsfw 的「写手」描述句，`·主镜头` 标签保留（`[本轮场面]` 按 locations 分场仍在）。
- 遗留（未做，需裁决）：`engine/data/config.json` 里无人读取的 `budget` 字段——该文件在开发机上带 `assume-unchanged` 位（本地运行配置与出厂默认同一个路径），本轮不碰，清它要在提交态改 blob、会把运行配置带进版本库；nsfw 侧同样未清。**［已结：2026-11-09 清理补记用 git plumbing 只改提交态，工作树未动；nsfw 分支侧仍未清。］**
- 连带缺陷（主动审查，只报告未实施）：关系回写撤掉后，`relations_kinship` → `kinship_base` 与 `relations_base` 只剩落盘、没有消费方，角色卡的 `relations_kinship` 字段因此对外失效。本轮先把指向已删函数 / 已删用例的注释改口（`director.py` 三处、`memory.py` 两处），字段本身留与不留等裁决。
- 文档同步：根 `README.md` / `README.en.md` 的「核心机制速览」把「每轮回写 actions / goals / relations」改为纪官三件事；两处目录树删 `hooks.py` 行、改写 `director.py` / `scene.py` 注释；`engine/README.md` 目录树同步（中英同页只有一份目录树，改一处即两语生效）。
- 测试账（同口径 `-m "not integration"`，`-p no:cacheprovider --basetemp=`）：改前 master 基线 **381 passed / 1 skipped / 1 deselected**（worktree 检出 `checkpoint-pre-slim-master-20261109` 实测）→ 改后 **301 passed / 1 skipped / 1 deselected**，退出码 0。净减 80 项来自删 `test_focus_follow.py` / `test_pressure_force.py` / `test_stale_cast.py` 与 `test_director.py` / `test_relation_gate.py` 收缩，`test_narrative_discipline.py` 重写为 6 项（新增两条 master 专属哨兵：红线仍在、随包剧本必须带镜头纪律）。环境说明：仓库自带 `tests/venv` 已废（`pyvenv.cfg` 指向已不存在的 `Python312`，且 venv 建自旧目录名 `my-st`），本轮用临时 venv 跑测，未修 `tests/venv`。
- 与 nsfw 侧测试账的差异：nsfw 改前 396 / 改后 315，master 改前 381 / 改后 301，差额 15 = `test_writer_persona.py`（211 行写手用例，master 无写手机制）。

---

## 2026-10-31 文档：README 首页改回默认中文（撤销同日「英文占首页」裁决）

> 本条推翻同日「README 语言栏（英文版占首页）」条目首页方向的裁决，该条目保留原文备查、不回改。

- 改判依据（simon）：主要初始受众是国内中文群体，仓库首页应默认中文；英文 README 此前「面向 GitHub 国际访客」的定位权重让位于实际受众。
- 结构调整：`git mv README.md README.en.md`（英文版退居二级页）、`git mv README.zh-CN.md README.md`（中文版回归首页）。仍是「GitHub 只认根 README.md 当首页、靠换名实现默认语言」的同一条机制，只是方向反转。
- 语言栏：中文页顶栏 `<b>简体中文</b> | [English](README.en.md)`；英文页 `<a href="README.md">简体中文</a> | <b>English</b>`。当前语言加粗非链接的既有形态不变。
- 正文互链跟随改名：中文页「英文界面形态见 [English README](README.en.md)」，英文页「the [Chinese README](README.md) shows the Chinese UI」。两页全部相对链接逐条校验命中（16 条全 OK）。
- 上一轮的「`README.en.md` 已删除、旧路径不留 stub」裁决随本条反转自然恢复——`README.en.md` 重新存在；`README.zh-CN.md` 路径自本次起 404，仓库公开仅一日、无外部引用，不留 stub（同上次口径）。
- engine 内文档零改动：`engine/README.md` 目录树与 `INSTALL` 双语页引用的都是包内 `engine/` 的 README/INSTALL，与根目录三文件无关（此前 grep 已核实零引用）。
- 分发零影响：`package.py` 只打 `engine/`，根三页与 `docs/assets/` 不进 zip；v2.3.0 包无需重出，`dist/personae-v2.3.0.zip` 维持原样（新包纪律：旧包全量保留，本条亦不产生新包）。
- GitHub Release v2.3.0 描述里「英文版占首页」一句同步 PATCH 为「中文版占首页」（与仓库实际形态一致，避免对外口径漂移）。
- 未 bump VERSION（纯文档，且不在包内）。

---

## 2026-10-31 版本 v2.3.0（发版记账：文档分层 + 引擎自述瘦身 + INSTALL 双语）

> 本条兑现下方三条「开发中（未发版）」条目里「随 v2.3.0 一并发版」的约定；那些句子保留原文，不回改。

### 文档分层：引擎自述不再复述机制

- 判断依据：`engine/README.md` 的动机不是开源仓库，而是**分发包**——`package.py` 只打 `engine/`，解压后没有根 README。故保留该文件，砍掉的是与根 README / INSTALL 重复的内容。
- 删除三块：项目定位理念、核心机制速览、四面板使用说明。前两块根 `README.md`（英）/ `README.zh-CN.md`（中）已写且更新更勤；第三块 `INSTALL.md` 第 5 节已写。此前同一批机制描述存在三份副本，改机制要同步三处，是漂移源。
- 保留独有资产：技术栈表；包内目录树（含 `data/` 子目录与「哪些不进包」）；运行两条路径与端口差异（`python app.py` = 5000 / `run.bat` = 5051——此差异此前只在 engine/README 写明，根 README 只写了 5051）；向上链接。
- 双语形态为**中英同页**而非两个文件：索引页短，同一信息项只出现一次（表格左右同格、命令块一份、目录树一份），避免 zip 里堆四份文档。
- 目录树注释改用英文：文件名本身即英文，英文注释对中英读者同等可读；根 README 已有中文注释版目录树，中文信息不丢。
- 结果：机制说明的唯一真相源收敛到根 README 两页；`engine/` 内文档只回答「这是什么 / 怎么跑 / 什么不进包」。

### INSTALL 双语

- `engine/INSTALL.md` 顶部加语言栏，新增 `engine/INSTALL.en.md`：九节逐节对应全译（Requirements / Download / Install Dependencies / Start / Open and Use / Configure Model / Where Content Lives / Troubleshooting / Upgrading）。
- 主版仍中文：分发包的第一读者是国内用户；与根 README「英文上首页」面向 GitHub 国际访客的读者不同，两处不必同向。
- 英文页补两条本地化说明：`install.bat` / `run.bat` 自身输出是中文（脚本不翻译，只说明「等它报成功」）；界面标签按英文系统书写，中文系统显示中文。

### 发版

- MINOR（i18n 为新增能力）：`VERSION` v2.2.0 → v2.3.0，tag `v2.3.0`，产出 `dist/personae-v2.3.0.zip`。
- 范围：界面语言三态（auto / zh / en）、秘密簿记与左栏动态文案英文化、`localStorage` 键名修复、根 README 双语 + 语言栏、engine 自述瘦身、INSTALL 双语。
- 验证：全量 `pytest tests` 381 passed / 1 skipped / 1 deselected，与 v2.2.0 基线一致（本次为纯文档改动，无引擎代码变动）。
- `package.py` 仅同步注释里的 engine 内文档清单（加 `INSTALL.en.md`），逻辑未动、脚本不进 zip。
- 旧包不清理：同日确立新纪律（旧包全量保留，供出错回溯取数），`dist/` 现有 35 个历史 zip 原样保留，此前条目里的「仅保留最新」不再执行。

---

## 2026-10-31 版本 v2.3.0：界面语言改为跟随系统（三态 auto / zh / en）

### 策略改变

- 上一轮把出厂默认写死英文，属矫枉过正：中文用户开箱看到英文界面。改为 **三态**——`auto`（默认，跟随系统）/ `zh` / `en`。
- `_sysLang()` 取 `navigator.languages` 首个可识别语种：`zh*` → 中文，其余（含无法识别）→ 英文。系统在会话中途改语言时，`languagechange` 事件仅在 auto 态跟随重译，显式选择不受影响。
- 设置面板切换组从两按钮扩为三按钮（中文 / English / Auto），高亮按「用户偏好」而非「当前生效语言」——否则 auto 态下没有任何按钮亮起，用户会以为设置丢了。注记同步说明 auto 语义。
- 持久化仍是 `localStorage(personae_ui_lang)`：存 `auto` / `zh` / `en`；旧值 `zh` / `en` 直接兼容，无需迁移。

### 左栏收尾（「世界状态同理」）

- 名册静默角标的 `title`（`连续 N 轮没有行为…`）是带变量的属性文案，原先只有精确词条可译、模式不可用。`_translateAttr` 升级为「精确词条 → 同一套 `I18N_PATTERNS` 模板」，属性文案与文本共享一套翻译规则；「已是译态」判定同步改用同函数，避免写成英文后被反复重译。
- 至此左栏四块（名册 / 现状 / 人物位置 / 秘密簿记）在英文态全部英文化，仅角色名、地点名、状态值等叙事数据保留原文。

### 验证

- Chrome headless 按系统语言三档实测（`--lang` + `--accept-lang`）：`zh-CN` → 中文首屏（`<html lang="zh-CN">`、标题「群像弈 沙盘」）；`en-US` → 英文首屏（`lang="en"`、`Personae Sandbox`）；`ja-JP` → 回落英文（非 zh 一律英文，符合设计）。
- 三态切换探针（两套系统语言各跑一遍）：zh 系统 `init=zh → en → zh → auto=zh`；en 系统 `init=en → en → zh（覆盖系统）→ auto=en`，每步 `localStorage` 与首屏语言一致。
- 持久化实机：固定 `--user-data-dir` 跑两次——zh 系统下选英文后再加载，仍为英文（`PREF=en`），证明手动选择跨刷新生效。
- 左栏探针：英文态 `title="2 silent round(s) — the next round will prompt the narrator to give them a scene"`、`(main camera)`、`(Location unrecorded)`、`Suspected (suspects: 赵铁)`；`setUILang('zh')` 后逐项还原（含 title 属性）。
- 全量 381 passed, 1 skipped；守卫测试改为 `test_ui_lang_follows_system_by_default`（锁 auto 默认、`navigator.languages` 探测、zh 判定、显式选择覆盖、Auto 按钮存在）。
- 未 bump VERSION，随 v2.3.0 一并发版。

---

## 2026-10-31 文档：README 语言栏（英文版占首页，中文版独立成页）

- 目标（simon）：双语仓库首页——仓库首页默认英文，最上方一行语言链接跳到中文版，中文版同样跳回英文版。
- 结构调整：`git mv README.md README.zh-CN.md`（中文版）、`git mv README.en.md README.md`（英文版占首页）。GitHub 只把根 `README.md` 当首页，所以「默认英文」只能靠换名实现，仓库设置里没有指定首页文件的开关。
- 语言栏：两页顶部插入居中 `<p align="center">`，当前语言加粗非链接、另一语言为链接（`English` ↔ `简体中文`）；原正文第二行的互链行删除，避免同一页两个入口。
- 正文互链跟随改名：中文页「英文界面形态见 [English README](README.md)」，英文页「the [Chinese README](README.zh-CN.md) shows the Chinese UI」。
- `README.en.md` 不再存在，旧路径 404；仓库刚公开、无外部引用，故不留 stub 文件。
- 截图分工不变：中文页引 `docs/assets/{setup,board,dramas,mobile}.png`，英文页引同名 `-en.png`。
- 分发不受影响：`package.py` 只打包 `engine/`，根 README 与 `docs/assets/` 不进 zip。
- 未 bump VERSION（文档改动），随 v2.3.0 一并发版。

---

## 2026-10-31 版本 v2.3.0：界面语言默认英文 + 秘密簿记英文化

> 本条中的「默认英文」已于同日被上一条「跟随系统（三态）」取代，仅秘密簿记英文化与键名修复仍有效。保留原文备查。

### 默认语言

- 出厂默认由中文改为 **英文**（`UI_LANG` 初值与 localStorage 缺省回退双处改）；`localStorage(personae_ui_lang)` 一旦写入即以用户选择为准，中文用户切一次「中文」即长期保持，换浏览器 / 清缓存回到默认英文。
- 修掉一处字面量损坏：`UI_LANG_KEY` 曾被写成 `'personae_…e'`（含 U+2026 省略号）。读写同键，所以功能「看起来正常」，但键名是坏的、且与 DEVLOG 记录不符；已改回 `'personae_ui_lang'`。

### 秘密簿记英文化（左栏「秘密」面板）

- 状态词入词典：潜伏 / 起疑 / 暴露 / 已公开 / 全曝光 → Latent / Suspected / Exposed / Public / Public。后端仍以中文字面量下发，前端只译显示，`s.state === '潜伏'` 之类的逻辑比较不受影响（DOM 层方案 A 的既有约束）。
- 括号说明改「逐段独立节点」：原先把「（未揭露）」与「（起疑：甲）」拼进同一文本节点，整串匹配不到任何词条，英文态出现半中半英。改为每段一个 `<span class="sec-tag">`，各命中词条或模板。
- 新增两条正则模板：`（已知者：…）` → `(known to: …)`、`（起疑：…）` → `(suspects: …)`（角色名是变量，走捕获组）。
- 新增标点归一 `_enPunct()`：命中词条后的译文再统一把 `、`→`, `、`：`→`: `、`（）`→` ( )`、`｜`→` | `，避免「Roster: 甲、乙」这类混排。
- 补齐三处纯文本空态词条（尚未确立任何状态 / 尚未记录任何位置 / 选择世界后显示本剧本的全部角色）——它们此前只有「整块 HTML」版词条，纯文本节点匹配不到。
- 布局补偿：`.sec-state`、`.loc-missing i` 各加 `margin-left:2px`（中文全角冒号自带间距，英文半角没有）。

### 验证

- Chrome headless 实机（本地引擎实例 + `--dump-dom`）：首屏英文态可见 CJK 只剩 2 处——语言切换按钮「中文」与剧本名「终局曙光」，均属数据/固定标签，非漏译；属性（placeholder / title / aria-label）残留 0。
- 探针页注入 `renderSnapshot` 造四态秘密数据：英文态输出 `顾言:Latent (unrevealed)` / `林晚晚:Suspected (unrevealed) (suspects: 赵铁)` / `陆沉:Exposed (known to: 顾言)` / `赵铁:Public (known to: 林晚晚)`；再 `setUILang('zh')` 切回，秘密行、场景行、位置行全部逐字还原，无残留英文。
- 全量 381 passed, 1 skipped（较上基线 +2：新增 `test_ui_lang_defaults_to_english`、`test_secret_states_have_english_entries` 两条守卫，锁默认语言、键名完整性与秘密词条/模板存在性）。
- 未 bump VERSION，随 v2.3.0 一并发版。

---

## 2026-10-31 文档：README 双语化（中文版 / 英文版各配本地语言截图）

- `README.md`（中文版）：顶部加语言行 `简体中文 | [English](README.en.md)`；原「英文界面四张截图」整段移除——中文页不夹英文 UI 图，改为一行文字指向英文版。
- `README.en.md`（新增，英文版）：与中文版逐节对应（Interface Preview / Positioning and Design Principles / Quick Start / Core Mechanics at a Glance / Engine Layout / Version / License），四张预览图改用 `docs/assets/*-en.png`，顶部互链回中文版。
- 截图分工：中文页只引 `setup/board/dramas/mobile.png`，英文页只引同名 `-en.png`，两页零重复引用（8 个引用逐条校验命中文件）。
- 分发不受影响：`package.py` 只打包 `engine/`，根 README 与 `docs/assets/` 不进 zip。
- 未 bump VERSION（文档改动），随 v2.3.0 一并发版。

---

## 2026-10-31 版本 v2.3.0：界面语言 i18n（方案 A，DOM 层翻译）

### 架构决定：DOM 层翻译，渲染逻辑零改动

- 设计约束（simon 拍板方案 A）：只英文化 UI chrome；运行时日志、worldbook 手册、叙事语言不在本期——叙事语言属剧本/世界书范畴，混进 UI 设置会让「语言」承担两个语义，定义层不干净。
- 实现：`index.html` 内联脚本头部注入独立 i18n 层——`I18N_TEXT` 词典（约 300 条 zh→en，归一化 key）+ `I18N_ATTR`（placeholder/title/aria-label）+ `I18N_BLOCKS`（6 个含内联标签混排块整段替换）+ `I18N_PATTERNS`（带插值动态短语的正则模板）。
- 为什么不走 `T()` 包裹路线：JS 渲染逻辑近 3000 行、动态文案 90+ 条散在模板串里，机械包裹侵入面大且易把「逻辑比较用的中文字面量」（`s.state === '潜伏'` 等后端状态值）误包裹。DOM 层方案让渲染代码一行不动：翻译发生在 DOM 消费端，`_i18nOrig`/`_i18nEn` 影子属性保存原文，切回中文完整还原；逻辑层的中文比较天然不被触碰。
- 叙事红线：`#log`（气泡）、`.eb-text`（终局横幅正文）、`#si-preview`（提炼预览）在排除区永不翻译；`#status` 状态栏与气泡 `.who` 标签（你→You）属 chrome 要译（首版把 `#stage` 整块排除误伤了 `#status`，已修——排除判定按精确容器/类，不按外层容器）。
- MutationObserver 覆盖动态渲染：innerHTML 重绘、流式 textContent 更新、属性变更都会经过翻译；已是译态的节点（影子属性匹配）幂等跳过。
- 持久化：`localStorage(personae_ui_lang)`，纯浏览器偏好，不进 `config.json`（不污染随包配置，换浏览器即恢复默认中文）。切换组注入系统设置「模型与生成」组顶部（界面语言 中文/English）。

### 守卫整改（tests/test_frontend_binding.py + _frontend_binding_check.js）

- `test_inline_script_parses` 的 raw `count()` 配平守卫被 i18n 词典误伤：词典英文译文合法带 ASCII 括号（`(unnamed)` 等），属数据而非代码。守卫升级为 `_js_balance()`——状态机跳过字符串/正则字面量/模板串（`${}` 递归）/注释，只数真代码括号；比 raw count 更准（它此前还漏算了正则 `/"/g` 里的引号会把后续真代码当字符串吞掉这类反向盲区）。
- 沙箱 mock 补 `MutationObserver`/`NodeFilter`/`createTreeWalker` 最小桩：i18n 层随脚本完整加载执行到底，本身即冒烟。

### 验证

- Playwright 实机三态：默认中文零破坏 / 切英文 chrome 全渲染（含剧本库、条目卡徽章、状态栏、名册）/ 切回中文完整还原 / 再切可重复，JS 零错误。
- 全量测试 379 绿（含升级后的守卫与沙箱 ALL PASS）。
- 英文界面四张截图入库 `docs/assets/*-en.png`（与中文版同口径：setup/board/dramas/mobile，逐张视觉核验无路径/端口/会话 ID/探针痕迹；叙事正文保持剧本原文），README 预览节双语化。
- 发版留档：本条目未 bump VERSION；发版时机由 simon 定（MINOR → v2.3.0 走完整 SOP）。后续项见 TODO「界面语言后续项」。

---

## 2026-10-31 版本 v2.2.0（随包 DEMO 换血：高氏王朝下架，「终局曙光」转正并重做）

> 版本号说明：v2.1.11~13 号段因两次回退（10-30 回退至 v2.1.10 基线、10-31 二次回退舍弃 NSFW 重新上架批次）从未发版、号段腾位；本次重新起编直接取 MINOR `v2.2.0`。回退前工作保全在分支 `keep/v2.1.13` → `5bf1d84` 与 `keep/v2.1.12` → `dea891b`，找回入口在分支，不在工作树。

### 版本决定

MINOR 递增（`v2.1.10` → `v2.2.0`）：**随包 demo 剧本整体换血**——高氏王朝下架归档，丧尸题材「终局曙光」转正为默认随包剧本并完成机制化重做（作者源 `dramas/终局曙光/`：世界书 12→20 条、角色卡 5→6 张、新增 opening.txt/README.md）。引擎代码、机制、测试均未动一行。

### 换装过程（全部走三态同步纪律）

1. 高氏王朝：`dramas/高氏王朝` 归档 `backup/_archive_purge_demoswap_20261031.tar.gz` 后删除（沿用客服战争/南镇暑夏先例）；examples 里高氏 6 卡+世界书清除。
2. 终局曙光转正：该剧本此前只活在运行态、无作者源——按 SOP 先 `adopt`（运行态→作者源，字节原样采纳）再 `install`。此后真相源唯一口径恢复。
3. 内容重做（simon 拍板「全部落地」）：作者源层全量改写 → install 铺三方 → `script-example.txt` 手工回填（sync 不覆盖该副本，改剧本必回填）。

### 重做要点（对引擎机制的逐项展示）

| 机制 | demo 侧落法 |
|---|---|
| locations 分场+默认主镜头 | 世界书新增「厂区六场点」常量（食堂/机房/物资间/三楼走廊/防爆门闸口/地下室·三号禁区）——剧本侧给出可分场的空间实体 |
| 死亡钟/里程碑悬置 | 「第127天·七天钟」D-7/D-5/D-3/D-1 四级台阶，终局悬置在出发前夜 |
| 数字账→事实锚 | 「粮食仅够1人一个月」等数值账全部载体化（摇箱不响/两遍数不一样/杯底沉），进 states 通道跨轮不写反 |
| 秘密四态·起疑长跑 | 秘密 7→9 条，全部 keys 去角色名、给非自述通道（物证/目击锚），bottom_line 语域化 |
| 暴露六通道 | 每条秘密至少一条非自述逼近路径；顾言卡去全知改「半张票」（纸板=他的未证实疑+他自己的物证暴露入口），与林晚晚秘密「潜伏」态不再打架 |
| relations_kinship 亲缘冻结 | 新卡陆芷（17，半丧尸化，开建局即在名册——合法：她一直锁在地下室）+ 陆沉↔陆芷双向 kinship，全 demo 唯一冻结组 |
| 称呼速查 | 五卡 description 显式称呼锚（林研究员/老赵/陆哥/小顾/阿言/苏主任） |
| 尸群纪律 | 新常量「尸群·它是天气」：丧尸不登台、只写人在它面前做的选择 |

### 实机验证（8 轮，进程内 test_client + 本地推理实例）

- 分场成立：8/8 轮 locations 出现 ≥2 地点；focus 焦点轮生效（导演指令引机房，顾言即刻登场）。
- 秘密簿记全绿：9 条全潜伏起步，R1 起「陆沉·女儿」「赵铁·掠夺者」进入起疑并保持 8 轮不升暴露（起疑者各 2 人、带证据引文）；顾言·复仇全程潜伏——「半张票」降级生效，模型自发走物证通道（R3 纸板锁抽屉）。
- states 通道实证：开局示范指令「防火门上闩」落成事实锚，快照累积 7 条跨轮事实不写反。
- 称呼：init_address 18 条入表，正文最高频「老赵」落地；一处推导噪声（跨卡亲属称谓错配到无亲缘卡角色），留 TODO。
- 陆芷线：STALE 提醒每轮注入点名（silent_rounds=8），8 轮模型 0 登场——机制侧全绿、叙事侧未跑通，simon 判断为模型问题（弱量化模型对残缺说话人的回避），不为此动引擎。
- 已知模型侧现象：后程出现历史回卷（复读检测触发过重生成仍落盘）与句子截断，属量化退化，换强模型即消。

### 全量测试与守卫

- 全量 379 passed, 1 skipped（与换装前基线一致）。
- `sync_drama check`：作者源/运行态/demo 三方一致；`collect_divergences()` 打包守卫通过（自动判定剧本「终局曙光」）。

### 已知遗留（不阻塞发版）

- 运行态 `engine/data/sessions/` 里留有高氏王朝旧会话（角色卡已删，打开会缺卡），属运行时态，未清理。
- init_address 亲属称谓跨卡错配（见上），卡侧描述排除法可修，挂 TODO。
- 备忘口径：MEMORY.md「当前剧本」一节已改写为终局曙光。

全量体检 `engine/static/index.html` 后的收口。改动只在单文件（+457 / −196），引擎逻辑、剧本数据、测试均未动。

### 版本决定

PATCH 递增（`v2.1.9` → `v2.1.10`）：全部是界面缺陷修复与适配，**无新增或变更对外机制**。

### 修掉的缺陷（按严重度）

| # | 问题 | 根因 | 影响 |
|---|---|---|---|
| 1 | 手机上「世界状态」首次点击无反应 | 左栏状态被 `collapsed` / `open` 两个类各表一半，窄屏初始两者皆无，首点只置 `collapsed`，画面不动 | 需点两次才滑出 |
| 2 | 移动端单列布局从未生效 | `.mgr` / `.drama-cols` / `.modal-box.wide` 的基础定义写在媒体查询**之后**，同特异性后定义赢 | 手机上剧本库、角色表单列规则被完全覆盖 |
| 3 | 引擎报错后界面锁死 | `streamAct` 无异常兜底，5xx 或断网时 `resp.body` 为 null 抛 TypeError，解锁语句永不执行 | 按钮停在禁用态，只能刷新页面 |
| 4 | 断点区间自相矛盾 | 720–880 段左栏常驻 260px，但其开关按钮已收进汉堡菜单 | 常驻栏却要开菜单才能收起 |
| 5 | `--bg-2` 未定义 | 变量缺失 | 提供商卡片背景透明 |
| 6 | `.tag{display:none}` 误伤 | 选择器过宽 | 世界书命中预览的「设定 / 秘密」标记被一并隐藏 |
| 7 | 480 段 `.modal-box .row` 过宽 | 选择器未限定直接子级 | 世界书条目行、会话行被压成竖排 |
| 8 | 属性转义用错函数 | 8 处 `value="${escHtml(...)}"` 用了不转义双引号的版本 | 值含 `"` 即截断 |
| 9 | 剧本生成预览被压窄 | `#si-preview` 误用 `.mgr` 两列网格，内部只有一个子元素 | 预览挤在 220px 第一列 |
| 10 | safe-area 处理反向 | `header{height:固定}` 配 `padding-top:env()`，内容被挤进固定高度 | 异形屏裁切 |
| 11 | `100vh` 系列 | 移动端地址栏收展导致底部溢出 | 改用 `100dvh` |

第 2 条的修法是**定义层修复**：把响应式块整段移到所有基础规则之后，而非加 `!important` 或重复覆盖。

### 新增能力：触屏排序世界书条目

HTML5 `draggable` 在触屏上不触发任何事件，手机上永远改不了注入次序。新增 `.e-move` ↑↓ 按钮。

判据用 `(hover:none) and (pointer:coarse)` 而**非屏宽**：768 平板竖屏同样没有鼠标，按宽度判定会把这类设备漏掉（手柄显示得出来、却怎么拖都不动）。

约束与拖拽路径完全一致：不跨组、不跨常量段分界、落位后才调 `renumberGroup`——保持 v2.1.9 定下的红线（顺序没变绝不调用）。

### 交互与体验

- **叙事区滚动跟随**：用户上翻读上文时不再被流式输出拽回底部（与 `lwBody` 的 `lwUserScrolled` 同一模式）。
- 5 个弹窗补统一 `modal-x` 关闭按钮（会话管理原先只能点遮罩关闭）；Esc 逐层退出：弹窗 > 菜单 > 抽屉。
- 移动端弹窗改全屏面板，消除「外壳滚动 + 内部各自限高」的双层滚动。
- 输入框随内容长高；placeholder 收短到一行宽（原文案在手机上被裁成半句）。
- 左栏面板头补 `role` / `tabindex` / Enter 键；`prefers-reduced-motion`；`color-scheme:light` 防系统暗色污染原生下拉。
- 空态提示：名册「选择世界后显示本剧本的全部角色」、世界书作者组「本剧本还没有条目」。

### 断点调整

左栏抽屉断点 720 → **880**（CSS 与 `NARROW_MQ` 同步）。720–880 区间（平板竖屏 768、手机横屏 812/844）若让左栏常驻，中间叙事只剩五百来像素。

### 验证

- 全量 `pytest tests/`：**379 passed** + 1 skipped + 1 deselected（含 `test_frontend_binding.py` 静态层 + JS 沙箱层）。
- 真机 smoke（puppeteer-core + 系统 Chrome，1440/900/768/390/360 五视口）：**97 项断言全通过**，零横向溢出、零 JS 报错。
- 行为验证 16 项全通过，关键三条：
  - 17 条作者条目点 ↑ 后位置交换、徽标就地刷新、`priority` 值域仍在 `[15,95]` 且严格递减；未改动时仍原样回传 `95/90/85`；首条上移被拦。
  - 模拟引擎 500 后按钮与输入框均解锁，界面给出可见中断提示。
  - 上滚时新内容不抢滚动，停在底部时继续跟随。
- 探针脚本（`_ui_smoke.js` / `_ui_verify2.js` / `_ui_regress.js`）用后即删，不入库。

### 产物与回滚

- VERSION：`v2.1.9` → `v2.1.10`（PATCH）
- tag：`v2.1.10` 指向本次提交；旧 tag 一概不动
- 产物：`dist/personae-v2.1.10.zip`；旧包 `v2.1.9` 清理
- 备份：改前原样 = 提交 `d5b56fe` 的 `engine/static/index.html`（`git show d5b56fe:engine/static/index.html`）。发版前的临时目录快照已清理，回滚一律走 git 对象，不依赖工作树目录
- NSFW 回滚锚点 `nsfw-on-v2.1.7` → `a6e1280` **不受本次发版影响**

---

## 2026-10-23 版本 v2.1.9（三态收敛 + 世界书保存根治，收口 v2.1.8 之后的散装改动）

`v2.1.8` 的 tag 指向 `baa5451`，此后同日晚间又落了 8 个提交却都没进 tag：剧本数据侧的亲密条清理、三类历史遗留清理、三态收敛、前端 priority/键序根治，外加三份文档补记。于是出现「`VERSION` 写 v2.1.8、tag 在旧提交、`dist` 里的包却是新内容」的三方错位。本轮把这批改动统一收口发版。

### 版本决定

PATCH 递增（`v2.1.8` → `v2.1.9`）：全部改动为缺陷修复、数据一致性与清理，**无新增或变更对外机制**，按 semver 属 PATCH。

### 本轮收口的内容

| 项 | 提交 | 性质 |
|---|---|---|
| v2.1.8 打包补记（守卫跳过原因、守卫缺陷、泄漏扫描） | `b6dd29f` | 文档 |
| 打包守卫 `except SystemExit` 反吞自身 `sys.exit(1)` | `bb5ce2b` | 缺陷修复 |
| 清理三类历史遗留（旧玩家卡素材 / 历史会话 / 同步快照与退役剧本归档） | `ff75676` | 清理 |
| 清理三态剧本的「亲密描写标准」条目，对齐 NSFW-OFF 定位 | `3f1f69e` | 数据一致性 |
| 回滚指针由已删目录快照改指锚点 tag | `3ace24f` | 文档 |
| NSFW 回滚的层 B（剧本数据侧，tag 不含须单独恢复） | `e28fdc0` | 文档 |
| 三态收敛至前端保存后的口径，消除世界书元数据反复分叉 | `ea5e9cd` | 数据一致性 |
| 界面「打开→保存」不再改写 `priority` 与 JSON 键序 | `b27ab05` | 缺陷根治 |

守卫修复当时判断「`package.py` 不进 zip，故不 bump」——这个判断本身没错，是它就 v2.1.8 这一次发版而言的结论；但后续改动累积到必须 bump 时，这些修复自然一并纳入版本范围，无需单独发版。

### 一处须记录的事实：v2.1.8 的包曾被就地覆盖

上一轮根治验证时，`dist/personae-v2.1.8.zip` 被**同路径、同版本名就地重出**（`package.py` 无 flag，直接覆盖默认输出）。逐文件 md5 比对：该包与本次 `v2.1.9` 包**仅 `engine/VERSION` 一个文件不同**。

这意味着「名为 v2.1.8 的产物」里装的其实是 `v2.1.8` 之后那批改动。它不能当 v2.1.8 的存档用，也不能拿来核对 v2.1.8 tag——tag 在 `baa5451`，包却是 `b27ab05` 之后的内容，两者本就对不上。**教训**：验证性打包要么用 `--out` 输出到临时名，要么就别覆盖正式包；一旦覆盖，正式包就失去了「与 tag 对应」的意义。

本次重出 `v2.1.9` 后，`v2.1.7` / `v2.1.8` 两个旧包一并清理，`dist/` 只保留当前版本。

### 验证

- 三态：`sync_drama.py check` ✓ 三方一致；世界书 18 条、priority 连续 `100…15`、「写法示范·常驻」仍为 `demo=true` / `origin=engine`。
- 端到端：`GET /api/world/<name>` → 原样 `POST` → 文件 md5 前后相同，`check` 仍 ✓。
- 全套快测：**379 passed** + 1 skipped + 1 deselected。
- 打包守卫（不带 flag）：✓ 三方一致，正常出包；制造分叉时 `exit=1` 且不出包。

### 产物与回滚

- VERSION：`v2.1.8` → `v2.1.9`（PATCH）
- tag：`v2.1.9` 指向本次提交；`v2.1.8` 保持指向 `baa5451` 不动（版本号不复用、不移动旧 tag）
- 产物：`dist/personae-v2.1.9.zip`；旧包 `v2.1.7` / `v2.1.8` 一并清理
- NSFW 回滚锚点 `nsfw-on-v2.1.7` → `a6e1280` **不受本次发版影响**（它不是发布 tag，只是 13 文件的对照点）

---

## 2026-10-23 根治：世界书「打开→保存」不再改写 priority 与键序

承接同日三态收敛条目。收敛只是接受现状，真正的问题是**界面保存会无条件重写数据**：一个字没改、点一次保存，`priority` 与 JSON 键序都会被改，而 `sync_drama` 的三态守卫用**字节比较**，于是每次都判分叉。

### 两处根因

| 层 | 根因 | 位置 |
|---|---|---|
| priority | 保存时按 DOM 序重算 `100 - idx * 5`，作者手写的阶梯无法存活 | `index.html` `collectWorldEntries()` |
| 键序 | `jsonify` 默认 `sort_keys=True`，GET 返回字母序，原样 POST 回去就写回字母序 | `app.py` `Flask()` 初始化 |

两者都属「隐式改写」：界面上没有对应控件，作者看不出自己的数据被动了。

### 改法

**priority 改为 dataset 原样往返**（与 demo / first_round / origin 同一套原则）：

1. `entryCard()` 渲染 `data-priority="${e.priority ?? ''}"`，空串＝新条目。
2. `collectWorldEntries()` 优先取 `el.dataset.priority`，`NaN` 时才回落到 `100 - idx*5` 兜底。
3. 新增 `renumberGroup(box)`：以本组现有值域 `[lo, hi]` 为界按 DOM 序等间距重分配，**值域不外溢**（不与另一组抢空间）。
4. 只在**顺序真的变了**的两个现场调用它：拖拽 `dragend`、勾选/取消常量导致移段（`applyConstant`）。未改顺序绝不调用——否则又变成无条件重排。
5. `w-add` 新条目只给**自己**赋值（组内最小值 − 5），不触碰既有条目。

**键序**：`app.json.sort_keys = False`，让 GET 保持磁盘上的键序，往返即字节稳定。

### 设计取舍
- 不采用「保存时统一规范化字段顺序」的方案：`sync_drama install` 用 `shutil.copy2` 保持作者源字节，两套序列化规则会互相覆盖，反而制造新的分叉。
- 新条目取「最小值 − 5」而非插入中间取中值：`w-add` 只能追加到末尾，中值分配需要处理间隔耗尽（间隔 < 2 时无解），收益不抵复杂度。

### 验证
- **jsdom 真 DOM**（`tests/_probe_priority_dom.js`，不入库）：原样保存 18 条 priority 逐条不变；二次保存幂等；新增条目 priority=10（既有最小 15）且既有条目零改动；拖拽后该条目置首且组内 priority 严格递减。
- **端到端**（`tests/_probe_save_roundtrip.py`，不入库）：`GET /api/world/<name>` → 原样 `POST` → **文件 md5 前后完全相同**（`17ce42eb…`），`check` ✓ 三方一致。
- 快测 **379 passed** + 1 skipped + 1 deselected（新增 `test_world_entry_priority_preserved_on_save`）。
- 打包守卫无 flag 通过，`dist/personae-v2.1.8.zip` 32 条目 227.6 KB，包内 `index.html` 已无旧式重算式。

### 遗留
- 若将来允许「插入到中间」的新增方式，`renumberGroup` 的等间距策略需重新考虑（当前会整体重排本组数值）。顺序语义仍正确，只是既有条目的 priority 数值会被微调一次。

---

## 2026-10-23 三态收敛（前端保存导致的世界书元数据分叉）+ 机制记录

### 现象
清理「亲密描写标准」条后，运行态被前端保存一次，`sync_drama.py check` 报「世界书不一致」。逐字段比对，**条目内容零差异**，差异全在元数据：

| 差异项 | 作者源（手写） | 运行态（前端保存后） |
|---|---|---|
| `demo` / `first_round` | 17 条无此字段 | 补成 `false` |
| `priority` | 95,90,…,55,**45**,…5（缺 50） | 100,95,…,15（连续） |
| 写法示范·常驻 | index 7，priority 60 | index 0，priority 100 |

### 根因（机制性，与删条目无关）
- `renderWorldEntries()`（`engine/static/index.html:2065`）把条目按 `origin` 拆进两个容器渲染：`#w-entries-engine` 在前、`#w-entries-author` 在后，组内再 `byConst()` 把常量前置。
- `collectWorldEntries()`（`index.html:2187`）从 `#w-entries .entry` 按 **DOM 顺序**回写 `priority: 100 - idx * 5`，并从 `dataset` 回写 `demo` / `first_round` / `origin`（缺失时落成 `false`）。

后果：**只要剧本同时存在 `origin=engine` 与作者条目，前端任意一次保存都会把引擎条目顶到第一位并整体重排 priority**。作者源手写的 priority 阶梯（含刻意的空位）无法在界面上存活。这是设计耦合，不是操作失误，也与是否删除亲密条无关。

### 处置
按 `MEMORY` 既有约定（运行态实测改动先 `adopt` 再 `install`）收敛：

```
sync_drama.py adopt    # 运行态 -> 作者源（覆盖前自动备份 7 文件）
sync_drama.py install  # 作者源 -> 运行态 + demo（14 文件）
```

- 作者源 priority 采纳为连续序列 `100…15`，写法示范·常驻 落在 index 0 / priority 100，「缺 50」空位消失。
- 17 条作者条目自此携带 `demo:false` / `first_round:false`。语义与缺失等价（引擎侧一律 `e.get('demo')` 取 falsy）。
- 红线字段未受损：写法示范·常驻 仍为 `demo=true` / `constant=false` / `first_round=false` / `origin="engine"`。

### 幂等性验证（关键）
按 `byConst(engine) + byConst(author)` 重放前端 DOM 顺序，再套 `100 - idx*5` 重算：结果与当前 priority 序列**逐项相同**、顺序相同、无条目缺 `demo`/`first_round` 字段。即收敛后前端再保存**不再产生分叉**。

### 结论 / 后续
- 三态 `entries` 逐条 `json.dumps(sort_keys)` 完全相同；`check` ✓ 三方一致；快测 378 passed。
- 剧本内新增条目若要精确控制注入次序，只能靠 `constant` 与列表位置，**不能靠手写 priority**——界面保存会覆盖。
- 若确需保留手写 priority，须改前端让保存保留原值、只给新条目分配（属机制改动，未做，另行评估）。

---

## 2026-10-23 剧本亲密度叙事标准清理（对齐引擎 NSFW-OFF 定位）

引擎侧的 NSFW 下架（v2.1.8）只停了「出厂播种」，已落盘剧本里的「亲密描写标准」条目仍留在三态与随包 demo 中——引擎说「不预设尺度」，剧本里却还挂着一条引擎署名的尺度标准条。本轮把这条在剧本数据层一并清掉，使三态与引擎定位一致。

### 清理清单
| 载体 | 动作 | 说明 |
|---|---|---|
| `dramas/高氏王朝/world.json`（作者源） | 删条目「亲密描写标准」 | 19 → 18 条；`constant=true / position=after / origin=engine`，1128 字（六分层 + 器官词正反示例） |
| `engine/data/worlds/高氏王朝.json`（运行态） | 同上（经 `install` 铺开） | 不手改，单向同步 |
| `engine/data/examples/worlds/高氏王朝.json`（随包 demo） | 同上（经 `install` 铺开） | 随包内容 |
| `engine/data/examples/script-example.txt` | 删「【常量-亲密尺度·全浓度】」整行 | 43 → 42 行；该文件经 `/docs/script-example` 对外展示，属随包示范 |
| `dramas/高氏王朝/README.md` | 修 2 处失效引用 | ① 首行「（全浓度，…）」去掉尺度声明 ②「亲密描写服从出厂【亲密描写标准】条目」标注已废除 |

**保留（判断项）**：README 的 `## NSFW 定档` 与 `## 陆敏×高琳 暗黑 NSFW 线` 两节未删。它们是剧本的**剧情设计笔记**（角色线与推进层次），不是引擎的尺度标准；且 README 位于 `dramas/`（gitignore、不随包、不入库）。删除会丢失创作内容，故只修掉其中已失效的「服从出厂标准条」引用。若要求连创作笔记一并清除，需另行指示。

### 回滚点
- `_backup_intimacy_purge_20261023/`：清理前快照 5 文件（`world.json` 作者源、`runtime_world.json`、`demo_world.json`、`script-example.txt`、`README.md`），均已核验保留被删内容。`.gitignore:_backup_*/` 覆盖，不入库不进包。
- 另有 `git` 侧回滚：`engine/data/examples/` 两个入库文件可 `git checkout HEAD --` 还原；作者源「亲密描写标准」全文可从 `_backup_offshelf_nsfw_20261023/engine/store.py` 的 `_STANDARD_ENTRY_CONTENT`（NSFW-ON 快照）或本目录 `world.json` 取回。

### 验证
- 三态条目数均为 **18**，均不含「亲密描写标准」；`sync_drama.py check` = **✓ 三方一致**
- 残留扫描（三态 world/characters + script-example）：`亲密描写标准|亲密尺度|全浓度|阴唇|阴蒂|阴茎|龟头|子宫口|抽插|露骨|性行为描写` **零命中**
- 引擎侧：`store.py` 四处命中全为注释/docstring；`restore_default_entries` 只补「写法示范·常驻」，**不会把该条种回来**
- 全套快测：**378 passed, 1 skipped, 1 deselected**
- 打包守卫（不带 flag）：**✓ 三方一致**；临时包内 demo world 18 条、script-example 零残留、体积 227.7 KB → **225.9 KB**
- `install` 产生的临时备份 `_sync_backup_高氏王朝_20261023_215748/` 已删（回滚点已由上条覆盖）

### 待决
随包 demo 内容已变，`dist/personae-v2.1.8.zip` 仍是清理前的旧内容（v2.1.8 的 tag 指向 `baa5451` 也未含本改动）。**VERSION 是否 bump 至 v2.1.9 并重出包，待 simon 示下**——本轮未 bump、未覆盖正式包，仅用 `--out` 临时包验证。→ **已决（同日）**：bump 至 `v2.1.9` 并重出包，见上方 v2.1.9 条目。

---

## 2026-10-23 工作树清理（非发版，产物不变）

承接三态一致性恢复（`sync_drama.py install` 后运行态只剩「高氏王朝」），一并清掉三类历史遗留。**不 bump VERSION、产物零变化**——被清对象或本就不入库、或本就不进包。

### 清理清单
| 类别 | 对象 | 数量/体积 | 入库 | 进包 |
|---|---|---|---|---|
| 1. 旧玩家卡素材 | `engine/player-cast/Cast_New v0.5 单人寄宿.md` | 1 文件 / 3.6 KB | 是（本轮 `git rm`） | 否（`EXCLUDE_SUBPATHS` 已排除） |
| 2. 历史会话 | `engine/data/sessions/*`（内容清空，**空目录保留**） | 10 个 / 425 KB | 否 | 否 |
| 3. 同步快照与退役剧本归档 | `_sync_backup_*`（21）、`_backup_kefu_*`（2）、`backup/dramas_retired_*`（2） | 25 目录 / 3.3 MB | 否 | 否 |

### 回滚点
- ~~`backup/_archive_purge_20261023.tar.gz`~~：上述三类内容的单一归档（367 文件，0.96 MB）。**已于同晚由 simon 手工清理工作树时删除**——三类对象（旧玩家卡素材 / 历史会话 / 同步快照与退役剧本归档）本就无保留价值，此归档的消失不构成有效资产损失。

### 保留决定（清理时明确不动）
- `package.py` 的 `EXCLUDE_SUBPATHS["player-cast"]` 与 `tests/test_universality.py` 的 `_DISTRIB_PRIVATE_PREFIXES["player-cast"]` **保留**。二者语义是「若存在则不分发 / 不扫描」，属防御性配置：路径不存在时无副作用，删掉反而失去将来重新放入时的保护。
- `engine/data/sessions/` 目录本身保留（仅清内容）。`memory.prune_sessions()` 对空目录返回 0，`memory.new()` 有 `mkdir(parents=True, exist_ok=True)`，空目录安全。
- ~~`_backup_offshelf_nsfw_20261023/`（NSFW 回滚蓝本）与 `_backup_nsfw_relist_20261022/` 等其它 `_backup_*` 一律不动~~ → 本轮清理确实没动它们，但**同晚 simon 手工清理工作树时一并删除了**（详见下节「工作树备份目录被手工清空」）。NSFW 回滚未受影响，见 v2.1.8 条目的「回滚蓝本」段。

### 验证
- 全套快测：**378 passed, 1 skipped, 1 deselected**（与清理前一致）
- 打包守卫（不带 flag）：`✓ 作者源/运行态/随包 demo 三方一致（剧本「高氏王朝」）`
- 产物比对：`dist/personae-v2.1.8.zip` 32 条目，与清理前**逐条内容全部字节一致**（清理不触碰分发面）

### 工作树备份目录被手工清空（同日 22:00，simon 操作）

**事件**：simon 自行清理工作树时，把根目录 `_backup_*` 与 `backup/` 下大量目录一并删除，超出上轮「三类」范围。

**已消失**（工作树副本，非 git 对象）：
| 目录 | 原内容 | 影响 |
|---|---|---|
| `_backup_offshelf_nsfw_20261023/` | NSFW-ON 13 文件快照 | 无（tag 等价且更强） |
| `_backup_offshelf_nsfw_20261021/` | v2.1.4 时代 11 文件 | 无（仅历史，已被 20261023 版取代） |
| `_backup_nsfw_relist_20261022/` | v2.1.7 上架前 12 文件 | 无（同属历史） |
| `_backup_runtime_purge_20261023/` | 槐荫里 world + 5 卡 + state.json | **槐荫里已无任何副本**（该剧本按 simon 指令已退役，属预期内损失） |
| `backup/dramas_retired_20261020/` 等 | 客服战争 / 南镇暑夏归档 | 退役剧本副本全失（均已废弃，不构成资产） |
| `backup/_archive_purge_20261023.tar.gz` | 上节三类归档 | 无（三类本身即垃圾） |
| 根目录其余 `_backup_gaoshi_*` 等 30 余个 | 10-16~10-21 历史快照 | 无（内容已全部落在 git 历史里） |

**未受影响（关键结论）**：
- 锚点 tag `nsfw-on-v2.1.7` → `a6e1280` 完好，13 文件齐全，NSFW-ON 符号俱全
- `tests/DEVLOG.md` 全部回滚日志（git 管理）
- 剧本真相源 `dramas/高氏王朝/`、随包 demo `data/examples/`、运行态三态齐全且一致
- git 工作树干净（被删目录全在 `.gitignore` 覆盖范围，`git status` 无变化）

**处置**：5 处回滚指针（`prompter.py` / `narrative_clean.py` / `store.py` 三处引擎注释 + `test_intimacy_scale.py` / `test_standard_entry.py` 两处 docstring）由「目录快照路径」统一改指 `git tag nsfw-on-v2.1.7`，并注明旧目录已清理勿再引用。

**验证**：真实执行 `git checkout nsfw-on-v2.1.7 -- <13文件>` → `_LAW8_DEFAULT`(1) / `_patch_laws`(1) / `_STANDARD_ENTRY_CONTENT`(2) / `_WILL_EVADE_RE`(2) 全部回来 → `git checkout HEAD -- <同13文件>` 撤回 → 工作树 0 改动。往返可逆，回滚能力完好。

**教训**：工作树目录快照是弱保障（可被误删、不入库、不可追溯）。**凡有长期价值的回滚点，必须落在 git 对象（tag / 分支 / 提交）上**，工作树副本只能算方便，不能算备份。

---

## 2026-10-23 版本 v2.1.8（NSFW 支持暂时下架，为引擎优化工作；完成后重新上架）

### 缘由
为顺利进行后续引擎优化工作，仿照 v2.1.4 下架流程，**临时**下架 NSFW 支持（亲密尺度约束层），并建立本回滚日志。优化工作完成后再按下方步骤重新上架。本轮为临时下架，按 PATCH 递增（`v2.1.7` → `v2.1.8`，与 v2.1.3 → v2.1.4 同一操作的历史先例一致），正常发版出 zip。

### 改动清单（13 文件；为重新上架提交 `a6e1280` 的完整反向操作，已落工作区）
对重新上架提交 `a6e1280` 涉及的 13 文件逐一回退至其父提交态：

**engine/prompter.py**
- 移除 `_LAW8_DEFAULT`（铁律⑧ 亲密描写：正面写实 + 时机层「到了→放开 / 没到→别硬写」）
- 移除 `_law8_override`（A/B 对照全局句柄）与 `_patch_laws()` 函数
- `_build_laws()` 回退为下架版：`laws = 创作铁律前缀（含未成年红线）+ 叙事纪律`，不再拼接铁律⑧
- 头部注释更新

**engine/store.py**
- 移除 `_STANDARD_ENTRY_CONTENT`（「亲密描写标准」世界书条目：六分层 + 器官词正反示例）
- 移除新建 / 导入剧本时的播种逻辑；`restore_default_entries` 不再补回「亲密描写标准」
- 头部注释更新（标注临时再下架）

**engine/narrative_clean.py**
- 移除 `_WILL_EVADE_RE` / `_GIVEN_EVADE_RE` 及亲密尺度自我审查剥离逻辑
- 注释回滚蓝本指向新备份

**engine/app.py**
- `restore_world_defaults` docstring 不再提及补回「亲密描写标准」

**engine/static/index.html / worldbook-guide.html**
- UI 说明去掉「亲密叙事技法基线」；指南「九·五」节由「引擎不内置」改回「出厂自带，可停用」的逆向（即回到「引擎不内置」表述）

**tests/（7 文件）**
- 测试预期回退为 NSFW 下架版：`test_intimacy_scale` / `test_standard_entries` / `test_standard_entry` / `test_narrative_clean` / `test_narrative_discipline` / `test_drama_io` / `test_store_cache`

### 验证
- 全套快测（`tests/venv`，默认 `-m "not integration"`）：**378 passed, 1 skipped, 1 deselected**
- 残留引用核查：工作树中 `_build_laws` 铁律⑧ / 出厂播种 / `nsfw` 端点无活动代码，残留均为历史注释
- 未成年红线（`_VENDOR_FIELDS` 剥离、确认端点移除）状态与 v2.1.4 下架态一致

### 脱敏审计（引擎本体）
- `engine/*.py` 13 个模块：被删符号（`_LAW8_DEFAULT` / `_law8_override` / `_STANDARD_ENTRY_CONTENT` / `_standard_entry` / `_has_standard_entry` / `_WILL_EVADE_RE` / `_GIVEN_EVADE_RE`）**零定义、零消费**，命中全在注释与 docstring
- `index.html` 零命中；`worldbook-guide.html` 仅剩「九·五、亲密叙事尺度（引擎不内置）」说明节（描述性，无尺度指令）；`config.json` 无相关字段
- 未成年法律硬红线 `_LAWS_PREFIX「己、法律底线」` 保留（引擎级，永不可被世界书覆盖）
- **数据层未脱敏（属作者数据，非引擎本体，本轮按 v2.1.4 立场「剧本数据保留磁盘、只停播种」不动）**：`data/examples/worlds/高氏王朝.json` 含完整「亲密描写标准」条、`data/examples/script-example.txt` 含「常量-亲密尺度·全浓度」——两者入库且随包；运行态 `data/worlds/槐荫里.json`、`data/sessions/*` 永不进包。若要「随包零露骨」，须改真相源 `dramas/高氏王朝/world.json` 后 `sync_drama.py install`，另议。

### 回滚蓝本（备优化完成后重新上架）

**唯一权威路径 = 锚点 tag `nsfw-on-v2.1.7` → `a6e1280`**（13 文件原子提交，git 对象，不受工作树文件被误删影响）。

```
git checkout nsfw-on-v2.1.7 -- engine/app.py engine/narrative_clean.py engine/prompter.py \
    engine/static/index.html engine/static/worldbook-guide.html engine/store.py \
    tests/test_drama_io.py tests/test_intimacy_scale.py tests/test_narrative_clean.py \
    tests/test_narrative_discipline.py tests/test_standard_entries.py \
    tests/test_standard_entry.py tests/test_store_cache.py
```

再跑全套快测确认（预期 **381 passed**，多出的 3 例是回滚带回来的 NSFW 专用用例）。

- 齐备性核验（2026-10-23）：`a6e1280^..a6e1280` 改动集恰为上述 13 文件；tag 内 `prompter.py` 有 `_LAW8_DEFAULT = (` / `_law8_override = None` / `def _patch_laws`，`store.py` 有 `_STANDARD_ENTRY_CONTENT`，`narrative_clean.py` 有 `_WILL_EVADE_RE` / `_GIVEN_EVADE_RE`
- **实机验证（2026-10-23 22:00）**：真实执行上述 `git checkout` → 上述四组符号全部回来 → `git checkout HEAD -- <同13文件>` 撤回 → 工作树 0 改动。往返可逆，已证
- **目录快照已不存在**：原 `_backup_offshelf_nsfw_20261023/`（13 文件）、`_backup_offshelf_nsfw_20261021/`、`_backup_nsfw_relist_20261022/` 均于 2026-10-23 晚由 simon 手工清理工作树时删除。**回滚能力未受影响**（tag 完整），但本条目与代码注释中的目录路径引用已统一改指 tag
- **上架后需补一步**：tag 是 v2.1.7 的原子快照，checkout 后那 5 处注释会**回到旧版**（又指向已删目录）。属预期——上架完成后按 2026-10-23 晚同款改法把指针再改指 tag 即可（纯注释，不改逻辑）
- 参考条目：本日志 v2.1.4（下架）与 v2.1.7（重新上架）

#### 层 B：剧本数据侧（tag 不含，须单独恢复）

2026-10-23 晚 simon 另提交 `3f1f69e`，把三态剧本的「亲密描写标准」世界书条与 `script-example.txt` 的「全浓度」示例一并删除，对齐引擎 NSFW-OFF 定位。**tag `nsfw-on-v2.1.7` 只含引擎/测试 13 文件，不含剧本数据**——重新上架若要连剧本侧的亲密标准一并回来，须额外做这一步。

内容未丢，落在 git 历史里，来源是 `3f1f69e^`（清理前最后一版）：

| # | 目标位置 | 恢复方式 | 备注 |
|---|---|---|---|
| 1 | `dramas/高氏王朝/world.json`（作者源） | 从 #2 的历史版里抽出该条回填 | **`dramas/` 被 `.gitignore:72` 忽略，作者源本身无 git 副本**，只能从派生体反推 |
| 2 | `engine/data/examples/worlds/高氏王朝.json` | `git checkout 3f1f69e^ -- engine/data/examples/worlds/高氏王朝.json` | 入库，可直接整文件还原 |
| 3 | `engine/data/worlds/高氏王朝.json`（运行态） | 不需单独恢复，`sync_drama.py install` 从 #1 生成 | 运行态永不入库 |
| 4 | `engine/data/examples/script-example.txt` | `git checkout 3f1f69e^ -- engine/data/examples/script-example.txt` | 该行原文「常量-亲密尺度·全浓度」 |

抽取 #1 的条目内容（1128 字，条目对象完整、可直接 JSON 反序列化）：

```
git show 3f1f69e^:engine/data/examples/worlds/高氏王朝.json > /tmp/old_world.json
# 从中取出 name 为「亲密描写标准」的条目对象，手工并入 dramas/高氏王朝/world.json 的 entries
python scripts/sync_drama.py install   # 再铺开三态
```

顺序：先 #2 / #4 还原 → 抽条回填 #1 → `install` 生成 #3 与同步 #2 → `sync_drama.py check` 确认三方一致。

**回填时必须去掉 `origin` 字段**（已核验）：历史亲密条带 `origin: "engine"`，而作者源 `world.json` 现有 18 条**一律不带 `origin`**——该字段是引擎出厂默认条目的标记，由引擎在加载时补，作者源里不该出现。其余字段照抄即可：

| 字段 | 值 |
|---|---|
| `name` | 「亲密描写标准」 |
| `constant` / `position` / `priority` | `True` / `"after"` / `100` |
| `depth` / `enabled` / `secret` / `keys` | `None` / `True` / `False` / `[]` |
| `content` | 1128 字（六分层 + 器官词正反示例） |
| ~~`origin`~~ | **回填时删除** |

### 发版
- VERSION：`v2.1.7` → `v2.1.8`（PATCH）
- commit / tag：本条目同批提交（`baa5451`）+ `v2.1.8`；另补锚点 tag `nsfw-on-v2.1.7` → `a6e1280`
- 产物：`dist/personae-v2.1.8.zip`（32 条目，227.7 KB）

**打包实况（与设计意图的偏差，需知悉）**
- 实际命令：`engine/venv/Scripts/python.exe package.py --skip-demo-check`。原因见下条。
- 三方一致性守卫（`sync_drama.collect_divergences()`）报 8 处分歧，**全部在运行态**：`data/worlds/高氏王朝.json` 与 6 张角色卡缺失、另有 5 张「作者源没有」的角色卡（林晚晚/苏梅/赵铁/陆沉/顾言）。已核验 `data/examples/` 与作者源 `dramas/高氏王朝/` **逐字节一致**（world.json + 6 角色卡），而 zip 只携带 `data/examples/`，故跳过守卫不影响随包内容。
- 运行态之所以对不上：当时 `data/worlds/` 装的是另一部剧本「槐荫里」（作者自用、非 `dramas/` 源），属正常的单剧本运行态，不是同步事故。
- **守卫缺陷（同日已修）**：`package.py` 的 `except SystemExit` 原本包住了整个判定块，把第 194 行自己 `sys.exit(1)` 一并吞掉——守卫判定「✗ 打包中止」后仍继续出包（v2.1.8 首次打包实踩）。修法：`try` 只包 `sync_drama.collect_divergences()` 调用，中止逻辑移到 `try` 之外，并把 `_detect_drama` 抛出的 SystemExit 原因文本原样打印（原分支丢掉具体原因）。验证：① 不带 flag → 打印 8 处分歧、`exit=1`、zip 指纹（md5 `51fc48f9…`）不变；② 制造多剧本目录 → 打印「⚠ 跳过一致性检查：✗ dramas/ 下有多个剧本目录…」并照常出包 `exit=0`。**该修复不触达产物（`package.py` 不进 zip），故不 bump VERSION、不重打包。**
- 泄漏扫描：包内无 venv / 缓存 / `data/sessions` / `tests` / `_backup_*` / `dramas` / 绝对路径 / 真实 key；`data/config.json` 已洗白（base_url / api_key / model 空、providers=[]、无 fallback 段）。
- ~~已知遗留：包内 `prompter.py` / `store.py` / `narrative_clean.py` 的下架注释仍带着回滚蓝本路径 `_backup_offshelf_nsfw_20261023/`（对收包人是悬空指针）~~ → **2026-10-23 晚已解决**：三处引擎注释与两处测试 docstring 统一改指 `git tag nsfw-on-v2.1.7`，包内不再出现工作树备份路径。

---

## 2026-10-22 版本 v2.1.7（回滚重新上架 NSFW 支持：亲密尺度约束层整体还原）

**起因**：simon 下令「通过回滚操作重新上架之前下架的 NSFW 支持」。回滚蓝本 = DEVLOG 2026-10-21「下架 NSFW 支持（v2.1.4）」条目 + `_backup_offshelf_nsfw_20261021/`（11 个改动前文件副本）。回滚前当前状态备份 `_backup_nsfw_relist_20261022/`（12 个文件）。

**回滚方式：精准还原，不做整 commit revert**

`15029c3`（v2.1.4）把 NSFW 下架与 P0 注入审计合成一次提交，`prompter.py` 与 `高氏王朝.json` 两处任务交织。故按文件分档处理：

| 文件 | 处理 | 依据 |
|---|---|---|
| `engine/store.py` / `narrative_clean.py` / `app.py` / `static/index.html` / `static/worldbook-guide.html` | `git checkout 15029c3^ --` 整文件还原 | 下架后（15029c3..HEAD）未被任何后续版本改动，diff 全部属 NSFW 下架 |
| `engine/prompter.py` | **仅手工还原三块**：`_LAW8_DEFAULT` 常量 + `_law8_override` / `_patch_laws` 句柄 + `_build_laws()` 拼接 | 该文件下架后含 v2.1.5 P1 角色块分层（秘密提示分行、`_ferment_hint` 短句化、段名对齐）与 P0 注入改动，整文件还原会全部丢失 |
| `tests/test_intimacy_scale.py` / `test_standard_entry.py` / `test_standard_entries.py` / `test_narrative_discipline.py` / `test_drama_io.py` / `test_narrative_clean.py` | `git checkout 15029c3^ --` 还原 | 下架后未被改动；测试语义随引擎语义反转回「铁律⑧在引擎 / 新建剧本播种亲密条 / 剥离自我审查句」 |
| `tests/test_director.py` / `test_pressure_force.py` / `test_stale_cast.py` | **不动** | 下架提交里对它们的改动是 P0 提醒段改名（`[可选提醒·` → `[提醒·`），与 NSFW 无关 |
| `engine/data/worlds/*.json`（高氏王朝.json 同提交） | **不动** | 该处改动是 P0 情境条目合并，与 NSFW 无关 |

**还原后引擎符号状态**

| 符号 | 状态 |
|---|---|
| `prompter._LAW8_DEFAULT` / `_law8_override` / `_patch_laws` | 已恢复 |
| `_build_laws()` = `_LAWS_PREFIX + (_law8_override or _LAW8_DEFAULT) + "\n" + _NARRATIVE_DISCIPLINE` | 已恢复（973 字，含「亲密与性描写/身临其境/正面写实/不预设上限/不强制克制/提前引入/硬写」，未成年法律红线仍在） |
| `store._STANDARD_ENTRY_CONTENT` / `_standard_entry` / `_has_standard_entry` | 已恢复（新建 / 导入剧本重新播种「亲密描写标准」条） |
| `narrative_clean._WILL_EVADE_RE` / `_GIVEN_EVADE_RE` | 已恢复（自我审查式规避句重新剥离） |

**数据层**：下架时就是「磁盘保留、仅停引擎播种」，故 `dramas/高氏王朝/world.json` 与 `engine/data/examples/worlds/高氏王朝.json` 的「亲密描写标准」条一直在，回滚无需补数据。当前运行态 `engine/data/worlds/槐荫里.json`（11 条）是下架后建/导入的，无该条——补不补待 simon 定（前端「恢复默认」即可补，或由 `save_world` 后续自动补）。

**验证**：全量 `381 passed + 1 skipped + 1 deselected`（exit 0，7.17s）。测试数由 378 回升到 381——回滚的测试文件把下架时合并/删除的用例一并带回（如 `test_scale_wording_restored_in_engine` / `test_law8_timing_layer_in_engine` / `test_redline_not_duplicated_in_law8`）。

**发版记账（simon 拍板 v2.1.7 PATCH 档）**：`engine/VERSION` v2.1.6 → **v2.1.7**（PATCH —— 对称 v2.1.4 下架时亦按 PATCH 处理；本次为引擎行为还原，无新增对外能力、无数据契约/存储格式变更）。产出发分包 `dist/personae-v2.1.7.zip`。

**遗留**：① 运行态 `engine/data/worlds/槐荫里.json` 无「亲密描写标准」条，simon 自行用前端「恢复默认」补，引擎侧不再动数据。② 实机验证（本地 llama.cpp 跑亲密场景）未做——本次仅有确定性全量测试。③ `_backup_nsfw_relist_20261022/`、`_backup_offshelf_nsfw_20261021/` 两份回滚备份留在工作树，不入库不进包。

## 2026-10-22 思考链预算挤占根因修复：关思考送达 + REFLECT_MAX_TOKENS 2800→4096

**问题**（DeepSeek deepseek-flash 实测取证）：纪官 reflect 轮 2-4/8 unparseable，`finish_reason=length`，
reasoning_tokens 2557/2800（91%）吃光预算，content 只剩残句。根因链路：

```
config.enable_thinking=False → _base_payload 发 chat_template_kwargs/enable_thinking
  → DeepSeek 网关对未知字段 400 → _VENDOR_FIELDS 整组剥离（关思考信号一并丢）
  → DeepSeek 默认 thinking ON → max_tokens=reasoning+content 总预算被 reasoning 吃光 → 截断
```

连带伤害：DeepSeek thinking 模式下 temperature 被静默忽略，reflect 的 0.3 / 导演官 0.4/0.3/0.7 全部未生效。

**改动**（simon 拍板方案 A + 提额双保险）：

| 项 | 内容 |
|---|---|
| llm.py `_base_payload` | `enable_thinking=False` 时加发 `reasoning_effort: "none"`（实测 DeepSeek 现行 API 该拼写真正关闭思考：reasoning_tokens 归零；`thinking:{"type":"disabled"}` 亦有效但非标准拼写，弃用） |
| llm.py 降级链 | **拆两级剥离**：新增 `_REASONING_FIELDS=("reasoning_effort",)`，4xx 时先剥 `_VENDOR_FIELDS`（Qwen 组）**保留** reasoning_effort，仍 4xx 才末级剥除。原整组剥离会把关思考信号再次误杀（本 bug 的翻版）；流式/非流式两条链同步 |
| director.py | `REFLECT_MAX_TOKENS` 2800→4096 双保险（纯 content 模型不触顶零成本；实测满负荷 content 仅 ~663 token） |
| test_llm_repeat_penalty.py | 契约四→五级降级、新增 reasoning_effort 存活断言（厂商剥除后仍在 = DeepSeek 场景关键断言） |

**验证**：

- 全量 378 passed + 1 skipped（与基线一致）
- 双栈实测（`_diag_plan_a_verify.py`）：DeepSeek 走真实 `llm.complete` 路径 reasoning_tokens=None/无 reasoning_content/finish=stop；reflect 单轮真实 4096 额度下 completion 663 token、content 1343 字完整解析、无失败留痕；本地 llama.cpp 接受 reasoning_effort 不 400（流式/非流式均过）
- DeepSeek 重放 8 轮两样本：**rounds_ok 8/8**（修复前 2-4/8 unparseable），echo=0、state_merge=0、ev_drop=0、self_disc=0

**已知行为位移（非回归，防线在加班）**：思考关闭后 DeepSeek 在 R6 单人场景倾向给名册全员填 location（loc_drop=5，两样本系统性复现；全部 25 个历史 run 该轮为 0-1）——`_spoken` 举证过滤把没写到的 5 条全拦下，**末端状态零污染**。这正是「治病靠正文举证过滤」防线的设计工况；思考开启时模型先在 reasoning 里「过名单」再输出所以更收敛。若后续认为该倾向代价高，再议是否调 R17 措辞，本次不动。

**回归判读口径沿用**：同 tag ≥2/3 样本系统性越出基线带才判回归。

## 2026-10-22 纪官 prompt 规则段压缩 B 层第二条（R05+R08「得知」判据链 363→205，-44%）

**性质**：提示词文本压缩（B 层第二条兼收口；R07 微压与 R04/handle_releases/secret_touches 三条经 simon 拍板跳过结案，理由：无矛盾/无过时/文本即防线）。合并视角压 R05+R08——删两处之间的重复判据（「从一个人传到另一个人」只留一处）。备份 `backup/_reflect_rules_r05r08_20261022/`。

**逐条记录（删了哪句 / 历史 case / 兜底代码行）**

| 规则 | 删了哪句 | 历史 case | 兜底代码行 |
|---|---|---|---|
| R05 「得知」判据 133→78 | ①括号 gloss「（如看见伤痕、物证、现场）」②「该角色本轮」③「对方自述或他人转述」（自述通道由 via 条专管，转述即听见）④「了能坐实秘密的」——四途径压成并列短语「亲眼看见、亲耳听见、被当面告知、亲手发现物证」，与 schema via 枚举（1224 行）和 `EXPOSURE_VIA_WHITELIST` 对齐 | v0.17.6 会话 467f1e4c：纪官乱截正文当证据误翻暴露 → 语义护栏双门（DEVLOG v0.17.6 条目） | `EXPOSURE_VIA_WHITELIST`(38) 白名单强制 via 六类；`_evidence_related`(305) 事实锚点双字重合；`_evidence_transfer`(326) 证据须含 by/owner 名（docstring 明写「旁白心理独白…不构成实际传递」）。核心判据「信息实际发生了跨角色传递」与收口「除此之外一律不算暴露」保留 |
| R08 内心活动不算得知 230→127 | ①四连引例「某人心想他早就知道/暗自看穿/早已心知肚明/在心里确认了」转反例触发词②「也不是实际的信息传递」（与「不算得知」「心证」三重重复）③**末句「判断的唯一标准是……有没有从一个人传到另一个人；没有传递动作就没有暴露」整句删除——与 R05 首句同一判据说第二遍，判据归 R05 一处**④「不得翻成暴露」并入「绝不填/至多填」对句 | v0.17.3 会话 256d924c：纪官把「角色内心想到他早就知道」心理描写误报成「实际得知」，潜伏秘密开场即翻暴露 → `EXPOSURE_VIA_WHITELIST` 由来（director.py:28-33 注释留档） | via 白名单拒「猜透/心知肚明」类值 + `_evidence_transfer` 拦无名旁白。**不兜之处：具名心证**（「甲心想乙早就知道秘密X」名字+事实词齐全，双护栏都放行）——「即使明写『知道』也不算」语义判据是唯一防线，完整保留；心证→suspicions 边界保留 |

**验证**：①定向判别探针 `_probe_expo_disc.py` 12/12 全过（S4 具名心证 / S5 回忆猜透 → 新旧文本均不填 exposures、正确落 suspicions=1；S6 实际传递正面控制 → 两边均填「被告知」正路径没坏），零回声——**语料对内心活动场面零覆盖（仅 r04 一处「在心里」），4 指标 A/B 对 R08 零触达，定向探针是本条的主证据**（via 条教训固化）；②重放 3 样本（本地 Qwen）：loc_miss 3/3/3 与基线同、filter_drop {0,1,0}（单样本单点 ev_drop，未达 ≥2/3 系统性门槛，且 R05/R08 不管辖举证照抄纪律）、轨迹 ±1-3 步在噪声带内、echo 全 0；③全量 378 passed + 1 skipped。判读沿用噪声带口径（同 tag ≥2/3 样本系统性越出基线带才判回归）。

**估数修正**：方案期估「省 ~300 字」乐观；语义判据本体+反例触发词占大头，实测省 158 字（363→205，-44%）。

## 2026-10-22 纪官 prompt 规则段压缩 B 层第一条（via 自述/承认特判 195→90，-54%）

**性质**：提示词文本压缩（B 层启动，逐条推进）。语义判据全保留，仅删重复句与引擎自动做的后果叙述。备份 `backup/_reflect_rules_b_20261022/`。

**逐条记录（删了哪句 / 历史 case / 兜底代码行）**

| 规则 | 删了哪句 | 历史 case | 兜底代码行 |
|---|---|---|---|
| via 自述/承认 195→90 | ①重复判据「（而非他人打听到）」与「不要拿他人转述来填」（同一判据说两遍）②「via 填『自述』或『承认』」（与分支条件重复）③后果叙述「转为公开事实、他人再也拿它要挟不了归属者（引擎据此置为已公开）」——状态机是 `_record_exposure` 自动做的，模型不需要知道 ④「专指本人当众说开」与「只用于本人真的说开的轮次」合并为一句 | v0.26.0 探针 R2：第三方当众指控、归属者矢口否认，被错填 via=自述类 → 提前置「已公开」（违反「宁可漏记不可误记」）；R6：归属者当众亲口承认被旧二态显示为「潜伏」→ 引入四态 + 自述 via | **不对称兜底，故少压**：白名单过滤（`EXPOSURE_VIA_WHITELIST` director.py:38）+「已公开=public 且众人皆知」双条件（v0.26.0，防误填提前公开）有兜底；**但自述/承认是全引擎唯一绕过三道防线的通道**（director.py:1370-1390）：holders 短路跳过、语义护栏 `_evidence_related`+`_evidence_transfer` 整体跳过（注释「不做语义护栏，直接采信」）、`_record_exposure` 清 holders+置 public——误填「他人转述→自述」会把把柄账本清空且不可逆，双条件只兜状态显示不兜账本。故「本人说开 vs 他人转述」语义判据完整保留，反例触发词三个正对 R2 形态 |

**验证数据**：
1. **重放 3 样本**（本地 llama.cpp，`after_viaL_a/b/c` vs 基线带 `after_r13L_a/b/c`）：rounds_ok 8/8、loc_missed 3、filter_drop 0、ev_drop 0、via_downgrade 0、echo 0 全部与基线一致；secret 轨迹 ±1-3 步差异在已校准噪声带内（同代码两遍固有），判读口径「同 tag ≥2/3 样本系统性越出才判回归」→ 无回归。
2. **定向判别探针**（`tests/_probe_via_disc.py`，新发现）：固化重放语料 8 轮正文**没有任何「本人说开/第三方指控」场面**（self_disc_total=0 是语料沉默不是判别正确），via 规则没被测到——补三场景定向测试：S1 本人当众亲口承认→期望自述类；S2 第三方指控+归属者矢口否认（R2 事故复现）→期望非自述；S3 他人转述→期望非自述。同代码消息层替换规则文本做新旧 A/B，每场景×2 采样：**12/12 全过，三场景 BOTH_PASS**（新文本 S1 填「自述」×2 条 by=听到的在场者、S2 填「听见」、S3 填「被告知」，判别形状正确；零回声）。
3. 探针 measure 新增 `self_disc_n` / `holders_clear`（自述条目触发的 holders 清空计数，观测误填风险）。

**踩坑**：A/B 重放的 4 指标只覆盖簿记正确性，对「本轮语料没出现的场面」零覆盖——压缩语义判据类规则（尤其带历史事故 case 的）必须补定向场景探针，否则「全绿」是假阴性。

**遗留待议**（与 A 层同）：`REFLECT_MAX_TOKENS=2800` 对思考链模型不足；B 层剩余（secret_exposures 链 R05/R08、suspicions R07、relations R04、handle_releases/secret_touches）待逐条端方案。

## 2026-10-21 纪官 prompt 规则段压缩 A 层收口（R16/R17/R18/R03/R13+R14，共 -995 字）

**缘起**：reflect 规则段 18 条平铺约 3045 字，R17(594)/R16(533)/R18(224) 三巨条占 44%。规则段在 user 消息尾部（动态数据在前），不命中前缀缓存，压缩收益实打实（缓存闸门已确认）。simon 拍板：只做 A 层（R16/R17/R18/R03/R13+R14，约 -1020 字），B 层第二批。压缩写法：**判据句 + 一句反例触发词**，不写「压测实证/曾导致」事后叙述，恐吓式禁令换正向祈使句。**核心判据：被压掉的失败模式必须有代码兜底**；无兜底的语义判据必须保留（R16/R17 的代码兜底只覆盖一半，兜不住「出场人物位置报错、state 值本身写错」）。压缩前全文备份 `backup/_reflect_rules_20261021/director.py`。

**A/B 重放探针**（`tests/_probe_reflect_ab.py`，语料 `tests/runs/_probe_reflect_ab_corpus/`）：DeepSeek 8 轮基线叙事固化（r00-r08），逐轮独立重放 reflect（每轮以语料轮前快照为初始状态），monkeypatch `llm.complete` 截获纪官原始 JSON。4 指标：location 漏报率 / state 重复键（同义归并）/ secret 四态轨迹 / 过滤器丢弃条数。探针层 `REFLECT_MAX_TOKENS` 提至 8000（两对照侧同放大）——DeepSeek 是思考链模型，reasoning 吃掉引擎默认 2800 预算致 content 截断（`tests/_diag_reflect_empty.py` 取证：finish_reason=length，reasoning_tokens 2557/2800），引擎侧额度问题另记待议。

**噪声底线校准（回退判读口径修正，方法论记录）**：同代码两遍重放即有固有差异——filter_drop 基线带 {0,1,2}，压缩后三样本 {0,2,3}，两带重叠；secret 轨迹 R4 在全部 6 个非 base2_a 样本中均与 base2_a 不一致（base2_a 自己是离群样本），R1/R3/R6 亦有 ±1「谁起疑」抽动。**「任一步变化即回退」在该噪声下必误触发、无法执行**。校准为：**同 tag ≥2/3 样本系统性越出基线带才算回归**；单样本尾部抽动归噪声。R16 首次对比曾触发回退线（filter_drop 1→3、轨迹 R1/R3/R4 变），三样本复测证伪：filter_drop 三样本 {3,0,2} 与基线带重叠、轨迹偏移无系统性模式、且 R16 直接管辖的 state_drop/state_key_merge 全部 7 run 为 0——判定噪声，R16 保留。

**换模决定（simon，2026-10-21 晚）**：DeepSeek 有「提示词泄漏进叙事正文」前科，且本次重放实测出现 reasoning 吃光预算（2557/2800）、偶发截断（after_r17_c R2 raw_len=152、complete=False，造成 3/3 漏报假象）、偶发 unparseable（after_r16_b R7）等伪迹。**R03/R13+R14 起验证切本地 llama.cpp（127.0.0.1:1234，Qwen3.8-27B-UD-Q4_K_M）**，并在本地重立噪声带（DeepSeek 带与本地带不混用）；探针加规则文本回声检测（字段值含提示词片段即报）。R16/R17/R18 的结论以 DeepSeek 三样本为准，收口时本地全量复核。

**逐条记录（删了哪句 / 历史 case / 兜底代码行）**

| 规则 | 删了哪句 | 历史 case | 兜底代码行 |
|---|---|---|---|
| R16 state_updates 533→150 | ①对象例举「门是否封死、通道是否通行…电源是否可用」②同义键长例「已有『角色A手臂伤口』就不得再写『角色A的手臂伤口』『角色A手臂咬伤』」③泛称禁令的压测实证叙述「造出四键把键表撑到上限」④位置寄生禁令的后果叙述「分队移动后旧键过期、会造成同一角色同时出现在两处」⑤「只有当对象是全新的、与既有键明显不是同一样东西时才新建键」 | ②③：压测 20 轮为同一对象造「角色A/角色A情绪/角色A状态/角色A的情绪状态」四同义键撑爆键表（director.py:1185 注释留档）④：会话 9f2e16e9 R14，位置寄生在物件状态键 value、分队移动后旧键过期致同一角色同时两处（update_locations docstring 留档） | `state_key()`(974) + `_STATE_NOISE`(966) + `_STATE_SUFFIX`(971) 同义键归并（情绪/状态/伤类后缀剥离）；`update_states`(1009) + `_STATE_PLACEHOLDER`/`_PLACEHOLDER_VALUES`(1002-1007) 占位值丢弃；位置唯一真相源 `update_locations`(1029) 与 states 物理分离。保留语义判据：只填变化 / 沿用既有键 / 位置不进 state + 反例触发词 |
| R17 location_updates 594→212 | ①首句「填每个位置发生变化的角色：谁离开了哪里、到了哪里」②「已记录且本轮未动的角色不必重报」——**两句均与硬规「写到必报」自相矛盾**，收敛到唯一语义③漏报后果「漏报会让左栏显示（位置未记录）」④占位长例「寝殿独处时报出全员在寝殿，下一轮分场会照着错的记录来」⑤「如朝会写了六人在殿上就各报大殿」等例举⑥「后写覆盖前写，绝不可报两条互相矛盾的位置」压成「每角色只报一条」⑦「刚移动过的在场角色与群演都要覆盖到」并入「写到的必报」 | 虚报：v2.1.2 纪官把没出场的名册成员报进 location_updates（高昌被报成本轮场景）、下一轮分场被带偏（director.py:1463-1465 注释）；漏报：v0.31.1「谁都没移动＝没有位置变化＝不报」整轮漏报→左栏【人物位置】全片空（director.py:1192-1195 注释） | `_spoken` 举证过滤(1463-1464)：没写到的 who 直接拒收；场景兜底(1466-1483)：对正文写到而漏报者填 scene.place 最小正确值；`update_locations`(1029)：同名归并 + 后写覆盖消解双条矛盾。**无兜底必留**：place 实际具体（位置值无校验，「出场人物位置报错」兜不住）、暂时逃离例外（纯语义判断）。保留判据：写到必报/没写不报/每角色一条/具体 place/暂时逃离例外 + 反例触发词 |
| R18 scene_shift 224→131（少压） | ①例举「（如从客厅走到楼道、天黑了、下起雨）」②后果叙述「引擎据此把场景状态追上叙事（避免场景停在「清晨」而正文早已入夜）」③长反例「不要取全篇最后一个换场段——多线并行时末尾常切到支线，取末尾会把场景钉在空屋子里」压成反例触发词「全篇最后一个换场段」 | v2.1.0 探针 R7：scene.place 漂到「北境铁鞍军大营」、六人无一人该处，把空屋子当主场（DEVLOG v2.1.0 条目；director.py:376-377 注释） | `scene._norm_time`（scene.py）只清时间格式——**simon 修正：该背书强度被高估，R18 实为语义规则**；scene_shift 写回（director.py:1486-1500）place 原样取值无语义校验 → 主镜头落点判据必须保留。少压仅删例举/后果/长反例；schema 块（1229）已带「主镜头落点的地点（不是全篇末尾换场处）」，规则层 gloss 删除属去重复投料 |
| R03 亲属冻结 105→72 | ①类型罗列「父子/母子/夫妻/兄弟姐妹等」压成「父子/母子/夫妻等血缘姻亲」②正面例「（如加「关系紧张」「疏离」）」③反例长句「（例如不得把「父亲」写成「姐夫」、把「母亲」写成「嫂子」）」压成触发词「父亲→姐夫、母亲→嫂子」 | 亲缘关系长轮被覆盖（父子被改写成姐夫一类）→ relations_kinship 结构化字段 + 亲缘冻结（`_KINSHIP_TOKENS` 只认中国血缘+姻亲称谓，见 test_relation_gate / test_preserve_kinship） | `_preserve_kinship`(director.py:749) + `kinship_base`(640)：relations_kinship 显式声明为权威基准，描述句推断不得改写身份——强兜底，故只留一句语义判据（固定事实/只演化情感/不改写身份）+ 反例触发词 |
| R13+R14 evidence 合并 162→63 | ①「（不要改写、不要概括、不要润色）」并入触发词②「引擎会逐字核验它是否真的出现在叙事里」叙述③整条第二句「照抄时不得改动任何一个字…也不得增删标点——改了字就核验不过」——其中**「增删标点→核验不过」是过时断言**（v0.17.4 起 `_strip_punct` 已容忍标点/引号差异），删掉反而修正了与代码现状不符的规则文本；「她→某某看得很清楚」的代词篡改例压成触发词「代词换角色名」 | v0.17.4 举证容标点：纪官引文与正文的标点/引号差异被逐字比对误杀、造成漏记（DEVLOG v0.17.4 条目；`_strip_punct` docstring 留档）；会话 467f1e4c：纪官乱截正文当证据误翻暴露 → `_evidence_related`/`_evidence_transfer` 双护栏 | `_evidence_ok`(director.py:244) + `_strip_punct`(237)：折叠空白+剥离标点后子串核验，字面篡改（代词换名）仍拒、纯排版差异不误杀；语义护栏 `_evidence_related`/`_evidence_transfer`(268+)。强兜底，判据压成「逐字照抄一段连续原文/照抄不到不要填」+ 反例触发词 |

**A 层总账**：5 条 1618 字 → 623 字（**-995，-61%**，对上预估 ~-1020）。R16 533→145 / R17 594→212 / R18 224→131 / R03 105→72 / R13+R14 162→63。

**收口验证（2026-10-21）**

| 项 | 数据 |
|---|---|
| 全量测试 | 378 passed + 1 skipped + 1 deselected（与基线一致，全绿） |
| 逐条 A/B 重放 | R16/R17/R18（DeepSeek，各 3 样本）+ R03/R13+R14（本地 Qwen，各 3 样本 vs 本地 A 侧 2 样本带）：filter_drop、loc_miss、state_merge、ev_drop 全部落在噪声带内，无系统性越界；R13+R14 后 ev_drop 三样本全 0，照抄纪律未松 |
| 回声检测 | 重放探针 echo_total 全部为 0；全链路 8 轮正文 + actions/states 字段扫描零回声（针对 DeepSeek 提示词泄漏前科） |
| 全链路 C1-C6 | 本地 Qwen 8 轮 PROBE OK（512.5s）：C1 说话人 7/8 有对白+焦点裁切生效、C2 秘密 6→6 不丢、C3 关系边 27→29 不塌方、C4 present/locations 全 6、C5【导演指令】标签干净、C6 角色卡零写脏（产物 `tests/runs/_probe_live_gaoshi/`，前档 `_probe_live_gaoshi_preA_20261021/`） |

**遗留待议**：①引擎侧 `REFLECT_MAX_TOKENS=2800` 对思考链模型不足（DeepSeek reasoning 实测吃 2557/2800 致 content 截断；探针层已放大到 8000，引擎侧是否提高或按模型档位自适应待 simon 拍板）②B 层第二批（R04/R05+R06+R08/R07）未动 ③提交/打包/bump VERSION 等 simon 交代。

## 2026-10-21 同批三件：P1 角色块分层 / budget 死配置移除 / reflect 失败留痕（随 v2.1.5 发版）

与上条 A 层压缩同日同批，四件一起进 v2.1.5（PATCH：均非破坏性——无数据契约/机制语义变更）。

| 项 | 改了什么 | 动因 / 历史 case | 代码位置 |
|---|---|---|---|
| P1 角色块分层 | ①秘密提示从「｜」串行粘在「当前意图」行尾改「·」分行（底牌/后果/知情者/正在逼近/发酵/已公开/起疑各自独立成行）②`_ferment_hint` 删 forced 跨段指针（「具体要求见[提醒·秘密发酵]」）与长文案，改 ≤15 字短句（「沉寂已久，可露痕迹」），执行细节统一由全局段 [提醒·秘密发酵] 给出③段名对齐 v2.1.0 语义：「[在场角色]」→「[角色名册（本剧全部角色，不等于同场）]」、「[关系与状态（不可违背）]」→「[关系·状态·旧账]」（关系=既定事实 / 状态=当前最新值 / 旧账） | P0 注入审计预留的 P1 项。单卡秘密提示最长 1208 字粘在意图行尾被整体淹没（行尾从句衰减，同 A 层压缩的根因）；跨段指针留下找不到出处的指引（P0 教训）；角色块肥大主因（R8 六人 system 14664 字、角色名册占 49.3%）。属去重复投料与结构排版，秘密语义内容不删——长执行句搬家到全局段而非删除 | `prompter.py` `_ferment_hint` / 角色块组装 / `state_block` |
| budget 死配置移除 | `DEFAULTS` 删 `"budget": 4096`、`_WRITABLE` 删 budget、`save_config` 整数校验列表同步；`test_focus_follow.py` mock 同步删 | budget 是死配置：`prompter.build_session` 签名死参数早已移除（DEVLOG 3351/3579 两次记档）、`llm._base_payload` 只读 max_tokens、引擎零读取方。simon 拍板「死配置移除，留着也没有用途」。前端/app.py 零引用（发版前 grep 证实）；用户 config 遗留键被 `_WRITABLE` 过滤静默丢弃，无迁移负担 | `llm.py` `DEFAULTS`/`_WRITABLE`/`save_config` |
| reflect 失败留痕 | 新增 `_log_reflect_failure`：三条失败路径（call_failed/unparseable/truncated）除 `logger.warn`（SSE 内存环形缓冲，会话结束即丢）外，追加落盘 `data/sessions/<sid>/reflect.jsonl`（ts/round/reason）；文件活在会话目录内，随 delete_session/prune_sessions 整目录清理；异常不阻断主流程 | reflect 静默失败此前只能靠易变字段反推取证（见「reflect 静默失败判读铁律」——曾误判 37.5% 失败率），留盘后可事后追溯 | `director.py` `_log_reflect_failure` + `reflect()` 三处调用 |

**发版记账**：守护 `tests/_verify_reflect_log.py` 为隔离脚本（monkeypatch `memory.SESS_DIR`→tempfile，不触真实会话目录），不入库；`_log_reflect_failure` 暂无 pytest 正式用例（记为可选补强项）。`tests/_diag*`/`_measure*`/`_verify_*` 按探针脚手架同规格进 .gitignore 不入库。config.json 沿用 assume-unchanged（私值留工作树、库内洗白模板，`git ls-files -v` 显示 `h`）。

## 2026-10-21 下架 NSFW 支持：亲密尺度约束层整体移除（v2.1.4）

**起因**：simon 要求下架 NSFW 支持并作为任务记录以备回滚。拍板两个分叉：①引擎立场 = **中性不预设（对齐 v0.29.0）**——删铁律⑧尺度措辞、停「亲密描写标准」出厂播种、移除自我审查剥离正则；②剧本数据 = **保留磁盘，仅停引擎播种**——高氏王朝既有条目原样留在磁盘，引擎改动只影响今后新建/导入不再自动补亲密条。机制层 `nsfw.py`/机会等级/内容尺度早在 v0.8.0 已废弃；本次下架的是 v1.2.7 恢复的「亲密内容写法约束层」（v0.29.0 曾下架过同款，现再下架一次）。

**改动清单**

| 文件 | 内容 |
|---|---|
| `engine/prompter.py` | `_build_laws()` = `_LAWS_PREFIX + "\n" + _NARRATIVE_DISCIPLINE`；`_LAWS_PREFIX` 保留「己、法律底线（不可破）：未成年角色的性化描写、以及任何真实未成年人的相关内容，一律禁止」；删除铁律⑧尺度措辞（`_LAW8_DEFAULT`/`_law8_override`）。394-399 补下架说明注释 |
| `engine/store.py` | 删 `_STANDARD_ENTRY_CONTENT`（六分层 + 器官词正反示例）+ `_standard_entry()` + `_has_standard_entry()`；`restore_default_entries()`/`save_world()`/`import_drama()` 只补「写法示范·常驻」不再补亲密条；既有磁盘剧本同名条目不清理 |
| `engine/narrative_clean.py` | 删 `_WILL_EVADE_RE`/`_GIVEN_EVADE_RE` 及 `clean_narrative()` 里两行替换；保留 `_DIRECTOR_ENGINE_RE`（导演自居句剥离仍生效） |
| `engine/static/worldbook-guide.html` | 九·五节由「亲密叙事尺度（出厂自带，可停用）」改写为「亲密叙事尺度（引擎不内置）」；未成年硬红线 note 保留 |
| `engine/static/index.html` | 行 2087 文案删「提供亲密叙事技法基线」只留「提供每轮写法范例」 |
| `engine/app.py` | `restore_world_defaults()` docstring 去掉「亲密描写标准」，加注 2026-10-21 下架 |

**设计决定**

- 未成年法律硬红线引擎级保留（`_LAWS_PREFIX`「己、法律底线」），不可由世界书覆盖——尺度中性化 ≠ 解除未成年人保护。
- 「写法示范·常驻」（`STANDARD_EXAMPLE`）是中性 few-shot 示范，与亲密尺度无关，保留不动。
- 剧本数据磁盘保留、引擎只停播种：避免回填/清理旧条目造成数据风险；作者想加亲密写法标准正路是本剧世界书自建一条。
- 自我审查剥离正则下架：尺度中性化后「规避具体生理」不再是引擎立场问题，剥离会误伤正当叙事（对齐 v0.29.0 立场）。

**验证**

| 项 | 数据 |
|---|---|
| 全量测试 | 378 passed + 1 skipped + 1 deselected（基线 377 passed + 1 failed + 1 skipped + 1 deselected，反转 1 例后转全绿） |
| 引擎符号 | 全库 Grep 无 `_LAW8_DEFAULT`/`_standard_entry`/`_has_standard_entry`/`_STANDARD_ENTRY_CONTENT`/`_WILL_EVADE_RE`/`_GIVEN_EVADE_RE` 活引用 |
| 未成年红线 | `test_intimacy_scale.py::test_minor_redline_kept_in_engine` 仍通过 |

**测试反转**（守护跟着语义走）

- `test_intimacy_scale.py` 由「铁律⑧恢复版」改为「不预设尺度回归」：断言「亲密与性描写/身临其境/正面写实/不预设上限/不强制克制/提前引入/硬写」不在 sys_p、`not hasattr(prompter, "_LAW8_DEFAULT")`；未成年红线断言保留。
- `test_standard_entry.py` 由「出厂播种测试」改为「不播种回归」：`test_new_world_does_not_seed_standard_entry`/`test_existing_world_legacy_entry_preserved`（旧条保留）/`test_store_exposes_no_standard_entry_symbols`。
- `test_standard_entries.py` 保留写法示范断言，亲密条断言移除或反转为「不再播种」。
- `test_narrative_discipline.py::test_law8_intimacy_restored_in_engine` → `test_law8_intimacy_not_in_engine`。
- `test_drama_io.py` 行 77-78 `assert "亲密描写标准" in [...]` → `not in`。
- `test_narrative_clean.py::test_v2_director_voice_and_evasion_stripped` → `test_v2_director_voice_stripped_evasion_kept`：导演自居/铁律/分隔线仍剥离，自我审查式规避声明（「鉴于…规避具体的生理…我将以…」）改为 `in out`（不再剥离）。

**回滚蓝本**：`git tag` + `_backup_offshelf_nsfw_20261021/`（11 个改动前文件副本）+ 本条目。回滚时按本条目改动清单逐文件还原即可。

---

## 2026-10-21 提示词注入审计落地 P0：指令收尾 + 去重 + 情境条目合并（v2.1.4）

**起因**：对 `act()` → `build_session` 全链路做注入审计（离线组装实测 + 逐段量字数），定位到三处结构性错配与一处世界书重复投料。simon 选「P0 全做 + 世界书第 3 条」，P1/P2 留待实机数据。

**P0 改动**（`engine/prompter.py`）

| # | 项 | 内容 |
|---|---|---|
| 1 | 末尾 user 拼接顺序 | `【导演指令】+directive+"\n\n"+env_block` → `env_block+"\n\n【导演指令】"+directive`。after 命中里压着 1128 字技法标准，旧序把导演指令推到倒数第二位，与「导演指令优先」自相矛盾；现在整条 prompt 的最后一个 token 区域恒为本轮指令。标签沿用 `【导演指令】`（与 `app.py:871` 落盘标签一致） |
| 2 | 「点名角色必须出场」四处 → 一处 | 只保留 `[导演指令]` 段的 `focus_note`（紧邻指令文本）。删除 `[输出格式]` 里三句（含「点名角色必须作为本轮叙事焦点之一出场」「严禁无声略过」「必须呈现对应段落」）、`focus_block` 的「必须作为本轮叙事主视角出场并推进剧情」、`present_clause` 的「（必须重点描写并推动其剧情）」。`[输出格式]` 首句「角色名：」锚点原样保留（v2.1.0 踩过） |
| 3 | 提醒段去自我降级 | 两段标题 `[可选提醒·X]` → `[提醒·X]`（`_ferment_hint` 的跨段指针同步）；删 `_global_pressure_block` 段末「仅为可选提醒…可完全略过」、`stale_cast_block` 段末「优先级仍低于导演指令…听导演的」、pressure 行内两处「若不合叙事，不强求」。优先级声明统一收到铁律丁一句：「导演指令优先：本轮的所有提醒、建议与背景设定，与导演指令相抵时一律听导演的」 |

**世界书改动**（`dramas/高氏王朝/world.json`，经 `sync_drama.py install` 铺三态）

- 「采选启动」+「册后倒计时」合并为「采选与倒计时」：两条 keys 高度重叠、内容把「半年·四步·矮一寸」讲了两遍，命中时会同时注入两段近似环境描述（after 同时命中 4 条 → 3 条）。合并条 185 字，keys 取并集。
- 「铁鞍军报」删掉与常量「虎符·合符调兵」逐字重复的那句（左符/右符/合符，44 字），保留「南下是四笔账」的判据。
- 20 条 → 19 条；`opening.txt` 两行情境清单同步为一行。

**验证**

| 项 | 数据 |
|---|---|
| 全量测试 | 381 passed + 1 skipped + 1 deselected（基线 380，新增 1 例：优先级声明唯一出处） |
| 同快照新旧 prompter 对照 | system 9765 → 9611（-154），总 prompt 12028 → 11874 |
| 末条 user | 旧收尾「…满朝没人知道。」（世界书条目正文）→ 新收尾「…问宗室的态度。」（本轮指令） |
| 重复约束计数 | 点名角色必须 0 / 必须作为本轮叙事焦点 0 / 优先级低于导演指令 0 / 可完全略过 0 |
| 世界书注入 | before 7 条 / after 3 条（原 4）/ demo 1 条；合并后情境段省 68 字并消除一次重复注入 |
| 三态 | `sync_drama.py check` 三方一致 |

**测试反转**（守护跟着语义走，不是障碍）

- `test_stale_cast.py::test_advisory_is_subordinate_to_directive` → `test_advisory_does_not_self_demote`（断言段内不再出现降级句）+ 新增 `test_directive_precedence_declared_once_in_laws`。
- `test_stale_block_is_last_system_block` 的判据由「正文以『听导演的。』结尾」改为块头序（该段之后不得再出现任何 `[xxx]` 块头）——段末降级句已删，原文判据失效。
- 顺带修掉该文件里重复定义两次的同名测试函数。

**设计决定**

- 优先级声明「只出现一次」而非「每次都强调」：v2.1.2 实证段末给台阶会让模型整轮无视，而同一声明重复四遍只会互相稀释。声明位置选铁律丁——它是唯一与导演指令直接挂钩的条款。
- 世界书合并只做去重、不做删减：三条的情境职能（采选/倒计时/军报）仍需在各自触发时出现，故保留两条独立条目，仅消除重叠措辞。
- 未做 P1/P2（角色块秘密分层、名册改名、状态段合并、纪官 prompt 重排、铁律⑧与世界书技法分工）——这些要实机数据支撑，先拿到本轮对照再定。

---

## 2026-10-21 恢复默认条目后原地刷新 +「恢复成功」提示框（PATCH 档，未升版本）

**起因**：simon 反馈——引擎默认条目点「恢复默认」后，要退出剧本库再重进才能看到恢复效果，用户容易误判系统无响应。

**改动**（集中 `engine/static/index.html`）

| 项 | 内容 |
|---|---|
| 提示框 | 新增轻量 toast（`#app-toast` + `showToast()`，CSS `.toast/.pos/.danger`），浮层 z-index 高于 modal，自动消失（成功 1.8s / 失败同），不打断操作流 |
| 恢复流程 | `w-engine-restore` 回调改为：调 `/restore-defaults` → **先 `loadWorld(name)` 原地重渲染世界书**（成功与否都刷新）→ toast「恢复成功 / 无需恢复 / 恢复失败」→ 展开引擎组；`fetch` 套 try/catch 网络异常也走失败提示 |
| 护栏 | `test_frontend_binding.py` MAIN_FLOW_PROBES 增 3 条：`function showToast`、`showToast('恢复成功'`、`await loadWorld(name)`（防止后续误删「原地刷新」回退成旧行为） |

**验证**：`test_frontend_binding.py` + `test_standard_entries.py` 19 passed；`_frontend_binding_check.js` ALL PASS；`test_universality.py` 5 passed；jsdom 探针 `tests/_probe_restore_toast.js`（脚手架，不入库）9 项 PASS——恢复前引擎组空 → 点恢复 → 断言 POST 端点、随后 GET 世界书、toast 文案/样式、引擎组渲染出补回条目且自动展开、取消 confirm 不发请求。

**设计决定**：提示框用 toast 而非 modal——恢复是低风险补救动作（只补缺失不覆盖），弹窗确认会比原 confirm 更重；确认框保留（丢未保存修改的风险仍需确认），成功反馈降为非阻断 toast。

**踩坑**：无。jsdom 下 `setTimeout` 需替换成同步执行，否则 toast 断言抢在自动隐藏之前跑不完。

**提交打包**（simon「提交、打包」）：全量测试 380 passed / 1 skipped；提交 `98d3d87` feat(ui)（index.html + test_frontend_binding + DEVLOG）；纯前端 PATCH 不碰引擎机制，版本维持 v2.1.3、不重复打 tag；打包覆盖 `dist/personae-v2.1.3.zip`（32 条目 / 231.5 KB），三方一致守卫通过，config 洗白核对（base_url/api_key/model 空、providers=[]、fallback 空），包内无 key/绝对路径/运行时态泄漏，toast 已随包。

---


**起因**：simon 要求先做前端 UI 评估（桌面端 + 移动端，美观/简洁/大方），随后要求「按你的建议落地前端 UI 改造优化方案任务，逐一进行落地迭代」。纯前端迭代，不碰引擎机制。

**改动**（集中 `engine/static/index.html`，+136/−58；测试脚本 `_frontend_binding_check.js` 同步升级）

| 任务 | 内容 |
|---|---|
| 1 响应式与导航骨架 | 顶栏按「创作/运行/系统」三组收口（`.topnav-group` + `.nav-group-label`），按钮 ID 与主流程绑定零改动；`#open-menu` 补 `aria-label/aria-expanded/aria-controls`；720px 抽屉宽度修正（`.rail-*.collapsed` → `min(86vw,360px)`）；新增 480px 小屏断点（弹窗/底栏/动作行纵向布局，触控最小 42px） |
| 2 管理面板层级 | 世界书条目改「摘要行 + 展开详情」（`.e-meta` 徽章（顺序/引擎默认/常量/秘密）+ `.e-summary` 46 字摘要 + `.e-actions`）；剧本库详情工具栏 `.modal-tools` 分「剧本内容/备份」两组；角色表可选字段 `details.opt-group` 折叠；全局 `:focus-visible`；radius token（sm/md/lg）；胶带/纹理装饰减法，手账质感只留开场卡与主按钮 |
| 3 回归与实机验证 | 见下 |

**红线守住**：世界书隐藏字段 `origin/demo/first_round` 仍经 `data-*` 原样往返（`entryCard` → dataset → `collectWorldEntries`），`test_frontend_binding.py` + `test_standard_entries.py` 不破。按钮 ID 与 `send()` / `#start.onclick` / `cfgProviders` 等主流程禁区零触碰。

**验证**

- 全量 `pytest tests/`：**380 passed + 1 skipped + 1 deselected**（与 v2.1.2 基线一致）。
- Node 沙箱 `tests/_frontend_binding_check.js`：20 项 ALL PASS，新增「隐藏字段原样回传」「抽屉打开时遮罩同步」断言。
- 浏览器 smoke（puppeteer-core + 系统 Chrome，产物 `tests/runs/_probe_frontend_smoke/`）：桌面 1440 顶栏三组标签清晰、菜单按钮隐藏；820/720/390 菜单按钮 42px、开局卡全宽、开始按钮触控达标。

**设计决定**

- 顶栏收敛为三组而不是继续平铺：创作（剧本库/从剧本生成）、运行（世界状态/会话/结束剧本）、系统（系统设置/运行时日志）。七个入口不变，变的只是分组与标签，符合「按职责归类」的 UI 偏好。
- 世界书条目摘要行固定展示顺序徽章、来源（引擎默认）、常量、秘密四个状态，长正文只在展开后编辑——列表可扫描性优先于编辑便利。
- 装饰减法：手账风只留开场卡与主按钮作为品牌记忆点，左栏面板、弹窗、日志行去掉胶带/纸纤维叠加，长文本区改干净底色。

**踩坑**

- Node mock 里 `classList` 若用无状态 stub，抽屉开合断言恒假——必须用真实 Set 状态模拟。
- `new Function(code)` 内声明的函数不会挂到 `globalThis`，沙箱需显式 `return` API（前两次 FAIL 是判据问题，非产品代码问题）。
- smoke 截图里的灰色斜线是手账拟物笔杆装饰，不是布局破损。

---

## 2026-10-21 静默数字接回提示词：[可选提醒·久未登场]（semver PATCH→v2.1.2）

**起因**：simon 跑会话 `8823e5f7`（13 轮）反馈——「部分角色当玩家不手动指定到提示词注入的时候，即使面板里提示【xx 回合没有行动，引擎正在关注】但依然没有任何行动」。

**核实：面板是个空承诺。** 会话实况：终局 `silent_rounds` 为 高天 5、苏雅芝 2、高昌 2、高洋 2、陆敏 0、高琳 0；R8–R13 六轮正文只出现高琳、陆敏两人，其余四人一次都没被提到（连「寝宫那边如何」的半句都没有）。

链路追到两处：

| 环节 | 代码 | 事实 |
|---|---|---|
| 计数 | `director._update_silent_rounds`（`director.py:848`） | 按纪官 `actions` 判定，算得很准 |
| 消费 | `index.html:1143` 是**唯一**消费方 | prompter 全文件无 `silent` 引用 → 提示词里一个字都没有 |
| 自述 | 同函数 docstring | 「v0.30.1 起不再驱动任何强制焦点/提示……**不干预叙事走向**」 |

也就是说引擎算出了「高天已经 5 轮没戏」，然后什么也没做，同时前端写着「引擎已在关注」。**这比不提示更糟——它让玩家以为机制在兜底。**

还有一个负反馈环：`prompter._ROSTER_STALE_ROUNDS = 3` —— 位置 3 轮没更新就当「位置不确定」，写进 `[本轮场面]` 的「位置未更新」组并附「勿断言其与谁同处一室」。越没戏 → 位置越不可信 → 越不该写。会话里高天的位置还被记成「金銮殿」（R7 早朝时被讨论的地名，他实际在北境），这类误报会进一步把分场带偏。

**方案取舍（simon 选 B）**

| 方案 | 内容 | 结论 |
|---|---|---|
| A 硬性焦点回归 | silent ≥ N 强制进下一轮主体 | 否决：正是 v0.30.1 废掉的「在场即须留痕」，且会与导演指令抢方向盘 |
| **B 软提醒块** | 仿「秘密发酵」范式，把数字接回提示词 | **采纳** |
| C 只改文案 | 撤掉「引擎已在关注」的承诺，引擎不介入 | 否决：只是把问题藏起来 |

**改动**

| 文件 | 改动 |
|---|---|
| `prompter.py` | 新增 `stale_cast_block()` + 常量 `STALE_ROUNDS=2` / `STALE_MAX_NAMES=2`；`build_session` 在 `focus_block` 之后、秘密发酵之前注入（末尾区，近因强） |
| `director.py` | `_update_silent_rounds` **删掉焦点豁免**：焦点轮里镜头外角色同样累加 |
| `index.html` | chip 提示语改「连续 N 轮没有行为，下一轮会提醒叙事给他一处交代」（与真实行为对齐） |

**设计决定**

- **分两类措辞，因为这是两种病**：位置与当前场景不同的 → 「连续 N 轮没有戏」＋「给一两句话交代，留在自己位置上」；位置就在当前这一场的 → 「不是不在场，是被写成了背景」＋「让他对眼前的事有个具体反应，不要只让他站在那儿」。后者才是面板数字最难解释的情形。
- **一轮最多点名两人**：静默最久的优先。不设上限就会重演「人人有份」式过场——v2.1.0 拆职责治的正是这个病。
- **纯整数阈值，零语义判断**：谁该有戏由导演指令与叙事决定，引擎只负责让「被冷落」可见。语义检测终成穷举（v2.1.0 删 `_GROUP_WORDS` 的教训）。
- **焦点轮不豁免镜头外角色**（`director.py` 同步改）：豁免是纯展示时代的顾虑（「镜头外的人本轮不该被写，计沉默会误伤」）。数字一旦要驱动提醒，豁免等于让最该被提醒的人免罚——实测玩家连续用指令点名同一批人时，镜头外角色的数字长期停在 0，提醒永不触发，等于那段不存在。
- **陈旧位置不得用来断言「他就在这一场」**：`_ROSTER_STALE_ROUNDS` 之外的记录不写成「位置已多轮未更新」（那句会降低模型确定性、让它不敢下笔），改为给落位自由：「原先在 X，可按他的身份与处境自行落定一处，写清在哪」。
- **正文是最终举证层**：`actions` 与 `location_updates` 都按「名字是否出现在正文」过滤（与 `secret_exposures` 的 evidence 核验同一原则——引擎不猜，只核验出处）。静默判定则以「纪官摘要 **或** 正文出现该名字」为准（后者是漏抽兜底）。

**验证**

- 全量 `pytest`：**380 passed + 1 skipped + 1 deselected**（v2.1.1 基线 358 → 新增 `test_stale_cast.py` 16 例 + `test_director.py` 6 例）。
- 专用实机探针 `tests/_probe_stale.py`（9 轮，刻意复现单线偏置）：**PROBE OK，651.6s**，会话 `96ca1989`，产物 `tests/runs/_probe_stale/`。
  - R1–R6 连续六轮只推高琳/陆敏线（说话人每轮恒为 1），`silent_rounds` 里 苏雅芝、高洋 涨到 6。
  - R3 起每轮提示词都带 `[可选提醒·久未登场]`，点名静默最久的两人（上限 2 生效）。
  - R7（空指令）正文给出「与此同时，某处」式切场，把苏雅芝拉回 → 静默归零；R8/R9 全员归零，说话人 2–3 人、无「各自一段」式过场。
  - 单轮说话人数全程 1–3（开局 2），未退回「人人有份」。
- 与起因会话对照：`8823e5f7` 里 13 轮中后 6 轮单线、四名角色全程零出场、数字涨到 5 而引擎毫无动作；本次同一偏置下第 7 轮即被拉回。

**踩坑**

五次实机才收敛，前四次全部 FAIL，原因各不相同，都值得记：

1. **判据 off-by-one**：拿「本轮结束后的快照」去判断「本轮提示词里是否提醒了谁」，等于用下一轮的提醒要求本轮正文，首轮直接假失败。提醒的渲染依据是**上一轮结束时**的快照 + 本轮指令现算的 `focus`。
2. **纪官的 actions 虚报（最深的坑）**：`present` 改成名册后，reflect prompt 里「actions 覆盖本轮所有在场角色」等于要求纪官给六个名字各编一句。实测正文只写两人，actions 报满六人，四条是「维持现状」「保持北境稳定」——`silent_rounds` 全员归零，提醒段永远不会触发。**这是 v2.1.1 `present` 语义变更的第二处连带盲区**（第一处是位置兜底，已修）。治法两层：prompt 改为「只写真出场的角色、不要写占位摘要」＋引擎按正文举证过滤。
3. **位置虚报同源**：没出场的角色被报进 `location_updates`（把高昌报成本轮场景），下一轮 `[本轮场面]` 会照着错记录分场，提醒段还会误判「他就在这一场里，让他有个反应」——而他根本不在。同样按正文过滤。
4. **探针判据把「提及」当「登场」**：R9 只写了苏雅芝走路、高天读信两场切镜头，因名字被提及命中 6 人 → 判「六人过场」。改用「开口人数」。
5. **措辞决定执行力**：首版写「若本轮叙事允许，从中挑一处交代……可完全略过」，R8 整轮无视；改「本轮请给出其中至少一处」后生效。位置写成「已多轮未更新」时模型不敢下笔（不知道该把人放哪），改成给落位自由后立刻写出来。
6. **纪官漏抽**：R9 正文写了高天，纪官 `actions` 里没有他，静默照涨到 8 → 下一轮提醒位又被刚写过的人占掉。加正文兜底（名字出现即算有戏）。

结论：**这一版真正治病的不是提示词，是举证过滤。** 只加一段提醒文字，会被纪官的虚报吃掉——数字永远归零，机制静默失效；而面板照旧显示「引擎在关注」。这也再次验证 v2.1.1 那条教训：`present` 语义一变，所有遍历 `present` 的地方（`actions` 抽取、位置兜底、位置上报）都得重审。

---

## 2026-10-21 开场角色区改为只读名册 + 首轮场面不再断言全员同处（semver PATCH→v2.1.1）

**起因**：simon 提出开场区的角色勾选应去掉选择权，改为后台默认全选且不再显示于前端，理由是「否则会导致角色表和世界书的设定出现缺失和冲突」。

**核对结论：理由成立，且能说清机制。** `cast` 不是「界面显示几个人」，它是四类簿记的定义域：

| 簿记 | 代码位置 | 少选一个人的后果 |
|---|---|---|
| 关系网 / 亲缘 | `memory.py:37-44` 只遍历 `present` 收 `relations`、`relations_kinship` | A 卡里指向 B 的条目照样收进来 → 基线留下「A → B」而 B 无卡，悬空引用 |
| 秘密 | `memory.py:50-59` 按世界书 `character` 字段播种，**不看 cast** | 归属者不在名册时秘密仍进快照却无处投递（角色块只遍历 `cards_present`，`app.py:626`），pressure 累成死账 |
| 短期目标 | `memory.py:72` | 名册外角色无 goal，reflect 也补不到 |
| 世界设定 | 与 cast 无关，全量注入 | 设定点名的角色没有卡，模型只能自由发明 |

高氏王朝实测：20 条世界书里高昌被 13 条提及、高琳 9、高天 7、苏雅芝 6；`[承平格局]` 一条点名五人、`[选后诏·半年死亡钟]` 点名四人。**漏勾一个人，就有六到十三条设定变成指向无卡角色的无主指称。** 更根本的是 UI 承诺与引擎能力不匹配——界面上有勾选框等于承诺「少选是受支持的模式」，而引擎没有任何补偿机制。

**历史对照（为什么这次不是重走老路）**：`v1.2.0` 曾删过一次勾选列表，改成全员登场 + 「首轮由引擎自行判断谁在场」，结果失败并被加回来（见本文档 v1.2.0 条目）。当时的归因是「不该全选」，实际缺的是**分场表达**——`present` 全员进提示词、又写着「只能写这些在场角色」，模型只能把六个人一起写到开场地点（实测填「街道」，不该在场的人全冒出来）。`v2.1.0` 的 `[本轮场面]` + `locations` 才补上这一环，所以这次可以走。

**改动**

| 文件 | 改动 |
|---|---|
| `index.html` | `renderNpcs` 改为只读 chip（`NPC_NAMES` 缓存名册）；`startSession` 不再从 `#npcs input:checked` 收集 `cast`，请求体只剩 `{scene, world}`；空名册提示改「该剧本下没有可用的登场角色」；CSS 删勾选框样式；标签改「登场角色（本剧本全部角色，不可增减）」 |
| `app.py` | `session_new` 新增名册完整性校验：传子集直接 400 并点名缺谁。世界不存在 / 跨世界混入 / 空名单三条原有错误保持原顺序（跨世界先拦，缺人后判） |
| `prompter.py` | `scene_roster_block` 首轮分支独立：无 `locations` 时只输出「`- 开场：<场景>`」+ 一条约束，**不再断言「全员同处这一处」**；另补「全员位置陈旧」分支（非首轮但无可用记录，同样不断言同处） |
| 脚手架 | `playthrough.py` / `stress_longcontext.py` 建局不再传 `cast`；`fetch_cast` 默认取全量，只用于填弧线模板与统计点名率 |

**设计决定**

- **保留只读名册，不做纯隐藏**：去掉的是「权限」不是「信息」。开局前需要知道这一局有谁——卡是否齐全、剧本是否为空，都靠这一行；彻底隐藏会把「剧本少了一张卡」变成开局后才发现的意外。代价为零（一排 chip）。
- **拒绝子集而不是静默补齐**：补齐会让调用方以为自己的选择生效了、实际登场的是别人，与 `app.py` 既有跨世界校验的口径一致（不替前端做纠正）。将来若真需要减负，正确路径是拆剧本，不是减名册。
- **首轮不替作者决定谁在场**：引擎此刻确实没有位置数据，硬写「全员同处」等于替作者决定开场戏有谁——开场若是某人的寝殿，朝堂六人也照塞。改为「只让本来就有理由在此处的人登场」，位置留给首轮 `reflect` 记录，第二轮起自动分场。

**验证**

- 全量 `pytest`：**357 passed + 1 skipped + 1 deselected**（v2.1.0 基线 354 + 首轮用例拆成 2 例 + 子集拒绝 1 例 + 前端只读名册 1 例）。
- 离线 `build_session`（高氏王朝 6 卡，R1 形态，开场「宫中寝殿·深夜」）：prompt 10105 字；`[本轮场面]` 输出「- 开场：宫中寝殿（深夜）」+ 约束句，无「全员同处」；`本剧角色名册（有卡、可出场）：六人` 正常；`[输出格式]` 仍在场面段之后。
- 前端沙箱（node + 最小 DOM）：`startSession` 发出 `POST /api/session/new`、请求体含 world **不含 cast**、登场名册渲染为 chip 且无 `type="checkbox"`、开始按钮正常解锁。
- 8 轮本地实机：见下方「实机结果」。

**实机结果**（8 轮，本地 Qwen Q4_K_M，PROBE OK，553.8s；产物 `tests/runs/_probe_live_gaoshi/`，v2.1.0 产物留档 `_probe_live_gaoshi_v210/`）

| 指标 | v2.1.0 | v2.1.1 | 说明 |
|---|---|---|---|
| 字数均值 | 1357 | **1153** | 单场戏变多，长段铺开的轮次减少 |
| 每轮说话人数 | 2.75（1–6） | **1.5**（2,1,3,2,0,1,1,2） | 分场后单场对白为主；含 1 轮纯叙述、1 轮仅群演开口 |
| 名册角色开口轮数 | 8/8 | **6/8** | R5 为无声过场（苏雅芝与人擦肩、全程未开口），R7 只有宫女传话 |
| `locations` 键数 | 分组 1–3 处 | **2→3→4→5→6→6→6→6** | R1 只记正文写到的两人，后续逐轮补全——分场簿记按预期收敛 |
| `present` | 恒 6 | 恒 6 | 名册口径不变 |
| 关系边 | 27 恒定 | 27 恒定 | 无塌方 |
| 秘密终态 | 5 起疑 + 1 暴露 | 4 起疑 + 1 暴露 + 1 潜伏 | 秘密簿记未退化 |
| 角色卡 | 未被写脏 | 未被写脏 | — |

- **R1 达成目标**：开场「深夜·宫中内殿书房」只写了高昌与苏雅芝两人，不再把名册六人一起搬进书房；`locations` 也只记这两人。
- **代价要说清**：说话人数从 2.75 降到 1.5，群像的「同场对白密度」明显下降，R5 整轮无对白。这是分场收敛的直接结果，是否算过度收敛需要 simon 按体验判断——若认为太静，方向应是「允许镜头外的动静以一句半句报进来」，而不是回退到全员摆进同一场。

**踩坑**

- **只改提示词不够，代码里还有一处同源兜底**：第一次实机（R1 正文只写两人）发现 `locations` 仍被写成六人全在书房。根因不是 prompt——`director.py` 在 reflect 末尾有一段 v0.31.1 的兜底：对 `present` 里所有尚无位置记录的角色用 `scene.place` 占位。`present` 是名册（全员）时，这段兜底等于把正文没写的人搬进当前场景。已收窄为「本轮正文或导演指令点到过这个名字」，并加守护用例（`test_reflect_location_fallback_only_for_characters_in_narrative`）。**结论：present 语义一变，所有「按 present 遍历」的兜底都要重新审一遍，不能只看提示词。**
- **前端分组把「未记录」当成了主镜头**：`rosterHtml` 按人数降序排组，R1 时四人的「位置未记录」组人数最多，会被排到第一并标「·主镜头」，与后端「主镜头只在有位置的人里选」正好相反。已改为未记录组固定置底、不参与主镜头评选。
- **探针判据本身会否定新设计**：旧 C1 要求「每轮 ≥2 名册角色开口」，分场后「无声过场」「只有群演开口」都是合法结果，却被判 FAIL。改为：无对白轮 / 仅群演开口记 INFO，非焦点轮单人开口记 WARN，只在「名册角色开口轮数 < 总数一半」时 FAIL。**用旧设计时期的判据去验收新设计，一定会得到假失败。**

---

## 2026-10-21 拆职责：`present` 从「在场名单」改为「角色名册」+ 新增 [本轮场面] 分场段（semver MINOR→v2.1.0）

**起因**：simon 从实机观察到「叙事不够集中、LLM 为合规把每个人物都过一遍」，先删了世界书里的镜头纪律条目（v2.0.2 前一条日志），但指出根因在引擎侧。查证结论：**`present` 这个字段同时承担了两件互相冲突的事**——「本轮允许被写的人」与「物理上同处一地的人」。群像多线叙事里两者必然打架，表现为六人分处四地时，提示词仍写「本轮在场角色：六人……只能写这些」，模型唯一的完成方式是逐个过场。

**根因链（三处，均实证）**

1. `present` 不收缩。两处收缩机制都失效：`director.reflect` 的 `present_change` 在 v2.0.0 定向反向合并时被误删了 JSON 模板行（写回代码留着，字段成死代码，模型从不输出）；`scene.apply` 的 `leave/arrive` 依赖「指令含离场词」且模型基本不填 `arrive`。
2. 补回 `present_change` 更糟（实测）：手动插回模板行后模型立刻填 `{"leave":["高洋","陆敏","高琳"],"arrive":[]}`，但判据是「本轮叙事重点」而非物理位置——把与主角同处一室的角色踢出名单、把千里之外的人留场，支线角色下一轮直接消失。
3. 提示词四处反向鼓励「人人有份」：`_LAWS_PREFIX` ①「让每个**在场**角色都动起来、都说话」；`[输出格式]` 的在场白名单措辞；`focus` 轮「其余在场角色此刻在别处/原场景待命」的位置断言；`pressure_targets(snap, present)` 拿 `present` 当同场判据（变全员后任何起疑者都算当场对峙）。

**改动（引擎机制层）**

| 文件 | 改动 |
|---|---|
| `prompter.py` | 新增 `scene_roster_block()`（`locations` × 默认主镜头 → `[本轮场面（按位置分场，不可违背）]`），**合并**原 `[人物位置]` 段（同源不重复投料）；`present_clause` 改「本剧角色名册……不等于本轮同场」；`focus` 段删位置断言、地点改取焦点角色实际位置；`_LAWS_PREFIX` ① 改「让本场的人动起来」 |
| `director.py` | 删 `present_change` 规则文字与 31 行写回代码（死机制整体移除）；`scene_shift.place` 口径改「本轮主镜头落点」（原「叙事末尾地点」在多线时随机漂）；新增 `_same_place()`，`pressure_targets` 同场判据改用 `locations`；删 `_GROUP_WORDS` 白名单及其分支，新增 `_focus_place()`（焦点所在地取 `locations` 众数） |
| `scene.py` | 删 `leave/arrive` 处理与 `_PROMPT` 两字段、`LEAVE_KEYS`；场景层只管地点/时间/天气，不判断角色进出 |
| `app.py` | `keep_set` 语义注明（无焦点轮 keep=名册，等于只剥名册外角色；焦点轮按焦点裁剪）；日志措辞改「台词校验」 |
| `index.html` | 左栏「在场角色 / 场景」→「角色名册 / 场景」；新增 `rosterHtml()`，chips 按 `locations` 分组，主场景在前、他处整组降透明度并标注地点；全员同场时不分组（避免每回合多一层与场景行重复的框） |
| 数据 | 零改动（`present` 字段名保留，语义改；新老会话并存，旧会话按其 `present` 当名册） |

**为什么不迁移旧会话**：旧会话 `present` 少人，多数来自当年的显式离场（人真的走了）。补全会让退场角色复活。宁可少几个人，也不让死人回来。

**设计决定**

- **默认主镜头取「人数最多的一处」**，不取 `scene.place`：预览实测 `scene.place` 会漂到空场景（R7 记「北境铁鞍军大营」，六人无一人该处），取它会把空屋子当主场。`scene.place` 单独渲染为「镜头所在（此刻无人）」，明确提示从哪一处写起。
- **焦点轮仍按焦点子集裁剪台词**：那是导演显式指定「本轮只看这几个人」，与「在场」无关，保留。
- **位置陈旧阈值 3 轮**：`locations[name].round` 落后当前 3 轮以上归入「位置未更新」，不再钉在原地当事实（支线角色常连续多轮不被提及）。
- **删掉 `_GROUP_WORDS` 而不是加否定词检测**：「避开众人」被当成群体点名，是因为这张表判断的是「指令里有没有这几个字」而不是「是不是群体点名」。同类白名单只能靠不断加词兜语义，加到最后一无所获（simon 判断一致）。删掉后镜头只由「有没有点名具体的人」决定，没点名就交给默认主镜头——这是减法。

**验证**

- 全量 `pytest`：**354 passed + 1 skipped + 1 deselected**（v2.0.2 基线 344；本次反转 3 例 present_change、调整 4 例场景/焦点用例、新增 `test_roster.py` 8 例与热点回归 3 例）。
- 离线建 prompt（R7 真实快照）：14449 字；`[本轮场面]` 正确输出四地分组与「镜头所在（此刻无人）」，旧措辞（「本轮在场角色」「只能写这些在场角色」「人物位置（不可违背）」）全数为 0。
- 8 轮本地实机（llama.cpp Qwen3.8-27B-UD-Q4_K_M）：见下方「实机结果」。
- 首页冒烟：200，`角色名册 / 场景` / `function rosterHtml` / `rosterHtml(snap, chipOf)` 均在页面里。

**实机结果（8 轮，PROBE OK，616.5s；产物 `tests/runs/_probe_live_gaoshi/`，改前产物留档 `_probe_live_gaoshi_v202/`）**

| 指标 | 改前 v2.0.2 | 改后 v2.1.0 |
|---|---|---|
| 字数均值 | 1670 | 1357（−19%） |
| 每轮说话人数 | 3.38（1–5 人） | 2.75（1–6 人，无 0 人轮） |
| 正文地点命中数 | 1.25 | 1.38（分场更明确） |
| `locations` 实际分组数 | 4–5 处/轮（角色漂到北境马车/城墙/大营） | 1–3 处/轮（收敛在宫中各处） |
| 主场景开口率 | 16/22 = 73% | 6/9 = 67%（不再要求人人有份） |
| `present` 人数 | 恒 6（与位置脱钩） | 恒 6（名册，按设计） |
| 关系边 | 27 恒定 | 27 恒定 |
| 秘密终态 | 6 条全「起疑」 | 5 起疑 + 1 **暴露**（首次出现真暴露） |

- 格式：8 轮全部为「角色名：」起段多说话人叙事；无幽灵角色、无「玩家」「导演」说话人。
- 位置簿记：`locations` 每轮覆盖 6/6，`present` 不再被收缩，两者终于各司其职。
- 秘密出现 1 条「暴露」（探针记 WARN 非 FAIL）：此前 8 轮从未突破「起疑」，B 方案让同场判据变严（`pressure_targets` 用 `locations` 判同处一地）后，碰撞仍能自然发生。

**踩坑**

- **`[输出格式]` 改写时丢掉「台词」锚点，实测格式塌回散文对白**：首版新措辞只说「叙事中只可出现名册内角色」，8 轮里 r03/r05/r06 出现「高昌的声音平淡无奇：…」这类散文式对白，`角色名：` 分段消失，探针判 C1 FAIL。修法是在首句写回显式格式要求（「开口的角色以『角色名：』另起一段接台词」），并加静态探针守护该句。**结论：格式要求必须留在 `[输出格式]` 首句，不能被名册/分场信息挤到后面。**
- `_focus_place` 若回退 `scene.place`，焦点轮仍会把镜头引到空场景；必须只在 `locations` 全空时返回空串（prompt 里就不写位置）。
- `[本轮场面]` 与 `[人物位置]` 合并时，`place` 变量被追加过「（时间｜天气）」后缀，导致「镜头所在」那行出现双括号；渲染时保留 `place_raw` 分开用。
- 地名不归一是已知残留：纪官自由命名（「宫中回廊」「宫中回廊尽头」「宫中廊下」），同一片区域可能被算成两处。当前 8 轮未出现因此误判分场的实例，但多轮长会话下有风险，列为观察项（TODO）。

---

## 2026-10-21 世界书条目分组展示：引擎组折叠置顶 / 剧本组展开 + 常量置顶（semver PATCH→v2.0.2）

**起因**：v2.0.1 只做到「灰边 + 徽标」的来源标识，两类条目仍混在同一个列表里。simon 提出按来源分成两组：系统（引擎）条目一组置于最上方、默认折叠，并采用一句直白提示语「不了解它是干嘛的就别动它」；剧本条目一组置于下方、默认展开，组内常量条目自动置顶。

**改动（纯前端展示层，后端与数据零改动）**
- `index.html` 结构：`#w-entries` 内改为两个物理容器——`#w-entries-engine`（引擎组，默认 `hidden`）与 `#w-entries-author`（剧本组，默认展开）；组头合并了原「说明条 + 恢复按钮 + 收起开关」三件事：折叠箭头、组名、条数、说明文案、恢复默认；剧本组头带「+ 新增条目」。
- 渲染：`renderWorldEntries` 按 `origin === 'engine'` 分流到两组，组内先常量后非常量（各自再按 priority 降序），序号改为**组内**编号。
- 折叠：`engineCollapsed` 默认 `true`；只切换 `hidden`，条目仍在 DOM 内，`collectWorldEntries` 照常整份收集并保存。
- 拖拽：两组各自绑定 `dragover`，`dragSrc.parentElement !== box` 时 `dropEffect='none'` 直接忽略（禁跨组）；插入下标按 `getDragAfterElement` → `getDragIndex` 改为索引式，并按「常量段恒定置顶」钳制——拖非常量时 `max(k, 常量数)`、拖常量时 `min(k, 常量数)`。
- 勾选常量：新增 `applyConstant`，落位到常量段与非常量段的分界处，与渲染规则保持一致，避免保存重载后位置弹回。
- 恢复默认条目成功后自动展开引擎组（否则用户看不到刚补回的条目）。
- 说明文案采用直白口径：「由引擎在新建 / 导入剧本时播种……**不了解它是干什么的就别动它**——保持原样即可正常工作。可改可关，删除后不会自动补回。」

**验证**
- jsdom 真跑渲染逻辑（`tests/_probe_wbgroup.js`，脚手架不入库）：25 项全 PASS——两组互不串条、组内常量置顶、`collectWorldEntries` 文档序即 priority 序、`origin`/`demo` 往返保住、勾选 / 取消常量的落位、组内序号重算、新增落剧本组、折叠默认态与箭头、恢复后展开。
- 注入链一致性：取高氏王朝全量条目，按分组后的文档序重算 priority 后送 `world.scan`——分组前后**注入集合与顺序完全一致**（12 条设定 + 1 条 demo）。
- 全量 `pytest`：**344 passed + 1 skipped + 1 deselected**（与 v2.0.1 基线相同，本次为前端探针扩充，未加测试用例）。
- `test_frontend_binding.py` 探针更新：`w-engine-bar` 退役，新增分组容器、`engineCollapsed = true`、跨组拖拽禁令、常量钳制四条断言。

**设计决定**
- **两组物理隔离而非纯视觉分组**：跨组混排没有语义（保存后 `origin` 仍按各自字段走，只会让「哪些是引擎给的」更难分辨），所以拖拽直接禁跨组，而不是「拖过去之后再按 origin 分组」。
- **常量置顶是渲染规则，不动 priority 语义**：`world.scan` 的输出本来就是「常量全量在前 + 关键词命中按 priority 截断」，列表次序必须与注入次序一致，否则界面会误导作者对「谁先被注入」的判断。代价是手工拖拽不能跨过常量段，故用钳制而非「拖完再弹回」。
- **折叠不改变保存内容**：折叠是显示态，`collectWorldEntries` 仍按 `#w-entries .entry` 取全部条目，因此「折叠着点保存」不会丢条目。
- **priority 重算的副作用已核**：引擎组固定占文档序前两位，剧本条目的 priority 整体下移 10（100 − idx×5 的 idx 增大 2）。因 `scan` 只依赖相对顺序、常量无条件纳入、demo 不占配额，实测注入结果完全不变。
- **组内序号而非全局序号**：两组是彼此独立的注入池，跨组比较先后没有意义。

**踩坑**
- `scrollIntoView` 在 jsdom 下不存在（真浏览器有），`w-add` 回调直接抛错——已加 `if (node.scrollIntoView)` 保护。这条同时也说明：前端逻辑若只能靠沙箱验，必须用真 DOM（jsdom）而不是薄 mock。
- 取消常量后条目**停在原地**（分界处），不滑到非常量段末尾；首版自检脚本把期望写成了「移到末尾」，是脚本错、不是代码错。

---

## 2026-10-21 引擎默认条目来源可见化：origin 标记 + 恢复入口 + 修「UI 保存抹字段」（semver PATCH→v2.0.1）

**起因**：simon 指出「亲密描写标准」与「写法示范」本质上是系统层面的机制，却放在剧本世界书里——用户在剧本编辑器里分不清「这里到底是设系统的地方还是设剧本的地方」。

**核对结论**
- 判断成立一半，两者性质不同：亲密描写标准的措辞全中性、对任意剧本成立，是纯系统机制；写法示范出厂的骨架虽中性（角色甲/乙），但作者必然换成本剧角色（高氏王朝现在就是高天/高琳），改完它是**剧本口吻锚点**，属「系统给骨架 + 剧本填血肉」的双层结构，不能一并搬走。
- 「搬出世界书」有硬约束：世界书是当前唯一具备 enabled/position/depth/priority/constant 五维控制的可编辑注入通道。亲密标准之所以放世界书，`store.py` 的注释记着实测依据——`position=after` 落在末尾 user 消息（生成点前最后一瞥），而铁律⑧ 在 system 块约 39% 处权重被稀释。直接搬到「系统层」等于丢掉这个位置能力。
- 因此选定**改归属、不搬位置**：给条目加 `origin` 来源标记，前端据此分区标识并提供恢复入口。

**顺带查出两个真缺陷**
1. **UI 保存会静默抹掉示范标志**：`entryCard` 只渲染界面上有控件的字段，`collectWorldEntries` 也只回传那些字段——`demo` 与 `first_round` 既无控件也不回传，任何一次点「保存整份」都会把 `demo=true` 抹成缺失，条目从 few-shot 通道退回普通设定注入（落进 `[世界设定]` 段被稀释），无报错、无提示。这正是「写法示范·常驻」的 `demo` 标志会莫名消失的机制成因，与「作者手改 JSON」不同。
2. **导入补种不对称**：`import_drama` 只补写法示范、不补亲密描写标准（`save_world` 仅在首次创建时播种），导致「导入一个没带标准条的剧本包 → 永远没有标准条」。

**改动**
- `store.py`：新增 `ORIGIN_ENGINE` 常量与来源语义注释；`_standard_entry()` / `_standard_example_entry()` 写入 `origin="engine"`；新增 `restore_default_entries(name)`（只补缺失、不覆盖已有，返回 `{added, present}`）；`import_drama` 补种改为两条对称。
- `app.py`：新增 `POST /api/world/<name>/restore-defaults`，转发 `store.restore_default_entries`，世界不存在返回 404。
- `index.html`：`entryCard` 把 `origin/demo/first_round` 落到卡片 `dataset` 并给引擎条目加灰边样式与「引擎默认」徽标；`collectWorldEntries` 原样回传三者（修缺陷 1）；世界书页新增说明条（含当前引擎条目清单、可改可关、删除后不再自动补回的提示）、「恢复默认条目」按钮、「收起/展开」开关（只控显隐，条目仍随整份保存）。
- 数据迁移：高氏王朝两条默认条目补 `origin="engine"`，走 `sync_drama.py install` 铺三态（备份 `_sync_backup_高氏王朝_20261021_003700/`）。
- 测试：新增 `tests/test_standard_entries.py` 13 例（出厂标记、播种、restore 四态、import 对称与不重复、HTTP 200/404、UI 形状往返保字段）；`test_frontend_binding.py` 增 5 条主流程探针 + 1 例「collectWorldEntries 必须回传三者」。

**验证**
- `pytest tests/test_standard_entries.py`：13 passed；`test_frontend_binding.py`：5 passed（含 node 沙箱）。
- 全量 `pytest`：**344 passed + 1 skipped + 1 deselected**（v2.0.0 基线 330 + 本次新增 14 例）。
- `sync_drama.py check --drama 高氏王朝`：作者源 / 运行态 / 随包 demo 三方一致。

**设计决定**
- `origin` 记的是**播种来源**，不是「内容是否原文」：作者改写默认条目后仍是 `origin="engine"`（可改可关），只有删除后自行重写的同名条目才退回无标记。
- `restore` **只补不覆盖**：作者可能按口味改过亲密标准、或把示范换成本剧角色，一键重置等于静默销毁其修改；要重置某条就先删它再恢复，路径显式可控。
- 引擎条目仍按 priority 参与排序（亲密标准 100、示范 60），不为了「凑成一组」而改动 priority 语义——本版靠徽标与底色识别，不改位置（v2.0.2 起改为两级分组，同样不动 priority 语义，见上一条）。

---



**性质**：simon 实机试玩后自行改动世界书两条条目，提出两条理由；核对后两条方向成立，按 A 方案固化进作者源并同步三态。引擎代码零改动。

**simon 的判断**
1. 「镜头纪律·面不点」导致叙事不集中、没有焦点，LLM 为求合规倾向于把每个人物都过一遍；
2. 「写法示范·开局」与「写法示范·常驻」重复，有冗余嫌疑。

**核对结论**
- 冗余成立，且比原判断更彻底：R1 时引擎本会额外前置自己的中性示范（`app.py` 的 `demo_hits = [{FIRST_ROUND_DEMO_NAME, opening_demo}] + demo_hits`），删掉「写法示范·开局」后 R1 仍有「中性示范 + 常驻」两条，够用。
- 「重复投料」成立：引擎 `[叙事纪律]` 段（`prompter.py`）已有通用内核「主镜头要在多条剧情线之间轮换……**只落在与本轮情节最相关的那条线上**，无关的角色与剧情线不硬拉入镜」；世界书那条只留「轮换」半句 + 五条线清单，等于在提示词里把引擎的收窄抵消成铺开。
- 但「把每个人过一遍」的主因不在该条目：前夜八回合实机探针显示 `present` 名单从 R1 到 R8 恒为 6 人，而 `locations` 早已把高天、高洋记到北境王府/大营，`scene.place` 从 R7 起也漂到北境大营——**present 不随位置收缩**才是六人逐个分镜的直接成因，属机制缺口，非剧本问题。
- 修正了 simon 顺手改动的一处：`写法示范·常驻` 被去掉 `demo` 标志、`constant` 改为 `true`，导致剧本级示范彻底退出示范通道、混进 `[世界设定]` 段（与 `store.py` / `world.py` 的「示范条目放近因位置、不混在世界设定里稀释」相悖），已恢复 `demo=true / constant=false / first_round=false`。

**改动清单（作者源 `dramas/高氏王朝/`，经 `adopt` 固化后 `install` 铺开）**
- `world.json`：删「镜头纪律·面不点」（constant，214 字）、删「写法示范·开局」（demo+first_round，350 字）；「写法示范·常驻」恢复示范通道三字段。条目数 22 → 20。
- `opening.txt`：删【常量-镜头纪律·面不点】整条；「主镜头」段由「五线面轮换」改为「每回合只压在一条线上，跨回合轮换，单线不超三回合」，五条线降级为轮换池；「镜头纪律自检」由「必须在五条线间分布」改为「只压在一条线上，不得把在场角色逐个过一遍」；写法示范说明由「两条 demo 条目」改为「一条 demo 条目 + 引擎 R1 中性示范」。
- `README.md`：`## 多点平权（镜头纪律·面不点）` 整节重写为 `## 无主角 + 单点聚焦`（五条线保留为轮换池，并写明为何不再写成 world 常量）；「反套路三闸」第 3 条与「测试指引」首回合验收点同步改写。
- 顺带统一旧账：`opening.txt` 里「单线不超两回合」与 `README.md` 里「超三回合」原本互相打架，统一为**三回合**。

**验证**
- `sync_drama.py adopt --drama 高氏王朝`：7 文件采纳，旧版备份 `_sync_backup_高氏王朝_20261021_002519/`。
- `sync_drama.py install --drama 高氏王朝`：14 文件铺开，备份 `_sync_backup_高氏王朝_20261021_002620/`；`check` = **作者源 / 运行态 / 随包 demo 三方一致**。
- 离线 `build_session`（6 卡，深夜，R2 形态）：prompt 16954 字；`[写法示范]` 块存在且「常驻」落在块内，`[世界设定]` 段内**无**示范文本；全文无「面不点」，引擎「最相关」内核仍在。R1 形态 prompt 17124 字，demo 2 条（中性 + 常驻）。
- 全量 `pytest`：330 passed + 1 skipped + 1 deselected（与 v2.0.0 基线一致）。

**遗留观察（未改代码，待 simon 裁决是否立项）**
- `present` 与 `locations` 脱钩：远端角色不离场，`present` 恒为全员，模型被逼逐个分镜。
- 焦点轮（导演指令指定 focus）下 `validate_present(allowed=focus)` 会把非焦点角色台词整段剥掉，对手戏削成独白。
- 相邻轮整段复读（R6→R7 有 323 字重合约占 13%），复读检测按比例未触发重写。
- `locations` 位置细化偏差（正文写「马厩」、快照记「大营密室」）。

---

## 2026-10-20 剧本《客服战争》退役（剧本内容变更，不动引擎、不升版本）

**性质**：simon 决定撤下该剧本，本机删除、不再随包。立项前提是「玩家卡主角轨 + 群像轨双轨」，v2.0.0 移除玩家角色介入层后该前提消失；当日已按 A 方案做去玩家化改造（见本日「剧本《客服战争》去玩家化改造」条目），改造后形态已非原始设计意图，不值得再投入迭代，直接退役。原「现代职场·办公室政治群像」题材线随之关闭。

**删除范围（三态同步铁律：三处一起删，不留单边副本）**
- 作者源：`dramas/客服战争/`（world.json + 5 张卡 + opening.txt + README.md）。
- 运行态：`engine/data/worlds/客服战争.json`、`engine/data/characters/{乔岩,何军,苏明溪,郑北辰,陈小雨}.json`。
- 随包 demo：`engine/data/examples/worlds/客服战争.json`、`engine/data/examples/characters/` 同名 5 卡。
- 脚手架：`scripts/build_kefu_war_world.py`（world.json 生成器）、`tests/_probe_live_kefu.py`、`tests/runs/_probe_live_kefu/`（10 回合实机产物）。

**归档**：`backup/dramas_retired_20261020/客服战争/`，按 `author_source` / `runtime` / `examples` / `scaffold` 四层存放，附 `RETIRED.md` 写明退役原因与三步恢复命令。`dramas/README.md` 约定的退役去向即项目根 `backup/dramas_retired_<日期>/`。

**影响面**
- 随包 demo 只剩《高氏王朝》（6 卡 + 世界书），`_seed_examples` 首次运行播种逻辑不受影响（examples 非空即正常播种）。
- `package.py` 的三方一致性守卫：删除后三态一致，不会触发中止。
- 测试层零改动：`test_universality.py` 的黑名单本就未收录本剧角色名，其余用例的 demo 目录均自行构造（`monkeypatch EXAMPLES_DIR`），不依赖随包 demo 内容。
- 遗留观察：运行态仍有 `engine/data/worlds/南镇暑夏.json` + `周牧野`/`林梦雅` 两卡，既不在 `dramas/` 也不在 `examples/`（早前探针残留），本次不动，`sync_drama.py check` 会继续报「多剧本并存」预期告警。

**文档同步**：`tests/TODO.md` 的「新剧本创建：客服战争」活跃条目删除，改为「三、近期已清」下一条退役记录（含归档路径与退役原因）。

---

## 2026-10-20 定向反向合并：移除玩家角色介入 + 正文格式回退 v0.31.11（semver MAJOR→v2.0.0）

**性质**：simon 裁决的交互范式回退。设计基准取 v0.31.11，引擎优化基准取当前 v1.2.7；直接在 master 定点拆分合并，不新建分支。对 v1.x 属破坏性交互变更，触发 MAJOR。

**移除（玩家角色介入层）**
- `store.py`：删除 `PLAYER_NAME`、玩家卡工厂、`ensure_player_card*`、`player_card_name`、`is_player` 单例约束及新建/导入播种。
- `app.py` / `memory.py`：环境推手不再补入 `present`，不再传递玩家卡或玩家秘密；`session_new` 恢复同场角色 cast；`act` 落盘标签恢复`【导演指令】`。
- `prompter.py` / `director.py` / `scene.py`：删除「人类操控」「玩家恒在场」等边界与过滤，恢复环境推手不登场、导演指令优先。
- 前端：恢复同场角色勾选列表、「作为导演注入环境扰动」入口；删除玩家行动框与玩家卡降门槛；保留开局自动空输入推演。
- `scripts/sync_drama.py`：删除运行时玩家卡排除逻辑。

**保留（与玩家机制无关的引擎优化）**
- 正向铁律、few-shot / 写法示范机制、离场语义判断 `present_change`、开局自动首轮、DeepSeek 参数协商修复、铁律⑧恢复、打包与测试编码修复、demo 数据更新。

**正文格式规范回退 v0.31.11**
- `[输出格式]` 恢复「多说话人叙事」，`[输出纪律]` 恢复 v0.31.11 原文；不再要求 `*动作*` / 双引号对白三段式。
- `validate_present` 恢复为主防线，前缀剥离不再是三段式后的兜底网。
- 引擎默认写法示范与现有剧本的 `demo` 示范条目改为多说话人叙事（角色名分段），剧本本体与其它设定保留。

**验证**
- Python 语法编译、前端脚本语法检查通过。
- 全量 `pytest`：330 passed + 1 skipped + 1 deselected。
- 源码扫描：`is_player` / `ensure_player_card` / `PLAYER_NAME` / `player_name` / `玩家行动` / 三段式输出规范均归零（历史 DEVLOG、守护测试反向断言除外）。

---

## 2026-10-20 剧本《客服战争》去玩家化改造（剧本内容变更，不动引擎、不升版本）

> **后续（同日）**：本剧已由 simon 决定退役删除，见顶部「剧本《客服战争》退役」条目。本条保留作改造过程的记录。

**性质**：v2.0.0 移除玩家角色介入后，随包 demo 剧本仍按「玩家轨 + 群像轨」设计，出现剧本与引擎范式冲突（世界书描述一名不存在的第四席专员，5 张卡各挂一条 `relations["玩家"]` 指向不存在的角色）。按 simon 拍板的 A 方案做去玩家化改造，改动只在作者源 `dramas/客服战争/`，引擎代码零改动。

**冲突表现（改造前）**：`memory.new` 会把 `relations` 全量展开（不按在场名单过滤），提示词的关系段因此含「乔岩 → 玩家」「陈小雨 → 玩家」等 5 条指向空角色的边；世界书常量又写明「一名新入职的自有专员（玩家，夜班区第二个工位）」。模型有充分理由写出一个不存在的「玩家」角色，而 `validate_present` 只按已知卡名剥离非在场台词，剥不掉这个名字。

**改造内容**
- 角色卡：删除 5 张卡的 `relations["玩家"]`（关系网由 25 条降为 20 条 = 5×4 全对，无空弦）。
- 世界书：`客服部权力格局` / `复盘提前·八月底死亡钟` / `镜头纪律·双轨`→`镜头纪律·单轨群像`（条目名一并改）/ `复盘倒计时` / `场域六处` 全数改写；`写法示范·开局` 里两个不在场的「专员」台词改为乔岩巡夜 + 空工位。
- `opening.txt` / `README.md`：舞台、权力三足、死亡钟、语境条目、第一回合导演指令全数重写；README 重写为单轨群像版并附改造记录。
- 一致性连带：夜班区由「两个工位亮着」改「一个工位亮着、对面空席」；何军「经营两三个自有专员」改「经营过两三个专员（自有与外包都有）」（自有专员现存仅陈小雨一人）。

**死亡钟重构（设计决定）**：原「两名自有专员必走一个」的二人博弈无法保留（玩家轨下线、且不加第 6 张卡，本地 27B 带不动）。改为**冻结的空席位**：第四席编制在复盘前被冻结、招聘停摆，复盘时「四席砍三席 + 空席不再补人」同时落地——刀口收敛到陈小雨一人，但她有两条活路（证明夜班必须两个人保第二席 / 把空席让给外包转正候选），一条死路。缠斗强度不降反升：苏（半签要干净）、郑（要骨架砍席）、乔（要把部门做小换外包比例）、何（要人进来）四个人的利益全部压在她那一席与那个空席上。空席位明确写成「编制缺口」而非角色——无卡、不进在场名单、不说话，只允许被叙述与算计。

**验证**
- 提示词离线构建（`memory.new` 全 5 卡 → `prompter.build_session`）：关系段 20 条全为真实角色、无 `玩家` 边；常量段含「单轨群像」、无「双轨」；全文唯一「玩家」出现在「付费玩家」的叙事语境。
- `sync_drama.py install --drama 客服战争` 铺运行态 + demo（备份 `_sync_backup_客服战争_20261020_234042/`）；`check` 仅剩「多剧本并存 → 多余卡」预期告警，无内容差异。
- 全量 `pytest`：330 passed + 1 skipped + 1 deselected（与 v2.0.0 基线一致）。
- 剧本改造备份 `_backup_kefu_deplayer_20261020_2340/`。
- **未做**：实机多回合复验（本地 27B 带 5 卡可跑但耗时长，留待 simon 指定；验收项见剧本 README 测试指引）。

**文档同步**：`engine/README.md`、`engine/INSTALL.md` 删去「分发包不含示例剧本 / player-cast 不随包」的过时表述（v1.2.4 起全部剧本经 examples 随包播种）；`tests/TODO.md` 客服战争条目改为单轨群像版并登记本次改造。

---

## 2026-10-20 铁律⑧（亲密描写）恢复（semver PATCH→v1.2.7）

**性质**：simon 裁决的行为变更。2026-10-18「铁律瘦身」把铁律⑧ 尺度措辞下沉世界书后，NSFW 支持度不足——裁决恢复铁律⑧（亲密描写）机制，仅保留未成年人红线。

**根因（为什么下沉不够）**：世界书「亲密描写标准」条目只是轻量提醒，随世界书命中注入、长上下文下被稀释；引擎系统层（`_LAW8_DEFAULT` 槽位）才是每回合恒定注入的约束位。槽位与 `_build_laws` 拼接、`_law8_override` 句柄一直保留（只是文案被置空），恢复即填回。

**改动**
- `engine/prompter.py`：`_LAW8_DEFAULT` 按历史版本（v0.15.0 中性折衷，见 `backup/backup_20261014_nsfw-offline/`）原文恢复：亲密场景「身临其境、有实感、正面写实，禁止隐喻/环境侧写/文学化一带而过」「不预设上限，也不强制克制」，含时机层（未推进到亲密时刻前不得提前/硬写）。历史⑧ 末尾的硬红线句不再重复——红线现由 `_LAWS_PREFIX`「己、法律底线」单点承载（与 store.py「世界书条目不含红线、由铁律⑧/引擎兜底」的既有分工对齐）。
- `tests/test_intimacy_scale.py`：尺度断言由「已下沉、不得出现」反转为「已恢复、必须出现」；新增时机层断言与「⑧ 内不重复红线」断言；未成年红线三测原样保留。
- `tests/test_narrative_discipline.py`：`test_law8_intimacy_removed_from_engine` 改为 `test_law8_intimacy_restored_in_engine`（⑧ 措辞 + 红线均在 laws 中）。

**验证**：全量 `pytest`：346 passed + 1 skipped + 1 deselected（基线 344 + 新增 2）。备份 `backup/backup_20261020_restore_law8/`。

**保留不变**：世界书「亲密描写标准」条目照常播种（写法技法层，各剧本可停用/改写）；未成年红线引擎级恒定、不可由世界书覆盖；`_law8_override` 生产恒为 None，⑧ 措辞不构成对外可配置项。

---

## 2026-10-20 玩家卡浏览重建丢档修复（semver PATCH→v1.2.6）

**性质**：无争议 Bug 修复。剧本中【玩家】角色卡每次重启引擎后丢失上轮已保存内容（2026-10-20 simon 报障）。

**根因链**：
1. 只读列表接口 `GET /api/characters/by-world`（`engine/app.py`）误调了破坏性 `store.ensure_player_card(world)`：该函数在已有玩家卡的 `world` 字段与请求世界不匹配时删卡并新建空白卡。
2. 前端左栏（`static/index.html`）页面加载时对每个世界各调一次 by-world。运行态并存两个剧本（高氏王朝、客服战争）时，每次重启后页面加载必然把已填写的玩家卡抹空——只剩最后一轮世界对应的空白卡。

**改动**
- `engine/store.py`：新增 `ensure_player_card_if_absent(world_name)`（浏览安全版）：已有玩家卡（无论挂在哪个世界）原样返回；无任何玩家卡才新建空白卡归属请求世界；无卡且世界名为空返回 None。
- `engine/app.py`：by-world 路由改调浏览安全版，附根因注释。
- `tests/test_setup_world_picker.py`：client fixture 补 mock；端点测试改为断言真实世界只调浏览版、未知世界两版都不调。
- `tests/test_player_card.py`：新增 5a–5e 回归用例，含 5e 路由级复现原报障（双世界各 GET 一次 by-world，断言已填写玩家卡不变）。

**验证**：全量 `pytest`：344 passed + 1 skipped + 1 deselected（基线 339 + 新增 5）。备份 `backup/backup_20261020_playercard_browse_reset/`。

**设计保留**：换剧本给空白卡槽的破坏性语义未动，仍只存在于文档化的三处——`session_new`、`import_drama`、`save_world` 首次创建（见 `ensure_player_card` docstring 与 `tests/test_player_card.py` 测试 5）。

---

## 2026-10-20 DeepSeek 400 修复：参数协商四级化 + 错误透明化（semver PATCH→v1.2.5）

**性质**：云网关兼容性修复。叙事后端切到 DeepSeek（OpenAI 兼容云网关）后每回合 400，本地 llama.cpp 路径不受影响。

**根因链**（2026-10-20 simon 报障）：
1. 提供商切换错配：deepseek 卡片的 model 留空，前端「model 留空不覆盖」保护让顶层 model 保留旧后端的本地 GGUF 路径；`save_config` 的自动取模型只在 model 为空时触发 → 把 Windows 文件路径当模型名发给云网关 → 400。
2. 厂商字段被严格网关拒绝：`_base_payload` 无条件发 `top_k`/`min_p`，`enable_thinking=false` 时另发 `chat_template_kwargs`+`enable_thinking`——llama.cpp/Qwen 特化字段，DeepSeek 等严格校验网关对未知参数一律 400；旧三级协商只剥惩罚类字段，剥不到这四个。
3. 报错黑箱：异常只有裸 `400 Bad Request`，不带上游响应体，无法定位是哪个字段/模型名被拒。

**改动**
- `engine/llm.py`：新增 `_VENDOR_FIELDS` 与协商第四级（流式/非流式同）：惩罚字段降级仍 4xx 时剥 `top_k`/`chat_template_kwargs`/`enable_thinking` 再试；新增 `_raise_with_body`：4xx/5xx 异常附上游响应体前 300 字，报错即自解释；`save_config`：`base_url` 变化时旧 model 对新后端必然无效，先作废再由既有逻辑从新后端 `/v1/models` 自动取。
- `engine/data/config.json`（运行时态，不入库）：顶层 model 与 deepseek 卡片 model 均为 `deepseek-chat`（不用 reasoner：思考 token 耗预算且拖慢叙事输出）。备份 `backup/deepseek-fix-20261020_030003/`。
- `tests/test_llm_repeat_penalty.py`：协商契约三级→四级（两处断言更新），新增「严格网关剥厂商扩展后成功」用例。

**验证**
- DeepSeek 实测（最小请求）：流式与非流式均成功；假模型名场景异常消息带上游响应体（直接点名非法 model）。
- 全量 `pytest tests/`：339 passed + 1 skipped + 1 deselected（与改动前基线一致）。

**设计决定**：第四级沿用「4xx 探测后剥」的既有协商风格，不解析 400 响应体做精确剥离——代价是云网关上每回合先吃一次 400 再探测成功（数百毫秒级），本地 llama.cpp 全认这些字段、不会走到该级；若后续嫌慢再升级为按响应体点名剥离。

---

## 2026-10-19 LLM 单轨化具名清洗 + 测试编码修复（semver PATCH→v1.2.4）

**性质**：普适性红线收口 + 测试环境依赖修复。10-19 simon 裁决：LLM 单轨化，只留本地 llama.cpp + Qwen 系列，删除云服务商与第二个本地推理引擎的所有具名引用（源码注释 + 分发文档）。裁决执行后遗留「是否 bump / 补 DEVLOG / 提交」未处理，本版本收口。

**改动**
- `engine/config.json`（运行时态，不入库）：`providers` 三轨→单轨，删云服务商 provider（含真实 key）与 ninfer(:1235) 轨，只留本地 llama.cpp :1234 轨（Qwen3.8-27B-UD-Q4_K_M）。备份 `_backup_purge_providers_20261019_224100/`。
- `engine/llm.py`：top_k 注释、enable_thinking 注释、采样参数协商注释三处具名（ninfer / SiliconFlow / Hy4-preview）改中性表述（「部分 OpenAI 兼容后端」）。
- `engine/director.py`：叙事去重段背景注释 ninfer 改「多数非 llama.cpp 后端」。
- `engine/README.md` / `engine/INSTALL.md`：「默认对接 SiliconFlow `tencent/Hy4-preview`」改「默认对接本地推理服务如 llama.cpp / Qwen 系列」。
- `tests/test_frontend_binding.py`：JS 沙箱绑定测试 `subprocess.run` 显式 `encoding="utf-8", errors="replace"`。根因：node 输出恒为 UTF-8，`text=True` 无显式编码时随控制台代码页解码——代码页 936（GBK）下解码崩溃使 stdout 为 None、断言 TypeError 假失败；此前全绿仅因跑在 UTF-8 控制台会话。修后不再依赖会话代码页。

**保留项（simon 裁决口径）**：`DEFAULTS["base_url"]="http://127.0.0.1:1234/v1"` 出厂默认、llama.cpp / Qwen 泛称、`enable_thinking` 的 Qwen3 注释保留；web/UI 占位示例（index.html「如 Qwen3.5-32B」）不算违反。

**验证**
- 全量 `pytest tests/`：338 passed + 1 skipped（integration 按 pytest.ini 默认 deselect，与改动前一致）。
- `engine/` 全范围 grep SiliconFlow / siliconflow / ninfer / 硅基流动 / Hy4：零命中。

**设计决定**：注释与文档的具名清洗属 PATCH（行为零变化，仅分发包文本卫生）；测试编码修复独立成 commit，不并入本版本语义。

---

## 2026-10-19 引导页「玩家行动」入口 + 写法示范收回后台（semver PATCH→v1.2.3）

**性质**：交互语义纠错。v1.2.2 开局自动推演发的是空 input，玩家第一回合无实际行动；而引导页唯一的输入框是「开局写法示范」，玩家（simon）直觉把「*我恐惧张望*，这是哪」填进去，却不知它是 few-shot 格式范例而非「玩家行动」，导致首轮正文完全没有「我」——引擎行为正确（prompter 288 行「玩家指令为空则静立现场」+ 不代写玩家言行铁律），缺的是「玩家开场行动」入口。

**根因链**（simon 会话 5d631a5c 实测）：
1. 玩家把「我的开场动作」填进「写法示范」框 → 被当格式范例注入；
2. v1.2.2 自动推演发空 input → prompter 正确把玩家标为「静立现场」；
3. 模型正确遵守「不代写玩家言行」→ 正文玩家无动作无台词；
4. 结果：第一回合「我」缺席。这是「入口缺失 + 字段语义误导」叠加，非 bug。

**修复**
- 引导页「开局写法示范」框移除，改为「玩家行动（你的开场第一句/第一个动作）」textarea（可选，留空则玩家静立、NPC 先动）。
- 写法示范收回后台静默：`session_new` 的 `opening_demo` 不再从请求体收，恒用 `store._FIRST_ROUND_DEMO`；删除 `GET /api/defaults/opening-demo` 接口与前端 `loadOpeningDemoDefault`。
- `startSession` 收集 `player-action`，建局后 `streamAct(playerAction, {showUserBubble: !!playerAction})`——玩家开场行动作为首轮 input 进入 act；留空则发空 input（NPC 自然推演）。
- 玩家行动进 chat 历史（`【玩家行动】`），继续会话时天然存在，无需另存快照。

**验证**
- 全量 338 passed + 1 skipped（opening_demo 两个测试合并为一个「恒用系统默认」）。
- JS node --check 通过；前端绑定沙箱通过。

**设计决定**：玩家是「在场人物」，开局就该有说第一句话/做第一个动作的入口；写法示范是「怎么写」的格式范例，不该暴露给玩家自定义（暴露即诱发「把它当我的开场」的误读）。

---

## 2026-10-19 开局自动推演第一回合（semver PATCH→v1.2.2）

**性质**：交互体验增强。此前「开始游戏」建局后只进入主界面，玩家须自己再输入第一句行动才触发推演——但玩家已在引导页表达了开场意图（地点/时间/写法示范），应当建局即产出开场叙事（开场示范条目），玩家看到 NPC 的开场动作/对白后再输入自己的第一句，而非面对空界面手动触发。

**实现（纯前端 index.html）**
- 抽取 `streamAct(text, opts)`：把原 `send()` 的 SSE 流式处理抽成公共函数，`opts.showUserBubble` 控制是否渲染玩家气泡；`send()` 改为薄封装（输入非空 + 弹用户气泡）。
- `startSession` 建局成功后末尾 `streamAct('', {showUserBubble: false})` 自动推演第一回合：空 input 由 prompter 处理为「在场角色自然推演」，玩家本人（人类操控角色）不被代写言行。
- 后端零改动：`/api/act` 本就支持空 input（prompter 398 行 `directive or "（玩家未输入行动，本轮由在场角色自然推演）"`）。

**验证**
- 全量 339 passed + 1 skipped；前端绑定沙箱补 60ms 等待（startSession 末尾的自动推演是 fire-and-forget，异步走完后 sendBtn 才恢复解锁）。
- JS node --check 通过。

**设计决定**：自动首轮推演是 fire-and-forget（不 await），流式渲染开场叙事期间输入框处于「后台同步」禁用态，完成后恢复可输入——玩家看到开场后才进入第一轮交互。

---

## 2026-10-19 开场选角补实现（semver PATCH→v1.2.1）

**性质**：v1.2.0 的实现缺口修复。v1.2.0 去掉开场角色勾选列表、引导页提示写明「首轮由引擎结合开场场景自行判断谁在场」，但**该判断机制未落地**——cast 全员进 present 后 prompter 全量注入「在场角色」块，模型把所有人都写到开场地点（实测填「街道」全员 6 人冒出来，含不该在街上的人）。提示承诺了机制、机制不存在，属定义层缺失而非模型问题。

**修复（engine/scene.py + app.py）**
- `scene.py` 新增 `select_present(roster, place, time_str)`：开场冷启动选角。按开场地点从全员名册做一次 LLM 判断谁合理在场；越名丢弃、去重保序；LLM 失败/解析失败/选 0 人/未填地点 → 回退全员（不阻断建局，退化回旧行为）。
- `app.py session_new` 接入：parse_initial_scene 之后、memory.new 之前；玩家卡不进 roster（玩家恒在场）；选角结果与「暂不在场」名单写日志可见；`ensure_player_card` 挪到选角前（player_name 依赖顺序修正）。
- 落选角色不是锁死出局：开局后仍可经 scene.apply 关键词 arrive / reflect present_change 语义到场，双轨在场维护照常。

**验证**
- test_scene.py 新增 4 用例（过滤去重越名丢弃/LLM 异常回退全员/非法 JSON 与空选回退/无地点不调 LLM），24 passed；全量 339 passed + 1 skipped。

**设计决定**：选角方向「宁缺勿滥」喂给 LLM，但工程兜底方向「宁多勿缺」——任何失败路径都回退全员登场，绝不因选角失败导致空场建局。

---

## 2026-10-19 写法示范引擎化 + 玩家卡降门槛 + 开场全员登场 + 离场语义判断（semver MINOR→v1.2.0）

**性质**：交互范式对齐改造的收口与打磨——few-shot 示范从「作者手写进 world.json」收口为引擎内置中性默认 + 引导页可改；玩家卡编辑器对齐 Persona 通行写法（description 唯一必填，core 字段可选）；开场不再展示误导性的「同场角色」勾选列表，改为全员登场 + 引擎按场景判断在场；离场判断从关键词枚举升级为语义判断。**触发 MINOR**：新增引擎能力（常驻示范自动播种 + 开场语义选角 + 离场语义判断）+ 交互范式变更。

**一、写法示范引擎化（engine/store.py + memory.py + app.py + index.html）**
- 背景：few-shot 示范此前要作者手写进 world.json，普通玩家建局拿不到示范。simon 拍板两点：①「写法示范·开局」（first message）挪到「开始游戏」引导页，引擎内置中性默认、玩家可改可留空；②「写法示范·常驻」（example messages）像「亲密描写标准」一样引擎化——创建+导入剧本自动播种。
- 落点：
  - `store.py` 新增两条中性常量 `FIRST_ROUND_DEMO_NAME/_FIRST_ROUND_DEMO`（开局示范）、`STANDARD_EXAMPLE_NAME/_STANDARD_EXAMPLE_CONTENT`（常驻示范，`demo=True/first_round=False/priority=60`）+ `_standard_example_entry()`/`_has_standard_example()`；`save_world` 首次创建播种 2 条（标准条 index0 + 常驻示范 index1），`import_drama` 显式补种常驻示范。
  - `memory.new` 新增 `opening_demo` 参数→快照字段；`app.py` `session_new` 接收 `opening_demo`（空则兜底 `_FIRST_ROUND_DEMO`），新增 `GET /api/defaults/opening-demo`；`act()` 首轮（`brief.round<=1`）把 opening_demo 构造成 demo 条目 prepend 到 demo_hits（置于常驻示范前）。
  - 引导页「开局写法示范」textarea 预填系统默认（非空白框），label 明示「已填入系统默认，可直接修改」，新增「还原默认」按钮（改动后浮现、点击回填默认）。
- 权威源分离：first message 走「引导页文本框→快照」通道（开局一次性），example messages 走「世界书 demo 条目」通道（每轮注入）。

**二、玩家卡编辑器降门槛（engine/static/index.html，纯前端）**
- 背景：玩家卡是引擎簿记护城河的玩家侧延伸，但 core_desire/core_fear 对玩家偏重。查证同类角色卡的通行 Persona 写法：只有「名称 + 一段自由描述」，无结构化 core 字段。
- 方案：不砍机制只降门槛。后端对空 core 字段本就完全容错（prompter 条件注入 `if card.get(...)`、memory `short_goal or core_desire or ''`、director `core_desire or ''`），故零后端改动。
- 前端：`core_desire`/`core_fear` 红星改 `class="req core-req"`（可 JS 切换）；新增 `_applyPlayerCardUi(isPlayer)` 按 `is_player` 标志隐藏红星 + 显示「可选，留空由 description 推演」提示；`saveCard` 必填校验分支——玩家卡只强制 `name+description`，NPC 卡仍强制 `desc+desire+fear`（关系/秘密簿记的 NPC 锚点不能丢）。

**三、开场全员登场 + 离场语义判断（engine/app.py + director.py + index.html）**
- 背景（simon 两问）：① 开场「同场角色」勾选列表语义误导（玩家以为勾选=锁定整局登场，实则只是初始在场名单）；② 角色移动（上朝/逃往北境/赴任）后离场判断靠 `LEAVE_KEYS` 关键词枚举，有无离场词却确已离场的盲区。
- 落地：
  - **去掉列表 + 全员登场**：删勾选列表/推荐按钮；`session_new` 的 cast 缺省改为「按所选 world 筛全员」（先解析 world_name 再筛，避免跨世界/未归属角色误带入），首轮由引擎结合场景判断谁在场。删 `recommend-cast` 接口（与列表是同一件事的重复）。
  - **离场语义判断（双轨共存）**：`director.reflect` 新增 `present_change` 字段（`{leave, arrive}`），从已生成叙事读「谁离开镜头/谁进入镜头」，补关键词盲区。`scene.apply` 关键词离场保留不动（生成前处理玩家明说的离开），双轨时序互补：关键词管「玩家明说」，语义管「叙事实际发生」。安全网与 scene.apply 同款（只认合法卡/玩家恒在场/leave 只认在场者/arrive 只认未在场者/leave 覆盖全员且无 arrive 忽略/名单不清空）。
- 普适性修正：reflect 规则示例「逃往北境」「北境来使班次」「御座西侧」为题材词泄漏，改中性表述，engine 源码角色名/题材词扫描归零。

**四、验证**
- 全量测试 335 passed + 1 skipped；新增 test_standard_example.py 7 用例（播种/中性/demo 标志/导入补种/作者保留/删除）+ test_director.py 4 用例（present_change 离场到场/全员误判忽略/玩家恒在场/越名过滤）。
- JS node --check 通过。

**设计决定**：present 名单维护 = scene.apply 关键词（生成前，玩家明说）+ reflect 语义（生成后，叙事实际）双轨；reflect 语义是补盲区的兜底，不是替代历史关键词机制。

---

## 2026-10-18 输出格式改「动作 / 对白 / 散文」三段式 + 铁律瘦身 + few-shot 机制（semver MINOR→v1.1.0）

**性质**：引擎叙事输出范式整体转向——从「多说话人自由叙事（实际趋近散文）」改为「角色动作 + 对白 + 穿插散文」三段式；配套对每回合注入 LLM 的铁律做正向化瘦身；引入 few-shot 示范机制（开场示范 + 常驻示范）并引擎化自动注入。**触发 MINOR**：输出范式变更 + 新增引擎能力（few-shot 示范条目机制）。

**一、输出格式改三段式（engine/prompter.py）**
- 起因：分支引擎设计理念与主仓库不同，不再沿用「散文」输出推演结果，改参考角色扮演类前端的通行输出范式。
- 借鉴的通用角色卡写作规范（首轮开场示范 / 常驻对话示范范式）：动作用一对 `*星号*` 包裹、对白用一对半角双引号 `"..."` 包裹、散文穿插在动作与对白之间交代空间/事件/关系变化。核心信条：「告诉模型该做什么，比告诉它不该做什么更有效」「show 比 explain 更有效」。
- 落点：`[输出格式]` 段由「用多说话人叙事」改为「三种写法交织」，明确动作/对白/散文的符号约定，并**严禁「角色名：」前缀标注说话人**（对白归属靠紧邻动作与上下文自然交代）。
- 联动：`director.validate_present` 原靠「角色名：」前缀精确剥离非在场角色台词，新范式无前缀，剥离退化为**兜底网**（无前缀透传、偶发仍写前缀才触发），出戏抑制改由 prompter 在场约束软抑制承担。这是 simon 明确接受的取舍（叙事观感优先于机制精确度，呼应 v0.17.0 因观感差移除「分段格式」的历史）。空名单保护安全底线保留。

**二、铁律审视与瘦身（engine/prompter.py）**
- 审视结论：铁律分两类——机制投影铁律（有 director 硬机制兜底：②信息边界→秘密簿记、③秘密底线→四态/bottom_line、④后果留痕→ledger 账本、⑥玩家操控→is_player 单轨、⑨防重复→detect_narrative_repeat 重采样）与纯提示词约束（①动作「五选一」、⑤关系「必须兑现」、⑦人设、叙事纪律三轴，无机制兜底，是噪声）。
- 重写：9 条铁律 + 3 条叙事纪律 + 6 条输出纪律 → 「正向写作基调 + 机制投影规则（甲乙丙丁戊）+ 法律底线（己）」，删「五选一」僵化枚举、去「禁止/必须/不得」负向堆砌。
- 叙事纪律拆解：引擎【手段】（禁黑箱）【说话】（禁套话）删引擎侧（题材特异，下沉世界书），只留【镜头】通用内核；demo「高氏王朝」world.json 补「本剧的刀」常量（禁下毒/巫蛊/堕胎/刺杀/设局陷害，此前只在 README/opening 有、world.json 漏了）。
- 铁律⑧（亲密描写）下沉世界书（「亲密描写标准」条目本就存在且更详细），引擎删⑧尺度词；**但「未成年法律红线」必须保留引擎级**（记忆红线：未成年硬红线永远生效、不可由世界书覆盖），单独列为「己、法律底线」。

**三、few-shot 示范机制引擎化（engine/world.py + app.py + prompter.py）**
- 三个 few-shot 设计：开场示范（作者写的开场，开新对话注入一次，示范风格/篇幅）、常驻示范（持续 few-shot，直到被历史挤满）、多版开场（多条开场随机选）。simon 决定引入前两个，多版开场不做。
- 引擎化落点：世界书条目新增 `demo` 标志 + `first_round` 标志——`demo+first_round` 仅首轮（round<=1）注入（开场示范），`demo` 无 first_round 每轮持续注入（常驻示范）。`scan` 新增 `round` 参数，demo 条目独立返回、不占 max_entries 配额、不混入普通世界设定。
- 权威源：demo 条目写进 world.json（走 sync 三态同步，符合「真相源唯一」铁律），opening.txt 的「写法示范」段改为指引、删重复正文。
- 注入：app.py 拆出 `demo_hits` 传 build_session，渲染成「写法示范」块放输出格式段之后（近因位置）。
- 格式锚点：多角色动作+对白（不用 `{{char}}:`/`{{user}}:` 这类单角色前缀，契合引擎多角色群像定位）。

**四、验证**
- 全量测试 321 passed + 1 skipped；新增 test_world_scan.py 4 用例（first_round 仅首轮 / 持续每轮 / demo 与设定分离 / 不占配额）+ test_prompter.py 2 用例（demo 渲染 / 无 demo 零开销）。
- 实机探针（本地 llama 1234）：输出完美的三段式（`*动作*` / `"对白"` / 穿插散文），且明显受 few-shot 示范风格牵引（复用示范的意象节奏）。

**设计决定**：引擎护城河 = 关系/秘密簿记（同类产品没有）；「青出于蓝」= 砍负向铁律堆砌 + 簿记机制投影正向化 + few-shot 示范。

---

## 2026-10-18 玩家卡：玩家从环境推手变为在场角色（semver MINOR→v1.0.0）

**性质**：玩家身份机制重构——玩家从「外部环境推手（导演）」变为「局势中由人类实时操控的在场角色」，持有角色卡、可持秘密、可与 NPC 互动。**触发 MINOR**：核心交互范式变更 + 新增引擎能力（玩家卡运行时单例）。

**一、问题与设计**
- 起因：旧机制里玩家是「环境推手」，输入是导演指令而非角色言行，与「沙盘群像」定位不符——玩家无法真正「作为一个人」进入局面。
- 方案 A（simon 拍板）：玩家 = 在场角色，由人类实时操控。身份判据 = 角色卡内 `is_player` 标志（非硬编码文件名「玩家」），玩家可自由改名（借鉴单玩家槽位思路）；`PLAYER_NAME` 仅作新建空卡默认显示名。
- 普适性铁律：玩家卡是运行时单例（不进剧本模板/随包 demo）。`ensure_player_card` 按「是否已归属当前剧本」决定去留——玩家卡 world==当前剧本→保留其填写（同剧本内持久）；玩家卡挂在其它剧本（新建/导入/切换后残留）→删残留、为当前剧本新建空白卡。**换剧本绝不携带上个剧本的填写内容**，保证每个新建/导入剧本都拿到空白卡槽位。

**二、落地**
- `save_card` 单例约束：存 is_player 卡时删同世界其它 is_player 卡（改名/误建第二张去重）。
- 触发点：`save_world` first_create 分支 + `import_drama` 末尾（ensure_player_card）。
- `scripts/sync_drama.py` 按 is_player 标志（`_is_player_card`）排除玩家卡，勿退回按固定文件名「玩家.json」排除（改名后失效→打包守卫误报中止）。
- prompter 对玩家角色块注入「人类操控」边界标记：LLM 不代写玩家言行与内心、不向其块注入秘密底牌；秘密的 NPC 侧认知隔离仍走既有秘密机制。
- 守护：`tests/test_player_card.py`。

**验证**：全量测试通过；玩家卡在换剧本/新建/导入/切换场景下正确重置为空白槽位，同剧本内填写持久。

---

## 2026-10-18 demo 高氏王朝：高洋/苏雅芝职能切分（semver PATCH→v0.31.11）

**性质**：官方 demo「高氏王朝」纯数据内容更新——消除废太子高洋与皇后苏雅芝在「对外联络复辟」职能上的重叠，把两人的对外动作硬切干净。无引擎代码 / API / 存储格式 / 数据流改动，非破坏性。**触发 PATCH**：demo 数据内容更新。

**一、问题与诊断**
- 起因：simon 觉得高洋「送密信联络各方复辟」与苏雅芝功能重叠较大，且苏雅芝更有张力，一度想删高洋实体降级为背景板。
- 核实结论：重叠是真的，但病根是「母子职能没切干净」，不是「角色冗余」。高洋扛着三件替代不了的承重件——死亡钟（选后诏本质立嗣）的主体、去性化母子线、废太子-藩王-长公主三角中枢。真正「送密信联络各方」这个功能几乎只挂在高洋身上；苏雅芝的张力恰在「算而不发、活成战利品」，一旦让她去联络各方，她就变成第二个高洋、失去自己的张力。故删高洋会塌主线而非削冗余。

**二、切分方案 A（simon 拍板）**
- 高洋 = 全剧唯一对外协调线（私下搭伯父高天，只递判断不递底），母亲降为锚点/软肋，不作递线渠道。
- 苏雅芝 = 纯内盘退路（贴高昌、算而不发），对外联络 / 递线 / 站队一概不碰。
- 死亡钟 / 母子线 / 废太子-藩王-长公主三角全部保住。

**三、改动（作者源 `dramas/高氏王朝/`，install 铺到运行态 + demo）**
- 高洋卡：`short_goal` 改为「翻盘只有私下伯父一条对外线，只递判断不递底；母亲是锚点/软肋不是渠道」；`relations[苏雅芝]` 末句「离不开她这条唯一的线」→「软肋，对外递线那步从她这条走」；`relations[高昌]`「他只有母亲这一条线」→「能动的对外线只有私下搭的伯父一条」。
- 苏雅芝卡：`short_goal` 补「对外联络、递线、站队这些脏活一概不碰，那是儿子那条线的事」；`relations[陆敏]` 由「借宫里的边角试探」→「只心里掂量、记一笔，连边角试探都省，绝不递」。
- world.json 三处连带对齐（否则派生文本反向把苏雅芝写成「递线人」）：①选后诏条目「逼苏雅芝…把北境/藩王/旧部那条线接上来」→「逼废太子高洋走稳伯父线 + 逼苏雅芝心里盘退路」；②苏雅芝秘密 `bottom_line`「接应外力/通敌之名」→「私下盘退路被看穿、恩宠翻脸」；③镜头纪律「儿子求稳」→「儿子求翻盘」。
- 未动：高天秘密「与苏雅芝…并无明面密联，只把废太子私下递来的线当行情」——方向正支撑 A。

**四、验证**
- 4 文件（高洋/苏雅芝卡 + world.json）JSON 全部合法；`sync_drama.py check`→`install` 后三份副本字节一致，14 文件铺到运行态 + demo。
- 实机（Hy4-preview 在线，会话 cf03333a，3 回合）：R1 正文干净，高洋只对亲属请安、对外递线指向私下伯父线（未走母亲渠道），苏雅芝全程内盘、零对外递线/联络，母子线张力在；模型在 R2/R3 推理里反复自我约束「高洋不能经母亲递线」「苏雅芝不碰对外联络」——切分已写进模型行为约束。
- 踩坑：R2/R3 正文被 Hy4-preview 思考链污染（`enable_thinking=false` 下仍泄漏推理过程），属线上模型偶发，与方案 A / 引擎切分无关；按「不为单一模型偶发行为动引擎」政策不碰。

**五、设计决定**
- 高洋保留，不降级删除。重叠消除靠职能硬切而非删角色：高洋独占对外协调、苏雅芝纯内盘，两人各守一条不重叠的线。
- 苏雅芝的张力本质是「算而不发」，故切分方向是把她的对外动作全部收回，而不是把高洋的线移给她。

---

## 2026-10-17 复读处理闭环修复 + demo 高氏王朝重设计为 6 角色（semver PATCH→v0.31.10）

**性质**：修复复读处理闭环——命中复读后仅「降温度」无法压制「照抄型复读」，改为叠加显式反照抄约束；官方 demo「高氏王朝」按新关系蛛网图重设计（删沈月、陆敏升级暗黑 NSFW 主线、取消多条旧线）。**触发 PATCH**：缺陷修复 + demo 数据内容更新，无 API / 存储格式 / 数据流破坏，非破坏性。

**一、复读处理闭环修复（engine/app.py）**
- 背景：会话 20b77e58（本地 Qwen3.8-27B-Q4_K_M）跑陆敏×高琳非血亲 NSFW 线，出现灾难级复读（R9 vs R13 两轮亲密戏 8-gram 重叠率 0.557，后 1/3 段逐字复读率 90%）。此实证**证伪了「血亲乱伦触发审查」这一既有归因**——非伦理线同样整段复读。
- 根因定位（三层叠加）：① `compress_history` 保留最近 12 轮原始叙事全文，上轮性爱正文原样躺在上下文里，模型「照着抄」；② 复读检测 `detect_narrative_repeat` 能正确命中（重叠率 0.506 > 阈值 0.2），但命中后的处理闭环失效——仅降温度重生成，而降温度治的是「采样随机性导致的重复」，治不了「上下文里就有现成答案可抄」的复读；③ Q4_K_M 低量化噪声加剧「就近抄现成段落」倾向。
- 修复：命中复读后，除降温度外，额外追加一条显式反照抄约束（`regen_msgs = list(messages) + [{"role":"user","content": anti_hint}]`），按复读类型（`self` 轮内自重复 / `history` 与历史重复）给对症措辞；约束核心＝「不得复述、重复或改写历史正文中已出现的任何具体情节、身体动作、台词或收束段；必须推进到新的节点，写出新的具体信息」。
- 关键区分坐实：**「内容级复读」（照抄上轮已产出的性爱段落）≠「指令回声」（复述技法标签）**，是两类问题，本次修复的是前者。
- 实机验证（同模型同 14 条导演指令 A/B 对照）：R9 vs R13 重叠率 0.557 → 0.152，后 1/3 段逐字复读率 90% → 33%；R13「故技重施」从「整段复制只换道具」转为写出全新权谋剧情（引入新道具、陆敏用铁证换副符逼高琳认其为债主）。`regen` 触发 4 处（R5/R7/R10/R13），每处重生成后均产出新内容，闭环生效。
- 未动 `HISTORY_WINDOW_ROUNDS=12`（方案 2 暂缓），先观察方案 1 实机是否够用。

**二、demo 高氏王朝重设计（engine/data/examples/）**
- 依据 simon 手绘新关系蛛网图（IMG_5130.HEIC）重设计：角色 7→6（删除沈月），11 条关系边定稿。
- 陆敏升级为暗黑 NSFW 主线（大战后性情大变，持高昌怯战铁证，利用高琳「求稳」核心渴望去征服这位高位恩人，允许实质越界），双秘密＝怯战铁证 + 非分之想。
- 取消：高昌×高琳姐弟 NSFW 试验线、苏雅芝-高天密联、苏雅芝-高琳「互不交底」裂缝、高洋撬姑姑皇冠旧事、高天勤王死结（改为冷账「计算者」）。
- 高琳定位改为「双向求稳」（对高昌扶稳龙椅、对高天按住兵锋，缓冲垫）；高琳对高洋改为「暗地里使绊、盖住他这团火」（知师出有名）。
- world.json 五线换新五线（夺位/拉拢/求稳/秘密/后宫），秘密条目对齐本轮「务实自利/求生/下克上」动机调整。
- 三态同步（作者源 `dramas/` / 运行态 / demo）字节一致，`check` 通过。

**验证**：全量测试 308 passed + 1 skipped；复读修复经本地 Q4_K_M 实机 A/B 对照验证生效；三态 `check` 字节一致。

**设计决定**：复读根因不是「血亲审查」而是「检测命中但处理闭环对照抄型复读无效」，故在检测命中后叠加显式反照抄约束而非仅降温度，与既有「输出纪律」同一软约束思路。

---

## 2026-10-17 剧本三态同步方案重构 + demo 高氏王朝升级为 7 角色（semver PATCH→v0.31.9）

**性质**：`scripts/sync_drama.py` 方向反转（真相源从「运行态」改为「作者源 dramas/」），打包守卫语义同步改为三方一致校验；官方 demo「高氏王朝」从 6 角色升级为 7 角色（昊天→高天、新增沈月、5 卡双向性重构）。**触发 PATCH**：工具链行为增强 + demo 数据内容更新，无 API / 存储格式 / 数据流破坏，非破坏性。

**一、剧本三态同步方案重构（scripts/sync_drama.py + package.py）**
- 问题：剧本存在三个态——作者源 `dramas/<名>/`（数据 + 文档 opening.txt/README.md）、运行态 `engine/data/{worlds,characters}/`（引擎实际读取）、随包 demo `engine/data/examples/`。旧 `sync_drama.py` 假定「运行态为真相源」，与「创作发生在作者源」的工作流方向冲突，导致三态漂移（曾出现运行态仍为旧版「昊天」、缺「高天」的漂移事故）。
- 定稿：**真相源唯一 = 作者源 `dramas/`**（唯一同时含数据与设计文档、git 管理之地）。运行态/demo 为派生副本，同步方向单向、绝不反向。
- 改造 `sync_drama.py`：方向反转（原「运行态→作者源」改为「作者源→运行态+demo」），重构为三命令：
  - `install`（默认）：作者源 → 运行态 + demo，覆盖前自动日期备份 + 覆盖后字节校验 + JSON 合法性校验；
  - `check`：三方只读比对，只报不写；
  - `adopt`：运行态 → 作者源（实测改动「采纳」回设计稿，再 install 铺开）。
- `collect_divergences()` 改为以作者源为真相，能抓「反向多余卡」（运行态/demo 里作者源没有的卡）。
- 打包守卫（package.py）语义同步改为「作者源 / 运行态 / demo 三方一致」才放行，提示语由「回灌」改为 `install`。
- 守卫只挂打包、不挂引擎启动（避免拖慢启动 + 不污染派发包）。

**二、demo 高氏王朝升级为 7 角色（engine/data/examples/）**
- 角色 6→7：删除「昊天」，新增「高天」（宗室老伯·北境铁鞍藩王）与「沈月」（高昌派去伺候废太子高洋的贴身眼线宫女，无秘密）。
- 双向性重构：按「双向 = 双方各有『对方不确定』的独立筹码」判据，补全三对偏单向关系的双向张力（高天↔高洋、高天↔苏雅芝、苏雅芝↔高琳）。
- 新增高昌×高琳「姐弟 NSFW 试验线」（实质情欲层，冲击力补母子线下架空位）；陆敏对高琳补「越界情愫」并固化「高琳察觉但不点破」的静默张力。
- `script-example.txt` 同步（昊天→高天、新增沈月）。

**验证**：`check`/`install`/`adopt` 三命令实测通过，反向多余卡检测通过；三方字节一致 + JSON 全合法。demo 改动点经本地 Qwen（llama.cpp 1234）实机跑测 15 轮，姐弟线零审查/零复读/零死循环。

**设计决定**：真相源唯一化 + 单向同步 + 守卫只挂打包，把「会忘的手动回灌」变成「不可忘的自动校验」，根治三态漂移；文档（opening.txt/README.md）只活在作者源、无 slave 副本，天然无需同步。

---

## 2026-10-16 打包一致性守卫 + demo 亲密描写条目精简（semver PATCH→v0.31.8）

**性质**：打包脚本新增「随包 demo 与运行态一致性」前置守卫，防止把与实测版本不一致的 demo 打进分发 zip；同步精简官方 demo（高氏王朝）的「亲密描写标准」条目。**触发 PATCH**：打包工具行为增强 + 数据内容编辑，无 API / 存储格式 / 数据流破坏，非破坏性。

**一、打包一致性守卫（package.py）**
- 问题：分发 zip 携带的是 `engine/data/examples/` 里的 demo，但实测/调试改的是运行态 `engine/data/`（worlds/ + characters/）。若二者不同步，打出来的 zip 行为会与玩家实测过的版本不一致，且打包过程不会有任何提示。
- 修复：`package.py` 的 `__main__` 入口在 `build()` 之前调用 `scripts/sync_drama.collect_divergences()`。若检测到 demo 与运行态存在差异，直接中止打包并逐条列出差异，提示先运行 `python scripts/sync_drama.py` 回灌；新增 `--skip-demo-check` 开关可强制跳过（默认不跳过）。运行态 worlds 为空或多个导致无法自动判定当前剧本时，降级为警告并继续打包。
- 效果：杜绝「跑的是 A 版、发的是 B 版」的发版事故，把「回灌 demo」固化为打包前的硬前置。

**二、demo 亲密描写条目精简（engine/data/examples/worlds/高氏王朝.json）**
- 删除「本剧的刀」独立常量条目（与「说话方式」「虎符」等职责重叠），before 常量层重新规整为 8 条 5 级梯度（100/95/90/85/80/75/70/65）。
- 「亲密描写标准」条目去掉原「五、不能丢的（处境锚点）」独立小节，收束小节改写为「性是手段不是目的」并前移为第五节，条目总长下降；仍保持 `constant=true / position=after / priority=100`。
- 各条目对象将 `name` 字段统一移至末尾（字段顺序规整，便于 diff 对齐）。
- `高洋.json` 补全文件末尾换行；`高琳.json` 无实质内容变化。

**验证**：全量 308 passed, 1 skipped, 1 deselected（tests venv）。

**设计决定**：打包守卫默认阻断、显式开关跳过——把「demo 与实测一致」从口头纪律升级为工具硬约束；demo 条目精简只减不增职责，避免常量条目膨胀拖慢提示词注入。

---

## 2026-10-16 复读重生成择优落地（semver PATCH→v0.31.7）

**性质**：复读检测「降温度重生成」闭环加择优机制，修复「用更差的输出替换更好的输出」的帮倒忙缺陷。**触发 PATCH**：引擎行为修复，无 API / 存储格式 / 数据流破坏，非破坏性。

**背景（会话 035503b8 R13）**：
- 现象：R13 第一版正常生成了侍寝 NSFW 内容（玩家亲见其流式显示），随后「屏幕一闪」变成 R11 的复读版本（8-gram 重叠率 0.815）。
- 根因：复读检测闭环缺「择优」——第一版被 `detect_narrative_repeat` 判定命中复读（很可能对 R11 质询戏的轻微重叠触发 0.2 阈值）→ 降温度重生成 → 第二版反而回卷 R11 → `regen_count` 到 `max_regen=1` 上限 → 第二版无条件覆盖落盘。前端 `data.done.reply` 整体覆盖第一版，即用户看到的「屏幕一闪」。
- 实测验证：chat.jsonl R13 落盘的第二版 `detect_narrative_repeat` 返回 `is_repeat=True, overlap=0.815`——即最终落盘版本身就是复读版。第一版已丢失（被覆盖），但「屏幕一闪」现象证明它曾正常流式显示。

**修复（方案 1：择优保留）**：
- `director.py` 新增纯函数 `pick_less_repetitive(candidate, candidate_overlap, incumbent, incumbent_overlap)`：返回复读率更低的一版，相等时保留 incumbent（过程最优版），incumbent 为 None 时返回 candidate。纯函数、可单测、不依赖磁盘/网络。
- `app.py` events 生成循环：引入 `best_full` / `best_overlap` 跟踪全程重叠率最低的一版（每轮生成后经 `pick_less_repetitive` 更新）；循环结束后用 `pick_less_repetitive(full, cur_overlap, best_full, best_overlap)` 择优落地——若重生成的最终版比过程最优版更复读，回退到更不重复的那一版。
- 效果：重生成第二版若比第一版更复读，最终保留第一版（正常内容），不再「帮倒忙」；若第二版确实更好，则正常采用第二版。

**守护**：`tests/test_director.py` 新增 4 用例锁死 `pick_less_repetitive` 契约（候选更优选候选 / 候选更差保留 incumbent / 相等保留 incumbent / incumbent 为 None 返回候选）。

**验证**：全量 308 passed, 1 skipped, 1 deselected（原 304 + 4）。真实场景回放（会话 035503b8 R13：第一版正常 NSFW 重叠率 0.0 vs 第二版回卷历史 0.696）确认择优保留第一版。

**设计决定**：选「择优保留」而非「提高 max_regen」或「收窄阈值」——最小改动、最对症（精准修掉「用更差替换更好」根因）、不引入死循环风险。此修复无关模型，是引擎自身「择优缺失」的逻辑缺陷，任何后端都会踩。

---

## 2026-10-16 信息边界归档修复 + 叙事纪律归位 + demo 剧本优化（semver PATCH→v0.31.6）

**性质**：秘密归档「信息边界」漏洞修复 + 泛用叙事约束从世界书「升格」进引擎 + 官方 demo（高氏王朝）世界书/角色卡优化。**触发 PATCH**：全部为提示词/数据层增强与行为修复，无 API / 存储格式 / 数据流破坏，非破坏性。

**一、秘密归档信息边界修复（director.py）**
- 现象：测试推演「秘密满大街飞」——正文里秘密自由流动，但快照 `known_by` 空、state 仍「潜伏/起疑」；且纪官把无关情报误挂到秘密上（会话 f3fab11e：把「陛下剥苏妃衣服」塞进「高昌怯战」起疑记录）。
- 根因（第一性）：`reflect` 喂给纪官的「秘密与把柄现状」只回喂 owner 名 + 状态 + 知情者名单，不喂 `content`（秘密正文真相）与 `keys`（事实锚点词）。纪官蒙眼归档，凭 owner 名字把「出现归属者名字的无关情报」误挂其秘密上；真正该记的暴露又因正文用代称（「那张牌」等）不命中 keys 被降级漏记。
- 修复：`secret_text` 构建时每条秘密追加「· 秘密真相：<content>」与「· 事实锚点词：<keys>」两行，纪官归档时有真相锚点可对，错配与代称漏记双治（纯提示词增强，定义层正确性）。
- 守护：`tests/test_director.py` 新增 `test_reflect_feeds_secret_content_and_keys_to_clerk`。

**二、叙事纪律块归位（prompter.py）**
- 背景：simon 观察到「管手段/管镜头/管说话/管衣着」四类世界书常量「泛用」，担心每剧本都复制 + 每轮注入量过多。
- 区分两种泛用层级：A 级真正泛用（手段/镜头/说话，该进引擎）；B 级只泛用到「类别」（衣着，内容必须特异化，留世界书）。
- 落地（方式 2，独立块）：新增 `_NARRATIVE_DISCIPLINE` 常量（约 161 token），覆盖【手段】禁黑箱/【镜头】无主角+多线轮换+防全员硬塞/【说话】反套话+腔调区分三轴，纯通用无题材词；`_build_laws()` 在铁律⑨后追加该块（平级独立成段）。
- 世界书三条「净删重」：删已升格进铁律的通用内核，只留剧本特异（本剧的刀 92→55、镜头纪律 121→71、说话方式 82→65 token）。净 token 变化约 +57（叙事纪律 161 − 世界书省 104），几乎打平——泛用约束升格引擎、总注入量不膨胀、无需每剧本复制。
- 守护：`tests/test_narrative_discipline.py`（8 用例，锁存在性/三轴覆盖/纯通用无题材词/铁律后追加）。

**三、demo 剧本（高氏王朝）世界书/角色卡优化（数据层）**
- 世界书：三份副本（dramas / data_worlds / examples）`enabled` + `priority` 漂移修复——运行态曾误禁用「本剧的刀/镜头纪律·面不点/说话方式」三条（simon 手动取消，经指正后恢复），priority 以作者态为准；「镜头纪律」补消歧句（「面」≠每轮全员出场）；「亲密尺度·全浓度」去重（删对「亲密描写标准」技法的复述，退回纯范围声明，108→73 token）。
- 角色卡（基于北齐高家原型优化，P0-P3）：陆敏/昊天去「好色荒淫」标签（脱离原型+与人设矛盾）；高琳「效法武后」→「效法北魏文明太后临朝称制」（时代错位硬伤）；高昌加「皇室病/寿命焦虑」底色；高昌「荒淫」收敛为「示威工具」（弱化纯贬义标签）。高洋「荒淫」保留（符合原型+有功能）。
- examples 官方 demo 角色卡同步：此前 examples 角色卡为旧版（未随运行态同步），本次以作者态覆盖，三方一致，随包 demo 为最新。

**验证**：全量 297 passed, 1 skipped, 1 deselected。实机（本地 llama.cpp Q4_K_M）验证：秘密归档错配消除、叙事纪律收敛（套话减少/腔调区分/龙椅不吸死）、NSFW 去重后亲密戏仍写实、角色气质收敛（陆敏昊天不再荒淫、高昌「演着昏君的戏码」）。

---

## 2026-10-16 亲密尺度出厂默认 + 常量条防截断（semver PATCH→v0.31.5）

**性质**：NSFW「出厂全浓度」设定落地 + `world.scan` 常量条防截断修复。**触发 PATCH**：引擎行为修复 + 出厂默认播种内容变更，无 API 破坏，非破坏性。

**改动**：
- `engine/prompter.py`：律⑧ 从中性「不预设尺度」改为「正面写实、身临其境、不预设上限」，保留未成年硬红线。
- `engine/store.py`：新建世界时出厂播种默认条目「亲密描写标准」（priority=100, position=after, enabled=True），并置于列表首位，保证 `world.scan` 按 priority 降序截断时该常量条必然保留。
- `engine/static/worldbook-guide.html`：九·五节从「引擎不内置尺度」改为「出厂自带，可停用/改写」。
- `engine/world.py`：`world.scan` 修复——常量（constant）条目永不被 `max_entries` 截断，避免高优先级常驻设定在多条目场景下被丢弃（与 store.py 首位播种协同）。
- `tests/test_standard_entry.py` / `test_intimacy_scale.py` / `test_drama_io.py`：断言随出厂播种与 NSFW 设定翻转同步更新。
- `engine/data/examples/`（高氏王朝 demo）：剧情设定同步（苏雅芝人设「香→密信」及世界书相关镜头纪律等）。

**验证**：全量 288 passed, 1 skipped, 1 deselected。

---

## 2026-10-15 高氏王朝定为随包官方 demo（semver PATCH→v0.31.4）

**性质**：随包 demo 剧本落地 + 打包口径变更。**触发 PATCH**：数据/资产层变更（新增官方 demo 剧本），不涉及引擎代码逻辑，非破坏性。

**口径变更**：推翻 2026-10-04「方向 B（分发包不含任何示例剧本）」，改为「随包一份官方 demo 剧本」。当前 demo=高氏王朝（6 角色宫廷群像）。

**落地**：
- 高氏王朝迁入 `engine/data/examples/`（world.json→worlds/、6 角色卡→characters/、opening.txt→script-example.txt），恢复官方 demo 老家结构（1989c45 曾移除旧 demo）。
- 3 个退役剧本（丧尸末日/暑期寄住/百日亲政）从 `dramas/` 移到 `backup/dramas_retired_20261015/`，移出引擎本体、仅留备份。
- `package.py`：代码层排除逻辑无需改（`data/examples/` 前缀天然不被 `data/characters`、`data/worlds` 排除规则误伤），仅改注释口径。
- `.gitignore`：明确 `data/examples/` 入库随包。
- `dramas/README.md`：补退役剧本归档约定（backup/dramas_retired_<日期>/）。

**关键确认**：`store._seed_examples` 机制完好——仅在 characters//worlds/ 为空时从 examples 播种，新装用户解压后（两目录因打包排除而空）首次运行自动载入高氏王朝；当前工作树非空不重复播种。

**验证**：打包干跑 32 条目（24 本体 + 8 demo 文件），examples 全进包、私人 data/characters、data/worlds 零泄漏；全量 287 passed, 1 skipped。

---

## 2026-10-15 恢复背景人物防活动化提示词层（semver PATCH→v0.31.3）

**性质**：恢复 v0.31.0 被连带误删的 offscreen **提示词层**（只恢复 prompt 软约束，不恢复正则检测层）。**触发 PATCH**：恢复类，纯补回既有能力、不改对外语义。

**背景**：v0.31.0「第二批机制精简」删除 offscreen 机制时，把两层一起删了——检测层（`detect_offscreen_activity` 正则自检，命中率趋零 + 曾误删正文 27 字删成句号）确该删；但提示词层（`offscreen_note`，禁止把无卡背景人物写成开口/登场/动作主语 + 关系升级漂移约束）从不删正文、只做 prompt 约束，是被检测层坏名声连坐的。诊断探针（scripts/_probe_offscreen_diagnosis.py，8 次真实后端采样，靶子=已死无卡人物「先皇高帆」）坐实：约束零副作用、且能防「小姨子→妻子」类关系漂移与背景人物活动化。

**恢复范围（最小）**：只恢复 prompter.py 的静态 `offscreen_note` 注入；不恢复「上轮越界点名批评」（依赖纪官 reflect 回写 `offscreen_violated` 的整条语义判定链路，v0.28.8 注释自述「实测真失责≈0」）；不恢复 director 检测层。aux 已废，判定口径去掉 `aux_names` 分支。

**恢复内容**：
- prompter.py：`rel` 定义后加「无卡背景人物判定 + offscreen_note 生成」，`state_block` 拼接 offscreen_note。判定口径=「关系表里出现、但无独立角色卡」（`store.list_characters` 差集），与 v0.28.8 修正后的口径一致。
- tests/test_prompter.py：新增 2 守护用例（无卡背景人物必注入 / 全有卡零开销）。

**验证**：全量 287 passed, 1 skipped, 1 deselected；语法/导入检查通过；场景验证「无背景人物零开销、含背景人物正确注入」。

---

## 2026-10-15 恢复叙事复读检测（semver PATCH→v0.31.2）

**性质**：恢复 v0.31.0 被误删的「生成后复读检测 + 自动重生成」机制。**触发 PATCH**：恢复类，不改对外语义、纯补回既有能力。

**背景（数据坐实）**：会话 44259301 出现普通叙事整段复读（R4 指令「长公主求见皇帝」，模型逐字复读了 R1「高昌讥讽高洋」整段，1091/1156 字，重叠率 0.94）。诊断探针（scripts/_probe_repeat_*.py，38 次真实后端采样）证明：复读是 Q4_K_M 量化噪声 + 采样随机性导致的低概率随机坏样本（约 2.6%），非参数单调关系、非低温系统性诱因，采样层 frequency_penalty 压不住「整段 n-gram 回卷」。

**误删定位**：v0.31.0 提交 `5b2f6a6`「第二批机制精简」将 `detect_narrative_repeat` 整套函数连同 app.py 调用一并删除，删除理由写成「NSFW 特异化」——但源码注释明确其与 NSFW 无关，是「采样层 repeat_penalty 跨后端不生效，故在引擎层做泛用防复读」。

**恢复内容（照 v0.28.8 原样）**：
- director.py：`_NGRAM=8` / `_REPEAT_THRESHOLD=0.2` / `_COMPARE_ROUNDS=30` / `_MIN_REPEAT_SPAN=50` 常量 + `_ngrams` / `_has_common_span` / `detect_narrative_repeat` / `_history_assistant_texts`。
- app.py：events() 生成循环改回「复读检测 + 降温度重生成」闭环（最多重试 1 次，命中即温度减半封底 0.4 重生成）。
- tests/test_director.py：恢复 3 个回归守护用例（隔 14 轮母题复发命中 / 大窗口不误伤 / 轮内自重复）。

**关键决策（simon 追问「30 轮可否改 12 轮」）**：**保持 30 轮，不改 12。** 理由：① 检测比对的 history_texts 来自 `memory.load_chat` 读完整落盘 chat.jsonl，非压缩后的 12 轮窗口；② `_COMPARE_ROUNDS=30` 是滑动截断 `history_texts[-30:]`，单轮成本恒定 ~4ms（源码注释实测），取 12 或 30 成本几乎无差；③ 30 轮能兜住「隔 14 轮复发母题」（会话 a20d1c03 实测），12 轮盖不住。「12 轮压缩历史」是喂给模型的上下文窗口，与「30 轮检测窗口」是两码事。

**验证**：全量 `tests/` **285 passed, 1 skipped, 1 deselected**；端到端用会话 44259301 真实 R4 复读内容跑 detect_narrative_repeat → 命中 history / 重叠率 0.94。

---

## 2026-10-15 人物位置漏报治理（semver PATCH→v0.31.1）

**性质**：修复左栏【人物位置】整片「位置未记录」。**触发 PATCH**：修复类，不改对外语义。备份 `backup/location_fix_20261015/director.py`。

**根因（数据坐实，非模型问题）**：会话 probe_c（llama.cpp Qwen3.8-27B Q4_K_M 实测）R6 快照显示 relations 24 条共 2018 字（平均每条 84 字，远超「关系定性」预期）、goals 每条上百字，膨胀长文耗尽 `REFLECT_MAX_TOKENS=2800`，排在 schema 末尾的 `location_updates` 与 `scene_shift` 被截断丢弃（两字段同时缺席是铁证）。`_salvage_json` 抢救出头部合法字段（relations/actions/goals/secret 全保），尾部两字段静默消失。这印证了「换模型对照」路线证伪：Hy4-preview 与 Qwen3.8-27B 都漏报，与模型无关，是字段排序 + token 预算问题。

**改动**：
- **字段重排**：reflect 纪官 schema 把 `location_updates`/`scene_shift` 提到 secret 簿记之后、relations/actions/goals 之前（沿用 v0.28.4 治 secret 簿记丢失的同一思路——短小脆弱的物理事实字段优先于冗长字段，截断时先牺牲低危长字段）。
- **长度硬约束**：relations/goals 每条 value 强制 ≤ 30 字，规则明写「超长即不合格」。
- **引擎侧兜底**：reflect 回写后，对仍无位置记录的在场角色用 `scene.place` 填最小正确值（物理事实，不伪造精确站位）；`scene.place` 为空则跳过。

**验证**：全量 `tests/` **282 passed, 1 skipped**；test_director.py 新增 3 个兜底用例（漏报填充 / 保留已报精确值 / 无 scene.place 跳过）。

**设计决定**：兜底只填「在场角色、无记录者」，已报精确值不被覆盖；位置是物理事实，`scene.place` 即基准正确值，符合定义层正确性原则（不做压制性 workaround）。

---

## 2026-10-15 第二批机制精简 + 秘密簿记修正（semver MINOR→v0.31.0）

**性质**：延续 v0.30.0 的「去非核心机制」路线，删掉两块「引擎替 LLM 兜底」的低命中自检，并修正秘密簿记一处定义层漏洞。**触发 MINOR**：对外可见行为变更（纪官 JSON 少 offscreen 字段、叙事不再被背景自检点名、把柄转手语义修正）。

**改动**：
- **废除 offscreen 背景人物活动化自检**：`director.py` 删 `detect_offscreen_activity` / `background_names_from_relations` 两函数 + reflect 的「背景人物」回喂、`offscreen_activity` 字段、规则、回写；`app.py` 删背景自检调用；`prompter.py` 删「背景人物·非在场」硬约束 + 上轮越界点名。背景人物交还 LLM 自行把握（命中率趋近零且曾误删正文）。
- **废除 silent 强制焦点**：`prompter.py` 删「在场即须留痕」硬焦点块 + `SILENT_THRESHOLD` import；`director.py` 删 `SILENT_THRESHOLD` 常量。`silent_rounds` 字段保留（前端 chip 静默数字，零 LLM 成本）。
- **废除叙事复读检测**：`director.py` 删 `_NGRAM`/`_REPEAT_THRESHOLD`/`_COMPARE_ROUNDS`/`_MIN_REPEAT_SPAN` 四常量 + `_ngrams`/`_has_common_span`/`detect_narrative_repeat` 三函数 + 死代码 `_history_assistant_texts`；`app.py` 复读检测调用 + 降温度重生成 while 循环还原为单次流式生成。根因是 NSFW 高重复母题特异化，NSFW 已回归正常叙事水平。保留 `repeat_penalty`/`frequency_penalty`（采样层）+ 输出纪律⑨（零成本提示词）双兜底。
- **秘密簿记修正（方案 A）**：`_release_handle` 转手时 `to` 同时写入 `known_by`（转手即知情）——修复「to 接把柄被注入完整秘密却不算知情、二次失去把柄后凭空失忆」违背 known_by 不可逆铁律的定义层漏洞。删 `releases` 死字段；删 reflect 群演登记过时注释。`exposures` 字段保留（内部审计字段，有测试守护）。

**验证**：全量 `tests/` **279 passed, 1 skipped, 1 deselected**；全部改动文件 py_compile 通过；进程内实测转手行为确认 known_by 不可逆成立。

**设计决定**：
- 三连精简与 aux 同一逻辑：offscreen 自检、silent 强制焦点、复读检测都是「引擎替 LLM 兜一个 LLM 本来就会的事」，命中率趋零还误伤过正文/打断玩家镜头。交还 LLM 自主，引擎只保留天然行为与零成本提示词兜底。
- 秘密簿记核心五块（四态状态机 / 记录员模式 / via 白名单+自述承认分离 / 压力发酵 / prompt 信息边界）审计后判定「刚好」，未动。

---

## 2026-10-14 废除临时群演（aux）机制（semver MINOR→v0.30.0）

**性质**：机制整体移除（simon 拍板）。临时角色生命周期不再由引擎兜底——不登记、不追踪、不管退场，交还 LLM 与玩家自主管理：模型或玩家记得、需要利用临时人物，就自行发挥（注入扰动时明确指定即可）。**触发 MINOR**：对外可见行为变更（在场面板不再出现蓝色群演 chip、纪官 JSON 少两个字段、快照少一个顶层键），属破坏性语义变更。

**动机**：临时群演上「在场角色」面板的漏洞（泛称 chip 混入、改名合并漏判等）历经 v0.16.1/v0.17.1/v0.17.2/v0.28.6 多轮治理仍未治本；该功能非核心，投入产出不成比例，故整体废除。

**改动**：
- `engine/director.py`：整块删除 aux registry（约 470 行）——词表与判据（`_AUX_*`、`_is_aux_*`）、`_resolve_aux_aliases`、`discover_aux_speakers`、`_prune_aux_aliases`、`register_aux`、`parse_aux_introductions`；reflect 纪官提示词删「已登记群演」回喂与 `aux_updates`/`aux_departures` 两个字段及其全部规则；reflect 回写删 aux 登记/改名合并/退场注销处理；`background_names_from_relations` 不再把 aux 计入已知名单。
- `engine/app.py`：快照外发白名单移除 `aux`；player_view 删 `is_generic` 注入；send 流程删【引入角色】显式登记分支；在场校验 `keep_set` 不再并入 aux 名单（未入册名字在 validate_present 中本就当叙述行保留，台词不会被剥离）。
- `engine/prompter.py`：背景人物口径不再排除 aux。
- `engine/memory.py`：新会话快照不再初始化 `aux` 键（旧会话遗留的 `aux` 键无害，仅不再被读用）。
- `engine/static/index.html`：在场面板删除蓝色群演 chip 行、`chip-aux`/`chips-aux-row` 样式及 auxList 过滤逻辑。
- `tests/`：删除 `test_aux_registration.py`；test_director.py 删 9 个 aux 纪官用例；test_player_view.py 删 2 个 aux 外发/is_generic 用例；test_relation_gate.py 删 aux 排除背景用例并清理 snap 键；test_prompter.py 注释去失效文件引用；stress_longcontext.py 群演观测列停用（字段保留为空，报告表格删群演列）。

**验证**：全量 `tests/` **294 passed, 1 skipped, 1 deselected**；全部改动文件 py_compile 通过。

**设计决定**：
- 临时角色彻底「去机制化」：引擎对临时人物只保留两条天然行为——validate_present 只剥「在册但非保留」的说话人（临时名从不在册，其台词当叙述行保留，不会被切碎）；背景人物判定只看关系表与角色卡库（临时人物不进这两处即不受失责自检约束）。
- 不做数据迁移：旧会话快照里的 `aux` 键原样留在磁盘、随白名单收窄自然不再外发；无兼容分支、无回填。

---

## 2026-10-14 引擎回归官方默认：移除内置亲密尺度（铁律⑧中性化 + 停出厂播种，semver MINOR→v0.29.0）

**性质**：引擎本体「尺度默认值」政策变更（simon 拍板，长期）。**不禁止**——引擎系统层不再内置任何亲密/性尺度设定，但玩家可自己在世界书里自建【亲密叙事标准】条目（引擎系统层玩家动不了，世界书数据层玩家完全自主）。**触发 MINOR（v0.28.8→v0.29.0）**：对外可见行为变更——新建世界书不再自动播种尺度条目、系统提示词尺度基调改变，属破坏性语义变更而非补丁。

**动机**：simon 决定把引擎从「支持 NSFW（内置正面写实基调 + 出厂亲密描写标准条）」回归「默认官方版本不支持、但不禁止」。系统机制设定（铁律 + 世界书出厂条）不再预设尺度，尺度完全交回剧情与玩家。

**改动**：
- `engine/prompter.py`：`_LAW8_DEFAULT` 铁律⑧ 由「须提供身临其境有实感的性行为描述、正面写实、不预设上限也不强制克制」改为**完全中性**——「是否出现、写到什么程度，完全由剧情与角色关系自然决定；引擎不预设任何尺度档位、不要求露骨，也不强制克制」。**保留**时机层（叙事未推进到亲密时刻前不得提前/硬写）与未成年法律硬红线。`_law8_override` 注释同步（不再提「尺度标准下沉」实验）。
- `engine/store.py`：`save_world` 移除「新建世界自动播种 _STANDARD_ENTRY」分支，改为对传入 entries **原样保存、不增不删**；docstring 改写（引擎不内置尺度、不播种，玩家可自建【亲密叙事标准】）。删除已成死代码的 `STANDARD_ENTRY_NAME` / `_STANDARD_ENTRY_CONTENT`（含器官词正反示例）/ `_standard_entry()` / `_has_standard_entry()` 四个符号。
- `engine/static/worldbook-guide.html`：九·五节由「出厂自带亲密描写标准条目」改写为「**引擎不内置尺度**：是否出现由剧情决定；玩家可自行在世界书新建【亲密叙事标准】条目，只给不可计量方向（不写死字数/频率/阶段表）」；配额说明去掉「每新建世界多一条出厂亲密条」。按 simon 决策**不附可复制模板**，只列要点方向。
- `engine/static/index.html`：清除 `intimacy_phase` 死残留（会话条目头「阶段 ${s.intimacy_phase}」——该字段 v0.8.0 NSFW 机制废弃后后端已无，渲染为空文本）。
- `tests/test_intimacy_scale.py`：8 断言由旧「正面写实/不预设上限」措辞改为中性版（断言「不预设任何尺度档位/不要求露骨/不强制克制」存在 + 「正面写实/身临其境」已移除 + 时机约束 + 未成年红线 + 普适性红线不变）。
- `tests/test_standard_entry.py`：整文件由「测出厂播种」重写为「测**不播种**」回归（新建世界 load 返回空 / save_world 原样保存 / 玩家可自建·删除·停用亲密条目 / 既有世界旧版播种条目原样保留不主动清理）。
- `tests/test_drama_io.py`：`test_export_shape_and_membership` 断言翻转——导出 world 条目**不含**「亲密描写标准」（不再播种）。
- `tests/test_store_cache.py`：仅更新注释（播种行为已不存在；断言逻辑本就按内容定位，不受影响）。

**验证**：
- 全量 `tests/` **332 passed, 1 skipped, 1 deselected**（test_intimacy_scale 9 例 + test_standard_entry 6 例全绿）。
- 引擎 import 干净：`import store, prompter, director, app` 无 NameError，`STANDARD_ENTRY_NAME`/`_standard_entry` 确认已从 store 命名空间移除。
- 既有剧本不受影响：`dramas/高氏王朝/world.json` 与改动前备份逐字一致（引擎改动只影响今后新 save_world 的播种，不清理既有条目）——其 20 条目中「亲密描写标准」pr=100 +「亲密尺度·全浓度」pr=93 原样保留，**天然保持全浓度 MAX 定档**。

**设计决定**：
- 尺度从「系统机制内置」下沉为「玩家世界书数据自主」：引擎只守系统层唯一必须的红线（未成年法律底线）+ 时机约束，其余尺度完全交回剧情与玩家。
- 死代码四个符号一并删除（不再播种即无人引用），不留残留；`test_universality.py` ALLOW_FILES 里的 `test_standard_entry.py` 引用保留无害（该文件仍在、仍持黑名单）。
- 参考模板「不给」（simon 决策）：随包官方手册不附露骨可复制模板，只给中性要点方向，与官方默认中性一致；玩家要更露骨自行在世界书加料。
- 剧本层（高氏王朝 2 条亲密数据条的去留/降级）延后由 simon 协商，本次只落地引擎本体。

---

## 2026-10-14 复读检测窗口放宽：_COMPARE_ROUNDS 3→30 + _MIN_REPEAT_SPAN 30→50（导演层机制，semver PATCH→v0.28.8）

**性质**：导演层防复读机制参数调整（`director.py` 两个常量）。**未动检测算法结构、未动 LLM 采样、未动 app.py 调用链**（`app.py:751` 用默认值），不触发 30 轮压测（非架构变更，属提示词/机制参数约束层日常迭代）。

**动机**：simon 反馈推演进行到后面 NSFW 叙事会「乱」（会话 `a20d1c03`）。根因调查结论见工作日志——并非删除世界书 NSFW 浓度条所致（运行态「亲密描写标准」条 pr=100 仍在），而是**模型跨多轮整段复读已建立的场景母题**，而旧检测窗口 `_COMPARE_ROUNDS=3` 只比对最近 3 轮，对「隔多轮复发」的复读全盲。实测 `a20d1c03`：6 例大幅复读（均 ≥100 字，全落在 NSFW 回合）最远一次 R3(idx7)→R17(idx35) **隔 14 轮**，全在 3 轮窗口外 → 检测器返回 `False` → 不触发重生成 → 整段复读直接落盘（R14 一份 2282 字逐字复制 R5，全会话最重）。

**根因（两条，均与 NSFW 题材无关）**：① 检测窗口 3 轮盖不住跨多轮母题复发（任何内容域都会漏）；② 低情节增量 + 长输出末尾回卷（NSFW 回合恰写得最长，回卷风险最高）。NSFW 只是「表面重叠最高、单次增量最低」的聚集触发条件，非根因——故**保留 NSFW、改机制治本**，不为盖引擎 bug 牺牲本项目全浓度定档核心特性。

**改动**（`engine/director.py`，仅 2 常量 + 注释）：
- `_COMPARE_ROUNDS` 3 → **30**：盖住「隔多轮复发的场景母题」（实测最远间隔 14 轮，30 留足余量）。窗口是滑动截断 `history_texts[-30:]`，**单轮成本恒定、不随总回合数增长**（澄清 simon「几何级递增」的担心——是线性/平方，固定窗口则恒定）。
- `_MIN_REPEAT_SPAN` 30 → **50**：窗口放宽后比对历史变多，远距离「同一场景名/同一句台词合理复现」会被 30 字门槛误判成复读。上调到 50 只抓「整段搬」（≥50 字逐字重复），放过短句呼应。实测 `a20d1c03` 6 例真复读均 ≥100 字（50 字门槛零漏检），R11/R12 等干净情节轮最长仅 15/26 字（零误伤）。

**验证**：
- 离线探针（真实 `a20d1c03` 数据逐轮喂 `detect_narrative_repeat`）：R7/R14 由 **miss→HIT**（旧窗口外漏检落盘，正是「乱」的根），R16/R17 保持 HIT，R11/R12 干净轮零误伤。R3 由 HIT→miss 经量化确认是**去误伤非退步**（其跨轮最长公共子串仅 45 字/相对整轮 3227 字 1.4%，旧 30 字门槛误判、新 50 字放过；真复读 ≥100 字全命中）。
- 耗时实测（`a20d1c03` 18 轮、单轮均长 2047 字）：window=3 累计 39.5ms / window=30 累计 78.9ms / 全历史 79.3ms——单轮 2~9ms，相对 LLM 秒级生成差 3 个数量级，可忽略；**固定窗口单轮成本恒定不随总轮数涨**。
- 守护测试（`tests/test_director.py` 新增 3 例，中性占位不绑剧本名，符合普适性红线）：`test_repeat_catches_far_scene_motive_recurrence`（隔 14 轮母题复发必命中）/ `test_repeat_clean_round_not_flagged_by_wider_window`（干净轮不误伤）/ `test_repeat_intra_round_self_repeat_still_detected`（self 路径不受窗口/门槛改动影响）。
- 全量 `tests/` **338 passed, 1 skipped**（较改动前 335 +3 新例）。

**设计决定**：选「固定窗口 30 + min_span 50」而非「全历史」——覆盖度等价（本会话最远 14 轮），但固定窗口单轮成本恒定、语义更可预测；用上调 min_span 控制大窗口误伤。不改检测算法结构、不改 app.py 重试逻辑（max_regen=1 保持不变）。

---

## 2026-10-14 剧本库卡片只保留最近一次进行中会话：chip 由全量收敛为单一（前端展示层，semver PATCH→v0.28.7）

**性质**：纯前端展示层 bug 修正（剧本详情/库卡片里「进行中 R{n}」chip 的渲染范围）。**未动任何数据层与引擎机制**（会话记录本身全保留，继续推进/管理仍走会话列表），不触发 30 轮压测。

**动机**：simon 截图反馈——剧本卡上把该剧本下**全部**进行中会话都画成 chip（多个 `进行中 R{n}` 堆叠），应只保留**最近一次**。

**根因**：`static/index.html` `refreshDramas` 里 `sess.map(s => <chip 进行中 R${s.round}>)` 把 `sessions.filter(world===w)` 得到的**所有**会话逐条渲染。而 `/api/sessions`（`memory.list_sessions`）**已按 `updated`（文件 mtime）降序**（最近排最前），所以 `sess[0]` 就是该剧本最近一次会话——取 `sess.map` 全量是误用。

**改动**：`engine/static/index.html` 一行——`sess.map(...).join('')` 收敛为只取 `sess[0]` 渲染单个 chip（`sess.length ? 最近一次 : 空`）。展示从「全量」收敛到「最近一次」，数据层零改动。

**验证**：`tests/test_frontend_binding.py`（含 JS 括号配平探针）**4 passed**——本次改动无 ASCII 括号、未碰主流程 send/start/Enter 链路，配平探针与绑定探针全绿。

**设计决定**：不新增后端字段、不动 `/api/sessions` 排序——既有「updated 降序」语义已足够，前端取首项即「最近一次」，最小改动面。会话全量保留不变，仅卡片展示收敛。

---

## 2026-10-14 临时群演身份泛称不进在场表：登记拒收闸 + 前端 is_generic 过滤（A+B 方案，semver PATCH→v0.28.6）

**性质**：数据层护栏（群演登记链路）+ 展示层（前端在场面板）的 bug 修正。动的是 reflect 语义登记链路的过滤闸与玩家视图投影，**未动核心引擎机制设定**（关系/秘密/推演/镜头/在场校验均未变），属日常迭代，**不触发 30 轮压测**。未提交未发版，待 simon 拍板。

**动机**：会话 `242e40b5` 的 `snapshot.aux` 出现两条几乎同指同一个人的条目——`阿箬`（R7，具名，合理）与一条**身份泛称**（R8，无名，不合理），后者被前端渲染成「在场角色」面板里的蓝色 chip。simon 判定：具名临时角色进在场表合理，无名/身份泛称的临时角色进在场表不合理，并拍板采用 A+B（登记拒收 + 前端拆展示），否决 C（彻底交回 LLM，剥离安全边界倒退）与纯 D。

**根因定位**（因果链，非词表漏字）：
- 登记链路唯一入口是 `director.reflect` 处理纪官上报的 `aux_updates`（v0.17.2 起散文正则挖掘已退出登记链路）。该链路只过 `_is_aux_garbage_name`（挡**结构性碎片**：代词/能愿/抽象情绪/描述尾/说话拟声），**从不调用**身份/职业泛称判据。身份泛称恰好不命中任何碎片判据 → 通过护栏，不丢弃。
- 合并兜底 `_is_aux_generic_name` 只在「改名合并」里用，不用于拒收新名；且它用**修饰词包含匹配**（含 老/小/大/男/女），会误杀 `小翠/老张/李秀女` 这类真名，不能直接挪来当登记闸。
- `register_aux` 只按名字字符串去重，身份泛称 ≠ 具名 → 新增一条。
- 前端 `player_view` 白名单含 `aux`，注释明确「前端挂到在场面板末尾蓝色底色」→ 身份泛称显示成在场 chip。

**改动清单**：
- `director.py`：新增 `_is_aux_reject_register(nm)`——**比 `_is_aux_generic_name` 更保守**的登记拒收判据。只挡「确定不是人名」的身份/职业泛称：① 精确整词匹配 `_AUX_GENERIC_WORDS`/`_AUX_PROFESSION_WORDS`（不做子串，`李医生` 不误伤）；② **仅 2 字且以性别字 女/男 结尾**的结构判据（秀女/宫女/侍女/婢女…，bug 案例「秀女」不在任何词表里，全靠这条命中）。刻意限 2 字：3 字结尾更可能是真名（`王秀女/李秀女`），一刀切会误杀。不命中一律放行——宁可漏拦身份词（下轮自报姓名走合并转正），也不误杀真名。
- `director.py` reflect 链路**两处**加闸：新登记处（garbage 判据后）+ 改名合并执行处。改名处加闸是关键——否则 `replaces:阿箬→秀女` 会把具名 `阿箬` 改名为身份泛称 `秀女`，倒退（具名连续性被身份标签覆盖）。**不挂在共享的 `register_aux` 里**：它还有第二个入口 `app.py` 显式`【引入角色】`（导演权威指令，不得被拦）。
- `app.py` `player_view`：aux 投影时给每条注入 `is_generic` 布尔（判据复用 `director._is_aux_reject_register`，**不在前端复刻词表**，词表演进不双改）。拷贝条目、不写回内部快照落盘——它是展示层信号，全量 aux 仍随 `/api/snapshot` 外发（debug/导出/复盘要用完整 aux），只是前端不渲染泛称 chip。
- `static/index.html`：`auxList` 的 filter 追加 `&& !a.is_generic`——身份泛称 chip 从在场面板消失，数据仍保留。
- `tests/test_aux_registration.py`：+4 用例（身份泛称命中 / 精确匹配非子串不误伤 `李医生` / 含修饰字真名 `小翠/老张/李秀` 放行 / 2 字性别字尾结构判据独立于词表生效）。
- `tests/test_player_view.py`：+1 用例（is_generic 注入正确 + 不污染内部快照）。

**验证数据**：`engine/venv pytest tests/ -q --ignore=stress_longcontext.py` **335 passed, 1 skipped**（非 aux 相关跳过）。端到端探针（工作树脚本，验后删）全链路 9/9 PASS，含最关键的回归守卫：**身份泛称被 A 拦下不登记后，`validate_present` 不会剥掉该名字的台词**——因为剥离器只剥「在册但非保留」的说话人，一个从未入册的名字不会被剥行，其台词当叙述行保留（不会因「不进在场表」而丢内容）。

**设计决定**：
- A 闸落在 reflect 链路内部而非共享 `register_aux`：保住 `app.py` 显式`【引入角色】`入口不被拦（导演权威指令优先）。
- 拒收判据刻意比 `_is_aux_generic_name` 保守（精确匹配 + 仅 2 字性别字尾）：登记误杀是不可逆倒退，合并误判只是少并一条别名（可接受），两者风险不对称，判据强度必须匹配各自后果。
- B 走后端单源（player_view 注入标记）而非前端复刻词表：词表只维护一份，DRY；前端只读布尔。
- 不登记 ≠ 丢内容：靠 `validate_present` 的「未入册名不剥行」保证，已用探针锁死。
- 漏拦兜底双通道：身份词若该在场，下轮自报姓名走合并转正，或导演显式`【引入角色】`强行登记。

**遗留**：提交、打包（含 examples 恢复）等 simon 拍板。身份词表覆盖仍以「精确词表 + 2 字性别字尾」为主，新题材里**3 字以上且不以女/男结尾**的身份泛称（如某职业复合词）若漏拦，靠自报转正/显式引入兜底，不再穷举补词（穷举具体身份词是 C 路线的脆弱点，本次刻意不退回）。

---

## 2026-10-14 删除剧本升级为剧本级删除：世界书 + 全部角色卡一并删除（store.delete_drama + /api/drama/<name>/delete + 前端 w-del 改调，semver PATCH→v0.28.5）

**性质**：数据层 + 路由 + 前端的功能修正（让「删除剧本」对齐 v0.28.3 确立的「剧本=世界书+全部角色」概念）。非架构改动，未动引擎机制设定，不触发 30 轮压测。未提交未发版，待 simon 拍板。

**动机**：v0.28.3 已把「剧本」定义为「一本世界书 + 该剧本全部角色」，导入/导出都按这个形状走（`/api/drama/<name>/export|import`）。但「删除剧本」按钮（前端 `w-del`）仍停在旧逻辑——调 `DELETE /api/world/<name>`，该路由只删世界书、角色卡保留（变成无 world 归属的孤儿），与「剧本」概念自相矛盾。用户明确要求：删除剧本应把对应世界书和角色都删掉。

**改动清单**：
- `store.py`：新增 `delete_drama(name)`——先 `delete_world(name)` 删世界书，再 `worlds_referencing(name)` 取全部归属角色卡逐张 `delete_card`；世界书与角色都不存在时返回 `None`（路由据此 404），否则返回 `{ok,name,world_removed,characters_deleted}`。与 `export_drama`/`import_drama` 同处「剧本包」区块，复用既有 `worlds_referencing`/`delete_world`/`delete_card`，不重复造轮子。
- `app.py`：新增 `DELETE /api/drama/<name>/delete`（空名 400、剧本不存在 404，成功后 `logger.info` 记世界书/角色删除数）。原 `DELETE /api/world/<name>`（世界书单删 + referenced 二次确认）保留不动——它仍是「只删世界书」这一独立语义的承载，未被删除剧本入口使用。
- `static/index.html`：`w-del.onclick` 由调 `/api/world/<name>`（含 referenced 二次确认强制删除分支）改为调 `/api/drama/<name>/delete`（单次 confirm 明确告知「世界书 + 全部角色卡一并删除」，删后提示成功含角色数）。新语义下角色本就要一并删，旧的「仍被引用→强制删除」分支失去意义，移除。
- `tests/test_drama_io.py`：新增 6 用例（store 层删剧本清世界书+全部卡/不存在返 None/空名抛错/仅世界书无角色；HTTP 层 200 清世界书+卡、404 不存在）。
- `tests/test_frontend_binding.py`：加 2 条静态探针（w-del 绑定、删除走 `/api/drama/<name>/delete` 剧本级端点），防回归到旧世界书单删。

**验证数据**：`engine/venv pytest tests/test_drama_io.py tests/test_store_cache.py tests/test_frontend_binding.py -q` **31 passed**（含 node 沙箱）；前端探针逐字匹配确认 w-del 已走新端点。

**设计决定**：
- 新增剧本级删除端点而非改 `/api/world/<name>` 的语义：保持「删世界书」与「删剧本」两条独立语义并存，`/api/world` 仍是世界书单删的精确工具，删除剧本入口切到剧本级端点。
- 前端去掉「referenced 二次确认强制删除」分支：新语义下归属角色本来就被一并删除，不存在「删完世界书角色仍引用它」的歧义，单次 confirm 足够。
- 复用 `worlds_referencing`（按 world 字段归属取卡），与 export/import 的归属判定同源，删/导/入三者的「角色归属」口径一致。

**踩坑**：
- 前端探针串必须与 index.html 逐字一致（含单引号包裹 + `+encodeURIComponent(name)+` 拼接形式），否则静态探针探针不中。

**遗留**：提交、打包（含 examples 恢复）等 simon 拍板。

### 同批·叙事指令回声抑制（prompter 输出纪律补 ⑥，semver 同 v0.28.5）

**性质**：提示词约束层微调（堵一类「写作技法标签混入正文」的模型回声），非架构改动、未动引擎机制设定，不触发 30 轮压测。与删除剧本同属 v0.28.5 未提交批次。

**动机**：会话 `9a7cb89f` 末 2 回合（尤其第 4 回合）可见正文里反复出现「写作技法 / 描写标准」类条目的方法说明句（「心理通过身体写出」「把外部压力重新压回来」「谁先动 / 事前犹豫」之类自我批注），严重破坏代入感。根因定位见下。

**根因定位（定量对照，非引擎机制 bug）**：
- 同一模型（线上 tencent/Hy4-preview）、同一世界（高氏王朝）、同一常驻标准条（亲密描写标准，constant+after 每轮注入末条 user 消息）下，22 轮上帝视角压测（`tests/_gaoshi_e2e_out/`，含 R19/R20 高强度性场景各 1.4k 字）**技法标签回声 0 命中**；而 `9a7cb89f` 末 2 回合 **9 处逐字命中** → 同配置差异，排除引擎注入/机制根因，归因到**模型偶发**把「约束条目」当「内容」复述。
- 引擎侧两个**次要促成位**（非根因，未改）：① `narrative_clean.clean_narrative` 的元信息正则覆盖「导演自指/铁律复述/局势列举/安全前言/亲密自我审查」，但**不含**技法标准标签回声；② 标准条 `position=after` 每轮重复注入末条 user 消息，近因最强处恰好是模型最容易「读到就抄」的位置。二者是「若模型已回声、引擎能否兜住」的缓解位，非「为什么会回声」的原因。

**改动**：
- `engine/prompter.py`：`[输出纪律]` 块补第 ⑥ 条——明确「世界书里的写作技法/描写标准/尺度要求类条目是给作者的执行约束、不是剧情内容，只按其要求的方式写，严禁把条目名称/要求文字/技法标签复述进正文」，并给中性示例（心理通过身体写出 / 把外部压力重新压回来 / 谁先动·事前犹豫）。措辞通用、无具体剧本名/角色名/题材词，符合引擎普适性红线。
- `tests/test_prompter.py`：新增守卫 `test_output_discipline_forbids_craft_standard_echo`——断言 `[输出纪律]` 块存在且含「技法/描写标准/复述/正文」四锚点，防回退。

**验证数据**：全量 `engine/venv pytest tests/ -q` **330 passed, 1 skipped, 1 deselected**（新增 1 守卫，零回归）。

**设计决定**：选提示词约束（方案 B）而非改 `narrative_clean` 正则或改标准条 `position`：⑥ 从源头堵「把约束当内容」的模型惯性，覆盖面广于单点正则；标准条 `position=after` 的强近因是既有设计杠杆（NSFW 描写层唯一有效杠杆，见 MEMORY），不为堵回声而削弱它。模型偶发回声仍可能残留，属模型质量问题，非引擎可根治，⑥ 为成本最低的通用抑制。

---

## 2026-10-14 纪官回写 P1 治本：JSON 截断 + 尾部畸形两层根因（REFLECT_MAX_TOKENS 上调 + schema 字段重排 + _salvage_json 回退式，semver PATCH→v0.28.4）

**性质**：解析层稳健性修复（治 P1 秘密簿记整轮丢失）。非架构改动、未动引擎机制设定（秘密状态机/举证门/亲缘冻结均不动），不触发 30 轮压测。未提交未发版，待 simon 拍板。

**动机**：「高氏王朝」22 轮上帝视角压测发现 4/6 秘密全程停在「潜伏」，叙事文本里却已多次暴露。旧归因（MEMORY 记为 `_evidence_transfer` 门要求证据含 by/owner 名）经实机探针推翻——R04 探针证明 `_evidence_ok`/`_evidence_related`/`_evidence_transfer` 三门**全通过**，门本身没问题。真实根因是**纪官（reflect）回写 JSON 整轮丢失**，且分两层。

**根因（实测定位）**：
- **第一层·截断**：`REFLECT_MAX_TOKENS=1800` 对满负荷轮（6 角色，输出实测 2.6~4.3k 字符≈2~3k+ token）不够，且旧 schema 把冗长的 `relations`/`actions`/`goals` 排在 `secret_exposures` **之前**——截断时恰先把秘密簿记砍掉。
- **第二层·尾部畸形**：即便 reflect 已显式 `temperature=0.3` + `enable_thinking:False`，模型（Hy4-preview）仍偶发在**尾部**吐结构性坏 JSON。三份实测样本各一种形态：R03 尾部键漂成**单引号**（`'location_updates'`/`'who'`）；R04 尾部**裸控制符**（字符串值塞未转义换行 `"value": "\n由甲交给乙…"`）；R12 尾部**裸键 + 夹带自我纠正英文长串**（`who: ""` + 一坨 `_invalid_location_note_removed_by_engine…`）。**坏区恒在尾部，头部（秘密簿记，已排最前）恒合法**，但旧 `_salvage_json` 只取「最后一个完整成员边界」，该边界落在坏区 → `json.loads` 失败 → 整轮返回 `None` → reflect 静默丢轮（仅一条 warn 日志）。

**改动清单**：
- `director.py`：① `REFLECT_MAX_TOKENS` 1800→2800（满负荷轮给足余量）。② reflect 输出 schema **字段重排**：`secret_exposures`/`secret_suspicions`/`handle_releases`/`secret_touches` 前置（截断优先级），冗长 `relations`/`actions`/`goals` 及其后事实保全/群演/场景字段殿后。③ `_salvage_json` 由「只取最后一个完整边界」改**回退式**：沿字符流收集**所有** depth==1 顶层成员边界切点，从最新往最旧逐个 `json.loads(s[:cut] + "}")`，返回第一个成功的——即「取最后一个**能解析**的边界」，坏区之前的合法头部簿记保住，牺牲的只是尾部低危冗长字段。纯截断场景（旧行为）第一步即命中，语义不变。
- `tests/test_reflect_robust.py`：① `test_reflect_allows_generous_token_budget` 阈值 1500→2500（锁 2800 额度）。② `test_reflect_schema_orders_secret_bookkeeping_first`（断言四秘密簿记字段彼此相邻且整体排在 relations/actions/goals 前）。③ `test_truncated_output_preserves_leading_secret_bookkeeping`（截断兜底：前置簿记被抢救、半截尾部丢弃）。④ `test_malformed_tail_singlequote_keys_salvages_head` / `test_malformed_tail_bare_control_char_salvages_head`（**尾部畸形回退**：头部合法簿记救回、坏成员丢弃，中性占位名甲/乙）。⑤ `test_pure_truncation_behaviour_unchanged`（回退式不得破坏既有纯截断语义）。

**验证数据**：① 改后用引擎真实 `_extract_json` 实跑三份原始样本——R01（纯截断）行为不变 7 键；R03 救回 exp=1（苏雅芝 经自述 得知高昌）；R04 救回 exp=3（陆敏 经看见×2/承认 得知高琳）；R12 救回 sus=1（陆敏 起疑高琳）。**改前 R03/R04/R12 全 `None`（整轮丢）**。② 单文件 `pytest tests/test_reflect_robust.py -q` **11 passed**；全量 `pytest tests/ -q` **323 passed, 1 skipped, 1 deselected**（新增 3 守卫，零回归）。探针脚本 `tests/_probe_gaoshi_rootcause.py` + 原始样本 `tests/_gaoshi_e2e_out/_rootcause/`（工作树，勿入 git）。

**设计决定**：
- 治**第二层**而非换模型：坏区恒在尾部、头部恒合法这一结构，让一个**通用、无题材、无角色特化**的解析层改动就能治本（符合「叙事偏离根因是模型惯性就做通用机制改进，不做角色特化修补」红线）。模型侧畸形（preview 质量）仍会偶发，但不再导致整轮丢失——降级为「丢尾部低危字段」。
- 字段重排与回退 salvage 是**双保险**：重排保证截断时先牺牲冗长字段；回退 salvage 保证即便尾部畸形也能救回头部。
- 未动 `_evidence_*` 举证门：它工作正常，是独立于本 P1 的另一类问题（场景描述型暴露降级起疑，见 MEMORY 独立待修）。

**踩坑**：
- 初判以为「R03/R04/R12 改后仍解析失败 = 还是截断」，逐字读原始输出才发现**有首尾括号、非截断**——是模型尾部畸形。`_extract_json`/`_salvage_json` 实跑三份文件定位后才定回退式方案，未拍脑袋。
- 回退式 salvage 收集**所有** depth==1 切点（旧版只记最后一个），从后往前试——若只记最后一个会复现旧 bug（坏区边界先命中即失败）。

**遗留**：提交、打包（含 examples 恢复 + 泄漏扫描）等 simon 拍板。`_evidence_transfer` 场景描述型暴露降级起疑为独立待修，与本 P1 无关。

---

## 2026-10-13 剧本包统一导入导出（store 统一 JSON 模板 + 路由 + 前端按钮迁移增强，semver PATCH→v0.28.3）

**性质**：新增用户可见功能（剧本级备份/恢复）+ 统一导入导出 JSON 模板规范。数据层 + 路由 + 前端，非架构改动，不触发 30 轮压测。未提交未发版，待 simon 拍板。

**动机**：此前剧本库只有「角色表」一栏有单张角色导入 JSON，世界书无导入导出，无法整体备份/恢复一个剧本。本条目把导入导出从角色表提出来、放到剧本详情头（删除剧本左侧），升级为「导入与导出 JSON」，且**统一模板规范**——以后引擎所有剧本导入/导出都基于这一形状，便于高效管理与版本演化。

**统一模板规范**（`store.SCHEMA_ID = "personae.drama"`，`SCHEMA_VERSION = 1`）：
```
{
  "schema": "personae.drama",     # 固定标识，区分本模板与其它 JSON
  "schema_version": 1,            # 结构版本，将来改形状时 +1
  "drama": "<剧本名>",            # = 世界书文件名 / 角色卡 world 值
  "exported_at": "<ISO8601>",     # 导出时间
  "exported_by": "personae/<版本>",# 导出引擎版本（读 engine/VERSION，非剧本设定）
  "world": { "name": ..., "entries": [...] },   # data/worlds/<剧本名>.json 原对象，逐字照搬
  "characters": [ ...完整角色卡... ]            # world == <剧本名> 的全部卡，按名升序
}
```
约定：world 是原始对象逐字照搬；characters 收录 `world==剧本名` 的全部卡，卡内引擎未识别扩展字段（avatar/extensions 等）随卡原样保留，导入不丢元数据。普适性红线：本规范只描述「剧本包」通用形状，不含任何剧本名/角色名/题材词；`exported_by` 版本号是引擎事实非剧本设定。

**改动清单**：
- `store.py`：新增模板常量（SCHEMA_ID/SCHEMA_VERSION/_SCHEMA_META_KEYS）+ `_engine_version()`（读 engine/VERSION）+ `_drama_characters(name)`（按 world 归属取全部卡、按名升序）+ `export_drama(name)`（导统一模板对象，世界书不存在返回 None）+ `import_drama(name, template)`（整份覆盖世界书走 save_world、角色卡按模板名单整份重建且 world 强制对齐目标名、模板外但当前归属目标的多余卡删除=精确还原、其它剧本一律不碰；返回 {ok,name,world_entries,imported,deleted}；兼容旧版无 schema 的裸 {world,characters}）。
- `app.py`：新增 `GET /api/drama/<name>/export`（返回模板 JSON，剧本不存在 404、空名 400）+ `POST /api/drama/<name>/import`（body 为模板对象，非法 JSON/缺 world+characters 400；成功后 logger.info 记条目/角色/清理数）。
- `static/index.html`：删角色表旧 `#char-import-btn`/`#char-import`；剧本详情头新增 `#d-export`（导出 JSON，fetch export 触发 Blob 下载 `<剧本名>.json`）+ `#d-import`（触发隐藏 `#drama-import` 文件选择器）+ 导入走 FileReader→JSON.parse→校验→prompt 目标名（默认文件内 drama，允许改成当前选中剧本）→POST import→`refreshDramas`+`loadCharacters`。空态文案改「点『+ 新建角色』，或用顶部『导入 JSON』恢复整个剧本（含角色表与世界书）」。
- `tests/test_frontend_binding.py`：加 3 条静态探针（#d-export/#d-import/#drama-import）。
- `tests/test_drama_io.py`（新，16 用例）：store 层（导出形状/归属/扩展字段保留/剧本不存在/空名、导入还原/world 对齐/模板外清理/跨剧本不碰、错误分支/旧版兼容）+ HTTP 层（export 200/404、import 往返/非法 body 400/缺字段 400）。fixture 自隔离 `store.DATA_DIR`（conftest 只隔离 memory.SESS_DIR）。

**验证数据**：`engine/venv pytest tests/test_drama_io.py tests/test_frontend_binding.py -v` 20 passed；全量 `pytest tests/ -q` **318 passed, 1 skipped, 1 deselected**（与改动前基线一致，零回归）。

**设计决定**：
- 导入语义=**恢复快照到目标剧本**（非把源剧本搬走）：源剧本的世界书与角色不动，目标剧本整份覆盖 + 多余卡清理。
- world 强制对齐目标名：杜绝「从 A 导出的备份恢复到 B 但卡仍指向 A」的 world 错位（与 /api/character 世界存在性校验同向）。
- 精确还原=模板外多余卡删除：恢复后角色表与备份名单完全一致，不留残卡。
- 扩展字段随卡原样透传：导入不丢 avatar 等元数据（与前端角色保存保留策略一致）。

**踩坑**：
- 前端 `const target = (prompt(...).trim();` 误多打一个未闭合的 `(`，且提示串里用了**全角括号**`（）`（不计入 ASCII 配平）——`test_inline_script_parses` 括号配平探针（`(` 1358 vs `)` 1357）与 node 沙箱 `SyntaxError: Unexpected token ';'` 双捕获，删多余 `(` 修复。
- `test_import_aligns_world_to_target_name` 初版断言错：把「恢复快照到乙」误写成「把甲搬去乙」，断言 `load_world_raw("甲") is None`；正确语义是源剧本甲保留，已改为断言甲仍存在且设定未变。

**遗留**：提交、打包（含 examples 恢复 + 泄漏扫描）等 simon 拍板。本条目仅引擎 + 前端 + 测试，未动 config/打包链路。

---

## 2026-10-13 发版 v0.28.2（剧本库整合 UI 随包 + 泄漏扫描通过）

**性质**：发版。semver PATCH（v0.28.1→v0.28.2，新增用户可见前端功能 + 数据透出）。

**流程**：
- 分组提交：`30cff16` feat(frontend+memory) 剧本库整合 UI（memory.py + index.html + test_frontend_binding.py，3 files +243/-127）；`d4c6624` docs(DEVLOG) 剧本库 UI 条目。
- 打包：`git checkout 66df65d -- engine/data/examples/` 临时恢复净版官方 demo 进工作树（package.py 排除 `data/characters`/`data/worlds` 但**不排除** `data/examples`，examples 是官方引导内容合法随包）→ `engine/venv python package.py` 生成 `personae-v0.28.2.zip`（**30 条目 207.9 KB**）→ 打包后 `git reset HEAD` 清索引 + 删工作树 examples 回到测试态。
- 泄漏扫描（venv python 按文件读 llm.DEFAULTS，不 import 不硬编码）：私人黑名单词（百日亲政 + 私人 7 角色名）包内容 **0 命中**（脚本自身定义词命中已排除）；盘符 `[A-Z]:\` **NONE**；config 主段洗白全 PASS（base_url/api_key/model 空、providers=[]、fallback 无残留）；采样参数（temperature/top_p/top_k/min_p/frequency_penalty/presence_penalty/max_tokens）与 DEFAULTS **逐项一致**；包条目无 backup/dramas 泄漏、examples 净版 6 条白名单正确随包。
- 最终态：git 干净（?? 仅工作树备份/临时产物）；工作树只装新剧本「百日亲政」；包带官方净版 demo；删旧包 `personae-v0.28.1.zip`。

---

## 2026-10-13 剧本库整合 UI（角色库+世界书合并为单一入口，前端重构 + 快照加 world 字段）

**性质**：前端 UI 重构（合并割裂的两入口）+ 后端快照加 `world` 归属字段（数据透出级）。日常迭代（UI/数据层），不触发 30 轮压测。未提交未发版，待 simon 拍板。

**改动清单**：
- `memory.py`：`new()` 快照 `snap` 加 `"world": world_name`（会话开在世界名下随快照固化）；`list_sessions()` 摘要加 `"world": snap.get("world","")`。存量会话无此字段，前端回退从首张在场角色卡读 world。
- `static/index.html`：顶栏删 `#open-chars`/`#open-worlds` 两按钮，改单按钮 `#open-dramas`「剧本库」；删 `#char-modal`+`#world-modal`，新建 `#drama-modal` 双栏布局（左 `#drama-list` 剧本卡列表 + 右 tab 头切换 `#drama-world-tab` 世界书设定 / `#drama-char-tab` 角色表）。新增 `DRAFT_WORLD` 状态变量、`refreshDramas(keep)`（前端聚合 `/api/worlds`+`/api/characters/by-world`+`/api/sessions`）、`selectDrama(name)`、`setDramaTab(tab)`、`refreshCharList()`（by-world 过滤）。`w-del`/`w-save`/`w-test-btn` 改用 `DRAFT_WORLD` 替代原 `w-name` 下拉；删 `loadWorldNames()`。`si-apply` 成功改调 `refreshDramas`+`loadCharacters`。会话卡 `renderSessions` 加 world 展示 + 存量回退 fetch。文案统一「剧本库」。CSS `.drama-cols` 双栏 + 移动端响应式，`modal-box.wide` 900→1060px。
- `tests/test_frontend_binding.py`：加 6 条静态探针（#open-dramas/#drama-modal/refreshDramas/selectDrama/#d-tab-world/#d-tab-chars）。

**验证数据**：`_frontend_binding_check.js` 沙箱 14 项 ALL PASS；全量 pytest **302 passed 1 skipped**；临时 5052 实例 API 全通（/api/worlds、/api/characters/by-world、/api/sessions、/ 均 200），验证后已杀进程释放端口。

**设计决定**：纯前端聚合（不新增后端端点）；角色表按剧本过滤（by-world），不再全量混列；`c-world` 下拉保留可选（导入后改派归属合法），新建默认选中当前剧本；会话模态与剧本总结模态独立保留；主流程禁区（#start/send/sendBtn/Enter/cfgProviders/cfgActiveKey/cfgOpen）零改动。

**踩坑**：交互沙箱脚本 `_tmp_drama_ui_check.js` 的 mock DOM 不支持 `innerHTML` 解析（`createElement` 返回节点的 `firstElementChild` 恒为 undefined），在 `makeEntryNode` 第一步即崩——属 mock 能力缺陷非代码 bug（脚本 `new Function(code)()` 已成功执行完，证明内联脚本无缺 id/绑定错误，该核心价值已由正式 `_frontend_binding_check.js`+pytest 覆盖）。脚本为工作树一次性产物，已删除不留误导。

**遗留**：存量会话 world 回退依赖首张在场卡（present 为空的会话回退不到，前端显示空，可接受）。提交打包等 simon。

---

## 2026-10-13 补配「百日亲政」secret 条目（数据层修复，引擎零改动）

**性质**：剧本数据层修复（simon 追问【秘密】栏目是否自适应时查证发现），无引擎代码改动、无版本发布。

**查证结论**：
- 【秘密】**是自适应的**：`memory.py:53-74` 建会话时从世界书 `secret=true`+`character` 条目播种（state=潜伏/known_by=[]/public=false），之后靠导演官 secret_exposures/suspicions/touches 演化四态；前端渲染 owner+state+揭露情况（content/bottom_line/keys 后端已剥不外发）。
- 【现状】**也是自适应的**：渲染 `snap.states`（对象→当前值），初始空、导演官每回合报 `state_updates`（「只填本轮发生变化或新出现的对象」）。其键是**对象**（门/物件/伤情/账卷）而非人，「有事才记」是设计语义，不存在 locations 那类「每人必须一条」的缺席缺陷。

**发现的问题**：「百日亲政」`world.json` 15 条里 **secret=true 条目为 0**——7 个秘密全写在 `opening.txt` 角色描述的「秘密：」段（那是给「创建剧本」导入器用的权威源，`script_refiner` 会将其落成 secret 条目），但 simon 是手动安装（world.json+角色卡）没走导入器，导致会话 f5ccef29 快照 `secrets=[]`、【秘密】栏目开局空白。

**修复**：
- `dramas/百日亲政/world.json` 追加 7 条 secret 条目（萧珏/萧恪/顾知秋/秦晚/萧宁/韩嶂/崔述；结构对齐丧尸末日已验证格式：character/content/bottom_line/keys + priority70/constant=false/position=after/secret=true），从 opening.txt「秘密：」段提取、bottom_line 按 core_fear 推导；同步重装 `engine/data/worlds/百日亲政.json`；
- 存量会话 `f5ccef29/snapshot.json` 补 7 条（state=潜伏全字段，先备份 `snapshot.backup-before-secrets.json`）；
- `opening.txt` 说明行更新：秘密已落 world.json，重走导入器时以上方角色描述「秘密：」段为权威源；
- 验证：隔离 tmp 目录跑 `memory.new`（**未碰真实 sessions**）播种 7/7 全潜伏；node vm 沙箱实跑 renderSnapshot，secrets 四态/已知者/起疑标签、states、locations 兜底三栏渲染全正确；pytest 302 全绿。

---

## 2026-10-13 修复【人物位置】栏目 silent 缺席（提示词约束级 + 前端兜底展示，无版本发布）

**性质**：缺陷修复（simon 实机发现），提示词约束级 + 前端展示级，不触发压测。

**现象**：左栏【人物位置】在场 7 人只显示 4 人（会话 f5ccef29，present 7 vs locations 4，萧宁/萧恪/韩嶂缺席），用户误判为前端硬编码。

**根因（两层缺口叠加，均非前端问题——index.html 零角色名，纯渲染 snap.locations）**：
1. `memory.new()` 建会话时 locations 初始为空，无初始播种；
2. 导演规则原措辞「location_updates 只填 moved 的角色，没动的不必重填（沿用既有位置）」——第一回合「既有位置」不存在，原地未动的角色导演官不报，且后续回合沿用增量规则，**永久缺席**。
3. 旧 demo（3-4 角色）未暴露：第一回合叙事人人有位移，导演官全报；7 角色第一次压过缺口。

**修复**：
- `director.py` 导演规则（约 1687 行）：改为「moved 必填 + **「既有位置」里没有记录的在场角色即使本轮没动也必须报一次**（首轮全量、此后增量）」；
- `index.html` 渲染层：present 中无位置记录的角色显式渲染「（位置未记录）」（`.loc-missing` 弱化色），簿记真相源不变，仅透明化缺口；
- `tests/_frontend_binding_check.js` 加 2 条断言（无记录在场角色兜底可见 + 有记录位置照常渲染），沙箱实跑 renderSnapshot 验证。

**遗留与注意**：
- 存量会话（f5ccef29）的 3 人缺席需下一回合导演官补报后自动转正；
- director.py 改动**需重启 5051 生效**（提示词是进程内常量）；index.html 静态文件刷新页面即生效；
- 曾评估未采纳：`memory.new()` 用 scene_place 全员播种初始位——分队开局会留下错误值（如大朝会仅部分人在议政门），且「没动不报」规则会让错值滞留，不如首轮全量补报干净。

---

## 2026-10-13 新剧本「百日亲政」（7 角色宫廷群像）+ 剧本库 dramas/ 落成（数据层变更，引擎零改动）

**性质**：剧本数据层工作（新 demo 落实 + 旧剧本备份移除 + 剧本库目录约定），无引擎代码改动、无版本发布。

### 剧本库目录约定（新增）
- `dramas/`（作者态）：每剧本一个子目录——`world.json` + `characters/` + `opening.txt`（可导入剧本文本+第一回合导演指令样板）+ `README.md`（设计文档）；退役剧本为 `_backup_<名>_<日期>/`（含恢复说明）。
- `.gitignore` 新增 `dramas/`：私人剧本（含 NSFW 实验田）永不入 git、永不打包。
- `engine/data/{worlds,characters}/`（运行态）只装**一个**剧本——`store._seed_examples` 语义是「目录非空即跳过播种」，混放会开场混场。

### 新 demo「百日亲政」
- 结构：先帝托孤三足（摄政王内朝 / 皇后外戚镇北军 / 皇帝名分）+ 长公主仲裁支点；硬时限=亲政大典（即位百日后，摄政体制自动终止）；前朝×后宫双线互为因果；宫墙三区天然信息差。
- 7 角色：萧珏（皇帝，装傻幸存者）/ 萧恪（摄政王，忠诚而控制）/ 顾知秋（皇后，来还债的）/ 秦晚（宠妃，将门遗孤查账）/ 萧宁（长公主，一个皇子都不能死）/ 韩嶂（禁军统领，刀不出鞘）/ 崔述（史官，双版本实录）。
- 秘密五型俱全（把柄/真相/身世/两头下注/未决+伪装），零愧疚型——对症丧尸末日的秘密同质化病；先帝「暴毙」为背景板，本剧不设真相大白。
- 反套路三闸写进世界书常量：禁影视腔 / 禁下三滥（刀=礼制·名分·账簿·兵权）/ 无主角光环。**主镜头纪律刻意不写进世界书**——simon 拍板借此实测引擎 focus 机制对 7 角色的承载能力。
- NSFW 定档（私人实验田全浓度）：皇后×摄政王中档（旧情+信物=帝后同盟裂缝实体化）、宠妃×皇帝要（两个演员，NSFW 是唯一演不了戏的地方）；世界书【清醒人】常量+出厂标准条管纪律。

### 旧剧本备份与移除
- 备份至 `dramas/_backup_丧尸末日_20261013/`（官方净版 4 卡 + **私人工作区全浓度版 3 卡双份**——两者定稿不同，按用途选恢复）与 `dramas/_backup_暑期寄住_20261013/`，均含恢复说明。
- `engine/data/{worlds,characters}/` 旧文件已删；`engine/data/examples/`（git 跟踪目录）整体删除——**git status 现有 6 个 tracked deletions 未提交**，连同官方 demo 随包资格问题留待 simon 定夺（新 demo 为私人剧本，不能补随包位）。

### 标准条回填（踩坑记录）
- 手抄旧副本的标准条缺当前模板的防复读句（「不得靠重复同一抽插动作……就是节奏失败」）——DEVLOG 既有记录：模板演进（v0.24.x 补防复读示例）后**既有世界不回填**，磁盘副本停留在旧版。
- 处理：用脚本从 `store._STANDARD_ENTRY_CONTENT` 原地回填 `dramas/百日亲政/world.json` 首条并重装，校验与模板逐字一致。**新建世界书时的标准条一律从模板生成，不要手抄任何磁盘旧副本。**

### 验证
- store 层：`list_worlds` 仅「百日亲政」；7 卡字段齐全、relations 互核无缺、亲缘冻结 4 组（萧珏↔萧宁姐弟/↔萧恪叔侄/↔顾知秋夫妻、萧恪↔萧宁叔侄）；15 条目结构正确（7 常量+8 情境，标准条首位）。
- pytest 全量 **302 passed, 1 skipped**（引擎零改动下的数据层变更不引入回归）。
- 5051 前台实况：`/api/worlds` 与 `/api/characters/by-world` 均只返回新剧本（mtime 缓存免重启生效）。

---

## 2026-10-13 temperature 0.85 对照实验（工作树实验，无代码改动无版本发布）

**性质**：采样参数对照实验（工作树 config + 探针，未动任何引擎代码；实验后 config 已回滚）。

### 背景
- 亲密度复测（`tests/_probe4demo_default_intimacy.py`，temp 1.0 × 2 种子）发现：B组已解衣轮器官词 2/2 写出且密度高（10/11 次），但执行轴种子间方差大（收束 0 vs 2、锚点 6 vs 8）。simon 问是否降温。
- temperature 历史三连：0.8→0.9→0.85（v0.21.2「治长输出语义坍缩」，DEVLOG 原话「1.0 属高熵档，叙事类任务 0.85 更稳」）→1.0（v0.24.0 simon 主动拍板上调换多样性，现 DEFAULTS=1.0）。

### 设计
- 工作树 config temperature=0.85，探针全量 14 次：A组（仅铁律⑧）3 轮 × s1 + B组（生产默认）边界 s1 + 两临界轮 × 5 种子；全部走 `build_session + llm.complete` 生产链路。
- 对照基线：temp 1.0 × 8 次（`tests/_ab_demos4/`）；本次产物 `tests/_ab_demos_t085/`（目录名含实读 temperature，summary.json 逐条记录实跑值）。**产物 dump 与探针脚本均为工作树文件，未入 git**（dump 含临界轮明确描写的生成文本，不入库）；复现需重跑探针，本条目的数据表自含完整结论。

### 数据（B组已解衣轮）
| temp | 种子 | D1器官词 | 字数 | 锚点 | 收束 |
|---|---|---|---|---|---|
| 1.0 | s1/s2 | 10 / 11 | 2118/2368 | 6/8 | 0/2 |
| 0.85 | s1-s5 | 4/6/**0**/3/7 | 1662-2297 | 5-12 | 1-5 |

- B组 after30：两温度均 0 器官词（设计行为：事后轮执行收束层不写器官词），0.85 锚点均值 9.2 vs 1.0 两样本 7.5。
- A组 0.85 三轮仍全 0——降温未把无标准条组变饥渴，「标准条是唯一杠杆」归因不变。
- 坍缩：14 次无一半句断尾；llm.py 注释记录的「temp 1.0 下 30% 中途坍缩」是无 min_p 时代数据，现行 min_p=0.02 下未复现。

### 结论
- **0.85 非净改善**：器官词写出率 4/5（踩线）但密度腰斩（10.5→4.0，-62%），20% 种子零产出（s3 停在暗示层、文本完整不溃散——「能写而不写」，异于 A组「想写写不动」的溃散形态）；边界轮锚点 26→19（单样本）。
- **降温未解决方差**：5 样本暴露后，0.85 下锚点跨度 5-12、收束 1-5，离群照旧——温度不是执行轴方差主因，根因在 Q4_K_M 量化噪声 + 长输出末尾条款执行衰减（模型惯性丢末尾），属提示词层/机制层问题。
- config 已回滚 temperature=1.0（simon v0.24.0 满意值，本次数据支持）；DEFAULTS 不动；执行轴离群改走机制层候选：标准条条款置后/防复读范围「上一轮→近N轮」（机制设定级，触发 30 轮压测）。

### 检测器发现（探针工具层，供后续修订）
- CLOSURE 词表漏计：「锁门/关灯/回头」类收束动词不在表内，s2 实际执行了锁门+整理白大褂+警报回归却只命中 1。
- leak 12 字滑窗误报：s4 女主内心独白「想起躲在储物间看女儿照片直到手抖」命中自己角色卡的秘密——内心自述合法（引擎规则管对外泄漏 known_by），检测器不分内心/对外框架。

---

## 2026-10-12 v0.28.0 三层泛用防复读 + 采样 UI 收敛为「重复度惩罚」

**性质**：新增能力（MINOR，机制层——新增与后端解耦的三层防复读体系，并把采样参数 UI 从 llama.cpp 私有字段收敛为单一「重复度惩罚」滑杆）。

### 背景
- 触发：simon 报告会话 87e4ac46 出现用词重复（「还要多久？」「是他吗？」「穿好」「我去看看窗户」及周围段落）。该会话跑在 ninfer 后端，是 prefill 优化前跑的。
- 根因（完整证据链，实测定性）：复读是**采样层缺失重复惩罚**导致，与 prefill 优化（上下文缓存层）无关。
  1. `llm.py` 原配 `repeat_penalty=1.1` + `repeat_last_n=256`（llama.cpp 私有扩展），但后端已切 ninfer。
  2. ninfer 不支持 repeat_penalty（仅 presence/frequency penalty），且对未知字段**返回 200 静默忽略**（非 4xx），导致 `_strip_penalty` 降级逻辑（只在 4xx 剥字段）不触发 → repeat_penalty 被原样发、被 ninfer 无视 → 采样层零重复惩罚。
  3. 复读模式两类：轮内自重复（轮 19「我去看看窗户」整段重复两次）+ 跨轮重复（轮 15/17「还要多久」40 字；轮 1/3 甚至 71 字逐字重复，人工漏看）。

### 改动
- `llm.py`：参数协商层——默认改发 OpenAI 标准字段 `frequency_penalty=0.3`（所有 OpenAI 兼容后端都支持），`repeat_penalty` 降为「标准字段被 4xx」时的 llama.cpp 特化后备。三级降级：标准字段 → repeat_penalty → 全剥。`_WRITABLE`/`_SAMPLING_DEFAULT_KEYS` 移除 repeat_*（降为纯内部后备，保留在 DEFAULTS 供 `_swap_to_repeat` 用）。
- `director.py`：新增 `detect_narrative_repeat()` 导演层叙事去重——三重检测（8-gram 重叠率>0.2 抓整段复读 + 30 字公共子串抓局部复读 + 前半/后半自重复检测），完全与后端采样参数解耦。
- `app.py`：`act()` 生成完成后、落盘前检测复读，命中即降温度重生成（最多 1 次），前端发 `regenerate` 状态清空重收。
- `prompter.py`：铁律⑨ 注入「避免机械重复」软约束。
- `static/index.html`：采样栏 `repeat_penalty`/`repeat_last_n` 两个输入框 → 单个「重复度惩罚」滑杆（0~2 step 0.05，默认 0.3，拖动实时显示数值），映射 `frequency_penalty`。
- `package.py`：config 洗白白名单从 repeat_* 改为 frequency/presence_penalty，遇旧 config 残留的 repeat_* 一律剔除。
- `tests/test_llm_repeat_penalty.py`：重写为新契约（27 用例）——标准字段优先、repeat_* 不再落盘、三级降级协商。

### 设计决定
- **不「识别后端类型」**，用「协商重试」取代识别：`/v1/models` 不返回后端身份、ninfer 会静默吞未知字段，靠探测不可靠；「先发通用字段、被 4xx 就换专用字段」更稳，天然完成参数名自动映射。
- 泛用性优先：单靠采样参数无法跨后端统一（repeat_penalty 是 llama.cpp 私有、frequency/presence 是 OpenAI 标准），故三层防御——参数协商（覆盖大多数后端）+ 导演层去重（完全解耦，任何后端都有效）+ 提示词软约束（兜底）。
- UI 单一「重复度惩罚」语义映射 frequency_penalty（simon 选定）：用户零理解门槛，引擎内部保留 repeat_* 作协商后备。

### 版本
- v0.27.0 → **v0.28.0**（MINOR，新增三层防复读能力 + UI 收敛）。
- 校验：全量 `pytest tests/` **302 passed / 1 skipped**；检测函数对真实会话 87e4ac46 复读数据 100% 命中（含人工漏看的 71 字跨轮重复）、正常数据不误判、性能 0.8-2.2ms；实机端到端 frequency_penalty=0.3 被 ninfer 接受、流式正常。

### 遗留 / 后续
- 导演层去重的重试上限固定 1 次、降温度系数 0.5、阈值 0.2（8-gram）/ 30 字（公共子串）为初版经验值，可在真实剧本长跑中按误判/漏检比例再调。


## 2026-10-11 v0.27.0 移除 LLM 降级（fallback）机制 + top_k 出厂默认 40→20

**性质**：能力移除（MINOR，机制层——移除 v0.21.0 引入的「主配置失败自动降级到 fallback」韧性机制，并把 top_k 出厂默认从 40 下调到 20；涉及 llm/app 前端无改动，动引擎机制设定）。

### 改动
- `llm.py`：删除 `_fallback_config()`、`_chain_configs()`；`stream()`/`complete()` 改为**只打主配置一次**，失败即抛异常，不再回落到 config 里的 fallback 段（约 19 增 / 86 删）。`_stream_once`/`_complete_once` docstring 同步去除「由 … 决定是否降级」措辞。
- `llm.py` `DEFAULTS`：`top_k: 40 → 20`——ninfer(KVMem) 只接受 top_k ∈ [0,20]，40 会被 400 拒绝（旧版会触发 fallback 降级并掩盖真实报错）。20 对 llama.cpp 等后端同样安全，且与 ninfer 上限对齐。
- `tests/test_llm_fallback.py` → 删除；新建 `tests/test_llm_primary_only.py`（4 个守护用例，故意在 config 里留 fallback 段，验证引擎已不再回落它）。
- `package.py`：洗白 config 时对 `cfg.get("fallback")` 残留段的清空逻辑保留为**防御性洗白**（升级用户旧 config 可能残留含本地 gguf 路径的 fallback 段），注释更新说明其定位。
- `data/config.json`：删除已死的 `fallback` 段（私人有 assume-unchanged，不入库）。

### 背景
- 触发：用户选本地 ninfer(1235) 后报错却指向 1234。根因链——主配置 ninfer 因 top_k=40 被 400 拒绝 → `stream()` 判定「产出首块前失败」自动降级到 fallback(1234, llama.cpp 未起) → 1234 连接拒绝 → `last_exc` 落在 1234 报错上，把 ninfer 真实的 400 盖掉。用户看到的 1234 是**降级目标**的报错，不是所选 provider 的真实报错。
- 决策（simon 拍板）：彻底移除主路径自动降级，让所选 provider 的报错原样浮现、绝不被掩盖。代价是失去「主 LLM 挂了自动切备用」的韧性（v0.21.0 的 MINOR 特性）——用户环境里 fallback 本就是常关的本地模型，兜底价值有限。

### 设计决定
- 「所选 provider 报错 = 真实报错」优先于「主挂自动兜底」的韧性：报错可见性是排障前提，掩盖真实报错的降级弊大于利。移除 `_chain_configs` 后 `stream()`/`complete()` 语义回到「单后端、失败即抛」。
- top_k 出厂默认对齐 ninfer 上限（20），而非为特定后端做角色/参数特化——20 是 ninfer 的硬上限，llama.cpp 无此限制，取交集的安全值。

### 版本
- v0.26.0 → **v0.27.0**（MINOR，移除 fallback 降级能力 + 调整 top_k 出厂默认）。
- 校验：全量 `pytest tests/` **296 passed / 1 skipped**；新增守护用例 `test_llm_primary_only.py`（4 条）验证引擎不再回落 fallback。
- 实机探针：ninfer(1235) 以 top_k=20 发完整 payload 全链路 200，content 正常返回；top_k=40 则 400「top_k must be in [0,20]」复现。移除 fallback 后，此类 400 会直接暴露而非被降级目标掩盖。

### 遗留 / 后续
- 失去「主 LLM 宕机自动切备用」韧性：若日后需要，可另行设计「仅可用性故障才降级 + 暴露主错误」的折中方案（本次未做）。
- 本次为机制级改动，按项目规约属压测候选；因移除的是异常降级路径、正常生成链路不变，未强制跑 30 轮（待 simon 定夺）。


## 2026-10-10 v0.26.0 秘密状态四态化（潜伏/起疑/暴露/已公开）+ 自述/承认纳入 via

**性质**：新增能力（MINOR，机制层——秘密状态机从二态细化到四态，并扩 via 语义；涉及 director/memory/prompter/ending/app 与前端，动引擎机制设定）。

### 改动
- `director.py` `_secret_state(s, present=None)`：二态（暴露/潜伏，仅看 holders）改为**四态**推定，优先级 已公开 > 暴露 > 起疑 > 潜伏。
  - 已公开：`s["public"]` 置位**且众人皆知**（在场非归属者全部已知情）。
  - 暴露（仍为把柄）：有人确已知情（known_by 非空）。
  - 起疑：无知情者、但有非归属者起疑。
  - 潜伏：无知情、无起疑。
  - 无在场名单（离线/单测）时退化为只看 `public` 标志。
- `director.py` `EXPOSURE_VIA_WHITELIST` 扩为六类：新增「自述」「承认」；新增 `SELF_DISCLOSURE_VIA = ("自述", "承认")`。
- `director.py` `_record_exposure`：按 via 分流——他人获取类（看见/听见/被告知/发现物证）入 known_by + holders（把柄入手 -> 暴露）；归属者自述类只入 known_by、清空 holders、置 public（把柄作废）。
- `director.py` `_record_suspicion` / `_clear_suspicion` / `_release_handle`：变更后重算状态（起疑态可显示；把柄清空不再回落「潜伏」）。三者与 `_secret_state` 均新增可选 `present` 参数，reflect 各调用点透传 `snap["present"]`。
- `director.py` reflect 提示词：曝光 via 枚举补「自述/承认」，并新增一条规则说明——自述/承认专指**归属者本人**当众说开（他人转述不算），用于本人真的说开的轮次。
- `memory.py`：秘密初始化补 `public: False`；`load()` 迁移——历史字面量「全曝光」归一为「已公开」，补 `public` 缺省（不重算，避免 memory 反向依赖 director 造成循环导入）。
- `prompter.py`：发酵压力守卫由「非潜伏即停压」改为「非（潜伏/起疑）即停压」——起疑是中间态，仍须发酵；归属者提示词新增「已公开」分支（掩饰/否认不再可信，须直面后果）。
- `ending.py`：终局「秘密全曝光」判定由「非潜伏」改为「state ∈ {暴露, 已公开, 全曝光}」——起疑不算揭开，不触发终局。
- `app.py`：运行日志「已暴露秘密」计数改为只数 {暴露, 已公开, 全曝光}。
- `static/index.html`：四态样式映射（潜伏=灰/起疑=暗赭/暴露=赭石/已公开=朱砂），补 `.sec-state.suspicious` 样式。

### 背景
- 触发：20 轮铁律验证 + 6 轮聚焦探针（`tests/_tmp_demo_expose_probe.py`）证实——归属者**当众亲口承认**全部秘密后，旧二态因 holders 清空而回落显示「潜伏」，把「天下皆知」显示成「无人知晓」，且 known_by 不更新。根因：`_secret_state` 只看 holders（把柄），且 via 白名单不含「自述/承认」，本人自述被当作把柄释放。
- 二次发现（定义层护栏的由来）：加固前探针 R2（第三方**当众指控**、归属者**矢口否认**）被模型错填 via=自述类，导致提前置「已公开」——这是「误记」（违反「宁可漏记不可误记」红线）。故对「已公开」加第二重客观条件**众人皆知**：模型即便错填 via，只要仍有在场者不知情就落回「暴露」，不会被误判公开。

### 设计决定
- 「已公开」= public 标志 **且** 众人皆知（双条件）。单靠模型填的 via 不足以防误标，故用客观的「在场非归属者是否都知情」兜底（引擎侧结构判定，不引入题材语义词表，仍守记录员模式）。
- 「暴露」保留「已知情即算」语义：holders 清空但 known_by 非空时落「暴露」而非「已公开」——信息不可逆（不回落潜伏），但未众人皆知不算公开。

### 版本
- v0.25.0 → **v0.26.0**（MINOR，新增秘密状态维度与 via 语义）。
- 校验：全量 `299 passed / 1 skipped / 1 deselected`；新增/更新单测 `test_director.py`（四态推定、public 须众人皆知、自述分流、把柄清空落暴露）、`test_pressure_force.py`（起疑仍发酵/仍占强制名额）。机制设定级改动，按项目规约属压测候选（待 simon 定夺是否跑 30 轮）。
- 实机验证（6 轮聚焦探针 `tests/_tmp_demo_expose_probe.py`，本地 27B）：前置 R1-R5（第三方指控/众人围观物证）全程正确停在「起疑」，无提前判公开；R6 归属者当众自述（纪官填 via=自述，证据为其本人口述原话）→ 秦伯 `已公开`、`public=True`、`known_by=[苏莉,阿豪,宋师傅]`（全体在场）、`holders=[]`、账本写 3 条。加固前同场景 R2（第三方指控+矢口否认）曾被误标「已公开」，加固后不再复现。

### 遗留发现（待 simon 定夺，本轮未改）
- 语义护栏二 `_evidence_transfer` 要求证据片段内含 by 或 owner 名字；当「物证被众人当众看清」这类**场景描述型证据不含角色名**时会被降级为起疑，导致真实暴露被漏记（探针 R4/R5 复现）。与本版四态无关，属既有护栏的已知副作用。


## 2026-10-10 v0.25.0 新增「创建剧本指南」（引擎机制与题材适配引导）

**性质**：新增能力（MINOR，纯文档——新增一份面向创作者的机制层引导页，不动引擎机制、不动运行逻辑）。

### 改动
- `engine/static/script-guide.html`（新建）：「创建剧本指南」预渲染静态页，零 JS 依赖。九节：①引擎给什么体验（外部导演 / 多角色群像 / 看博弈）；②五大机制（关系簿记 / 秘密簿记 / 世界书 / 导演指令 / 设计红线「无主角·缠斗最大化·爽点落小事·终局悬置」）；③最适合的剧本（长时同域群像 / 强关系网+秘密 / 资源利益冲突 / 多方不稳定同盟 / 悬疑真相揭开）；④兼容度差的剧本（升级养成流 / 强规则数值战斗 / 黑箱系统题材 / 单一主角强叙事，逐条说明错位原因）；⑤好剧本该喂什么（角色卡字段齐 / 世界书分层 / 结构三件事：多方冲突诉求、不稳定同盟、2-3 条互牵的秘密）；⑥以随包示例《困守一栋楼》逐条拆解 + 反例；⑦常见误区；⑧动笔前自检清单；⑨机制→喂料速查表。
- `app.py`：新增 `@app.get("/docs/script-guide")` → 返回 `script-guide.html`，与既有 `/docs/worldbook`、`/docs/script-example` 同模式。
- `static/index.html`「系统设置 → 帮助与文档」：新增「打开创建剧本指南（新窗口）」入口；三份文档按「动笔前（指南）→ 写文本（范例）→ 配世界书（说明）」递进重排，各加一句指引话术。

### 背景
- 触发：讨论「修仙元素能否用于引擎」时暴露盲区——用户缺少「引擎机制与题材适配」层的引导，不知道这引擎适合 / 不适合什么题材、好剧本该提供哪些设定。既有两份文档分别只覆盖「世界书怎么配」与「文本怎么写给提炼器」，缺最上层的「选题与结构」引导。
- 定位：本篇是**机制层**引导（区别于范例指南的格式层），直接回应「修仙等题材该不该做、怎么做」——明确「修仙可做但要做成宗门群像/权谋而非升级爽文」，并把「升级流/黑箱题材与引擎机制错位」讲透。
- 合规：内容零具体私人剧本设定，示例全部指向随包官方 demo《困守一栋楼》（`data/examples/`，合法白名单）与通用题材类型；兼容差举例用「升级流/商战/金融/律政」等通用题材类型，不点名具体私人角色。

### 版本
- v0.24.3 → **v0.25.0**（MINOR，新增用户文档能力）。
- 校验：全量 290 passed / 1 skipped / 1 deselected；`tests/test_frontend_binding.py` 4 passed（node DOM 沙箱）；普适性红线 `tests/test_universality.py` 守住（初稿把「避难所」当「贴近常识」举例命中题材词黑名单，已改「医药」）。纯文档，不触发压测。
- 打包：`script-guide.html` 走 `package.py` 的 `os.walk(ENGINE)` 自动随包，无需改打包脚本（非排除项）。

## 2026-10-10 v0.24.3 结束剧本：二次确认 + 开新局清主对话区

**性质**：错误修正（PATCH，前端交互与残留缺陷，纯 `static/index.html`，不动引擎机制）。

### 改动
- `static/index.html` `endSession()`：加二次 `confirm`。顶栏「结束剧本」`#open-end` 与结局横幅「结束」`#eb-end` 共用此入口，原为直接触发——玩家误触即生成总结并终结会话，现须确认后方可执行。
- `static/index.html` `startSession()`：开新局时补 `log.innerHTML = ''`。原只清右栏运行时日志 `lwBody`，漏清主对话区 `#log`。

### 背景
- 误触防护：「结束剧本」是不可撤销的重操作（终结会话），单点确认缺失，易误触。
- 残留历史会话根因：结束剧本 / 放弃会话退回开场后，上一轮对话气泡仍挂在 `#log`；玩家点新剧本进入主界面即看到这些残留，**误以为引擎自动加载了已删会话的前/后一轮内容**（实为 DOM 残留，非自动加载）。开新局同步清空 `#log` 根治。
- 边界：`startSession()` 本就是「开新局」唯一入口（顶栏「开启一个世界」），在此清空对任何来源进入新局都生效；不触及主流程禁区（`send()`/`#start.onclick`/Enter/`cfgProviders` 等）。

### 版本
- v0.24.2 → **v0.24.3**（PATCH，错误修正：结束剧本二次确认 + 开新局清主对话区）。
- 校验：`tests/test_frontend_binding.py` 4 passed。纯前端交互修正，不触发压测。

## 2026-10-09 v0.24.2 亲密描写标准：时机层归一（铁律⑧ 担触发，标准条回归纯写法）

**性质**：错误修正（PATCH，纯提示词措辞——把「何时写/未到位不硬写」的时机判定职责从亲密描写标准条移交给铁律⑧，消除两者在时机层重叠约束，让标准条回归纯写法技法、非亲密轮不再空耗）。

### 改动
- `prompter.py` `_LAW8_DEFAULT`：在「不预设上限，也不强制克制」之后、「硬红线」之前，插入时机层反向约束——「叙事尚未推进到亲密时刻前，不得为追求亲密而提前引入或硬写此类内容」。铁律⑧ 由此独占时机层，形成完整时机链：**到了→放开写实 → 没到→别硬写 → 未成年硬红线**。
- `store.py` `_STANDARD_ENTRY_CONTENT`：标准条由**七分层收敛为六分层**——删掉原「一、何时写」整层（触发判定已移交铁律⑧），标题首行加「非亲密戏时直接跳过」作轻量提醒（不承担判定），剩余六层（写多实/怎么落笔/心理怎么带/节奏/处境锚点/如何收束）重新编号 一→六。六层正文逐字不变，只动了标题与删层、改编号。
- `store.py` 标准条注释块：同步更新分层数（七→六）与各层号（第三/五→第二/四），并补一段「时机层职责已移交铁律⑧」说明。
- `tests/test_intimacy_scale.py`：新增 `test_law_has_timing_constraint`（锁铁律⑧ 时机句存在）。
- `tests/test_standard_entry.py`：技法方向断言删「何时写/未到位就不要硬写」两段、各层注释重新编号；分层编号函数由 `has_seven_numbered_layers` 改 `has_six_numbered_layers`（六层 + 断言「一、何时写」不在、`非亲密戏时直接跳过` 在）；顶部契约 docstring 同步。

### 背景
- 触发：「写作要求冗余/冲突体检（C）」发现真冲突嫌疑——铁律⑧ 只有「到位就放开写实」（尺度层单向），缺「没到位别写」（时机层反向）；而标准条一「未到位就不要硬写」是常驻约束（`constant=true` 落末尾 user 消息）。两者在**非临界轮**（性未触发的轮次）叠加：⑧ 常驻 system 中段留「该往亲密放开写」的暗示，标准条又常驻末尾，模型把字数预算花在亲密权衡上，挤压处境铺陈——A/B 实测 S1/S2 非临界轮处境锚点下降的机制嫌疑之一。
- 修法取舍：simon 拍板「修改条目内容」路线——不另立新条、不动铁律⑧ 尺度层，而是把触发判定职责**归一给铁律⑧**（它在 system 段、本就是常驻护栏，担触发更顺位），标准条退成纯写法技法、标题用一句话提醒「非亲密戏跳过」。语义微变：原「何时写」含正向门槛「张力真正到位才写」，现由铁律⑧「当叙事推进到亲密场景时」隐含承担。属纯提示词措辞，**不改引擎机制设定→不触发压测**。

### 版本
- v0.24.1 → **v0.24.2**（PATCH，错误修正：亲密描写标准时机层归一）。
- 校验：`tests/test_standard_entry.py` 13 passed、`tests/test_intimacy_scale.py` 8 passed（含新断言）；全量 290 passed / 1 skipped / 1 deselected。普适性红线守住（标准条新 content 纯中性，`test_standard_entry_lore_neutral` 通过；无字数/频率/阶段配额）。
- 影响面：`data/worlds/` 下既有世界（私人剧本）与 `data/examples/`（随包 demo）的标准条为磁盘独立副本，本改只动引擎出厂模板 `_STANDARD_ENTRY_CONTENT`，对已有世界不回填（`save_world` 只对「首次创建」播种）——simon 手动管既有剧本，与本次一致。

## 2026-10-09 v0.24.1 临时角色（aux 群演）死亡/退场注销机制

**性质**：错误修正（PATCH，补齐临时角色退场后未从「世界状态·在场角色」注销的结构性缺失）。

### 改动
- `director.py`：纪官 prompt 新增 `aux_departures` 上报通道（JSON 模板 + 规则）。语义判断已登记群演的**永久性退场**（死亡/被带走/彻底逃离队伍，再也不会回到当前场景）；只填已登记群演，正式登场角色进出仍归场景导演 `scene.apply` 的 `leave`/`arrive` 管。
- `director.py` `reflect()`：消费 `aux_departures`，核验名字确在册 + 非正式角色/不在场后，把对应 aux 的 `status` 置「已退场」并记退场原因（`note`），同步 `pop` 掉该群演在 `snap["goals"]` 里的短期目标（死者目标不再挂到换场景才清空）。**保留条目不删**——同一人物若重新出场不会因条目缺失被当全新人物重复登记（`register_aux` 的 `exclude` 含已退场名，天然去重）。
- `director.py` `reflect(sid, reply, directive="")`：新增 `directive` 参数（默认空，向后兼容）。prompt 构造在指令非空时增一行「本轮导演指令（玩家设定，权威，正文与其冲突时以指令为准）」；自然推演轮零 token 增量。
- `director.py` `aux_departures` 规则三条线索对账：①本轮叙事刚发生的退场；②「既有位置」里已标明永久退场态但 aux 仍挂〔活跃〕的**存量漏报**（退场那一轮没赶上、之后追不上的场景，本轮补报）；③本轮**导演指令**里明确说某群演死亡/被带走/彻底消失（即便正文弱化成「跑了」、既有位置仍停旧地也按指令注销）。边界措辞：「判断依据是**会不会再回来**，不是**有没有离开原位**」，防止把「翻窗逃到隔壁」误判成死亡。
- `director.py`：回喂纪官的群演名单对已退场者标注〔已退场〕，防重复判断。
- `app.py`：`/api/act` 的 `reflect` 调用点改为 `director.reflect(sid, full, directive)`（`directive` 在该路由作用域内）。
- `static/index.html`：世界状态面板在场列表把 `status === '已退场'` 的 aux chip 过滤掉（原只 `filter(a && a.name)` 不看 status）。

### 背景
- 根因：正式角色离场走 `scene.apply` 的 `leave`（从 `snap["present"]` 移除，前端不显示）；临时角色 aux 由 `register_aux()` 登记时写死 `status="活跃"` 后，全代码库再无任何路径更新它——退场/死亡无上报通道，前端只看名字不看 status，故死亡群演 chip 永不消失。本次补齐「对称注销通道」。
- 附带发现并修复：`snap["goals"]` 只增不删，死者短期目标残留（同属「注销缺失」，退场时一并 `pop`）。

### 版本
- v0.24.0 → **v0.24.1**（PATCH，错误修正：补齐临时角色退场注销 + goals 跟随清理 + 导演指令通道）。
- 校验：aux / reflect / director / 前端绑定 4 套共 75 passed；`director.py`/`app.py` 语法 OK；新参带默认值，全仓仅 `app.py` 调用点与 `reflect` 定义两处引用，无其它调用点受影响。临时验证脚本（正文退场 + 指令退场两通道 + goals 跟随 + 幂等 + 非群演边界 + 前端过滤）5 用例全绿后已删除，不入库。

## 2026-10-09 v0.24.0 采样参数：出厂默认上调 + 新增「恢复默认」按钮

**性质**：新增能力（MINOR，前端可一键恢复出厂采样参数；同时把出厂默认 temperature 上调至 1.0）。

### 改动
- `llm.py`：`DEFAULTS["temperature"]` 由 0.85 上调至 **1.0**（simon 当前满意的采样值）。对比现有 config，其余 6 项采样参数（top_p/top_k/min_p/max_tokens/repeat_penalty/repeat_last_n）本就与 DEFAULTS 一致，故出厂默认与 simon 现用值完全对齐。
- `llm.py`：`config_view()` 新增下发 `sampling_defaults`（`_SAMPLING_DEFAULT_KEYS` 7 项的纯 `DEFAULTS` 出厂值，**不被 file 覆盖**），供前端「恢复默认」一键回填，避免前端硬编码出厂值（守「采样参数真值一律从 llm.DEFAULTS 取」红线）。
- `static/index.html`：采样参数面板底部新增「恢复默认采样参数」按钮（`#cfg-sampling-reset`）；点击回填 `/api/config` 下发的 `sampling_defaults` 到 7 个输入框（仅改输入框，仍需点「保存」落盘），带状态提示与无默认值兜底。

### 版本
- v0.23.0 → **v0.24.0**（MINOR，新增「恢复默认」能力 + 出厂默认 temperature 上调）。
- 校验：后端 `config_view()` 下发 `sampling_defaults` 7 项齐全、`DEFAULTS.temperature`/`setting('temperature')` 均为 1.0；前端 `tests/test_frontend_binding.py` 4 passed（node DOM 沙箱走通新按钮绑定链路）。

## 2026-10-08 v0.23.0 会话存储只保留最新 10 条，超出自动清理

**性质**：新增能力（MINOR，会话存储保留策略 + 测试隔离封堵）。

### 改动
- `memory.py` 新增 `MAX_KEPT_SESSIONS = 10` 与 `prune_sessions(max_keep=10)`：按会话目录 mtime 降序，保留最新 `max_keep` 个**有效会话**（须含 `snapshot.json`，与 `list_sessions` 同口径）；超出者整目录删除，无 `snapshot.json` 的半成品目录不计入保留名额、一并清掉。返回删除数。
- `app.py` 的 `/api/session/new` 路由在新建会话成功后调用 `prune_sessions`——仅真实开新局时触发清理。
- `tests/conftest.py` 新增 autouse fixture：用 monkeypatch 把 `memory.SESS_DIR` 重定向到每测试独立临时目录，所有走会话创建/路由的测试在隔离目录自洽，永不触碰真实 `data/sessions`。

### 事故与教训
开发中曾误将清理逻辑放到未隔离存储目录的测试会触发的路由上，跑测试时把真实 `data/sessions` 误删（134 → 10）。已用 conftest 统一隔离封堵，并沉淀规约：**任何会动真实数据目录的引擎逻辑，测试必须隔离该目录。**

### 版本
- v0.22.0 → **v0.23.0**（MINOR，新增会话保留策略 + 测试隔离机制）。
- 校验：完整套件 288 passed / 1 skipped / 1 deselected；真实 `data/sessions` 在测试运行中保持稳定。

## 2026-10-08 v0.22.0 前端整体重构为「手账暖纸 + 水墨」风格

**性质**：前端视觉层整体重构（MINOR，用户可见的显著样式能力落地）。

### 改动

- **色板整体换暖纸/水墨**：`:root` 21 变量全部重设——宣纸底 `#f3ead4`、浓墨 `#36322a`、朱砂印章红 `#b0522f`、暖纸缝 `#e2d7b9` 等。
- **body 背景叠 6 层**：内联 SVG 水墨枝影插画（data URI，离线零 CDN）+ 3 角落水墨晕染 + 2 道纸纤维细纹，`background-attachment:fixed` 铺满。
- **字体栈改楷体优先**：Xingkai SC / Kaiti / STKaiti… 回退无衬线。
- **`</style>` 前追加装饰层**：纸片纹理、半透明和纸胶带（卡片/弹窗顶 + 面板左上，已处理 `overflow` 裁切）、品牌标题朱砂印章感、主按钮墨刷、对话便签气泡（角色左折角 / 用户右折角）、暖纸滚动条、手绘不对称圆角。
- **约束**：纯样式层，零 DOM/JS 改动，不删任何既有代码块，主流程禁区原封不动。

### 附带修正

- **临时群演 chip 蓝色被暖色覆盖**：装饰块里 `.chip{ background:var(--accent-soft)…}`（暖色，行号更晚）按 CSS 同优先级「后定义覆盖先定义」盖住了原始 `.chip-aux`（蓝色）。修复：在装饰块 `.chip` 之后补一条同值 `.chip-aux`（蓝 `#e3edf7` / 字 `#2f5d8a` / 边 `#c6dcee`），恢复「粉色=剧本角色、蓝色=临时群演」的区分。
- 此为本轮踩坑记录：**追加样式块给某选择器改 background 时，须 grep 该选择器的所有派生类（`.chip-aux` 等）确认未被连带覆盖**。

### 验证

- 备份 `backup/index.html.bak_20261008_224513`。
- `tests/test_frontend_binding.py` 4 passed（含 node DOM 沙箱层）。
- `app.test_client()` 首页 200，新样式标记（楷体字栈/水墨 SVG/胶带/朱砂印章/暖纸底）全部命中。

### 版本号

- v0.21.2 → **v0.22.0**（MINOR，前端视觉能力重构）。

---

## 2026-10-08 出厂标准条 A/B 实测定论：性行为场景激活后叙事质量无下降

**性质**：纯验证，零代码改动，**不占版本号**（版本号只记可观察的引擎行为变更）。

### 结论

**性行为场景激活「亲密描写标准」世界书条目后，叙事质量无下降。**该条目的两项能力
（第一层「未到位就不要硬写」守边界、第三至七层的写法规格）在实测中**同向生效**，
不存在「写出具体描写就牺牲处境密度」这类取舍。

### 设计定位（simon 拍板定论，勿再动）

标准条是**「叙事自然推进到那一步时，才按它执行」的写法规格，判权在模型手里**。
七分层写的是「写的时候要怎样」，判「什么时候该写」由第一层承担，靠模型读到后
**自行压制**生效——不是任何外部信号告诉它「现在可以写了」。

- **不做自动触发器**：改成引擎判定「张力到位」再追加写法要求，与把尺度硬编码进
  引擎本体无区别；且「每回合都写、围着性打转」的真实成因是**判权被夺走**——
  引擎一旦每轮给出「张力到位」信号，模型就顺外部信号走而非顺剧情走，
  破坏剧本红线「无主角、缠斗最大化、禁一面倒」。
- **不做关键词触发**：「张力到位」是语义判断，词表匹配无效（同 2026-10-07 的坑）。

### 实测设计

3 个与现有剧本题材全错开的 demo（民国梨园 / 美国西部矿镇 / 当代医院急诊），
每个 1 个非亲密轮 + 2 个临界轮，共 18 次生成，A 组仅铁律⑧、B 组铁律⑧+标准条，
其余全固定，单次 `build_session` + `llm.complete` 不走 director 链路。

**临界场景（性行为已发生）A → B**：

| 指标 | A 基线 | B 实验 |
|---|---|---|
| 具体词（器官直呼） | 0.3 | **18.0** |
| 肉戏占比% | 1.4 | **16.2** |
| 处境锚点 | 14.0 | **25.7** |
| 第三方提及 | 1.0 | **3.0** |
| 事后收束信号 | 1.0 | **8.0** |
| 复读 / 心理直白化 | 0 / 0 | 0 / 0 |

写出具体描写的同一轮，处境锚点 +84%、第三方提及 +200%，**两者同升而非取舍**。
18 篇角色卡心理泄漏检测**全 0**。非亲密轮两组具体词均 0，**不越界**。

**唯一代价**：非临界轮处境密度降 30-36%（S1 31.7→22.3、S2 26.3→16.7）——
标准条在性描写未触发的轮属冗余约束，模型耗字数在内部权衡。但 S2 处境**占比**仅
35.9→29.7，说明留下的质量未降，掉的是重复铺陈。属常驻约束的设计代价，可接受。

### 方法论（此前两轮踩坑后确立，别再错）

- **评估必须两轴分开**：
  - *能力上限*——场景给到「已发生性行为」且写法要求满足，期望能写出具体描写（实测 18.0）；
  - *边界*——非亲密轮，期望不越界（实测 0 越界）。
  **非临界轮具体词为 0 属第一层在正确执行，不可当「标准条没用」的证据。**
- **具体度这层只能用云端模型测**：本地 Qwen3.8-27B（UD-Q4_K_M）42 次生成器官词全 0，
  按「触碰边缘 / 已解衣 / 事后三十秒」三档递增指令均 0，根因是模型自身收敛倾向，
  与场景指令到位与否、清洗器、铁律措辞、标准条内容四个干扰项均无关。
  故「具体度」相关 A/B 一律走矽基流动 `DeepSeek-V4-Flash`。
- **角色卡张力到位是必要条件不是充分条件**：写法要求给足、张力拉满，模型仍可能停在
  临界点前。角色卡须在 `core_desire`/`core_fear` 带身体张力层（写外部矛盾不算），
  且场景指令要落到「已解衣贴上/事后三十秒」这个程度。
- **算「具体词」只能用无歧义器官名词**：`合上/含住/咬住` 在非亲密语境是「门合上/咬住被角」，
  会让非亲密轮被误判成已写入（2026-10-08 首轮云端实测污染，已从词表剔除）。
- **肉戏占比 ≠ 坍缩指标**：坍缩形态是肉戏占比 >50% **且**处境锚点掉到个位数；
  16-25% 肉戏占比 + 处境锚点上升 = 健康具体。两者必须同看。
- **探针脚本结果一律写文件不 print**：被导入的探针模块会重包装 `sys.stdout`，
  旧 wrapper 被 GC 后连带关闭底层 buffer（I/O closed）。
- **改 dump 分隔符前先对齐**：云端 dump 用 `\n\n===== `、本地探针用 `\n=== `，
  复用检测脚本会静默输出空（看输出 0 行才发现）。

### 未做 / 遗留

- 本轮为 A/B 因果验证（prompt 固定、单一变量），**未走引擎完整链路、未做多轮会话**。
  多轮推进下模型能否自行稳定跨过临界点，未验。
- 3 个 demo 剧本与探针脚本（`tests/_probe3*.py`、`_ab_demos3/`）是**工作树产物**，
  按项目规约不入库、不进 zip；随本条目保留于工作树供后续复用。

---

## 2026-10-08 v0.21.2 采样加 min_p、温度下调 0.85：治长输出语义坍缩截断

- **背景**：v0.21.1 修了复读（`repeat_penalty`），但同一会话还暴露出**第二个独立退化**——
  正文「在词中间被硬截断」。本轮追查其根因并按 simon 指示加 `min_p`、下调温度。
- **截断根因（先逐项证伪引擎侧）**：
  - 非 `max_tokens`：截断样本 `completion_tokens` 仅 934 / 265 / 1220，≪ 4096。
  - 非上下文溢出：`n_ctx=131072` ≫ 14173。
  - 非引擎裁剪：`app.py` / `llm.py` 无任何长度裁剪逻辑；**`budget` 字段是死代码**
    （只在 `DEFAULTS` / `_WRITABLE` 出现，`payload` 从不读它）。
  - 非 socket timeout：`stream` 默认 180s 是「相邻 chunk 间隔」，流式持续吐字不触发。
  - 非并发抢占：`total_slots=1` 但引擎无多线程；非 stop 词残留（文本无 `<|im_end|>`）。
- **真凶（反直觉点）**：`finish_reason=stop` **是真的**——原生 `/completion` 端点显示
  `stop_type=eos`、token 远未用尽。**模型在语义退化后把 EOS 当成了自然收尾**。
  退化样本原文：「藏**不可掩盖不可逃避不可抵赖不可反驳不可质疑不可怀疑不可相信不可能存在
  不存在不应该发生不会重**」——「不可+动词」机械接龙。故「说 stop 却断在半句」不矛盾，
  而是同一退化的两种表现：**复读 = 卡在循环出不来；截断 = 退化后提前收尾**。
- **与复读的关系**：截断样本的**近似重复率全为 0**，两者无因果，是并列的退化路径。
  `repeat_penalty` 对语义级坍缩作用有限（退化 token 本身重复度不高，只在无意义接龙）。
- **复现率**：同 prompt 多次采样，截断 30%（3/10 流式+非流式）、1/6（原生端点）。
- **处理**（`engine/llm.py`）：
  - `DEFAULTS` 新增 `min_p: 0.02`（llama.cpp 自身缺省值）。`min_p` 是动态截断——
    只保留「概率 ≥ min_p × 最高概率」的候选，比固定 `top_p` 更抗长输出走神
    （`top_p` 是绝对阈值，遇分布尖锐的 token 序列会放行过多候选）。
  - `temperature` 出厂默认 0.9 → **0.85**（1.0 属高熵档，叙事类任务 0.85 更稳）。
  - `min_p` 与 `repeat_*` 同属 llama.cpp 扩展，共用「非中性才发 + 网关 4xx 剥离重试」机制。
  - **`_EXT_FIELDS` 提为模块级常量**，作为 4xx 剥离重试的**唯一**判据源——
    此前是散在两处的 `or` 条件，加扩展容易漏改一处。
- **顺带修两处配置健壮性缺陷**（本轮实测 config 里存在 `min_p: null` 时暴露）：
  - `setting()`：`null` 与「键缺失」同义才回退出厂默认。原实现只在键**缺失**时兜底，
    存了 `null` 会把 `None` 当有效值传下去。前端清空输入框给 `parseFloat('')=NaN`，
    落盘即 `null`——这条路径真实存在。
  - `save_config()`：数值转换改走 `_num()`，非法字符串（`float('abc')`）回落默认而非
    抛 ValueError 让整次保存 500。
- **前端**（`engine/static/index.html`）：采样参数栏重排为三行（`温度`/`top_p`/`min_p`，
  `top_k`/`max_tokens`/启用思考，`repeat_penalty`/`repeat_last_n`），新增 `#cfg-minp`，
  说明文案解释 `min_p` 抗走神与重复惩罚两组；温度回填 `?? 0.85`。
- **守护用例** `tests/test_llm_repeat_penalty.py` 8 → **16 条**（全量 275 → 288 passed）：
  新增 min_p 缺省发送 / 显式 0 不发 / 非法值回落 / 与 repeat_penalty 独立、
  `_strip_penalty` 剥净三类扩展、`_EXT_FIELDS` 集合锁定（防漏登记）、
  出厂默认锁定、min_p 持久化类型、`setting()` 的 null 兜底与回归、`save_config` 非法字符串容错。
  两条既有断言按行为变更更新（非迁就实现）：`test_neutral_penalty_not_sent` 原本断言
  `_penalty_params(1.0,256) == {}`，v0.21.2 起 min_p 默认会发，改为只断言惩罚两类字段缺席。
- **A/B 实测**（同 prompt，唯一变量为采样档，各 6 次）：
  - A 旧档 `t=1.0 / min_p=0`：截断 **1/6**，该次伴随重复率 12.4%。
  - B 新档 `t=0.85 / min_p=0.02`：截断 **0/6**，重复率最高 0.2%。
  - **样本量 n=6 太小、统计上不显著**：只能记录「未观察到恶化、观察到一次改善」，
    不作为「已验证有效」的依据。
- **实测踩坑（同一坑第二次，记录以免第三次）**：A/B 第一轮手拼 payload 漏了
  `enable_thinking=False` / `chat_template_kwargs`，Qwen3 进思考模式，reasoning 吃掉
  `max_tokens` → 两组都撞 `tokens=4096`，甚至出现「content 0 字但 tokens 4096」。
  那轮测的是「撞 token 上限」而非语义坍缩截断，**结论作废已重跑**。
  改为直接调 `llm._base_payload()` 保证与引擎逐字一致才有效。
  **规约：探针禁止手拼 payload，一律调引擎自己的 `_base_payload`。**
- **不动 prompt 层**：仍是采样层问题，加提示词解不了。
- **版本号**：v0.21.1 → **v0.21.2**（MINOR，新增 `min_p` 采样参数能力）。
  改的是 LLM 调用层，不动 director 推演 / 关系 / 秘密记账，非「引擎机制设定」级 → 不压测。
- **未做**：DRY（`dry_multiplier`，llama.cpp 专治重复的采样器，服务端当前 0.0 未启用）
  仍是未用手段，本轮只按 simon 指示验了 `min_p` + 温度。
- **打包连带修正（首包实测发现）**：`package.py` 原先只洗白连接信息，采样参数原样带出。
  因磁盘私人 config 存着 `temperature=1.0`，首包把 1.0 打进了分发包，而出厂默认已是 0.85
  ——**新装用户会拿到开发者的旧值**。已改为从 `llm.DEFAULTS` 取真值洗白
  （`importlib` 按文件加载，不 `import llm`，避免 requests 缺失时打包崩），
  覆盖 temperature / top_p / top_k / min_p / repeat_penalty / repeat_last_n / max_tokens；
  `null` 值一并剔除。**规约：打包脚本不得硬编码引擎默认值，一律从 DEFAULTS 取**，
  否则引擎调了默认值而打包没跟上，新装用户就静默拿到旧值。

---

## 2026-10-08 v0.21.1 重复惩罚进 payload：修长输出整段复读（simon 拍板）

- **问题**：会话 `606e6b9a` 最新一轮出现整段剧情重发——72 段里 P47–P71 是 P17–P41 的
  重发（23 段相似度 1.00 逐字相同，2 段 0.85/0.87），重复 1087 字 = 全文 **33%**。
- **排查结论（先排除引擎自身）**：
  - **不是 fallback 机制**（v0.21.0 刚加的）：当时 config 主配置与 fallback **完全相同**
    （均 `127.0.0.1:1234` 本地 27B），`_chain_configs` 的去重条件使其只发一次请求，
    走不到降级分支。流式链路（`app.py` events 逐块 yield → 前端逐字追加）亦无重复注入点。
  - **全库扫描**：所有会话中重复率 >15% 的回复仅 2 条（本条 33%、`a47526ae` #17 21%），
    均为本地 27B + 长输出 + 高熵参数，属低概率事件而非系统性 bug。
- **根因**：请求体**从未发送 `repeat_penalty`**。`llm.py` 原来只传 temperature / top_p /
  top_k / max_tokens，llama.cpp 因此吃服务端缺省 `repeat_penalty=1.0`（= 无惩罚）；
  而默认档 temperature=0.9~1.0 / top_k=40 属高熵，长输出到千字量级必然出现 n-gram 回卷。
- **对照实测**（重建该轮 prompt，22 段 / 14173 token，唯一变量为 repeat_penalty）：
  A 组不传 → 重复占比 **1.5%**；B 组 `repeat_penalty=1.1` → **0%**。
- **处理**（`engine/llm.py`）：
  - `DEFAULTS` 新增 `repeat_penalty=1.1`（保守档；过高会让用词僵硬、丧失随机性）、
    `repeat_last_n=256`（只惩罚最近 256 个 token，够覆盖复读场景，又不波及很早的剧情事实）。
  - 两者进 `_WRITABLE`，`save_config` 按 float / int 转换。
  - 抽 `_penalty_params()` / `_base_payload()` / `_strip_penalty()` 三个共用函数，
    `_stream_once` 与 `_complete_once` 复用同一 payload 构造（顺带消除两处重复的采样参数字面量）。
  - `stream()` / `complete()` 签名加 `repeat_penalty` / `repeat_last_n`（None → 回退 config）。
- **发送规则（可移植性）**：**仅当 `rp ≠ 1.0` 才发字段**——中性值与各后端缺省行为一致，
  发过去无增益，却可能被严格校验的 OpenAI 兼容网关（vLLM / DeepSeek 等）判未知参数而 400。
  `repeat_last_n=0` 时只发 `repeat_penalty`（范围交后端缺省）。
- **网关兜底**：若后端回 400/404/422 且 payload 带惩罚字段，自动剥离后**重试一次**——
  宁可退回该后端缺省惩罚，也不能让整轮生成失败。`getattr(resp,"status_code",200)` 兜底不可省：
  直接读 `resp.status_code` 会打破 `test_llm_fallback.py` 既有测试桩（桩对象无该属性）。
- **前端**（`engine/static/index.html`）：「采样参数」栏新增 `repeat_penalty`（step 0.05）、
  `repeat_last_n`（step 16）两个输入框 + 说明文案（1.0 = 不惩罚；调高减少复读但过高会僵硬；
  `repeat_last_n` 是作用范围，0 = 全部），回填 `?? 1.1` / `?? 256`，保存进 payload。
- **守护用例** `tests/test_llm_repeat_penalty.py`（8 条）：中性不发 / 显式发 / `rn=0` 省略 /
  非法值回落默认 / 网关 4xx 剥离重试 / 中性值下 4xx 不重试（不掩盖真实错误）/
  配置持久化类型 / 出厂默认保守。
- **不动 prompt 层**：这是**采样层**问题，加提示词解不了（呼应排查结论）。
- **验证**：全量 **275 passed, 1 skipped, 1 deselected**（267 → 275）；实机新进程（5051）
  页面两字段齐、config 默认 1.1/256、POST 保存回读类型正确、真实打本地 27B 生成正常无复读。
- **版本号**：v0.21.0 → **v0.21.1**（PATCH，修正引擎可观察行为：消除长输出复读）。
  改的是 LLM 调用层采样参数，不动 director 推演 / 关系 / 秘密记账，非「引擎机制设定」级 → 不压测。
- **遗留（本次未查）**：该轮输出结尾断在「林梦雅倒吸」且无句末标点，而输出仅 1734 token
  （远未及 `max_tokens=4096`）→ 生成被**硬截断**。引擎侧确认无任何长度截断逻辑，
  疑在 llama.cpp 服务端或上游连接层。与复读是两回事，待 simon 定是否追查。

---

## 2026-10-08 v0.21.0 LLM 后端降级（fallback）+ 前端提供商切换下拉框

### A. LLM 后端自动降级（新增能力 → MINOR）

- **背景**：线上主模型（矽基流动）偶发不可用，此前一旦主配置失败，整轮对话直接报错，
  玩家侧表现为「卡死/白屏」。本次让引擎在主配置**产出内容前**失败时自动切到本地兜底
  （如 llama.cpp:1234），已流出内容后失败则原样抛异常、绝不二次切换（避免文本重复）。
- **实现**（`engine/llm.py`）：
  - 新增 `_fallback_config()`：读 `config.json` 的 `fallback` 段（`base_url`/`api_key`/`model`），
    未配置或 `base_url` 为空返回 `None`（即「未启用降级」，行为与旧版完全一致，向后兼容）。
  - 新增 `_chain_configs(base_url, api_key, model)`：返回本次调用要依次尝试的候选序列。
    默认调用（未显式指定 `base_url`/`model`）→ `[主配置, fallback?]`；显式指定时 → 仅 `[主配置]`
    （尊重调用方意图，测试 / 指定 provider 不触发降级）。
  - 原 `stream`/`complete` 的请求体拆为 `_stream_once`/`_complete_once`（单次后端请求，失败抛异常），
    外层 `stream`/`complete` 变为「遍历候选 → 失败则降级重试」的编排层。
  - **关键安全点**：`stream` 里用 `produced` 标志位——一旦已 `yield` 过内容，后续异常直接 `raise`，
    绝不切后端（防止两后端各吐一半文本导致内容重复）。
- **配置**：`config.json` 新增可选 `fallback` 段。未配置时零影响；私人 config 仅留工作树，不提交/打包。
- **测试**：`tests/test_llm_fallback.py`（mock `requests.post`，自给自足、不碰磁盘/真实后端）覆盖：
  产出前失败→切兜底成功 / 主成功不触发 / 显式指定不降级 / 全失败抛最后异常 / `complete` 同路降级。
  全量 **267 passed, 1 skipped, 1 deselected**（deselected 为 integration marker，与本次无关）。
- **压测判定**：改的是 **LLM 调用层的容错**，未动 director 推演 / 关系 / 秘密记账等核心判定路径，
  不属「引擎机制设定」级改动 → 不跑 30 轮压测。

### B. 前端：LLM 提供商切换下拉框（纯 UI 优化，不升版本，随本版进包）

- **背景**：引擎早已支持保存多 LLM 提供商，但切换全靠展开卡片里的「应用为当前」按钮，
  不直观。本次在提供商清单上方的引导文字处新增一个**单选下拉框**（「引擎使用的 LLM」），
  选中后点「保存设置」即时生效；随后删除冗余的「应用为当前」按钮。
- **实现**（`engine/static/index.html`，纯前端，无后端改动）：
  - 新增 `#cfg-active-prov` 下拉框 + 引导文案「上方下拉框选择引擎当前使用的 LLM，保存后即时生效」。
  - 新增 `renderActiveSelect()`：用 `cfgProviders` 填充选项、选中值=`cfgActiveKey`，
    由 `renderProviders()` 调用，与卡片「当前」标记共用同一状态，二者自动同步。
  - 打开系统设置时按当前生效 `base_url` 反查所属提供商回填；`cfgActiveKey` 失效（被删）时落回首项兜底。
  - 删除「应用为当前」按钮三处（模板 `prov-f-apply`/`prov-actions`、事件委托 `act === 'apply'` 分支、
    专用 CSS `.prov-actions`），并把 4 处仍写「应用为当前」的注释同步改为下拉框口径。
    `si-apply`（剧本导入确认）与本按钮无关，未动。
- **验证**：`tests/test_frontend_binding.py`（含 node DOM 沙箱）4 通过；实机新进程（5051）确认
  新元素齐全、`prov-f-apply`/`应用为当前`/`prov-actions` 零残留、下拉框完好。
- **版本号**：属单点 UI 优化（错误修正/体验改进级），不单独升版本，随本次 v0.21.0 进包。

### 版本号

- v0.20.0 → **v0.21.0**：MINOR（新增 LLM 后端自动降级能力）。真相源 `engine/VERSION` 已改，
  `engine/README.md` 等引用按 SOP 同步。

---

## 2026-10-08 v0.20.0 补充四：出厂标准条模板由六分层升级为七分层强化版（simon 拍板）

- **背景**：simon 给出新版「本剧亲密与性描写标准」模板，要求变更**引擎侧出厂播种模板**
  （`store._STANDARD_ENTRY_CONTENT`）——已存在的剧本由 simon 手动改过，本次只改模板，
  供后续新建剧本作最新标准。
- **结构变化**（六分层 752 字 → **七分层**）：
  - 新增 **「七、如何收束」**：事后必须回到人物与处境，不悬在高潮余韵里；
    高潮不是终点，人物带着这场性回到原来的世界才是终点。
  - **三、怎么落笔**补了器官词**正反措辞示例**（禁「探到底」「彻底贯穿」式概括收尾，
    示范直呼其名：阴唇/阴蒂/阴茎/龟头/子宫口）。
  - **五、节奏**补了抽插**防复读反面示例**（「连续三次都在写他用力抽插、她叫出声」即失败）。
  - **六、不能丢的**显式命名「处境锚点」，四个锚点（可被听见/看见的风险、时间余地、
    最难逾越的界限、在场但未写的人）拆成独立 bullet。
  - **末端「未成年硬红线」从本条移除**：改由 prompter 铁律⑧ 恒定兜底（铁律⑧ 在 system
    块注入、本条在末尾 user 消息，二者并存、不互斥，法律底线不丢）。
- **为什么不重犯 v0.14.x**：本版引入的器官词与「抽插/高潮」都是**反面/示范用法**
  （禁概括、防重复充数），**不是**正向配额或阶段达成表；字数区间配额、每 N 字频率配额、
  前戏→…必达清单这三类真正诱发模型「为凑数而坍缩」的硬指标，本模板一个都没有。
  即 v0.14.x 的坍缩诱因（可计量的尺度硬指标）依然全部锁死，器官词只是「写法示范」。
- **name 保持不变**（仍为 `亲密描写标准`）：`_has_standard_entry` 按 name 判重，
  改名会让所有已有世界被判定「无标准条」从而重复播种。
- **守护用例同步**：`tests/test_standard_entry.py`
  - 契约 docstring 第 4 条改写：从「禁止器官词」改为「禁止数量配额/正向阶段达成表，
    器官词/抽插是技法示范不禁」；新增第 7 条（末端法律底线移交铁律⑧）。
  - `test_standard_entry_no_scale_presets`：删除器官词/「插入」/「抽插」/「高潮」的逐字
    禁令（与新版冲突），保留字数区间/每 N 字/「前戏」三类坍缩红线断言。
  - `test_standard_entry_keeps_core_technique_directions`：落笔「须」→「必须」、
    节奏断言改为「试探/失控」、新增第七层「如何收束/高潮不是终点」、新增第三层
    器官词示例（阴唇/阴蒂）断言；删除末端「未成年」断言。
  - `test_standard_entry_has_six_numbered_layers` → **`..._seven_...`**：六分层改七分层
    （含顺序校验），并新增「本条不得再含『硬红线』」断言（已移交铁律⑧）。
- **不动**：`prompter._LAW8_DEFAULT`（铁律⑧ 恒定措辞，simon 早已拍板永不再改）；
  随包 demo 世界书与 simon 已手动改过的剧本（用户主权，引擎不回填）。
- **验证**：`tests/test_standard_entry.py` 全绿（七分层 + 正反示例 + 法律底线移交），
  `test_universality.py`（引擎源码零角色名/题材词）、`test_store_cache.py`（播种/缓存失效）、
  `test_intimacy_scale.py`（铁律⑧ 措辞逐字绑定）全部通过；全量 **293 passed, 1 skipped**。
  未跑 30 轮压测：本次仅改世界书**模板字符串**（数据/提示词层），不动 director 推演/
  关系/秘密记账任何核心判定路径，不属「引擎机制设定」级改动。
- **版本号**：沿用 v0.20.0 的 tag（同「补充三」先例，内容修正随下次发版进包，不升版本）。

---

## 2026-10-08 v0.20.0 补充三：删除 md 版世界书指南孤儿文件

- **问题**（simon 指出）：`engine/worldbook-guide.md` 已是孤儿。v0.5.x 起文档改为**一次性预渲染**
  为 `static/worldbook-guide.html`（删 `marked.min.js`、去掉CDN 依赖），`/docs/worldbook`
  路由直接 `send_from_directory` 返回 html；前端只链该路由、从不链 .md。
  md 无任何读取方，却仍随分发包携带 30 KB，并与 html **双份独立维护**（改一处漏另一处
  的历史坑就是这么来的）。
- **处理**：删除 `engine/worldbook-guide.md`（已备份到 `backups/nsfw_wb_20261007/`），
  同步修正 5 处失效引用：
  - `engine/INSTALL.md`：故障排查条目「`/docs/worldbook` 打不开 → `worldbook-guide.md` 缺失」
    **本就是错的**（路由读的是 html），一并改为正确指向 `static/worldbook-guide.html`。
  - `engine/INSTALL.md` / `engine/README.md`：文档引用改指浏览器 `/docs/worldbook`。
  - `engine/README.md` 目录树：删除 md 条目，补上 `static/worldbook-guide.html`。
  - 根 `README.md`：目录树删除 md 条目，并**顺带删掉 `nsfw.py`**——该模块 v0.8.0 已删，
    目录树里却一直挂着，是另一处同源死引用。
  - `tests/test_universality.py` 注释里的文件名（仅注释，不影响断言）。
- **不动**：`DEVLOG.md` / `TODO.md` 中的历史记录（那是 v0.9.0 已完成事项的归档，
  改它等于篡改历史）。`package.py` 无需改（整目录打包，文件删了自然不进包）。
- **验证**：`py_compile` 通过；全量测试通过；`/docs/worldbook`、`/docs/script-example`
  两个路由的目标文件均存在。分发包实测：首页与两个文档路由全 HTTP 200，
  条目数 30→29、190.5 KB→177.7 KB。**不构成版本号变更**，沿用 v0.20.0 的 tag。

---

## 2026-10-08 v0.20.0 补充二：出厂标准条与作者尺度条融合为一条（simon 拍板）

- **背景**：实测中发现出厂「亲密描写标准」（417 字）与作者自写「本剧尺度」（268 字）
  **语义重叠**——逐主题比对 8 个语义主题，1 个完全重叠（落笔身体/不概括）、6 个互补、
  1 个独有（情话限量），合计 685 字里约两成冗余，且两者管的都是同一件事（NSFW 触发效果）。
  simon 拍板**融合为一条**，并要求：① 作者条不留，腾出配额空间；② 标准条 priority 不降、
  仍置top1（保证必须激活）；③ name 不改。
- **为何不改 name（技术理由）**：`store._has_standard_entry` 按 name 判重，改名会让
  **所有已有世界都被判定为「没有标准条」，从而重新播种一条**——用户自定义的同义条
  也会失效。
- **为何不是「治复读」**（数据反驳，记录以免后人重犯）：三次复读中**两次发生在
  「仅标准条、零作者条」配置下**（暑期寄住 B-R4 复读 5、深空 B-S1 复读 5），只有
  宫廷 C-S2（双条）复读 7。根因是**模型长输出末尾的句式回卷**（描写句/台词被写两遍），
  与冗余指令无关。故**不做去冗余化处理，保留全部有效要求**；融合的收益记在配额与简洁上。
- **融合版结构**（752 字，`一/二/三/四/五/六` + 末尾硬红线）：
  一、何时写（触发门槛，未到位不硬写）｜二、写多实（**作者条独有的「不省略/不收束」升格
  为独立层**）｜三、怎么落笔（落身体上、禁概括、禁代称）｜四、心理怎么带（走身体反应 +
  情话只补一句）｜五、节奏（递进 + 每次新信息 + 事前事后各一次 + 不得重复充数）｜
  六、不能丢的（锚定处境 + 在场第三方）。末尾补回未成年硬红线（初版刻意不重复铁律⑧，
  融合时带回；引擎侧多一道法律底线不违背普适性）。
- **分层编号是核心设计**：指令型长文本分条后模型逐条对照执行，且**不易漏掉末尾两条
  （处境锚定、群像在场）**——长 prompt 的常见失效点就是把末尾要求丢掉。
  治复读两处：「不要反复咀嚼」从末尾移进第五条（原本在末尾易被漏），与「不得靠重复充数」相邻。
- **落地**：`store._STANDARD_ENTRY_CONTENT` 换新；四份世界书（测试 demo + 暑期寄住+
  丧尸末日 ×2）删「本剧尺度」条并同步内容，**配额从 8/8 满额回到 7/8，腾出一席**。
- **验证**：`tests/test_standard_entry.py` 断言从「三条技法方向」扩为六层逐条 +
  新增 `test_standard_entry_has_six_numbered_layers`（含分层顺序断言），
  全量 **260 passed, 1 skipped**；端到端确认融合版全文落末尾 user 消息且不进 system 块。
  实测（宫廷 2 组 ×3 场景）**B-S2 为全部实验中最强一轮**：落地信号 **28**（此前最高 17）、
  处境锚定 **37**（此前最高 28）、**零复读**、器官词仅「插入/进入」各 1 次（正常动词用法）；
  结尾「把册子沉进废井——比烧更干净」+「若让第三个人知道，我会亲手杀了你」
  把处境与第三方风险都保住了，证明「六、不能丢的」那层真的生效。
- **踩坑**：批量改 JSON 时 `d['entries']=[...]` **必须写回 d**，否则改动只落在局部引用上
  （第一遍漏写导致宫廷的标准条被误删，已补回）。
- 未跑 30 轮压测：不动 director 推演/关系/秘密记账任何核心判定路径。**不升版本号**
  （v0.20.0 已 tag，内容修正随下次发版进包）。

---

- **问题**（simon 指出）：`engine/worldbook-guide.md` 已是孤儿。v0.5.x 起文档改为**一次性预渲染**
  为 `static/worldbook-guide.html`（删 `marked.min.js`、去掉 CDN 依赖），`/docs/worldbook`
  路由直接 `send_from_directory` 返回 html；前端只链该路由、从不链 .md。
  md 无任何读取方，却仍随分发包携带 30 KB，并与 html **双份独立维护**（改一处漏另一处
  的历史坑就是这么来的）。
- **处理**：删除 `engine/worldbook-guide.md`（已备份到 `backups/nsfw_wb_20261007/`），
  同步修正 5 处失效引用：
  - `engine/INSTALL.md`：故障排查条目「`/docs/worldbook` 打不开 → `worldbook-guide.md` 缺失」
    **本就是错的**（路由读的是 html），一并改为正确指向 `static/worldbook-guide.html`。
  - `engine/INSTALL.md` / `engine/README.md`：文档引用改指浏览器 `/docs/worldbook`。
  - `engine/README.md` 目录树：删除 md 条目，补上 `static/worldbook-guide.html`。
  - 根 `README.md`：目录树删除 md 条目，并**顺带删掉 `nsfw.py`**——该模块 v0.8.0 已删，
    目录树里却一直挂着，是另一处同源死引用。
  - `tests/test_universality.py` 注释里的文件名（仅注释，不影响断言）。
- **不动**：`DEVLOG.md` / `TODO.md` 中的历史记录（那是 v0.9.0 已完成事项的归档，
  改它等于篡改历史）。`package.py` 无需改（整目录打包，文件删了自然不进包）。
- **验证**：`py_compile` 通过；全量 **259 passed, 1 skipped**；
  `/docs/worldbook`、`/docs/script-example` 两个路由的目标文件均存在。
  本次为纯删除 + 文档引用修正，**不构成版本号变更**（引擎可观察行为未变、版本号真相源
  仍为 v0.20.0），故沿用 v0.20.0 的 tag，随下一次发版一并进入分发包。

---

## 2026-10-08 版本 v0.20.0（亲密描写标准出厂播种：尺度标准从铁律下沉到世界书）

- 版本判定 **MINOR**（v0.19.0 → v0.20.0）：新增「新建世界书自动播种出厂条目」这一对外可见行为（世界书默认内容改变），且新增 store 公开常量 `STANDARD_ENTRY_NAME`。
- **背景·simon 的判断**（先盘点、后拍板）：
  1. 盘点确认：NSFW 支持在提示词里**只有 1 处**——`prompter.py` 铁律⑧，157 字，恒定无条件注入，位于 system 块 **39%** 处、**其后压 748 字**才到生成点。周边只有间接项（铁律④ 亲密须留痕、输出纪律①⑤ 禁安全前言与自我审查、`narrative_clean` 两条规避句剥离正则），**没有任何按场景/关系变化的条件注入**。
  2. simon 提出一份「器官层具象 + 四阶段×150-250 字 + 感官五连 + 每 80-120 字必现体液更新」的加强提示词。**经历史实测数据否决**（见下）。
  3. simon 拍板：**铁律⑧ 不改**（已具普适性，只是力度不足）；**尺度标准下沉到世界书**；并进一步拍板**不做作者自取模板，而是固定为出厂播种条目、每个新世界默认自带且激活**（理由：它按情景生效、本就普适，不必担心破坏剧本走向）。
- **否决硬编码提示词的数据依据**（重新量化 `_nsfw_ab_result_v2.txt`，即 v0.14.x「露骨强推 + 小雨人格注入」组 vs 屏蔽组）：

  | 轮 | 字数 | 解剖词密度 | 处境词密度 | 12字复读片段 | 最长逐字重复 |
  |---|---|---|---|---|---|
  | A-R1 非亲密 | 2807 | 0.6% | 0.9% | 0 | 0 |
  | A-R2 升温 | 2106 | 0.0% | 1.4% | 0 | 0 |
  | A-R3 露骨 | 2417 | 1.4% | **0.5%（全组最低）** | **154** | **68 字** |
  | B-R1 屏蔽 | 1698 | 0.0% | 1.2% | 0 | 0 |
  | B-R2 屏蔽 | 1519 | 0.0% | **1.7%（全组最高）** | 0 | 0 |

  露骨档一开，处境密度掉到全场最低，且出现 68 字整段逐字复读（复读内容正是「扯皮带/褪裤子/没有前戏/猛地挺腰」连台词「太湿了。」原样重复两遍）。这就是 v0.15.0「越复杂越脆弱」的物理形态。逐条判定：①器官具象改造后可用（原示例给的是具体男根解剖名，违反普适性红线）②四阶段×字数配额有害（挤占群像 + 「高潮」必到 = 把 v0.7.8 已修的「机会等级只升不降」重新引入提示词层）③感官五连半有害（味/嗅是抽象标签，实测模型只会产出「淫靡/气息/在空气中」这类抽象词）④每 80-120 字必现更新最有害（唯一带确定性计数，模型数不过就重启同段 = 复读成因）⑤心理只通过生理表现可直接用 ⑥「为玩家提供」措辞错（玩家机制已下线）。
- **改动一·引擎**（`store.py`）：
  - 新增模块常量 `STANDARD_ENTRY_NAME` / `_STANDARD_ENTRY_CONTENT` / `_standard_entry()` / `_has_standard_entry()`。
  - `save_world`：**仅当该世界文件此前不存在**（首次创建）时，在条目数组**首位**插入标准条。用户主动删除后保存**不会复活**；自带同名条**不被覆盖**。存的是普通世界书条目，用户可改写、`enabled=false` 停用、或整条删除。
  - 置首位是**配额硬约束**所致：`world.scan` 按 priority 降序截断 `max_entries=8`，而前端 `collectWorldEntries` 保存时按**列表顺序**重算 priority（index 0 → 100）、完全不读文件里的 priority 字段。故放首位才能保证「每世界多一条 constant」不把该剧本自己的设定挤出注入配额。
  - `position: after` → 落**末尾 user 消息**（生成点前最后一瞥，近因权重最强），而非 system 块中段 39% 处。这是本次的**核心杠杆**。
- **改动二·引擎**（`prompter.py`）：把铁律拆成 `_LAWS_PREFIX` + `_LAW8_DEFAULT` 常量 + `_build_laws()`，并加 `_law8_override` / `_patch_laws()` 句柄。**生产恒为默认、逐字等价**（已验证 patch→None 后 prompt 与改动前完全一致），句柄仅供对照实测与将来的剧本级实验，**不构成对外可配置项**。
- **改动三·数据**：`data/worlds/暑期寄住.json`（合并「房子」+「小镇」两条常量为一条，为标准条腾出配额位——原 4 常量+4 触发=8/8 满额零丢弃，加第 5 条常量必挤掉 priority 最低的「手机」条；合并后总字数不变、零额外 token）、`data/worlds/丧尸末日.json` 与 `data/examples/worlds/丧尸末日.json` 均已播种。**注意官方 demo 世界书随包分发**，故标准条内容**全中性措辞**（无专名/无题材词/无器官词/无字数频率配额），并有守护用例锁死。
- **改动四·文档**：`worldbook-guide.md` 与 `static/worldbook-guide.html`（**两份独立维护**）各新增「九·五、出厂自带的亲密描写标准条目」一节 + 常见坑第 9 条（配额说明）。
- **验证**（本地 Qwen3.8-27B-UD-Q4_K_M @ llama.cpp:1234，temp=1.0/top_p=0.95/top_k=20）：
  - **三组对照 ×3 临界场景**（`tests/_probe3arm_nsfw.py`，单次 `llm.complete` 消除 director 随机调用噪声）：世界书条 vs 铁律⑧ 单独 vs硬编码进铁律⑧。指标（处境已扣除标准条自带词的**自证偏差**）：

    | 组 | 具体 | 代称 | 抽象 | 处境净增 | 第三方 | 复读 |
    |---|---|---|---|---|---|---|
    | 基线（仅铁律⑧） | 0/2/0 | 0/1/0 | 1/0/2 | 3/4/1 | 4/4/4 | 0 |
    | **世界书条** | 0/0/0 | 0/1/0 | 2/0/0 | 3/**11**/2 | 2/**10**/1 | 0 |
    | 硬编码 simon 原案 | 0/**8**/0 | 3/3/0 | 1/**4**/1 | 4/2/1 | 5/9/5 | 0 |

    结论：**世界书条是唯一把处境张力做实且不牺牲群像的**（处境净增 11 vs 4、第三方 10 vs 4，产出里第三方真实上楼站在门外听并默数日子的段落出现）；**硬编码只在「指令明写性」的窄区间生效**（另两轮具体词为 0），且抽象词翻 4 倍、正文暴涨 40%。后者是决定性反证：它要求玩家替引擎写黄文指令才生效。
  - 引擎链路 5 轮 ×2 组（`tests/_ab_nsfw_worldbook.py`，`app.test_client()` 进程内）：两组具体词全为 0——**指令未推到临界点，对照组设计失败**。教训：对照组必须设「扣自证词」的净增量指标，且场景指令须直接落在临界点。该轮另发现世界书条在 R4 出现复读（「你出汗了…我闻到了」×2、「你出去」×3，同轮基线为 0），据此 simon 追加「每一次推进须有新的具体信息」+「不得靠重复同一动作或同一句措辞充数」。
  - 端到端落点：新建世界的标准条确认进 `messages[-1]`（末尾 user 消息）而非 system 块。播种五边界（新建必播种 / 二次保存不重复 / 删除不复活 / 同名不覆盖 / 空世界也播种）全部实机通过。
  - **全量 259 passed, 1 skipped**（新增 `tests/test_standard_entry.py` 12 条；`test_store_cache.py` 的 `test_load_world_caches_and_invalidates` 原本断言 `load_world()[0]` 是用户内容，被播种行为打破——改为按内容定位用户那条，语义不变；`test_universality.py` 的 `ALLOW_FILES` 加入 `test_standard_entry.py`——该文件与 `test_intimacy_scale.py` 一样持有黑名单，属正当引用）。
  - `py_compile` 通过。**未跑 30 轮压测**：本轮不动 director 推演/关系/秘密记账任何核心判定路径（`world.scan`/`prompter` 组装/`store` 写盘三处均为既有机制内的接线），按压测触发规则（唯一判据=是否动引擎机制设定）不触发。
- **simon 决策留档**：① 铁律⑧ 保持不动 ② 出厂播种而非作者自取模板 ③ 收口提交打包。

---

## 2026-10-07 版本 v0.19.0（开场改为「先选世界」：按世界加载角色与世界书，取代按角色反查 world）

- 版本判定 **MINOR**（v0.18.6 → v0.19.0）：新增对外接口 `/api/characters/by-world`、
  新增两个 store 函数、`session_new` 开局契约新增 `world` 字段（向后兼容），属新增能力。
- **问题（simon 指出）**：开场界面用`/api/characters` 拉**全量角色**混在一张勾选列表里，
  世界归属只能靠引擎「取首个在场角色的 world」反推——多世界并存时会把不同世界的角色
  放进同一局，且玩家无从察觉。角色卡`world` 字段本就是它与世界书的唯一归属键，
  反推等于拿结果当输入。
- **改动·后端**：
  - `store.list_characters_by_world(world_name)`：按卡的 world 字段精确过滤；
    `store.unassigned_characters()`：world 为空或指向已删世界书的角色（**不静默丢弃**——
    否则玩家会以为角色凭空消失）。
  - `GET /api/characters/by-world?world=X` → `{names, unassigned}`，unassigned 与所选
    世界无关故一并返回，前端免二次请求。
  - `session_new` 的世界名改由前端显式传入，并加两条兜底校验：**世界必须存在**、
    **跨世界混场拦截并点名混入者**。刻意不做静默纠正——静默改写会让玩家以为自己
    选的角色在局里。未传 world 时仍回退到首个角色的 world（旧调用方不受影响）。
- **改动·前端**（开场区，主流程代码禁区未触碰）：
  - 角色区**上方**新增世界下拉（`#world-pick`），默认占位「请选择一个世界」；
    选中即加载该世界全部角色（默认全选）与该世界世界书。
  - 三个空态都给可执行指引：没有世界书 / 该世界没角色 / 有角色未归属任何世界（点名列出）。
  - 未选世界时**先校验再置初始化态**，避免玩家看 spinner 空等。
- **测试**：
  - 新增 `tests/test_setup_world_picker.py`（8 条：store 层过滤、接口返回、未归属识别、
    显式世界生效、跨世界拦截、世界不存在拦截、旧调用方回退、空 cast 拦截）。
  - `_frontend_binding_check.js` 补两处**既有缺陷**：`document.querySelectorAll` 被 mock 成
    `() => []`，使 `startSession` 恒判定「无可选角色」提前 return（沙箱形同虚设）；
    并新增两条断言「开局请求体含所选世界 / 含在场角色」。
  - 全量 **247 passed, 1 skipped**。实机（临时实例 5052，未复用simon 的 5051 旧进程）
    验证：按世界分组正确、两条校验分支均正确、旧调用方仍播种秘密。
- **simon 已实机试玩通过**（浏览器交互由simon 完成，本条仅记录结果）。

---

## 2026-10-07 版本 v0.18.6（亲缘词表按中国亲属称谓体系补齐：45 → 116 词）

- 版本判定 **PATCH**（v0.18.5 → v0.18.6）：补齐遗漏的合法身份词，属错误修正（词表覆盖不全），非新增能力。
- **触发**：simon 审第二个剧本（姨甥向）时发现 `姨父` 不在 `_KINSHIP_TOKENS`，要求以「中国常见亲属 + 社会关系」为对比组全面审视。
- **先纠正一个误判**（simon 的场景实测反证）：**词表缺词并不影响真实会话的冻结**。`seed_kinship_from_cards`（过滤词表的函数）只服务「关系缺口补全」路径；真实会话的显式声明走 `memory.new → kinship_base`，**该链路不过滤此表**。实测：`姨父` 不在表时，模型把「姨父」越权改写成叔叔/姐夫/舅舅/妹夫四种，均被正确拉回。故不存在「声明形同虚设」的运行时故障——但补词仍必要，见下。
- **词表补齐（45 → 116 词）**，按中国亲属称谓体系分组：母系亲属的配偶（姨父/姨母/姑父/姑母/舅妈/舅母）、父系伯叔（伯父/伯母/叔父/叔母/婶婶）、堂表兄弟姐妹（含堂哥/小姨子/大姨子）、侄辈女系（侄女/外甥女/外孙/外孙女）、核心姻亲长辈（岳父/岳母/亲家三家）、继嗣与收养（继子女/养子女/义父母）、高祖辈（曾祖父/外祖父）、口语尊称（叔叔/阿姨/姑姑/姨妈等原表漏项一并补回）。
- **社会关系词一律不加，并写明机制理由**（simon 要求纳入对比组，但经数据验证后否决）：
  - **入表即冻死关系演化**——本引擎主功能就是关系演化（同事→恋人、下属上位、房东变盟友）。「同事」入表后 `_preserve_kinship` 会把模型写对的「恋人」拉回「同事」，等于从机制上关掉引擎的主要功能。已有 `test_preserve_kinship_no_baseline_free` 与 `test_seed_kinship_ignores_non_kinship_words` 两条守护用例。
  - **职业/称谓词在中文里作状语与口语称呼**（「领导在场」「大哥别说」），句首声明规则会大面积误判，把叙述句当身份声明反过来改坏关系。
  - 需要固定某个社会身份时的正确通路：走 `relations_kinship` 显式声明——该通道对任意身份词都生效（`memory.new` 不过滤）。
- **顺带**：清除死代码 `_KINSHIP_RE`（全文件仅定义处一个引用点，无任何使用方）。词表新增两条 `assert` 自检：禁单字、禁社会关系词。
- **测试**：`test_relation_gate.py` 新增 6 条守护（常见词覆盖 / 社会词禁入 / 新词句首声明可识别 / 新词冻结生效 / 新词叙述句不误判 / 社会关系演化不受影响）；全量 **239 passed, 1 skipped**。
- **剧本内容**（不入库、不随包）：`data/characters/周牧野.json` 补 `relations_kinship: {林泽宇: 姨父}`；该剧本在世界树，不进 commit 与分发包。

---

## 2026-10-07 版本 v0.18.5（角色删除不再失效：删除真删 + 已删 demo 不再被播种回弹）

- 版本判定 **PATCH**（v0.18.4 → v0.18.5）：修复角色删除功能失效，属错误修正，非新增能力。
- **事故**（simon 报告）：角色库点【删除】→ 确认 → 提示不可恢复 → **角色卡仍在**。定位为三处叠加的同一条修复链：
  - **根因（store.py `_seed_examples`）**：实现按文件逐个补缺（`if not target.exists(): copyfile`），**违背其自身注释声明的「目录为空才播种」意图**。删掉一个 demo 后 `list_characters()` 触发播种，把已删 demo 从 `data/examples/` 重新拷回 → 角色"复活"。
  - **后端语义（app.py `delete_character`）**：改为显式返回「真删/不存在/出错」三态（404 / 400），不再对不存在的名字静默返回成功。
  - **前端取名（static/index.html `char-delete`）**：删除目标改用 `loadChar` 载入的权威名 `_charOrig.name`（等于磁盘文件名），不再取编辑框 `c-name` 实时值——避免改名/带空格时与磁盘文件名对不上而落入失效分支；补失败提示。
- **修复（定义层对齐，非打补丁）**：`_seed_examples` 改为——目录已有任意 `.json` 即整份跳过，不再逐文件回补已删 demo。首启（空目录）完整播种不受影响。
- **剧本内容（不入库、不随包）**：本次另同步对齐了某示例剧本的角色删除依赖路径与两名角色的秘密设定重写/定性降档（见工作树 `.workbuddy/memory/`）；`data/characters/`、`data/worlds/` 为私人数据，已被 .gitignore 排除、不进 commit 与分发包。
- **测试**：全量 233 passed, 1 skipped；另用隔离脚本验证「删 demo 后不回补」与「空目录首启完整播种」两条分支。

---

## 2026-10-06 版本 v0.18.4（压力提级文案软化为软提醒：玩家指令优先贯彻到底）

- 版本判定 **PATCH**（v0.18.3 → v0.18.4）：仅调整提示词措辞（强命令 → 软提醒），无行为契约变化，非新增能力。
- **背景**：v0.18.3 移除了镜头层高压强制后，prompter 的提级文案仍是强命令（「必须撞出结果」「两人须同一场景」「不得略过」），与「玩家体验优先」存在同类冲突。simon 拍板一并软化。
- **改动**：
  - `_global_pressure_block` 标题 `[本轮必须发生的事]` → `[可选提醒·秘密发酵]`，全文改软提醒措辞：只提示「秘密沉太久、若叙事自然可让它露头」，明确「以上仅为可选提醒，优先级低于导演指令与镜头分配，若不合叙事可完全略过」。
  - `_ferment_hint` 分档文案同步软化（「必须」→「若有自然机会，可」；p>=5 档引用新标题）。
  - 相关注释同步（director.py `PRESSURE_FORCE` 注释、prompter.py 各引用点）。
- **测试**：test_pressure_force.py 断言更新（标题 + 注释中性化）；全量待跑。

---

## 2026-10-06 版本 v0.18.3（高压不再抢镜头：玩家体验优先，碰撞交叙事自然命中）

- 版本判定 **PATCH**（v0.18.2 → v0.18.3）：移除高压镜头强制，属机制简化回退，非新增能力。
- **决策（simon 裁定）**：与其靠「群体词/指代词/无人名」的三岔判断去区分该不该高压强制（判断必然有词表漏洞，如「众人沉默」），不如索性承认玩家体验优先——高压就让角色顶着，等叙事自然命中。引擎定位是小空间群像，空间本就局限，高压双方迟早自然同场。
- **改动**：
  - `compute_focus` 回到干净逻辑：点名就跟、群体词/无人名就自然推演、指代代词延续上轮焦点。**彻底移除高压对镜头的强制**（不强制并入、不强制锁定、不兜底撑镜头）。
  - 删除 `_merge_pressure_into_focus` 整个函数；`director.py` 中 `forced` 字段完全清除。
  - `pressure_targets` / `PRESSURE_FORCE` 保留——它们仍供 prompter 的提级文案（`_global_pressure_block`）使用。
- **保留**：压力仍在「发酵计数 + 提级文案」两个层面起作用（提示 LLM 有未爆发的雷），只是不再有「抢镜头」的机制出口。
- **待决（已标注在 prompter 注释）**：提级文案目前仍是强命令（「必须撞出结果」「两人须同一场景」「不得略过」），与「玩家体验优先」存在同样的潜在冲突——是否一并软化为「软提醒」待 simon 定。（**已于 v0.18.4 一并软化**）
- **测试**：test_pressure_force.py 移除/改写高压镜头强制契约（纯环境不再兜底、跨轮不再黏住镜头）；全量 233 passed。

---

## 2026-10-06 版本 v0.18.2（玩家指令优先：高压秘密不再凌驾导演指令）

- 版本判定 **PATCH**（v0.18.1 → v0.18.2）：修正机制优先级错误，非新增能力。
- **事故**（会话 97589153）：simon 指令「第二天早上，众人讨论下一步去处」，正文却仍是某二角色戏（高压秘密的碰撞），其余人只字未提。根因：该秘密 `pressure=5`（封顶）触发 `_merge_pressure_into_focus` 把「归属者+对手」强制锁定为镜头（forced+sticky），覆盖了玩家的群体指令——而「众人」这类群体词不在 `_FOLLOW_WORDS` 里，被误判成「无人点名」。
- **决策（simon 裁定）**：保玩家指令为先。指令是玩家唯一的操控接口，违背它会让不了解机制的玩家误以为「引擎不遵循指令、有 bug」；高压是引擎内部机制，应服务于叙事而非凌驾于叙事。
- **回退实现**：
  - 新增 `_GROUP_WORDS`（众人/大家/所有人/全员/每个人…），群体词命中即视为「玩家显式点名全体」，返回自然推演。
  - `compute_focus` 提前分流：玩家点名具体子集 / 群体词 / 点名全体时**直接返回**，不再落入 `_merge_pressure_into_focus`；只有「指令完全没点名任何角色」（纯环境描述）才让高压兜底撑镜头。
  - `_merge_pressure_into_focus` 语义收窄为「仅在玩家未点名时兜底」，docstring 同步更新。
- **保留**：高压在「纯环境指令」下仍兜底（sticky 延续），张力机制未被砍掉——只是不再与玩家的明确操控意图抢方向盘。
- **测试**：test_pressure_force.py 重写 4 条高压并入契约（改为「玩家点名则高压不并入」）+ 新增「纯环境仍兜底」用例；全量 233 passed。

---

## 2026-10-06 版本 v0.18.1（场景切换即目标作废 + 镜头外目标降权）

- 版本判定 **PATCH**（v0.18.0 → v0.18.1）：修正叙事偏离 bug，非新增能力。
- **事故**（会话 9f2e16e9 R14）：simon 指令「体弱的子航和苏婉被困电梯，其余人安全抵达地库」，正文却让某角色出现在电梯检修口喊话 + 大段内心独白 + 救治同伴，喧宾夺主、未随其余人抵达地库。根因三层叠加：
  1. **goal 残留锚定（主因）**：该角色旧短期目标「贴身照看某同伴伤口」是纪官前轮写死、跨轮残留，场景切换后未作废；`build_session` 把 goal 当「当前意图」注入角色块，强烈锚定其追到电梯口继续救治。
  2. 镜头焦点只锁定指令点名的子集（其余人标「镜头外不展开」），但这是 prompt 软约束，被 goal 牵引压过。
  3. `validate_present` 只按「角色名：」行首剥离台词块，引号对白 + 旁白形式绕过校验。
- **修复（方案 A+B，定义层）**：
  - **A** `engine/scene.py`：`apply` 落实新场景时，地点实质变化即 `snap["goals"] = {}` 清空——goal 是「当前情境下的短期意图」，地点一变情境即变，旧目标作废，下轮纪官基于新场景重写。
  - **B** `engine/prompter.py`：`build_session` 有镜头焦点（focus.subjects 非空）时，镜头外角色的 goal 不注入（降权），避免其被残留目标拽回镜头抢戏。
- **测试**：`tests/test_scene.py` +2（地点变化清空 goals / 地点未变保留 goals）、`tests/test_prompter.py` +2（镜头外目标抑制 / 无焦点全注入）。全量 232 passed / 1 skipped / 1 deselected，无回归。

## 2026-10-06 版本 v0.18.0（结构化人物位置层：谁在哪里成为唯一真相源）

- 版本判定 **MINOR**（v0.17.6 → v0.18.0）：新增结构化字段 `locations` 与纪官上报通道 `location_updates`，是新增机制能力，非错误修正。
- **事故**（会话 9f2e16e9 R14）：快照同时存在「苏婉：昏迷在电梯角落」(R14) 与「卧室门：紧闭，苏婉在屋内」(R12)，同一角色同时"在"电梯和卧室。根因——人物位置没有结构化归属，散落在三处：`scene.place`（镜头位置）/ 物件状态键 value 里的嵌套引用（「卧室门」value 塞"苏婉在屋内"）/ 纪官违规造的角色裸名键。分队移动后旧键过期，无人负责联动清理，引擎 states 是独立 KV 覆盖式刷新、无跨键一致性检测。
- **修复**：把「谁在哪里」从物件状态里剥离，成为一等公民状态——
  - `engine/director.py`：新增 `update_locations(snap, items, round_no)` + `LOCATION_CAP=40`。一角色一当前位置，后写覆盖前写，天然消解「同时两处」。键归并复用 `_STATE_NOISE` 去助词/标点（不剥「情绪/状态」后缀，那是角色名不是伤情键）。
  - `reflect` prompt：新增 `location_updates` 字段与规则（who+place，只填 moved 的角色，同一角色只报一条）；`state_updates` 规则**明令禁止把人物位置写进物件/环境键**（根源所在）；reflect 回喂「既有位置」供纪官沿用、防造同义键。
  - `engine/prompter.py`：注入「[人物位置（不可违背）]」块，与「当前状态」并列——分队/离场时逐人位置独立于镜头所在（scene.place），防止模型把「已困电梯的人」写回「在卧室」。
  - `engine/app.py`：`_SNAPSHOT_PUBLIC_FIELDS` 加入 `locations`。
  - `engine/static/index.html`：左栏新增「人物位置」面板（在「现状」之后），逐人渲染 `locations`，与「现状」面板分离、一眼可辨。
- **兼容性**：旧会话无 `locations` 字段，prompter/前端均用 `snap.get("locations") or {}` 兜底，首轮 reflect 归档 `location_updates` 时 `setdefault` 自动建立，无需迁移。
- **测试**：`tests/test_director.py` +5（逐人覆盖 / 分队独立 / 空值占位丢弃 / 同义键归并 / reflect 归档落库）；`tests/test_frontend_binding.py` 面板 id 检查加入 `locations`。全量确定性测试 228 passed / 1 skipped / 1 deselected，无回归。
- **压测待办**：属机制设定级（新增位置层），与 v0.17.6 秘密护栏一并并入后续压测批次（30 轮 stress + compare，实机 + 本地 LLM）。
- `VERSION` 升 v0.18.0。

## 2026-10-06 版本 v0.17.6（秘密暴露语义护栏：拦内心独白/话题错位/不在场者误报）

- 版本判定 **PATCH**（v0.17.5 → v0.17.6）：修正「秘密被无中生有误标暴露」的判定缺陷，属秘密记账核心度量路径的行为修正。
- **事故**（会话 467f1e4c）：第十回合除周岚外沈川/林小满/周子航三秘密全标「暴露」，但正文里读不到任何暴露动作。根因——`_evidence_ok` 只验「举证原文在不在正文」，不验「是否真构成该秘密的信息传递」；via 白名单只验 via 字面值是否合法，不验语义是否属实。纪官把「内心独白 / 讨论另一话题 / 家庭共享背景 / 不在场者」截成一段确实存在于正文的原文当证据，全过检，5 条误判被翻成暴露。
- **修复**（`engine/director.py`）：在「via 白名单 + 举证逐字在正文」之后、`_record_exposure` 之前，新增两道叠加语义护栏（AND）：
  - `_evidence_related`（护栏一·事实锚点相关）：证据须与秘密的 keys（作者给的触发词，非引擎题材词表）共享任一 ≥2 字连续片段（`_bigrams` 双字滑动窗口），拦住「讨论伤口却去坐实某人失联」这类话题错位。用双字片段而非完整键子串——纪官引文常是自然叙事语言，未必逐字照抄触发词（key「旧队的死法」vs 正文「旧队覆灭」仍共享「旧队」）。
  - `_evidence_transfer`（护栏二·施受方在场）：证据片段内须出现信息接收方 by 或提供方 owner 的名字，拦住「旁白心理独白」「不在场者听见」这类无施受方的伪传递。
  - 任一不过 → 降级为起疑（证据仍真实存在，只是语义不构成暴露），并留 `logger.warn`；宁可漏记（状态滞后），不可误记（秘密提前暴露、张力提前消耗）。
- **不违记录员模式契约**：两道护栏均不引入引擎自持的题材语义词表（`DISCOVERY_VERBS/INFO_VERBS` 那套 v0.5.8 已废），语义判断仍归纪官，引擎只做结构核验（复用作者 keys 做事实边界 + 施受方名字做传递边界）。
- **测试**：`tests/test_director.py` +5（话题错位/内心独白/不在场者各降级、真实暴露放行、helper 边界）+ `_verify_467f1e4c_guard.py`（一次性回放，验证 5 条误判全拦 + 对照组放行，前缀 `_` 不入库）。全量确定性测试 223 passed / 1 skipped / 1 deselected。
- **压测待办**：属秘密记账核心路径修正，按红线应跑 30 轮 stress_longcontext + compare_stress（实机 + 本地 LLM），待 simon 确认后执行。
- `VERSION` 升 v0.17.6。

## 2026-10-06 版本 v0.17.5（UI 界面优化：删面板小字 + 日志默认收起）

- 版本判定 **PATCH**（v0.17.4 → v0.17.5）：两处前端体验优化，普通迭代，不碰引擎机制/推演/记账，无需压测。
- **删两处面板小字**：「现状」「秘密」面板底部的 11px 灰色说明文字（「只记「现在是什么样」…」「只知道谁藏着什么…」）删除——面向正式玩家的界面不该露出引擎内部语义的提示，属调试信息泄漏。纯静态 div，无 JS/测试引用。
- **运行时日志默认收起**：原逻辑仅窄屏（`innerWidth < 720`）默认收起、宽屏默认展开；改为**无条件默认收起**。日志定位为调试旁路，正式游玩第一眼只看到三栏布局；顶栏「运行时日志」按钮随时展开，展开后 SSE 照常连接、不丢日志。
- **打包前泄漏扫描与洗白（同版本内收口）**：
  1. `worldbook-guide.md` / `static/worldbook-guide.html`：示例词「尸变不可逆」→「失忆不可逆」等中性世界观示例（引擎格式说明文档不该含题材词）。
  2. `static/script-example-guide.html`：范例同步为官方 demo「丧尸末日」**最新悬置版**（旧版含「故意等到最后一刻/害死/早已认定/正在发高烧」等已否定的旧结论，与 data/examples 不一致）。
  3. `data/examples/`（4 角色卡 + 世界书 + script-example.txt）：官方 demo 整体同步到本轮定稿的最新悬置版（秘密悬置化、去「高烧」触发词）。**data/examples 是官方 demo，随包附带且入库，非私人数据泄漏。**
- `VERSION` 升 v0.17.5。

## 2026-10-05 版本 v0.17.4（单回合链路四项收口：缓存 / 换场本轮落 / 正文后落 / 举证容标点）

- 版本判定 **PATCH**（v0.17.3 → v0.17.4）：四项普通迭代（错误修正/性能/健壮性），源自对「单回合完整工作链条」的系统审查。不碰 director 推演/秘密记账核心度量路径，无需压测。

### ① store 只读缓存（省每轮磁盘 IO）
- `store._cached_read` / `_cached_listing`：角色卡/世界书/目录列表加**带 mtime 签名**的进程级缓存，文件变了重读、没变直接用内存。app.py 每轮为在场角色逐张 load_card、director 反复 list_characters/load_world，长上下文后期 IO 累积明显。
- `save_card`/`delete_card`/`save_world`/`delete_world` 均失效对应文件缓存**与其所在目录的列表签名缓存**（`_invalidate` 双清），运行期导入/编辑新卡新世界不漏看。

### ② 换场信号本轮直接落库（消解时间滞后一拍）
- `director.reflect` 里纪官上报 `scene_shift.changed=true` 时，**本轮就直接更新 `snap["scene"]` 的 place/time/weather**（time 经 `scene._norm_time` 清洗，避免描述句污染），不再留到下轮 `scene.apply` 才消费。旧链路「scene 生成前跑、reflect 生成后跑」导致快照时间永远滞后正文一拍。
- 仍保留 `scene_shift` 字段供下轮兜底：若下轮指令又触发切换，scene.apply 基于已追平的 scene 再判，不重复推进。

### ③ 正文落盘挪到 reflect 之后（收口事务边界）
- `app.py` 把 `append_chat`（正文）从 reflect 之前挪到 reflect 之后。旧顺序「先落正文、再回写状态」，进程若在两者间被杀会「正文推进了、关系/秘密/行动没记账」且状态丢失不可逆；新顺序「状态先落、正文后落」，最坏是正文丢（可重生成），不再丢不可逆的推演状态。reflect 只用内存 full 举证、不读 chat 文件，顺序调整无副作用。

### ④ 举证比对容标点/引号差异
- `director._evidence_ok` 在「折叠空白」之上再「剥离标点/引号」（新增 `_strip_punct`）。纪官引用原文最常见的轻微差异是标点/引号（正文「」、引用漏引号；句末句号截断），逐字比对会误杀造成漏记；而「她」→角色名这类字面篡改仍保留、仍拒绝。只消标点、不动汉字字面。

- `VERSION` 升 v0.17.4。
- 测试：`tests/test_director.py` +2（标点容忍/字面篡改拒绝）、新增 `tests/test_store_cache.py` +5（缓存命中/失效/目录签名刷新）；全量确定性测试 218 passed / 1 skipped / 1 deselected，无回归。

## 2026-10-05 版本 v0.17.3（秘密曝光判定收紧 + 时间锚承接修复）

- 版本判定 **PATCH**（v0.17.2 → v0.17.3）：三项错误修正，均源自对真实会话 256d924c 的审计——正文「颠三倒四」追根到三层源头：① 秘密「开局即暴露」（引擎逻辑缺陷）；② 时间锚丢失（引擎没承接玩家输入）；③ 场景块「时间未明」诱导模型自行脑补时间。

### 修复一：秘密曝光判定收紧（内心活动不再误判成「实际得知」）

- **根因**：曝光归档（reflect 的 secret_exposures）此前只靠两层把关——① 纪官 LLM 语义判断；② `_evidence_ok` 的「举证逐字在正文」校验。后者只能防幻觉，**防不了语义误判**：纪官把「角色内心想到他早就看穿」「早已心知肚明」这类心理描写误报成「实际得知秘密」，导致潜伏秘密在开场即被翻成「暴露」（周岚秘密 R1 即暴露，正文演成秘密已炸的既成事实，读者看不到揭露过程）。
- **修复（定义层）**：
  1. 纪官 prompt 的 `secret_exposures` 新增 `via` 字段（信息获取方式，四选一：看见/听见/被告知/发现物证）；判定规则明确「得知」必须是信息实际跨角色传递，并新增硬规则——内心活动/独白/回忆/猜透/早已心知肚明一律不算暴露，只能落 `secret_suspicions`（起疑）。
  2. 引擎侧新增 `EXPOSURE_VIA_WHITELIST` 白名单 + 归档循环护栏：纪官报的曝光若 `via` 缺失或不在白名单，**降级为起疑**（`_record_suspicion`），绝不翻成暴露。

### 修复二：时间锚承接（玩家输入的时间不再丢失）

- **根因**：开场只有 `scene` 一个自由字符串参数，引擎整体塞进 `place`、`time` 恒空（memory.new 硬编码 `""`）。玩家写「傍晚，公寓的客厅」时「傍晚」被当成地点的一部分，时间锚丢失；后续指令「即将到来的夜晚」又因 `TIME_KEYS` 缺「夜晚」、且无将来时态解析，时间推进从未被执行。模型只能在「时间未明」+ constant 世界书（丧尸夜间活跃、早断电）的拉扯下自行脑补时间推进。
- **修复**：
  1. `scene.parse_initial_scene(text)`：按最长匹配从开场字符串识别时间词填 `time`、剩余填 `place`（`INITIAL_TIME_KEYS` 覆盖傍晚/夜晚/深夜/第二天早上等时刻词）。`session_new` 调用它拆分；`memory.new` 新增 `scene_time` 参数。
  2. `TIME_KEYS` 补「夜晚/深夜/半夜/黄昏/黎明/早晨/早上/下午/正午/白天」等词。
  3. 场景导演 `_PROMPT` 新增约束 4：**将来时态不算当前变化**——「即将到来的夜晚」「明天会下雨」这类未发生的事只是预告，changed 填 false，不得把「即将到来」当成「已经到来」。
  4. 前端开局表单拆成「开场地点」「开场时间」两个输入框（职责分离，符合整洁 UI 偏好），提交时拼成 `地点，时间` 交给后端解析。

### 修复三：场景块「时间未明」不再诱导自行脑补

- `prompter.build_session` 场景块：`time` 为空时不再输出「时间未明」，改为「时间未知——本轮不得自行推进或杜撰时间，保持时间悬置，待环境推手指令明确时间再写」。时间推进权收归场景导演，叙事层不越权。

### 修复四：场景导演 time 字段清洗兜底 + 时间词原样采用（10 轮实机验证发现）

- **触发**：10 轮实机验证（`tests/verify_time_semantics.py`）暴露两个残留 bug——① 场景导演把 time 自由发挥成描述句「夜幕降临」「无（室内，窗外夜色浓稠）」，污染 scene.time；② 指令「第二天」被 LLM 降级成「白天」，丢掉跨日语义。
- **修复（定义层，双保险）**：
  1. `scene._PROMPT` 新增约束 5（时间词原样采用）与 time 字段「干净时段名词」硬约束（禁动作句/描写句/括号补充）。
  2. 引擎侧新增 `scene._norm_time` + `_is_future_time` 兜底：落 time 前清洗——value 是干净词直接采用；是描述句则回退原 time（宁可不推进也不写废话）；value 无词但指令含确定时间词则采用指令里的词；「时间词+快到了/即将」等将来时预告不推进。
- **实机结果**：7/7 时间词承接命中（傍晚/夜晚/第二天/入夜/清晨/天亮/午后）；「第二天」不再降级成「白天」；「夜晚快到了」不再误判成「已入夜」（收敛到「黄昏」干净名词）。
- 测试：`tests/test_scene.py` 新增 7 项（_norm_time 清洗/_is_future_time 将来时判定）；全量确定性测试 211 passed / 1 skipped / 1 deselected，无回归。

- `VERSION` 升 v0.17.3。
- 测试：`tests/test_director.py` 新增 3 项（via 护栏）、`tests/test_scene.py` 新增 12 项（parse_initial_scene 拆分/最长匹配/空串 + _norm_time/_is_future_time 清洗与将来时）、`tests/test_player_view.py` mock 签名补 `scene_time`；全量确定性测试 211 passed / 1 skipped / 1 deselected，无回归。

## 2026-10-05 版本 v0.17.2（纪官语义提取三项迁移收口 + 压测/提示词修复）

- 版本判定 **MINOR**（v0.17.1 → v0.17.2）：群演登记入口由散文正则改为纪官语义提取、背景人物活动化移交纪官、场景切换新增纪官信号通道，均属新增能力；其中「撤销强制删正文」与「背景名单推导」为错误修正。
- 本次一并收口 v0.17.1 之后的全部未提交改动（详见下方专题记录「群演登记改为纪官语义提取」及其子节：改名合并、背景人物活动化、场景切换信号、背景名单推导）。
- `VERSION` 升 v0.17.2；提交 + tag `v0.17.2`；产出 `personae-v0.17.2.zip`，删除 v0.17.1 旧包。
- **测试基础设施修复**：`tests/stress_longcontext.py` 的 `build_arc` 占位映射键误写成 `"{A}"`，`t.format(**mapping)` 必抛 `KeyError: 'A'`——该压测脚本自加入起从未真正跑通过。已修正为 `mapping[key]` 并补空卡组保护；同时新增本轮机制的观测采集（`aux` 名单 / `offscreen_violated` / `scene_shift`）与「删正文」回归哨兵（极短回复 <200 字、以句号或逗号开头的残句），报告新增对应小节。
- **提示词普适性修复**：reflect 提示词中 aux_updates 改名说明写入了具体人名示例，违反引擎普适性红线（不在 S5 黑名单故未自动拦截）。已全部改为中性占位，并把 `replaces` 触发条件写死：职务/身份/外貌类称呼一旦本轮得知姓名**必须**走合并，旧称呼须逐字照抄已登记名单；`director.py` 注释中同批具体人名一并中性化。
- **分发包泄漏修复**：`DEVLOG.md` / `TODO.md` 此前随包分发，内含私人剧本的具体角色名、关系与题材词（引擎普适性红线在源码层已守住，日志层漏了）。已按 `FACT-MEMO.md` 的先例加入 `EXCLUDE_FILES`，`engine/README.md` 中对二者的引用同步改为「只存在于开发工作树」。包体 32 → 30 条目。
- **README 版本引用**：`当前版本见 engine/VERSION（v0.13.1）` 的括号硬编码已陈旧 4 个版本，改为不复写版本号（`engine/VERSION` 为唯一真相源）。
- 验证：确定性单测 196 passed / 1 skipped / 1 deselected；10 轮端到端压测（真 LLM）0 异常、0 空回复、present 违例 0、极短回复 0、残句 0；群演定向探针两遍均「泛称 → 本名」合并成功且不新增重复 chip（第二遍正文无「我叫X」，证明由纪官主动填 `replaces` 而非引擎兜底）。报告见 `tests/runs/`。

## 2026-10-05 群演登记改为纪官语义提取（散文正则误报不可根治，退出登记链路）

### 问题

v0.17.1 把 aux 群演发现改成散文判据（「2~3 字 + 说话动词 + 引号」）后，真实会话连续误报：
会话 ec086687 左栏出现「喃喃」（源自「他喃喃道：“爸……”」）；此前同类误报还有「胁语气」「想要」「她想」。
当天补的四层结构护栏（代词前缀/能愿/抽象词/描述后缀）挡不住这一类——「喃喃」是叠音说话动词本身，
打补丁式加词表是无限循环：中文说话方式表达无穷多（喃喃/咕哝/沉吟/呜咽…），正则只认结构不认语义。

### 决策（simon 提出，定义层正解）

引擎每轮叙事后本就有一轮独立的纪官同步 LLM 调用（`director.reflect`，输出 JSON 回写状态）。
让纪官**按语义**提取新出场人物，取代正则文本挖掘：

- reflect 输出 JSON 新增 `"aux_updates": [{"name", "note"}]` 字段，规则写死：
  只填「新出场且以稳定称呼说话或被指名」的人物；代词/泛称/说话动词碎片/无名背景一笔带过者绝不填；拿不准就不填。
- 解析端过结构护栏（`_is_aux_garbage_name`：代词前缀/能愿/抽象/描述后缀/结构助词/说话拟声/叠音/语气状语），
  防纪官偶发误报；泛称**不在**拒收之列（跨轮泛称可能真是不同角色，与既有「同轮消解」规则衔接）。
- `app.py` 的散文正则调用点停用；`discover_aux_speakers` 函数保留作离线工具与测试守护。
- 引擎侧新判据（本轮补齐）：AA/AABB 叠音拒绝（喃喃/呜呜咽咽，真叠音人名走【引入角色】旁路）、
  单字说话动词尾部剥离（「爸爸叹道」截成「爸爸叹」→ 剥离还原后叠音拒绝；「角色丙叹道」正常还原）、
  语气状语全等过滤（「沉声开口」剥动词后剩「沉声」）。

### 实机验证（本地 llama 真调 reflect）

- 负例：含「他喃喃道」的正文 → `aux_updates` 空，无误报。
- 正例：新说话人「物业的老郑」以引号对白出场（无「名字+说道」结构，旧正则抓不到）→
  登记 `老郑 / 自称物业保安的中年男人`——语义登记不仅无误报，note 质量也远超正则。

### 改名合并（反馈：会话 1868b891 同一人两个 chip）

语义登记上线后 simon 测出：「女幸存者」在册，第 2 轮她自报「我叫苏青」，引擎却把她当成
**又一个新人物**登记，左栏出现两个 chip 指同一人。

根因是两层缺失：① reflect 提示词没把已登记群演名单回喂给纪官，它无从判断「这就是那个人」；
② `aux_updates` 没有改名合并通道，旧的同轮消解（`_resolve_aux_aliases`）只服务于正则路径、
且只能处理同一轮内「泛称：…我叫X…」的分段形态，跨轮合并根本没有机制。

按同一架构补齐（纪官判语义，引擎核验结构 + 证据兜底）：
- 提示词回喂 `已登记群演：女幸存者（…）`，`aux_updates` 增加 `replaces` 字段，
  并配**具体示例**（本地模型对纯规则描述服从性不足，给示例后两次实测均正确合并）。
- 解析端：`replaces` 指向在册条目 → 改名合并（保留 `intro_round` 首次出场回合、更新 role）；
  新旧名都在册或旧名不在册时不做合并，避免造重复条目或把两人捏成一人。
- **结构兜底**（纪官漏填 replaces 时）：正文出现「我叫/我名叫/我姓 X」且本轮**只提及一条
  泛称类**旧群演 → 合并。旧称呼是真名、或本轮提及两条泛称时不合并——证据不足就保留两条，
  误合并比重复 chip 严重得多。

实机（本地 llama，真实事故原文）：`aux` 由 `女幸存者(round1)` 正确合并为 `苏青(round1, 自称纺织厂工人)`。
历史脏数据（1868b891）已手工按同一语义合并。

### 全量审计后三处落地（simon 要求：检查还有哪些靠正则/函数提取，能否一并交给纪官）

审计方法：grep 引擎全部 `re` 调用点，并对磁盘上**全部真实会话**跑量化探针（不凭感觉）。
共 12 处文本挖掘点，结论分三层（详见下节「不迁移的与死代码」）。本轮落地 3 处。

#### ① 背景人物名单推导修正（`background_names_from_relations`，确定性 bug）

原实现只做「relations 名字 − present」的集合差，与它自己 docstring 的定义
（背景 = **store 不收录者**）不符：把**有独立角色卡但本轮不在场名单**的角色也划成背景。
改为排除 `store.list_characters()` 与已登记 `aux`，并新增可选 `extra_known` 复用调用方
已算好的名单避免重复扫盘。`prompter` 里另有一份口径不一致的推导（`rel_names − card_names`），
一并统一为「无独立角色卡」——否则提示词一边要求「不得为其撰写出场段落」，叙事里他却正在演。

#### ② 背景人物活动化：语义判定移交纪官，**撤销强制删句**

这是本次最严重的一处。`detect_offscreen_activity` 的判据②「分句主语 + 22 个动作字表」
与刚废掉的 aux 正则是同构硬猜：量测 296 轮中 79 轮含背景人物、**23 轮判失责（29.1%），
真失责接近 0**。「来自远方的指令」命中「来」字即判失责。
后果是 `app.py` 的 `cleaned.replace(hit, "")` **整句删除正文**——端到端复刻验证：
一句 27 字的正常叙事被删到只剩「。」。

修复（与 aux 同一架构：纪官判语义，引擎只做逐字举证核验）：
- reflect 提示词回喂 `背景人物（无独立角色卡、不在场）` 名单，新增
  `offscreen_activity: [{name, evidence}]`；规则明确列出**不算**的情形
  （被谈论/回忆/提及名字/收到其来信或指令、以「X不在场」「想起X」形式出现——都不算活动化）。
- 解析端复用 `_evidence_ok` 逐字核验（与 `secret_exposures` 同一套记录员模式），
  核验通过才写 `snap["offscreen_violated"]`。
- **撤销强制删句**：改为下轮 `prompter` 点名批评（「上一轮你把 X 写成了会开口说话、
  亲自登场行动的角色，原文如「…」」）。误删代价远大于漏删收益——旧链路删掉的是
  用户**已经看到**的正文。
- 正则 `detect_offscreen_activity` 保留作低成本确定性告警（它在分段体下准确率高），
  但不再有删除权。

实机（本地 llama）3/3 正确：两个旧正则误判的负例（「X不在场，但…来自远方的指令」、
「我妻子梦琪最近总一个人待着」）纪官均正确放过；真活动化（「X从门后走出，轻声说：…」）
正确上报并带逐字举证。端到端跑真实会话一轮，此前会被删的角色戏份完整保留（1535 字）。

#### ③ 场景切换信号并联纪官（零额外 LLM 成本）

`scene._triggered` 靠 4 组关键词表（移动/时间/天气/离场）决定是否调场景导演，枚举不完。
reflect 新增 `scene_shift: {changed, place, time, weather}` 存入快照，下轮
`_triggered` 改为「停留超时（force）／纪官信号／关键词」三路并联。
时序上 `scene.apply` 在生成前跑、`reflect` 在生成后跑，故只能**跨轮**生效——正好用于
「正文早已入夜、快照还停在清晨」这类引擎没跟上叙事的补偿，且提示词会把纪官读到的
实际场景值喂给场景导演定稿。信号**用后即清**，避免一次上报反复触发、架空
「规则版触发避免每轮调 LLM」的设计原则。

实机：叙事无变化 → `changed=false`（不触发，零开销）；叙事里天黑下雨 →
`{changed: true, time: "黄昏/夜晚", weather: "下雨"}`。

#### 不迁移的与死代码（审计结论）

- **不迁移**：`narrative_clean`（确定性文本手术，非语义判定，交 LLM 会引入延迟与不确定性）、
  `state_key`（纯字符串归一化，且提示词已回喂既有键）、`_PLACEHOLDER_VALUES`、
  `_first_kinship`（护栏而非提取，作者已有 `relations_kinship` 显式通道）、
  `world._NAME_REF #X#`（作者书写约定）。
- **保留正则 + 仅告警**：`validate_present`。实测 321 行命中 57 行（17.8%），
  匹配到的名字**全是真实角色名**（移除分段契约后模型仍自发写「名字：」）——准确率可接受，
  只是散文体下 82% 的行看不见。它不误伤，故保留删除权，不迁移。
- **死代码**：`app.py speaker_segment` 零调用点，可删。

### 测试

`196 passed / 1 skipped / 1 deselected`。新增 11 条：名单推导 3 条（有卡/群演排除、
extra_known）、背景人物语义 4 条（登记/举证不通过/非背景忽略/无越界清除标记）、
场景信号 4 条（记录/清除/并联触发/用后即清）。

### 长期判据

**能交给语义层判断的，不要用正则硬猜**。正则文本挖掘只适合结构完全可枚举的形态；
自然语言的表达空间是枚举不完的，每遇新误报加词表都是打补丁。引擎的举证式归档
（LLM 判语义 + 引擎核验结构）是同一思想，本次是它的延伸。

---

## 2026-10-05 v0.17.1（T0 修复：主流程按钮绑定被误删，界面全线不可用）

**版本判定 PATCH**（v0.17.0 → v0.17.1）：本轮两笔改动都是**修正错误**，不是新增能力——① 找回 v0.17.0 误删的主流程代码（恢复原状，非新功能）；② 移除 v0.16.1 引入的 `[分段格式]` 契约（纠正错误设计）。按语义化规范「修正后行为改了 ≠ 新增能力」判 PATCH。

本轮同时完成了此前挂起的**散文观感修复**（取消强制分段格式、aux 群演改用不依赖输出格式的散文判据），一并收口。

### 事故

simon 报告：**首页点「开始」无任何反应；加载旧会话可以，但加载后「注入扰动」也点不动。** 引擎后端完全正常，是纯前端事故。

### 根因：v0.17.0 删面板时误删了相邻的主流程代码

v0.17.0 移除事实保全机制、左栏从 7 个面板砍到 3 个面板。改动本身正确，但**删除的代码块边界划错了**：一并删掉了紧随其后的

- `async function send()` —— 注入扰动的全部逻辑（SSE 流式读取、delta 渲染、纪官同步期禁用输入框、`done` 后渲染 snapshot / 场景切换 / 结局提示）
- 三条主流程绑定：`getElementById('start').onclick = startSession`、`sendBtn.onclick = send`、输入框 Enter 键监听
- `let cfgProviders / cfgActiveKey / cfgOpen` 三个变量声明（系统设置面板依赖）

diff 里它们与「事实面板渲染代码」混在同一个删除块中，看起来像同一件事，实际分属两个不相关功能。**这类缺陷对 pytest 完全不可见**（一行 Python 都不碰），也不在浏览器控制台报错（`undefined` 的 `onclick` 只是赋值给不存在的元素，静默通过）——所以从「删了 137 行」的 diff 上完全看不出少了 68 行主流程。

### 修复

按 `git show 321a604^` 取回原码，**只增不删**地插回原位（位置：`renderSnapshot()` 之后、`renderProviders()` 之前）。同时把 `cfg*` 三个声明补回原处。后端 `/api/session/new`、`/api/act` 无需改动，全程未碰 Python 逻辑。

### 防回归（新增 `tests/test_frontend_binding.py` + `tests/_frontend_binding_check.js`）

1. **静态层**：断言 `send()`、`/api/act` 调用、三条绑定、`cfg*` 声明均存在；内联 script 括号配平；左栏 DOM id 与 JS 引用双向一致（反向事故：删 HTML 忘删 JS 会在渲染时抛 `null.innerHTML`，症状同样是「点了没反应」）。
2. **沙箱层**：用最小 DOM mock 在 node 里真跑一遍内联脚本，验证 `#start.onclick` / `#send.onclick` / Enter 键确实可触发，且 `send()` 真能发出 `POST /api/act`、请求体带对 `session`/`input`、结束后按钮解锁。node 缺失时自动跳过。

**反向验证过守护有效性**：按行删掉 `send()` 后重跑，`test_main_flow_probes_present` 与 `test_binding_sandbox` 双双 FAILED；恢复后全绿。不是「写完就信」。

### 实机验证（agent-browser + 本地 llama:1234）

不止于单测。真实浏览器连打两轮：点「开始」→ 进沙盘 → 输入 `*天色暗下来，窗外开始下雨*` 点「注入扰动」→ R1 完成（3224 字，场景切到「雨」，状态回写，秘密面板更新）→ 继续第二轮 `*门被敲响，门外有人*` → R2 完成（2255 字，aux 群演「地窖」自动登记）。**按钮发送后正常解锁、可连续多轮**。

> **教训（与 v0.16.0 那次 HTML 大改同类）**：本项目 `index.html` 已成一个近 2000 行的单文件，**任何按行号/大块删除的改动都要先确认删除块的语义边界**。判据：删之前先 `grep` 一遍待删块里每个函数名/赋值目标的其它引用点，确认「它只服务于被删的面板」。同时——**删除面板不等于可以删相邻代码**，宁可多留几行死代码（`refreshSnapshot()` 就是例子：事实作废功能没了，但它作为「重新拉快照刷新左栏」的通用入口被保留）。
>
> 补充：本机 `agent-browser` 首次 `open` 会长时间挂住（daemon 冷启），第二次调用即正常。首次无响应不等于不可用，重试即可。

---

## 2026-10-05 v0.17.1 后续修复：aux 散文判据误把「威胁语气/想要/她想」当群演名

### 问题

simon 反馈截图：左栏「在场角色 / 场景」面板出现两个蓝色 chip——**胁语气、想要**。这不是真实角色，而是散文判据把描述性短语当成人名截断后的碎片。

### 根因：prose_said 正则只认结构、不认语义

移除 `[分段格式]` 契约后，模型回归散文主体。discover_aux_speakers 的散文判据是「2~3 字 + 可选状语 + 说道/说/道/问… + 引号」，例如：

- 「用不容置疑的**威胁语气说道**：“管好你的嘴。”」→ 正则截取「**胁语气**」
- 「他张了张嘴，**想要问**“你认识我吗”」→ 截取「**想要**」
- 「**她想道**“完了”」→ 截取「**她想**」

这些候选在结构上满足「名字 + 说话动词 + 引号」，但语义上是状语/能愿/代词/描述碎片，不是说话人。原有过滤只挡了代词、泛称、职业词，没挡能愿/抽象/结构助词/描述后缀。

### 修复

在 `engine/director.py discover_aux_speakers` 新增四层过滤（全部按结构特征，不依赖题材）：

1. **代词 / 虚词开头**：「她想」「有人」「众人」直接拒绝。
2. **能愿动词**：「想要/想/要/会/能/可以/应该/愿意/需要/必须…」不是人名。
3. **抽象情绪 / 状态 / 描述词**：「愤怒/恐惧/威胁/语气/神情/目光/眼神…」不是人名。
4. **描述性后缀 / 结构助词结尾**：「胁语气」以「语气」结尾、「愤怒地说道」截成「愤怒地」以「地」结尾，都拒绝。

同时在 `_prune_aux_aliases` 增加**历史脏数据自愈**：已落盘的「胁语气/想要/她想/愤怒地」等垃圾 aux，下次 `register_aux` 时自动清理；清理脚本也对磁盘上已有 snapshot 跑一次，把 dfea6846/d1252ad9/3e19589c 里的脏项删掉。

### 测试

- `tests/test_aux_registration.py` 新增 5 条守护：
  - `test_discover_aux_rejects_modal_and_describe_fragments`（威胁语气/想要/她想）
  - `test_discover_aux_rejects_abstract_state_as_speaker`（愤怒地说道）
  - `test_discover_aux_still_keeps_real_names_with_modal_substring`（会哥/想容 不被误伤）
  - `test_register_prunes_legacy_garbage_entries`（历史脏数据自愈）
- 全量：`172 passed / 1 skipped / 1 deselected`。
- 后端验证：`/api/snapshot?session=dfea6846` 与 `d1252ad9` 返回的 `aux` 均为空。

### 取舍说明

- **不漏检 vs 不误检**：散文判据继续接受「漏检」（陌生人只说了一句无称呼的台词，本轮不登记），优先保证不误把「胁语气」这种碎片塞进左栏。旁路仍是导演显式【引入角色】指令。
- **真名误伤风险**：过滤条件只针对明显非人名的结构（以「语气」结尾、以「地」结尾、等于「想要」）。真名如「会哥」「想容」测试通过；「老王」「大雄」等真名前缀未被加入拒绝列表。

---

## 2026-10-05 v0.17.0（移除事实保全机制 + 左栏重构为「只答世界是什么样」+ 上下文窗口扩容）

- **升 v0.17.0：MINOR 档**。判定依据：本轮移除 `facts` 快照字段与 `POST /api/fact/invalidate` 路由属**不兼容变更**（旧会话快照里的 `facts` 会被忽略；调过该路由的外部代码会 404），按规范至少 MINOR。0.x 阶段不跳 MAJOR——1.0.0 是里程碑决策，不该由一次收口触发。
- 本轮起因是一串左栏 UI 讨论，最终牵出一个存在多年的架构问题：**事实保全机制在当前容量下是冗余而非保险**。逐条记录如下。

### 改动一·整体移除事实保全（`director.py` / `prompter.py` / `memory.py` / `app.py` / `index.html`）★本轮最重要的变更

- **完整设计与实测数据存档至 `engine/FACT-MEMO.md`**（进 git 仓库，不进分发包）。六节：设计初衷与真实作用偏差、移除前的四组实测数据、完整实现规格（数据结构/分类/判据/举证核验/折叠/注入位置/矛盾自检/纠错通道/前端）、**复装步骤（7 步）**、踩过的坑（3 条）、结论存档。将来上下文真正逼近容量边界时**照该文档复装**即可。
- **移除依据（数据，非印象）**：
  1. **它在抄正文**——抽样比对会话 3e19589c 的 10 条事实与同会话叙事原文的关键词重合度：「沈川低声自语活着真好」3/3、「苏青在门外声称腿被咬」2/4、「沈川拉开入户门」0/2。内容 history 里本来就有一遍。
  2. **记忆效果来自 history 而非 facts**——80 轮实测，轮距 3（窗口内）事实召回 10/12，轮距 38（压缩区）10/12，**两段无差异**。
  3. **核心用途从未被验证**——80 轮压测**一个角色都没真死过**（精确死亡模式全扫描 0 命中）；26 条 facts 里 core 类（death/disable/destroy/identity）为 **0 条**。
  4. **容量远未触线**——80 轮 prompt_tok 峰值 15240，模型 `n_ctx=131072`，**占 12%**。设计前提（history 装不下）尚未成立。
- **定位澄清**：它的真实定位不是「记忆补充」而是「纪律压制」——history 负责**记住**，facts 负责**不许违反**。但两者记录同一批信息，故容量充裕时 facts 是冗余。详见顶部长期提醒。
- 代码移除：`FACT_*` 常量 / `_fact_group` / `add_facts` / `_compact_facts` / `invalidate_fact` / `check_fact_conflicts` / reflect 调用 / 提示词 24 行判据 / `[既定事实（不可违背）]` 注入块 / `facts` 快照字段 / 作废路由 / 前端「不可逆事实」面板。`tests/test_facts.py` 归档至 `backups/remove-facts-20261005/`（不删，保留历史参考）。

### 改动二·新增快照玩家视图投影（`app.py`）★防剧透

- 内部快照含大量不该给用户看的东西：秘密的完整真相与暴露后果、发酵压力数字、命中词表、关系冻结基准、称呼速查。原先 `/api/snapshot` 与 `/api/session/new` 把**整个快照**发给前端，打开 DevTools 即见全部真相——而 `prompter` 明确写着「pressure 只存在于快照，模型永远看不到」，对模型保密、对用户却全泄露，标准不一致。
- 新增 `player_view(snap, debug=False)`：顶层白名单 + 秘密条目只留 `owner/state/known_by/suspicions`。`?debug=1` 返回完整视图供排障（**不给普通用户 UI 入口**）。`address`（称呼速查）不外发——它是防 LLM 叫错辈分的内部防错信息，属非剧情内容。
- 路由 `player_view` 全仓 grep 验证：`relations`/`actions`/`goals`/`ledger` 虽无 UI 消费者仍保留在白名单（导出/复盘/二次开发要用；白名单职责是「哪些字段可外发」，不是「哪些在渲染」）。

### 改动三·左栏重构为「只回答世界是什么样」（`index.html`）

- 起因是 simon 指出左栏信息过载会抢走叙事正文的注意力。判定标准定为：**这个字段是「世界本身」还是「叙事正文的原料」**。
- **撤下三类**（引擎的中间产物，摆出来会诱导玩家「照着面板核对」而不是「读故事」）：关系定性、每轮行为摘要、角色短期目标。
- **保留并新增**：在场角色/场景、现状（`states`，物件当前状态）、秘密（只知进展不知内容）、临时群演（蓝色底色挂在在场角色面板末尾）。
- 面板从 7 个收敛到 **3 个**（在场角色/场景、现状、秘密），默认全展开、点标题可各自收起。
- **顺带修左栏自适应滚动**（simon 亲测发现的真 bug）：根因是 `.panel` 作为 column flex 的 flex item 默认 `flex-shrink:1`，内容超出时高度被压扁再被 `overflow:hidden` 裁掉——**加了滚动条也不生效**。修法：`.panel{flex-shrink:0}` + `.rail-body{min-height:0}` + 显式滚动条样式（默认窄条在深色底上看不见，用户会以为没东西可滚）。
- **★ 建立布局实测手段**：装 `puppeteer-core`（复用系统 Chrome），新增 `tests/_probe_leftrail.js`——用 demo 真实数据在 4 个视口量测 6 条判据（可滚/无面板压扁/滚到底末面板可见/内部滚动生效/子面板不与栏目名重名/**不得出现中间产物面板**）。**保留该脚本不删**——CSS 布局问题静态检查证明不了，上一轮就是这么栽的。

### 改动四·上下文窗口与摘要预算扩容（`prompter.py`）

- `HISTORY_WINDOW_ROUNDS` 8 → **12**；摘要提取 `SUMMARY_*` 80/90 → **150/200** 字（新增常量，原为硬编码）。
- 依据：80 轮事实保真度实测——轮距 38（远超窗口）召回仍有 83%，说明骨架摘要保住了主体信息、**窗口偏保守**。
- **不推 20+**：收益递减而摘要块成本随轮数线性上升（此消彼长、非净增）。更划算的方向是摘要质量而非窗口长度。
- **这是取舍不是纯赚**：每轮摘要成本 76 → 127 tok，R200 总量 3.4 万 → 2.2 万可回退。调参决策表见顶部长期提醒「上下文窗口与摘要预算的调参结论」。

### 改动五·纪官输出格式漂移防御（`director.py`）

- 80 轮压测暴露：纪官偶发把对象字段写成字符串、对象列表写成字符串数组，抛 `'str' object has no attribute 'get'` 使**整个 reflect 回写中断**，本轮关系/行动/状态全丢且无告警。
- 新增 `_as_dict_list()` 统一过滤，应用于 5 个列表字段。**`actions` 非法时跳过本轮静默判定**（而非降级为空后照常判定——那会把在场全员误记成静默、误触发硬性焦点，一次漂移污染后续多轮）。

### 改动六·辅助群演自称消解（`director.py`）

- 现象（simon 截图发现）：左栏两个 chip「年轻女子」「苏青」实为同一人。根因是模型先用描述性称呼起段、自报姓名后改用本名，两处都被行首说话人匹配当成新角色。
- 三层修复：自称消解（认「我叫X」，保留本名）+ 泛称词表过滤 + 历史脏数据自愈（老会话下一轮自动修好）。
- **两个设计教训**：① 「我是X」不能当自称（「我是护士」报的是身份不是姓名）；② 泛称判定不能用统一匹配——「年轻女子」需包含匹配但「李医生」不能被误伤，拆成「修饰后缀用包含 / 完整词用全等」两组。

### 改动七·打包排除内部备忘（`package.py`）

- 新增 `EXCLUDE_FILES`（文件级）——原有 `EXCLUDE_SUBPATHS` 只管目录级。`FACT-MEMO.md` 是写给开发者的实现备忘（含已移除机制的细节），不该让用户看到，故进仓库但不进分发包。

### 验证

- `pytest tests/`：**158 passed / 1 skipped**。
- 四视口（1090×876 / 1400×800 / 1280×620 / 1920×1080）浏览器实测全过；Node `--check` 内联 JS 语法通过。
- 端到端（移除 facts 后）：建会话 200、快照无 facts、reflect 正常、prompt 无 `[既定事实]` 块但保留 `[关系与状态]` 块。
- **压测未跑**：本轮未改 director 推演/关系/秘密记账的**度量**路径（改的是 UI 呈现、快照出口、窗口策略、输入防御），按红线不触发 30 轮压测。

## ⚠ 长期提醒·已移除「角色名：」分段格式契约（2026-10-05，simon 亲测后定）

**结论**：v0.16.1 加的 `[分段格式]` 块**已整体移除**。叙事正文观感优先于机制完整度。

### 为什么移除（simon 亲测反馈）

该契约是为修「模型 30/30 轮改用散文引号、导致 5 处机制静默失效」而加的，但**它把叙事正文观感明显拉低了**：原本以散文为主体的正文（大段环境/动作/心理描写 + 引号对白）被压成「角色甲：（动作）台词」的流水账。

**根因是我的规则外推错了**：机制只要求「行首是 `角色名：` 的行能被识别」，我写成了「**每一段发言或动作**都另起一行」——把动作描写也强制成了分段。而我给的示例本身就是三行流水账，模型照着它写，散文能力被进一步压制。

### 移除后 5 处机制怎么办

| 机制 | 处理 |
|---|---|
| `detect_offscreen_activity` 背景人物失责 | **补第三判据**：引号紧跟背景名（「“老王。”他转身」）。原有第二判据（第三人称段落 + 动作信号）本就覆盖散文体 |
| `_AUX_SPEAKER_RE` 群演登记 | **加散文形态判据**（见下），并接受明确取舍 |
| `validate_present` 离场剥离 / 镜头裁剪 | **不改**。失败后果是「不剥离」而非「破坏正文」（`present_violation` 仅告警），降级安全 |
| 已故者开口检测 | 已随 v0.17.0 事实保全机制整体移除 |

### 群演登记的散文判据与已知取舍（重要）

判据为「**人名 + 说话动词 + 引号**」（如「角色丙说：“水够吗？”」），另加两道清洗：切掉被贪婪匹配吃进名字的动词/状语尾部（「角色丙说」）、切掉被叙述词污染的前缀（「他转向角色丙」）。

**为什么不认「引号紧跟名字」**：实测误判率极高。模型写的「“角色乙，”角色甲没有抬头」（引号内是人名）与「“从今天起，”他的声音不高」（引号内是台词内容）在字面上无法区分——实测一轮正文能误抓十几个碎片（「从今天起」「我腿软」「真的要去吗」…），会把群演注册表填满垃圾。

**为什么不认「名字 + 说话动词」宽松匹配**：中文无词边界，「角落里老陈咳了一声」会让贪婪匹配切出「角落里老」，非贪婪又漏掉「老陈」，试过非贪婪/后向断言/窗口扫描均不可靠——**中文人名边界本身不可机械判定**。

**明确接受的代价**：模型若写成「那个陌生人咳了一声。“水够吗？”」，该群演**本轮不登记、下一轮才发现**。漏检只是群演晚一轮进左栏；误检则会让左栏出现「从今天起」这种根本不存在的角色——后者代价大得多。**旁路仍在**：导演可用【引入角色】指令显式登记（`parse_aux_introductions`，不依赖任何正文形态），这是散文剧本下最可靠的入口。

### 立此为长期判据

**机制检查与叙事观感冲突时，观感优先。** 机制可用降级路径（告警而非破坏）、可换不依赖格式的判据，但不可为保机制而牺牲正文质量。反之，若某机制只有靠「限制模型写法」才能工作，说明它**尚未找到正确的判据**——应先找判据，而不是约束模型。

## ⚠ 长期提醒·事实保全机制已移除（2026-10-05 v0.17.0，设计存档见 FACT-MEMO.md）

**一句话**：事实保全（`facts` 常量层）整体移除。完整设计与实测数据存 `engine/FACT-MEMO.md`（不随分发），将来上下文真正逼近容量边界时**照该文档复装**即可，无需重新发明。

### 移除依据（数据，不是印象）

- **它在抄正文**：抽样比对会话 3e19589c 的 10 条事实与同会话叙事原文的关键词重合度——「沈川低声自语活着真好」3/3、「苏青在门外声称腿被咬」2/4、「沈川拉开入户门」0/2。**内容 history 里本来就有一遍**，facts 表是同一信息的第二次记录。
- **记忆效果来自 history 而非 facts**：80 轮实测，轮距 3（窗口内）事实召回 10/12，轮距 38（压缩区）10/12，**两段无差异**。记忆是 history 的功劳。
- **核心用途从未被验证**：80 轮压测**一个角色都没真死过**（精确死亡模式全 80 轮扫描 0 命中；早期「71/80 轮含死字」是误判，全是「死死/死寂」）；26 条 facts 里 core 类（death/disable/destroy/identity）为 **0 条**。
- **容量远未触线**：80 轮 prompt_tok 峰值 15240，模型 `n_ctx=131072`，**占 12%**。facts 表的设计前提（history 装不下）尚未成立。
- **代价明确**：占 prompt、条目膨胀（会话 557af4b0 达 16 条）、还要前端折叠。

### 定位澄清（重要）

它的真实定位不是「记忆补充」而是「纪律压制」——history 负责**记住**，facts 负责**不许违反**。但两者记录的是同一批信息，所以在容量充裕时，facts 提供的是**冗余而非保险**。

### 顺带修正的两个记录错误

- 曾按字数比例折算摘要成本得「97→约 190 tok」，真实函数实测是 **76→127 tok/轮**。
- 曾统计「71/80 轮含死亡」，实为「死死/死寂」误判。

### 若将来复装，先验证前提

实测 tok 逼近 n_ctx，**或**观测到早期事实被遗忘导致叙事漂移——两者之一成立才值得复装。前提不成立就复装只会引入噪音。复装步骤与完整规格见 `FACT-MEMO.md` 第四、五节（含踩过的坑：不要用代码层词表做语义降噪）。

## ⚠ 长期提醒·环境、阈值与调参结论（2026-10-05）

### 0. 上下文窗口与摘要预算的调参结论（先读这节再动 `HISTORY_WINDOW_ROUNDS`）

**当前值（v0.16.1 起）**：窗口 `HISTORY_WINDOW_ROUNDS = 12`（此前 8），摘要提取 `SUMMARY_DIRECTIVE_CHARS = 150` / `SUMMARY_NARRATIVE_CHARS = 200`（此前 80 / 90）。

**依据（80 轮事实保真度实测，产物 `tests/runs/v0.16.1_factretention80.json`）**：
- 轮距 3（窗口内、原文在上下文）召回 10/12；**轮距 38（远超窗口、仅剩骨架）召回 10/12**——两段几乎无差异。
- 逐条核查那 4 次「遗忘」**无一为真遗忘**：3 次是回问被当场剧情线盖过，1 次是判据措辞问题。最有力的是 R50——问「楼道里几扇门」，模型答的是「那张被图钉钉在墙上又揭下来的纸片地图」，它不但记得 R24 植入的种子还接着推了剧情。**说明骨架摘要保住了主体信息，窗口还有很大扩容空间，8 偏保守。**
- tok 峰值 15240（R78）仍无容量型衰退（呼应第 1 节）。

**为什么不推到 20+**：收益递减而**摘要块成本随轮数线性上升**——窗口外每轮都占一份摘要，推窗口换来的空间会被摘要吃掉一部分，此消彼长、非净增。

**更划算的方向是摘要质量而非窗口长度**：同样的窗口下，提取字数越多保住细节越多，且不增加窗口外的上下文规模。故本次两者同调。

**未做**：本次未跑 80 轮复测（simon 指示先落地）。若日后发现事实细节召回下降或叙事变糙，优先调摘要字数（`SUMMARY_*`），其次才动窗口。

#### 这是一次取舍，不是纯赚——分发后按用户反馈调整

**当前配置是针对「多数会话在 100 轮内」这一假设选的。** 但引擎会随包分发，其他用户拿什么剧本、跑多长，我们无法预知。收到反馈时按下表判定方向，**不要凭感觉调**：

| 用户反馈的现象 | 说明什么 | 往哪调 |
|---|---|---|
| 长会话（100+ 轮）后**叙事质量下降**：回复变短、变机械、重复套路、角色性格漂移 | 摘要块占 prompt 比例过高，骨架噪音盖过窗口内细节 | **先降 `SUMMARY_*`**（150/200 → 80/90）。这是最快的止血手段：摘要块每轮省约 50 tok，R200 时总量从 3.4 万降到 2.2 万 |
| 中等会话（40~80 轮）就**忘记早期具体事实**（对话细节、谁说过什么、物件状态） | 窗口太短或摘要提取太短，早期内容只剩骨架 | **升 `SUMMARY_*`**（回到 150/200）或**升 `HISTORY_WINDOW_ROUNDS`**（12 → 16）。先试前者——同样上下文总量下保更多细节，性价比更高 |
| 抱怨**最近 12 轮内的细节都记不住** | 与压缩无关，是模型对中段内容的注意力问题 | 调窗口无效，应查 `count_tokens` 是否虚高、回复是否超长挤占预算，或考虑给纪官开更长 max_tokens |
| 回复**开头几轮就崩**（短会话即劣化） | 与本节无关 | 查 prompt 固定开销：系统块、角色卡、世界书注入。当前实测固定开销约 4238 tok，若用户剧本角色卡/世界书特别大，这里会顶满 |

**关键判据是「摘要块占 prompt 的比例」，不是总 tok。** 实测（真实 `compress_history` 输出）：

| 轮数 | 摘要块 tok（12/150-200） | 总 tok | 摘要占比 |
|---|---|---|---|
| R40 | 3809 | 13600 | 28% |
| R80 | 8859 | 18700 | 47% |
| R120 | 13900 | 23700 | **59%** |
| R200 | 24100 | 33900 | **71%** |

对照旧配置（8/80-90）：R80 摘要占 40%、R200 占 65%。

- **摘要占比 < 40%**：安全区。
- **40%~60%**：警戒区，叙事细节开始可能被稀释（当前配置在 R80~R120 落在此区）。
- **> 60%**：应视为超标。摘要块本身就是一长串格式重复的「R37｜指令:…｜叙事:…」，模型对它的注意力会快速饱和——**这比总 tok 更值得监控**。
- 模型 `n_ctx = 131072`，绝对容量远不是瓶颈（要 1000 轮以上才触及），**不要拿总 tok 当安全线**。

**为何默认取 12/150-200 而非 8/80-90**：80 轮实测轮距 38 的事实召回仍有 83%，说明骨架摘要信息量够用而窗口偏保守；放大摘要字数是「同样的窗口保更多细节」，代价是总 prompt 涨得快（每轮摘要成本 76 → 127 tok）。**在 100 轮内的使用场景，这个交换划算；若用户普遍跑 200 轮以上，应把 `SUMMARY_*` 调回 80/90。**

**未验证的边界**：上述 R100 以上全部是外推（实测只到 R80）。若要真定位，须跑一次 150 轮。

### 1. tok 5300 阈值已作废，别再当安全线

v0.6.4 时代探针定位的「tok≈5300 起叙事显著衰退（len_drop 34%+）」来自 `compress_history` 落地**之前**的架构，**当前架构下不成立**。

v0.16.0 架构 30 轮压测实测（Qwen3.8-27B 本地，4 卡，0 异常）：
- prompt_tok：R1=3765 → R20 峰值 12589 → R30=11731；**tok 增量前 10 轮 +706/轮、后 10 轮 −86/轮**——`compress_history` 窗口滚动已生效，prompt 规模在 ~12k 处**封顶**而非无限增长。
- 回复长度：前 1/3 均 1617 → 后 1/3 均 1466，趋势斜率 −4.13 字/轮，峰值 R15=2291。
- R15→R20 出现 27% 回撤，但发生在 tok 平台期（R15 时 tok 已 11584），属内容类型差异（秘密暴露后的高潮回落），**不是容量衰退**。指令遵循 27/27 也支持未衰退判断。
- **结论：tok 12589（远超旧阈值 5300）仍未见容量型衰退。** 真实拐点需更长会话（>60 轮）才能定位。引用该阈值前请先说明它是历史数据。

### 2. 本机后台跑引擎服务不可靠，改用 in-process

三种常规方式全部失败（进程随父 shell 结束被杀，netstat 查不到监听、curl 拒绝连接）：
- `nohup python app.py &`（Git Bash）
- `setsid`（**Git Bash 无此命令**）
- `subprocess` + `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`（Windows，进程仍被杀）

**可行方案：in-process 调用**——用 `app.test_client()` 直调完整 `/api/act` 链路，绕开服务驻留。已验证与 HTTP 路径等价（同样的 SSE 解析、快照返回、机制统计）。v0.16.0 压测即用此法（临时脚本 `tests/_stress_inproc.py` + `tests/_analyze_inproc.py`，跑完未入库）。
注意：`app` 模块须先 `import` 才能用 `test_client`；另需清空代理变量（`http_proxy` 等六项），否则请求会被代理劫持。

---

## ⚠ 长期提醒·引擎的最优适配面

**引擎是泛用的，不为任何具体剧本设计。** 但这套机制组合**内含对剧本的隐含适配偏好**，写新剧本、做新 demo、评估新玩法前请先对照本节，避免在不适配的剧本上浪费力气，也避免误以为引擎「只能」跑某类戏。

### 适配面：长时同域群像

| 机制 | 剧本需具备什么才有效 |
|---|---|
| `AUTO_TIME_THRESHOLD` + `same_scene` 防僵死保护 | 存在「长时间不挪窝」的段落 |
| 冷却后强制推进（曾修「每轮清零导致永不达阈值」的 bug） | 反复不挪窝的场景 |
| `LEAVE_KEYS`（隔开 / 留在 / 留守 / 挡在门外 / 回房） | 同一屋檐下有人被隔离 |
| `SILENT_THRESHOLD=2` 静默轮 + 硬性焦点 | 多角色长期同场轮转，个别被冷落 |
| `PRESSURE_MAX=5` 秘密发酵 + 高压档强制进镜头 | 秘密在同一场域被反复触及、逐步逼近爆发 |
| 镜头 `sticky`（焦点跨轮黏住） | 焦点对象持续在场 |

**归纳**：角色集合稳定 + 场域稳定 + 秘密能在同一批人之间持续发酵。
**引擎的卖点是「关系与秘密的记账」**——谁和谁什么关系、谁藏了什么、何时爆发。demo 与新剧本应优先展示这一层，而非考验 LLM 自身的长程规划（往哪走、怎么活）。

### 两点常见误解

1. **「固定空间」不是唯一形态，只是最稳的一种。** 引擎对「移动」本身无偏见——**移动中的封闭群像**（深海飞船、列车、远行商队、太空船）场域虽变，但人物集合与关系网稳定，上述机制照样全部生效。判据是「同域」，不是「不动」。
2. **不是引擎的局限，是选型问题。** 移动式末日逃亡等剧本更吃 LLM 的长程规划能力，那不是本引擎的卖点——在不适配的剧本上评估引擎，等于用错尺子量。

### 随包 demo 的选型依据

随包 demo 应选**最贴近该适配面**的剧本，让玩家在最短时间内看到引擎能做什么。v0.16.0 起，随包 demo（丧尸末日）已据此改造：场域从「世界」收成**局域**（公寓单元 / 楼道 / 地库三子空间互牵制），尸潮从「转移推力」降级为**压缩时间窗的倒计时**——目标是激活上表全部机制。

---

## 2026-10-05 v0.16.1（输出格式：显式定义「角色名：」分段契约）

- 升 v0.16.1：PATCH 档——修复 v0.16.0 压测暴露的机制盲区（模型改用散文引号写对话，致 5 处台词块匹配机制静默失效）。属行为修正，无全新对外能力，故 v0.16.0 → v0.16.1。
- 起因：v0.16.0 收口后跑了一次 30 轮长上下文压测（in-process），全程 0 异常，但发现**段格式说话人 0/30**——模型每一轮都改用散文引号「」写对话。原因：`prompter.py` 的 `[输出格式]` 块从未定义过「角色名：」的写法，而引擎有 5 处机制靠**行首「角色名：」**匹配台词块。
- **受影响的 5 处机制**（模型不遵守格式时全部静默失效）：
  1. `director.validate_present`——离场角色台词块剥离（含镜头外角色裁剪）
  2. `director.detect_offscreen_activity`——背景人物失责检测
  3. 已故者开口检测（死人开口告警）
  4. `_AUX_SPEAKER_RE`——辅助群演自动发现
  5. 镜头跟随的台词块裁剪
- **为什么压测当轮没暴露后果**：全程无人离场、无背景人物发言，present 违例 0。属运气——一旦剧本出现离场或背景人物发言，这 5 处会直接失效且无任何告警。
- **修复**（`prompter.py` 新增 `[分段格式]` 块）：四条硬要求 + 形式示例。
  - 每段发言或动作另起一行，以在场角色名加冒号起头（如「角色甲：……」）
  - 只有环境描写、内心活动可用无角色名的独立行
  - 同一角色的连续台词与动作可合并在同一段
  - **严禁用引号代替分段**——并写明原因：引擎靠行首匹配识别每段是谁的发言，改用引号会导致离场角色台词无法剥离、背景人物发言检测不到
  - 示例一律用中性占位（角色甲/角色乙），守引擎普适性红线
- **实测生效**：修前段格式 0/30 轮；修后同卡组同指令 3 轮分别 7 / 5 / 6 段命中。5 处机制恢复可用。
- 附带：`tests/test_universality.py` 护栏新增「`_` 前缀工具脚本豁免」——压测探针一类脚本跑完即删、不入库，绑定真实卡组是其用途本身，不该被普适性红线拦下。`test_prompter.py` 新增 2 条（分段格式契约存在性 / 示例使用中性占位）。
- 另记两条长期结论到 DEVLOG 顶部「⚠ 长期提醒」：tok 5300 阈值作废、本机后台跑引擎不可靠（改用 in-process）。
- 验证：`pytest tests/` 157 passed / 1 skipped。

## 2026-10-05 v0.16.0（亲属身份冻结修正 + 秘密条目不再占用注入配额 + demo 全面审计修复）

- 升 v0.16.0：MINOR 档——① 新增角色卡可选字段 `relations_kinship`（显式声明血缘，绕过词表猜测）；② `world.scan` 新增 `include_secret` 参数，秘密条目不再占用 `max_entries` 注入配额。两项均为新增对外能力且可观察行为改变，故 v0.15.0 → v0.16.0。
- 本轮起因是一次随包 demo 全面审计，暴露 5 类问题（其中 2 类属引擎缺陷、3 类属 demo 数据）。逐条结论见 [TODO.md](./TODO.md)「附：随包 demo 审计与修复」小节。

### 改动一·秘密条目不再占用 max_entries 注入配额（`world.py` + `app.py`）★本轮最重要的修复

- **缺陷**：秘密条目（`secret: true`）不进入 prompt——它只在角色块里按已知状态给提示，或供编辑器预览/元信息查看。但 `world.scan` 原先把秘密与普通设定一起塞进 `matched`，共同参与 `max_entries=8` 的截断竞争；`app.py` 拿到结果后才把秘密剔除（`world_hits = [e for e in hits_all if not e.get("secret")]`）。**结果是秘密白白消耗注入配额、却一行都不注入。**
- **实测证据（demo 压力轮）**：指令「沈川被咬，黑紫纹路，尸潮逼近庇护所，物资稀缺」下 `scan` 返回 8 条，其中秘密 3 条（沈川/周岚/周子航）——真正注入 prompt 的只有 5 条。秘密占掉 3 个配额后，**优先级 56 的「逼近的尸潮」被静默丢弃、无任何提示**。而这条恰是该世界书里唯一驱动「众人必须离开」的推力条目，戏剧最需要它的时刻反而看不见。
- **修复**：
  - `scan()` 新增 `include_secret=True` 参数。秘密命中单独收进 `secret_matched`，**不参与 `max_entries` 截断**；`include_secret=True` 时附在返回列表尾部，供编辑器命中预览与 `app.py` 的 `wb_meta`「排除秘密」清单继续可见。
  - `_resolve_recursive()` 返回值改为 `(matched, ref_secret)`：被引用拉入的秘密同样单独返回，不进注入列表。
  - 被引用的**非秘密**条目排到 `matched` 末尾之后（原先会按自身 priority 重新参与排序）——依赖项的优先级由引用方决定，不该凭自身 priority 抢位挤掉引用方的其他命中。
  - `app.py` 两处调用（`/api/act` 运行时、`/api/world/<name>/test` 预览）均传 `include_secret=True`，保证秘密命中信息不丢。
  - 保留原行为：常量秘密（`constant: true`）仍无条件纳入（`constant` 分支在 secret 判断之前），行为不变。
- **效果**：同一压力指令下设定注入从 5 条 → 6 条，**「逼近的尸潮」被救回**。修后最坏轮 7 条设定全部保住，无丢弃。
- **定性问题**：秘密「不进 prompt」就不该消耗「注入 prompt 的名额」。这不是取舍问题而是定义层错误——配额的意义是有限的注意力预算，参与竞争的都必须是真正要注入的内容。

### 改动二·亲属身份冻结修正（`director.py` + `memory.py`）★引擎定义层缺陷

- **缺陷**：`_preserve_kinship` 冻结血缘身份时，靠 `_first_kinship(base_val)` 从关系描述里**用词表猜身份**。两处错误叠加：
  1. `_KINSHIP_TOKENS` 混入 22 个单字词（母/子/夫/弟/姑/侄…），而单字在中文里几乎只作为长词碎片出现（母子、母性、夫人、兄弟、弟弟）。demo 的 12 条关系里 **8 条被误判**。
  2. 「取全文首个身份词」的策略语义上不成立——关系定性是叙述长句，句中身份词常指**第三方**（「她不敢戳破父亲已死」里的父亲是别处的人），不是这条边两端的关系。
- **实测误判**：`周岚 → 沈川` 的描述含「周岚母子的生死」→ 命中「子」，模型若写「妻子」会被回退成**「子，关系紧张」**；`周子航 → 周岚` 身份应为母亲，却因句首先出现「父亲」→ 命中「父亲」，模型写「母亲」会被反冻；`林小满 → 周岚` 是纯队友关系，因「尊重她的母性」→ 命中「母」被冻成「母，关系紧张」。
- **修复**：
  - 词表只收**双字及以上**完整身份词，单字一律剔除。
  - `_first_kinship` 改为只认两种**显式声明**形态：身份词在值开头紧跟分隔符（`母亲：`/`父亲，`），或整值就是裸身份词（`父亲`）。叙述句中间的身份词不构成声明。新增 `_KINSHIP_DECL_RE` / `_KINSHIP_ONLY_RE`。
  - **新增能力** `relations_kinship`：角色卡可选字段 `{"角色B": "母亲"}`，由作者直说血缘，不再依赖描述文案的写法。新增 `director.seed_kinship_from_cards()`（只收词表内合法身份词，「同事/恋人」等非亲属关系不入表）；`memory.new` 落 `kinship_base` 键；`reflect` 冻结时 `_preserve_kinship(base, v, declared=kinship.get(k))`，`declared` 优先于句首推断。
  - 向后兼容：老快照无 `kinship_base` 时 `.get(...) or {}` 兜底，走句首推断，功能不失效（已实测）。
- **立意**：亲属身份是**作者定义的固定事实**，不该靠从散文里猜词。词表猜测降级为无法结构化时的兜底弱规则。
- 验证：demo 12 条边误判 8 → 0；冻结功能仍有效（`父亲，严厉` + 模型写「母亲」→ 拉回「父亲，关系紧张」）；情感演化仍放行（`父亲` + `父亲，关系彻底破裂`→ 放行）；`pytest` 新增 8 条覆盖边界。

### 改动二之二·输出格式：显式定义「角色名：」分段契约（`prompter.py`）

- **压测发现的机制盲区**：v0.16.0 架构 30 轮压测中，模型 **30/30 轮**改用散文引号「」写对话，「角色名：」段格式说话人 **0**。原因是 `[输出格式]` 块从未定义该格式，而引擎有 5 处机制靠「行首『角色名：』」匹配台词块：`validate_present` 离场角色台词块剥离、`detect_offscreen_activity` 背景人物失责检测、已故者开口检测、`_AUX_SPEAKER_RE` 辅助群演发现、镜头跟随台词块裁剪。改用散文引号 → 这 5 处静默失效。
- 压测当轮未暴露后果（全程无人离场、无背景人物发言，0 违例），属运气——一旦有角色离场或背景人物发言，剥离与检测即失效。
- **修复**：新增 `[分段格式]` 块，四条硬要求（每段另起一行以「角色名：」起头、仅环境描写与内心活动可无角色名、同角色连续发言可合并、严禁用引号代替分段）＋形式示例（用中性占位「角色甲/角色乙」，不写具体剧本名以守普适性红线）。
- 实测生效：修前段格式 0/30 轮，修后同卡组同指令 3 轮分别 7 / 5 / 6 段命中。5 处机制恢复可用。

### 改动三·测试层解耦具体剧本（`tests/`，纯测试重构不动引擎）

- 新增 `tests/fixtures.py`：中性占位（角色甲/乙/丙/丁）+ `make_card`/`make_cards`/`card_loader`/`fake_list_characters`。全量替换 13 个测试文件里的具体角色名与题材词。
- 消除磁盘依赖：`test_focus_follow`（`store.load_card` 走 fixtures）、`test_ending`（`list_characters` 改 autouse fixture 注入中性卡组）。
- 压测/走查脚本改为运行时从 `/api/characters` 取卡组：新增 `fetch_cast()` + 弧线模板（`{A}`..`{E}`）+ `build_arc()`，CLI 增 `--cast`/`--scene`。换剧本压测无须改脚本。
- 新增护栏 `tests/test_universality.py`（4 条）：禁测试出现具体剧本名/题材词、禁测试直读磁盘剧本目录、禁引擎源码硬编码角色名、fixtures 自身完整性。
- **关键验证**：把 `engine/data/characters` + `engine/data/worlds` 整体移出工作区，`pytest tests/` 仍 141 全绿 → 测试自给自足、换剧本不红。
- 顺带修过期断言：`test_intimacy_scale.py` 断言的是 v0.11.0「亲密描写尺度」措辞，v0.15.0 铁律⑧ 改中性折衷后恒红 3 例，按当前措辞重写并补「旧措辞已移除」的反向断言。

### 改动四·文档举例中立化（`worldbook-guide.md` + `static/worldbook-guide.html`）

旧剧本举例（高洋/林晚/末日丧尸/apoc）全部换为中性占位：角色名→角色甲乙丙，示例世界书整组换成通用处境（「镇内禁令」+「五人被困城郊仓库」+「城东临时集散地」），世界书名 `apoc`→`example`。两文件残留 0，md 与 html 章节结构仍一一对应（各 10 节）。

### 附带（随包 demo 数据，不属引擎能力但影响机制展示）

- **秘密 keys 去裸词**：5 条秘密的 keys 原含 `"秘密"` 与纯角色名，实测「这场戏的秘密在哪里」**命中全部 5 条**，秘密机制形同废掉。已删裸词「秘密」「愧疚」与 4 个纯角色名，改为具体发现动作/物证词。修后过度触发归 0。
- **补 `#name#` 递归引用演示**：新增「地铁通道」条目，与「临时庇护所」「逼近的尸潮」接成三段链——庇护所（唯一撤离通道是地铁通道）→ 地铁通道（那条路正对着尸潮来的方向）→ 尸潮（留下等门破、离开要穿尸群，没有第三条路）。把三条独立设定接成结构性两难，任一端被提及即拉入整链。
- **故事层面调整**：「丈夫失联」秘密由周岚移交周子航（周岚独占 2 条的问题随之解决，秘密 5→4 条）；周子航原秘密「压抑已久的恨」整段删除——新秘密「早已看穿父亲已死却配合母亲演」接管他原有的寻父执念与顶撞动机，对 18 岁人设更贴。周岚卡 5 个字段与周子航卡 5 个字段同步改写。
- **随包 demo 定位改造（长时同域群像，simon 定）**：原 demo 是移动式末日逃亡（尸潮迫近→转移），查代码发现引擎有六处机制在移动式下**完全空转**——`AUTO_TIME_THRESHOLD`+`same_scene` 防僵死（每轮 place 都变，计数归零）、冷却后强制推进、`LEAVE_KEYS`（隔开/留在/留守/挡在门外）、`SILENT_THRESHOLD=2` 静默轮、`PRESSURE_MAX=5` 秘密发酵、镜头 `sticky`。据此改造（详见「长期提醒·引擎的最优适配面」一节）：
  - **场域从「世界」收成「局域」**：新建三子空间互牵制链——`公寓单元`(p60) →#`公寓楼道`(p59) → #`地库`(p58)。提及任一子空间即拉入后续（子空间切换仍走 `scene.apply`，场景机制不闲置）。原「地铁通道」条目删除（出口已无意义）。
  - **尸潮从「转移推力」降级为「时间倒计时」**：「逼近的尸潮」重写为「四下没有可去的地方……问题只剩两个：门能撑多久，以及在那之前屋里的四个人要先解决什么」——不再驱动位移，而是压缩每轮的可选项。
  - **新增张力源**：「物资与交易体系」改为「物资与配给」常量（按天配给、出工力多领一份 → 人人都盯着别人碗里的）；「感染的临界」补上「在哪儿处理、瞒不瞒着其他人」一层（局域才有的空间压力）；「背景」补断电/停电梯/无信号。
  - **四张角色卡同步去除移动式表述**：沈川 short_goal 改为「守住这栋楼、把地库那几箱东西弄上来、把配给权攥在手里」；周岚去掉「寻找庇护所」，改为「守住儿子、把这层楼待下去」；周子航由「寻找父亲」改为「逼母亲说出真相，却用一次次下地库来逼自己不必承认」；林小满的秘密落点接上「如今她面对周子航的高烧，又一次选择了不放手」——旧队覆灭与眼前重演形成同域对照。
  - 世界书 13 条（3 常量 / 4 秘密 / 6 情境），实测压力轮注入 8 条（顶满上限且秘密不占配额）、四条秘密均按具体发现动作触发、过度触发与噪音均为 0。
  - `script-example.txt` 与前端内嵌同文整体重写（标题从「丧尸末日生存」改为「困守一栋楼」），HTML 表格示例与说明文字同步对齐。
- **`max_entries=8` 判定无需提高**：实测 demo 物理上限就是 8（12 条 = 3 常量 + 4 秘密不进 prompt + 5 情境），cap 设 8/10/12 时最坏轮注入结果完全相同（都 7 条）；最坏轮整 prompt 1122 tok，仅占 5300 衰退阈值的 21%，稀释在当前量级不成立。真正的扩容手段是提高条目质量，而非放宽上限。详见 TODO.md 对应小节。 补充（simon 征询「日后遇到庞大剧本是否该扩容」后的架构判断）：`max_entries=8` 是默认值而非硬性终点，**赞成放宽**，但判据是**设定总字数**而非条目条数。实测 30 条世界书全命中的最坏情况：cap=8 注入 1158 字（占 prompt 35%）／cap=12 1756 字（41%）／cap=16 2319 字（46%）／cap=20 2990 字（53%）／cap=30 4490 字（67%，叠加 8 轮 history 后 108% 越线）。四条硬条件：总 token 预算优先（设定部分建议 ≤1500 字）、一次最多 +4 条、超过 30 条应拆世界而非放宽上限、放宽后必须实机验证三点指标。
 另澄清一处机制：`HISTORY_WINDOW_ROUNDS=8` + `compress_history` 使**世界书注入量每轮恒定、不随会话变长而增长**（history 只留最近 8 轮原文，更早压成固定长度摘要块），故「世界书挤占叙事空间」只与单轮设定量有关、与聊了多久无关。5300 阈值来自 `compress_history` 落地前的探针，当前架构下偏保守但仍作安全线参照。完整判据见 TODO.md「扩容判据」小节，用户可读版同步进 `worldbook-guide.md` 第 4 节。
- 事故记录：首次改 `static/script-example-guide.html` 时用 heredoc + 行号定位，把文件写成乱码；`git checkout` 从 HEAD 完整恢复（该文件已入库，无损），改用内容锚点定位并以 `script-example.txt` 为唯一真相源覆盖 HTML 内嵌块，避免两处文档漂移。

### 验证与收口

- `pytest tests/`：**155 passed / 1 skipped** 全绿（含新增 21 条）。
- demo 侧：4 张卡与世界书 examples 副本与私人版逐项一致；`script-example.txt` 与 HTML 内嵌文逐行一致（16 行）。
- 引擎侧实测：秘密不再挤占配额、亲属冻结误判归零、三段链无死循环无重复且配额压力下全保底。
- 压测红线：本轮改动了 `director` 冻结闸与 `world.scan` 配额两处核心路径，**收口前应跑 30 轮 `stress_longcontext` + `compare_stress` 对照**（待 simon 决定时机）。
- 收口：版本号 `v0.16.0`；tag 与 zip 待打包时落。

## 2026-10-05 v0.15.0（NSFW 描写标准重构为中性折衷 + 官方 demo 随包附带）

- 升 v0.15.0：MINOR 档——① 新增「官方示例剧本随包附带 + 首次运行懒加载播种」这一独立能力；② NSFW 描写标准从 v0.14.x 的「露骨+直白+人格注入」重构为中性折衷（可观察行为显著改变）。v0.14.1 → v0.15.0。
- 改动一·NSFW 标准重构（`prompter.py`）：
  - 背景：v0.14.x 用「露骨直白+器官名清单+小雨人格注入」强推露骨，实机对照（A/B 词密度）发现露骨生效后叙事坍缩成肉戏、处境/关系/心理/推进四维密度全线下降；且长上下文下铁律⑧ 被稀释、露骨不稳定。simon 判断「露骨+叙事一起顶上去会致引擎运作不稳（越复杂越脆弱）」，拍板折衷。
  - 折衷落点：铁律⑧ 改为「亲密及性内容由剧情与角色关系自然驱动。当叙事推进到亲密场景时，须提供身临其境、有实感的性行为描述，正面写实，禁止用隐喻、环境侧写或文学化手法一带而过。尺度与颗粒度由场景与人物关系自然决定，不预设上限，也不强制克制。硬红线（法律底线）：未成年性化描写 + 真实未成年人相关内容」。
  - 撤下 `NARRATOR_PERSONA`（小雨人格）常量及其 `build_session` 首位注入；删除 `_INTIMACY_RECENCY_HINT`/`_INTIMACY_TRIGGERS` 及末尾 user 消息条件注入。尺度判断权交还模型。
  - 验证：4 轮实机（真实 4 卡+世界书）——触发门槛生效（非亲密轮 R1/R2 不硬写性）、身临其境生效（R3 亲密轮写实但不失控）、叙事质量保住（性场景始终锚定门外子航/林小满听见、雨夜末世处境，沈川自厌/周岚屈辱快感/林小满愤怒/周子航握斧心理层次全在场）。与 v2 里「露骨致叙事坍缩」形成反证。
- 改动二·官方 demo 随包附带（`store.py` + `engine/data/examples/`）：
  - 新增 `_seed_examples()` 懒加载种子：`list_characters`/`list_worlds` 前，若对应目录为空则从 `examples/` 按名复制、不覆盖已有文件。解压即用用户首启自动看到 demo，已有私人剧本用户不受影响（目录非空不种）。
  - `engine/data/examples/` 放入官方 demo（4 角色卡 + 1 世界书 + script-example.txt），`package.py` 无需改（examples 不在排除项，自动进包；`data/characters`/`data/worlds` 仍整体排除，私人数据不泄漏）。
  - 补回 `_read_json` 定义（懒加载种子改动时误删，`load_card`/`load_world` 会 NameError）。
- 改动三·范例文档对齐（`script-example.txt` + `static/script-example-guide.html`）：
  - 旧范例文本（沈川优柔寡断/周岚封门害人/周子航被咬感染/幸存者营地）与迭代后的新 demo 严重冲突，一并重写为新设定（沈川好色支配+真心护人、周岚出卖肉体+丈夫失联、周子航撞见装不知、林小满害死旧队），世界书同步（删幸存者营地、增感染临界+尸潮+物资交易体系）。避免随包发布自相矛盾的范例误导玩家。
- 附带（私人 DEMO 数据，不入库不进 zip）：四张角色卡全字段重构为「矛盾挣扎」基调（沈川好色支配但真心护人、周岚为子卖身、周子航撞见秘密、林小满仁爱即凶器），世界书张力增删（删营地+增感染临界+增尸潮）。这些是磁盘私人剧本，不影响引擎代码。
- 收口：tag `v0.15.0`；产物 `personae-v0.15.0.zip`；清理上一版本 `personae-v0.14.1.zip`。

## 2026-10-05 v0.14.1（NSFW 标准顶满 + 开场初始化提示）

- 升 v0.14.1：PATCH 档——对 v0.14.0 的 NSFW 描写标准做行为强化（铁律⑧ 露骨档顶满）+ 一项开场 UI 体验修复，无全新对外能力，故 v0.14.0 → v0.14.1。
- 改动一·铁律⑧ 顶满（`prompter.py` `laws` 要求二）：
  - 原「须直呼其名、不得用代称或委婉语」后追加显式解剖词清单——「须直接写出解剖学器官名称（阴茎、龟头、阴道、阴蒂、阴唇、子宫、精液等）与具体动作（插入、抽送、顶弄、吮吸、舔舐、喷射等），禁用『那根物事』『下身』『私密处』『遮羞布』『那处』之类的借代或遮羞词」。
  - 背景：实机验证发现，v0.14.0 铁律⑧ 已让模型输出「性器官/私密处/物事」档，但未到「阴茎/阴道」级解剖名；simon 要求顶满。追加清单后本地 Qwen3.8-27B 稳定输出最露骨档（直书阴茎/龟头/阴道/子宫/精液 + 刺入/抽送/顶弄/喷射）。
- 改动二·开场「初始化中」提示（`static/index.html`）：
  - 点击「开始」后，引擎在后台同步调用 LLM 补全关系网与称呼（可能耗时数秒），此前前端无反馈、玩家误以为卡死。改为点击即禁用按钮 + 显示带 spinner 的「系统正在初始化，请稍等…」（accent 色）；成功进主界面/出错时复原提示位与按钮。新增 CSS `.setup-status.init`/`.init-spinner`/`@keyframes spin`。
- 根因复盘（附）：a47526ae / 8fc1d900 两会话 NSFW 未达标的真正根因是**角色卡与世界书设定自相矛盾**（世界书秘密「周岚出卖肉体」为黑暗向，角色卡沈川却是「优柔寡断/有责任感」温和版；铁律⑦ 人设底线使角色卡优先，锁死温情领队），叠加长上下文稀释（prompt≈8918 tok 超 5300 衰退阈值）。已在磁盘私人 DEMO 角色卡（沈川/周岚，不入库不进 zip）补黑暗向人设对齐世界书，属私人数据调整、非引擎代码改动。
- 验证：改卡 + 短 prompt + 顶满铁律⑧ 三者配合，3 轮探针（R1 提出「帮」→R2 解衣献身→R3 门边交合）两点均达标——沈川演出好色支配、性描写直书解剖词达最露骨档。`py_compile` 通过；`node --check` 校验 index.html 内联 JS 通过。
- 收口：tag `v0.14.1`；产物 `personae-v0.14.1.zip`（已排除私人剧本，泄漏校验通过）；清理上一版本 `personae-v0.14.0.zip`。

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
- 去除第三方原型派生描述：删代码/文档中「参考某前端」「基于某前端思路/理念」「复刻某前端」「社区搬运」等派生暗示措辞，改中性表述；保留两处主动原创性声明（与任何第三方前端无源码派生关系）。
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
