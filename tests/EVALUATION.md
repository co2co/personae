# 群像弈（Personae）深度评估标准与需求重写报告

版本：v1（2026-11-01）　基线：v2.3.0（commit d860515）
性质：方法论与验收标准文档，不改引擎行为、不新增功能面。随 `tests/` 存留，不进分发包。

---

## 0 范围与假设

- 本报告针对「推演质量与簿记正确性如何被证明」这一层，即证据体系，不是功能面扩张。
- 分析材料：`tests/DEVLOG.md`、`tests/TODO.md`、`tests/FACT-MEMO.md`、`engine/{director,world,prompter,store,llm,scene}.py`、`scripts/` 与 `tests/` 下的探针脚本、`dist/` 产物清单。
- 复核限制：本机 `engine/venv` 的基础解释器路径已失效（`...\Programs\Python\Python312\python.exe` 不存在），`pytest` 未能运行。结论来自代码阅读与 §8 的两段独立复核脚本。测试基线是否仍为 381 passed 未由本次复核确认。
  - 2026-11-09 勘误：上一条的「解释器路径已失效」不成立。`...\Programs\Python\Python312\python.exe` 一直在盘上，当时未能启动是执行沙箱拒绝该路径，不是环境损坏。同日已实测：`tests\venv\Scripts\python.exe -m pytest -q` 在瘦身前锚点 381 passed，引擎瘦身后 301 passed / 1 skipped（见 `tests/DEVLOG.md` 2026-11-09 两条）。本报告其余结论是方法论判断，不受此勘误影响。

---

## 1 当前证据体系的十个结构性缺口

每条给出：现象 → 证据 → 专家口径修法 → 合格判据。

**G1 结论建立在单次探针上，没有重复计数、没有对照、没有区间。**
证据：`scripts/_probe_repeat_stats.py:28` `N = 5`（每组 5 次采样）；`scripts/probe_history_degradation.py:74` 每档只跑一条链（`[0,8,16,24,32,40,50,60]` 各 1 次）；DEVLOG 与 TODO 中反复出现 `8/8`、`6/9`、`18/18` 这类裸计数。
现场换算（Wilson 95% 区间）：

| 报告口径 | 95% 区间 | 实际含义 |
|---|---|---|
| 主场景开口率 6/9 | 35.4% – 87.9% | 「67%」实际只支撑「不低于 35%」 |
| 分场成立 8/8 | 67.6% – 100% | 全过也只能声明「不低于 68%」 |
| 点名出场率 18/18 | 82.4% – 100% | 全过也只能声明「不低于 82%」 |
| 秘密 9/9 潜伏起步 | 70.1% – 100% | 同上 |

功效换算（α=0.05、power=0.8）：轮级二元指标要从 67% 检出 77%，每组约 316 轮；从 67% 检出 85%，每组约 88 轮；回复长度若 SD 约 300 字，检出 15% 变化每组约 25 轮、检出 7.5% 变化每组约 99 轮；配对设计（McNemar，不一致率约 0.4、位移 10pp）需约 314 对。另有一条硬事实：9 轮配对探针在任何效应下都不可能达到 p<0.05，符号检验至少需要 6 对不一致且全部同向。
修法：任何结论必须来自预注册假设、配对或随机化设计、点估计与区间、停止规则。
判据：报告里每个数字都带 n、分母、区间；无区间的数字不作为结论。

**G2 判据阈值未标定。**
证据：`REPEAT_LCS_THRESH = 500`、`ratio >= 0.5` 为源码硬编码（`scripts/_probe_repeat_stats.py:29,107`）；TODO 中「出现复读/死循环/安全泛化内容任一项即回滚」依赖人工目测。
修法：阈值必须在标注样本上标定，画 ROC/PR 曲线，按固定假阳率（如 FPR 不超过 5%）取点，报 AUC、FPR、FNR；阈值外置为配置而非源码常量。
判据：第三方重跑同一脚本能得到同一判定结果。

**G3 裁判与被测对象同源，属循环论证。**
证据：`engine/director.py:1147` `reflect()` 让模型自己从本轮叙事抽取 actions / goals / relations / secret_exposures，秘密是否「真正被揭露」的真值因此来自同一次生成链路的同一个模型，再经 `_secret_state`（`director.py:48`）推定状态。全仓库未见任何人工标注文件或标注规范。
修法：把纪官与 reflect 从「裁判」降级为「被测抽取器」，另建人工金标注集（同一批叙事，双标注加分歧仲裁，Krippendorff's alpha 不低于 0.80 方可作真值），辅助标注改用不同模型家族以规避 self-preference bias。
判据：分通道（看见 / 听见 / 被告知 / 物证 / 自述 / 承认）的 precision、recall、F1 与混淆矩阵，以及引擎判定与人工标注的一致率。

**G4 世界书是检索系统，却从未按检索评测。**
证据：`engine/world.py:65,117,124` 关键词命中、priority 排序、`max_entries` 截断；TODO 的扩容判据只统计注入条数与设定字数。
修法：建立 gold 查询集（真实指令语料加应命中条目的真值），报 precision@k、recall@k、MRR、nDCG@k，并跑 BM25 与 embedding 两条基线对照，量化关键词方案的召回缺口。
判据：召回与误召回各自有数，明确关键词命中相对基线是优是劣，劣则给出替换或混合方案。

**G5 注入预算没有硬不变量（已现场复核，见 §8 复核 B）。**
证据：常量条目不受 `max_entries` 约束（`world.py:121-125`）。40 条常量各 400 字时 16000 字一次性注入，无任何上限。
修法：以 token 口径声明整轮注入预算不变量，超限按确定性策略裁剪并落审计记录。
判据：存在测试证明任意条目输入下注入量不超过声明上限。

**G6 递归依赖的保底承诺不成立（已现场复核，见 §8 复核 A）。**
证据：被 `#name#` 拉入的条目排在 `matched` 尾部，随后 `kw_out = [...][:max_entries]` 截断，链尾被静默丢弃。TODO 中「配额压力下三子空间全保底」成立的前提是该 demo 总量本就不超过 8。
修法：二选一并写测试锁死。其一，先算依赖闭包再分配配额，引用链保底。其二，明确声明引用不保底，并把丢弃事件可见化。
判据：随机条目图加随机配额的 property 测试中，实际保底行为与文档表述一致。

**G7 采样不可复现。**
证据：`engine/llm.py:244-252` 的请求参数集只有 temperature / top_p / max_tokens / top_k 与各类 penalty，无 `seed`，出厂 `temperature: 1.0`。因此同一次探针无法重放，DEVLOG 中「间歇性」「重放时偶尔正常」类描述均属此类。
修法：两层分离。确定性层用 temperature=0 加 seed，用于回归与录制回放。分布层用 temperature>0，每配置固定 n 次采样，只允许以统计形式出结论。每次产物记录采样指纹与模型权重哈希（GGUF SHA-256）。
判据：同一命令重跑得到一致结果，分布层结论只允许以「n 次采样加区间」形式出现。

**G8 长度度量把字符与 token 混用。**
证据：TODO 关于 `max_entries` 的两张表同时出现「设定字数」与「占 5300」两列，而 5300 这个阈值本身已作废。仓库内无 tokenizer 口径，也无精确计数工具。
修法：以模型自带 tokenizer 为唯一计数口径（llama.cpp `--tokenize` 或 HF AutoTokenizer），字符数只用于人读展示。退化拐点用变点检测加 bootstrap 区间重测，因子必须同时包含注入位置（开头 / 中部 / 结尾）与注入量两个维度，当前只测了长度一个维度。
判据：任何容量结论给出 tok 口径、随机化位置、拐点置信区间。

**G9 分发与供应链无完整性证据。**
证据：`engine/requirements.txt` 仅 `Flask>=3.0`、`requests>=2.25`，无锁版、无哈希。`dist/` 内 35 个 zip 无 SHA-256、无签名、无 SBOM。仓库内无静态扫描痕迹。
修法：锁版加哈希，生成 CycloneDX 或 SPDX SBOM，发布产物哈希与署名（GitHub artifact attestation 或 Sigstore），静态扫描进测试链。
判据：任一 zip 可被第三方独立校验哈希、文件清单与依赖清单。

**G10 数据层把名称当文件名，缺路径安全与写原子性。**（安全项，严肃口径）
证据：`engine/store.py:138-147` `save_card` 仅 `name.strip()` 后即 `folder / f"{name}.json"`，`save_world`（`store.py:305-330`）同构。`engine/script_refiner.py` 的白名单字段包含 `name`，即模型产出的字符串可直接决定落盘文件名。写入均为 `p.write_text`（非原子）。未见 Windows 保留名、非法字符、Unicode NFC/NFD 归一、MAX_PATH、大小写冲突处理，未见实例并发锁。
风险类别：CWE-22 路径穿越、任意 `.json` 覆盖与删除、半写损坏、跨平台文件名失效。
修法：名称拆成安全 ID（不可注入、稳定 ASCII）与显示名（可中文）两字段，文件名只用 ID。写盘走 temp 加 `os.replace` 加 `fsync`。补一组安全回归测试与崩溃注入测试。
判据：`..\..\x`、`CON.json`、`<>:"|?*`、NFD 组合名、超过 260 字符路径、`a` 与 `A` 同名，六类输入全部被安全拒绝或安全落盘且失败可见。

---

## 2 顶尖专家会采取的做法（按学科）

### 2.1 交互叙事与游戏 AI

- 引擎承诺与模型产出分开评。Riedl 与 Bulitko（AI Magazine, 2013）对 interactive storytelling 的划分即如此。drama management 传统（Nelson 的 Matryoshka、Mateas 与 Stern 的 Façade）评估的是控制器不变量，不是文笔，Façade 当年的评估用的就是问卷加 believability 与 autonomy 分类口径。
- 把「谁在场、谁知道什么」形式化为信息状态。叙事学参照：Genette 的聚焦类型（internal / external / zero）对应镜头跟随，Chatman 的 story 与 discourse 区分对应事件层与呈现层。
- 体验测量用已发表量表，不自造问卷：ITC-GDUE（Game Experience Questionnaire）、Presence 类问卷、SUS、UMUX-Lite、NASA-TLX。专家走查用 Nielsen 十启发式加严重度 0 至 4，5 至 8 名被试可饱和约 85% 的可用性问题。

### 2.2 认知逻辑与形式化验证（本仓库最可能完全未接触的一层）

把秘密机制建模为 Kripke 结构：状态是可能世界集合，每个角色一条可达关系。`known_by` 的含义是「在该角色所有可能世界里该命题同真」。「暴露 → 已公开」等价于公共宣告（public announcement logic）。「起疑」是可能性算子而非知识算子。经典参照系是 muddy children 与 Wang Xin 谜题家族。

用 Z3 让求解器找违反例，或用 MCMAS / NuSMV 做模型检查。要证的七条不变量：

1. 单调性：知情集合不随轮次缩小，除显式遗忘或把柄转手事件。
2. 归属隔离：owner 不因他人发现而自我知情。
3. 在场性：未在场角色不得经叙述通道进入 `known_by`。
4. 通道合法性：`via` 白名单外的谓词不得产出「暴露」。
5. 公开判定：已公开等价于在场非归属者全知情，对在场集合封闭。
6. 交换性：亲缘冻结与关系演化的先后顺序可交换。
7. 无生循环：`#name#` 依赖图必须无环，或引用展开存在确定不动点。

价值在于这些是数学结论，一次成立即与模型换代无关，是真正「深」的部分。

### 2.3 LLM 评测与统计

- 成对随机化加反平衡：强制二选一，顺序随机且双侧各跑一遍，消除 position bias，同时显式控制 verbosity bias 与 self-preference bias。MT-Bench 与 Chatbot Arena 一脉的文献把这三类偏差列为默认风险，并以 judge 与人类偏好的一致率作为 judge 是否可用的前置条件，其报告的一致率在 80% 量级。
- judge 先校准再使用：Prometheus 2（开源可本地跑，论文报告与人类直接评分相关性约 0.8 量级）、G-Eval（form-filling 加 logprobs 概率加权，降低离散评分方差）。未校准前 judge 只能作筛选，不能作结论。
- 消融实验：五项机制（秘密簿记、世界书注入、focus 镜头、compress_history、STALE 提醒）各自单独关闭，同剧本同初始、顺序随机化、每格 n 不低于 30 会话，每个因变量报效应量（Cliff's delta 或 AUC）加区间加多重比较校正（Benjamini-Hochberg）。
- 假设先行：探针脚本改造成预注册格式（假设、指标、样本量、停止规则、失效判据），失败后不得调参重试。TODO 里「不做二次调参尝试」是好纪律，把它形式化即可。
- 偏好统计用 Bradley-Terry 最大似然加 bootstrap 区间（Chatbot Arena 的口径），不用裸平均分。

### 2.4 检索与长上下文

- 检索指标口径：precision@k、recall@k、MRR、nDCG@k。零样本检索的外部参照系为 BEIR。
- 基线：`rank-bm25`、SQLite FTS5（零额外依赖，符合本项目零依赖负担哲学）、本地 embedding（bge-m3 或 nomic-embed-text 加 sentence-transformers）。目的不是换方案，而是量化关键词方案的召回缺口。
- 长会话记忆基准化：自建 LoCoMo 式跨轮事实问答（单跳、多跳、时序、开放域、对抗五类），直接测 `compress_history` 丢了什么。外部参照：LongBench、LongBench v2、RULER、NoLiMa、MRCR。已知现象参照：有效利用率随上下文长度下降（Lost in the Middle，NeurIPS 2023），多轮对话中模型倾向重述早期答案并显著退化（MIT 2025 多轮实验，报告平均约 35% 下降）。
- 拐点定位：`ruptures`（PELT 或 binary segmentation）做变点检测加 bootstrap 区间，因子同时含注入位置与注入量。
- 采样侧现成工具优先于自研：llama.cpp 的 `--samplers dry,xtc,top_k,top_p,min_p`（DRY 与 XTC 是专治复读的采样器）、`--dynatemp`、`--seed`、`--temp 0`、`--no-caching`，以及 llama.cpp examples 里的 `llama-sweep` 可直接对比采样预设。复读与多样性用已发表指标：Self-BLEU（EMNLP 2018）、distinct-n（AAAI 2016）、n-gram 重复率。

### 2.5 软件工程严谨度

- 录制回放：`vcrpy` 把真实 LLM 响应存成 cassette，让集成测试变确定性可重跑，只有 live 档才走真实模型。
- property-based testing：Hypothesis 随机生成角色、条目、指令组合，锁不变量（present 永不为空、秘密态迁移合法、引用无环、注入不超预算）。现有 `tests/test_universality.py` 方向正确，缺的是随机生成器。
- mutation testing：`mutmut` 度量测试能否杀死变异，直接暴露 381 个测试里哪些是装饰性的。
- fuzzing：`atheris` 对 `store.load_card/save_card`、`script_refiner` 解析、`director.reflect` 解析入口做覆盖引导模糊（畸形 JSON、Unicode、超长、深嵌套）。
- 崩溃与并发一致性：`taskkill /F` 注入加双实例并发写，验证不产生半截 JSON、不出现「已删角色复活」（DEVLOG 已出现过一次同类根因）。
- 可观测性标准化：按 OpenTelemetry GenAI 语义约定打 span（prompt、completion、usage、model、finish_reason、延迟），使指标跨工具可比。

### 2.6 本地化与可访问性

- 字符串外置为单一真相源（key 到 zh/en 的目录），DOM 层替换可保留为渲染手段，但词典升格为受测资产，加「无未译 chrome」自动断言，覆盖 `title`、`placeholder`、`aria-label`、`aria-live` 与带变量的动态 title。
- 伪本地化扫描硬编码与截断风险。语言标签按 BCP 14，格式化按 ECMA-402 `Intl` 与 CLDR，现有 `_enPunct` 升级为 CLDR 口径。
- 译文质量按 MQM/DQF 错误分型计错（critical、major、minor，每千字错误率），参照 ASTM F2575-17 与 LISA QA Model 2012 错误权重，加回译校验。
- 可访问性：axe-core 对 WCAG 2.2 的自动通过率加键盘-only 走查加屏幕阅读器抽测，Playwright 多视口视觉回归（基线截图加像素差）。
- 流式接口正确性按 W3C EventSource 语义测：断连、重连、事件顺序、重复投递、幂等。

### 2.7 遥测（当前完全没有的一层）

- 本地埋点：会话长度分布、每轮指令原文、撤销与重试运行率、弃局点（第几轮弃局）、错误率、p50/p95 延迟与 token 成本。
- 分析口径：漏斗与流失点、弃局时间生存曲线、按剧本与模型与界面语言分层对比。
- 隐私边界：埋点全部本地，与 `engine/data/sessions/` 同级处置，不进分发包。

---

## 3 他们会用的未经加工的原始数据

引擎侧（现在已有、但未结构化）：

1. 每轮注入前与注入后的完整 prompt 原文，两版对照，用于证明注入确实发生。
2. SSE 原始分块与到达时间戳、序号、`finish_reason`、`usage`、模型标识与版本、采样参数指纹、逐轮延迟。
3. 纪官返回的原始串，包括解析失败与截断的原始尾部。抢救前的原始串是最有价值的缺陷语料，现在被丢弃。
4. 状态快照全序列：present、known_by 与 holders、relations 基线与演化、kinship_base、silent_rounds、focus 历史、locations 与 place、states 事实锚。
5. 精确 token 序列（模型自带 tokenizer）与 `logprobs` / `prompt_logprobs`，用于量化注入的设定是否真的被模型采纳，而不是靠肉眼判断。
6. 本地推理侧上下文状态：n_ctx 占用、prompt eval 时间、cache 命中、slot 保存与恢复。

人工侧（现在完全没有）：

7. 秘密事件抽取标注：span、时刻、通道、知情者集合、判定依据，加双标注原始记录与分歧样本、仲裁记录。
8. 镜头与出场标注：每轮主体是谁、焦点是否跟对、镜头外角色是否被误剥。
9. 检索 gold 集：真实指令到应命中条目的真值。
10. 体验量表原始作答与弃局记录。

外部参照语料：CharacterEval、PersonaGym、RoleLLM（角色一致性口径）、LoCoMo（跨轮记忆）、LongBench 与 LongBench v2 与 RULER 与 NoLiMa 与 MRCR（长上下文能力）、PLAUD（剧本与戏剧生成的角色一致性、情节一致性、时间线一致性、幻觉口径，NeurIPS 2024 Datasets and Benchmarks）、长篇故事类基准（以现有可得版本为准）、CLDR 数据（本地化格式基准）、NVD 与 OSV 与 GitHub Advisory（漏洞基准）、semver 与 Keep a Changelog（版本与变更规范本体）。

仓库内现成但未被利用的存量：`dist/` 35 个历史 zip、根目录与 `backup/` 下 26 个 `_backup_*` 与 `_sync_backup_*` 目录、`audit/` 内 4 份审计与验证产物、564 KB 的 `tests/DEVLOG.md`。这些是现成的变更历史语料，可反推回归率与改判率，例如同日 README 首页方向改判、v2.1.11 至 v2.1.13 号段作废、NSFW 两次上下架。决策返工率本身是过程质量的客观指标，口径见 ISO/IEC/IEEE 29119 与 IEEE 1012 的缺陷与验证统计要求。

---

## 4 工具清单（分三档）

零依赖档，标准库或现有栈内可做，优先做：

- `sqlite3` 加 FTS5：检索基线与 trace 存储，不引入第三方包。
- `statistics` 与 `math` 加自写 Wilson 区间、bootstrap、符号检验、McNemar：把 G1 补上。
- `hashlib`：产物与依赖哈希。
- `os.replace` 加 `tempfile` 加 `os.fsync`：原子写。
- 现有 pytest：把 §6 的验收条款逐条落成测试。

轻量档，纯 Python 小工具，装进 `tests/venv`：

- `hypothesis`（property-based）、`mutmut`（mutation）、`coverage`、`pytest-randomly`、`pytest-timeout`、`vcrpy`（LLM 录制回放）、`atheris`（fuzzing）。
- `scipy`、`statsmodels`（功效与最小可检效应）、`scikit-posthocs`、`nltk`（`nltk.metrics.agreement` 提供 Krippendorff's alpha 与 Cohen's kappa）、`pingouin`（ICC）。
- `ruptures`（变点检测）、`rank-bm25`、`networkx`（依赖图判环）。
- `z3-solver`（不变量反例搜索）。
- `tiktoken`：仅作字符近似误差的对照，不作为正式口径。

外部资源档，需要下载或人工投入：

- `promptfoo`（评测编排：yaml 断言、llm-rubric、similarity、token 与成本、CI、red-team）、`Inspect AI`（评测与日志）、`Langfuse`（自托管 tracing 加数据集加人工复核队列）。
- `sentence-transformers` 加 bge-m3 或 nomic-embed-text（embedding 检索基线）。
- Prometheus 2（本地 judge 模型，须先与人工标签校准）。
- Playwright 加 axe-core（WCAG 自动检查与视觉回归）。
- `bandit`、`semgrep`、`pip-audit`、`detect-secrets`、CycloneDX SBOM 生成、Sigstore 或 cosign 与 GitHub attestation。

安装走本地代理：

```powershell
$env:HTTP_PROXY  = "http://127.0.0.1:3067"
$env:HTTPS_PROXY = "http://127.0.0.1:3067"
D:\codes\personae\tests\venv\Scripts\python.exe -m pip install hypothesis mutmut coverage pytest-randomly pytest-timeout vcrpy scipy statsmodels ruptures rank-bm25 networkx z3-solver
```

注：`tests/venv` 当前指向的基础解释器已失效，需先重建 venv 才能装包。

---

## 5 外部客观标准（可判真伪的清单）

A 层，立刻可判定，不需要人工投入：

- SemVer 2.0.0：能力新增走 MINOR，行为修正走 PATCH。当前「纯文档不 bump」与「改了引擎行为但不 bump 而随下版本发版」并存，需统一为单一口径。
- Keep a Changelog 1.1.0 加 SPDX 加 CycloneDX SBOM：每个 zip 附带依赖清单与哈希。
- CWE Top 10（2024 与 2025 版）加 OWASP ASVS 4.0.3 或 5.0 Level 2 自查表：按条目给出通过与不通过，G10 属必查项。
- W3C EventSource 规范语义：断连、重连、事件顺序、幂等。
- WCAG 2.2（W3C 推荐标准，2023-10，另有 ISO/IEC 40500 对应版本）：axe-core 自动通过率作为下限指标。
- BCP 14（语言标签）加 ECMA-402（格式化）加 CLDR：i18n 技术合规下限。
- OpenTelemetry GenAI 语义约定：trace 字段命名与采集口径。

B 层，需要少量投入但完全客观：

- ISO/IEC 25010（产品质量模型，2023 版）加 ISO/IEC 25023（可度量质量指标）：功能适合性、容错性、资源利用率、易用性四项各配一个可测指标。
- ISO/IEC/IEEE 29119 系列（软件测试）加 IEEE 1012:2016（V&V）：测试用例设计、缺陷分级、回归与验证记录。
- OpenSSF Best Practices（原 CII）Gold 级判据加 ossf/scorecard 数值分。
- NIST AI RMF 1.0 的 MEASURE 函数：要求文档化的度量、明确的评估方法与结果记录。本项目全部实机结论都落在这条要求之下。
- ACL Rolling Review 可复现性清单：每一个探针脚本按其条目自证。
- ASTM F2575-17（机器翻译质量指南）与 DQF/MQM 错误分型、LISA QA Model 2012 错误权重：i18n 译文质量的可复核口径。
- SLSA v1.0 构建完整性（L2 至 L3 思路）：分发包可溯源。
- 统计学标准：Wilson 或 Clopper-Pearson 精确区间、McNemar 配对检验、Wilcoxon-Mann-Whitney、Cliff's delta 或秩双列相关作效应量、Benjamini-Hochberg FDR 校正、功效分析给出最小可检效应与所需样本量。

C 层，专业同行评议类：

- CharacterEval、PersonaGym、RoleLLM：角色一致性是否达到同类系统水平。
- PLAUD：剧本类生成的角色一致性、情节一致性、时间线一致性、幻觉四项指标。
- LoCoMo：跨轮记忆的评测任务设计（单跳、多跳、时序、开放域、对抗）。
- BEIR：零样本检索的相对位置。
- ITC-GDUE 与 GEQ、SUS、UMUX-Lite、NASA-TLX：体验与负荷量表，分值须与已发表常模比较，不能只报自造均值。
- ACM 工件评审徽章口径（Artifacts Available、Evaluated、Reproduced）：探针产物是否可被他人复现。

---

## 6 用上述标准重写的需求

原需求隐含的是「引擎能把群像、秘密、关系、镜头跑起来」。重写后的需求是一组可证伪条款，每项给出操作定义、测量方法、判据、样本量、失效边界。以下十二条即新版需求本体。

**REQ-1 秘密簿记判定有效性**
- 操作定义：对一批已标注叙事，引擎判定的秘密状态迁移与人工真值一致。
- 测量：人工金标注，双标注加仲裁，Krippendorff's alpha 不低于 0.80，分通道出 precision、recall、F1 与混淆矩阵，附 Wilson 95% 区间。
- 判据：暴露判定 precision 不低于 0.90、recall 不低于 0.80，起疑误升暴露率不超过 5%，自述通道与物证通道分别单独达标。
- 样本量：标注叙事不少于 60 轮、标注秘密事件不少于 120 个。
- 失效边界：标注不足或未达 alpha 阈值时，本条不得出结论，只出观察。

**REQ-2 秘密可见性不变量（形式化）**
- 操作定义：§2.2 的七条不变量全部成立。
- 测量：Z3 反例搜索、Hypothesis 随机场景不少于 5000 例、现有确定性回归。
- 判据：无反例。若存在反例，必须给出可复现最小反例与修复方案。
- 失效边界：模型无关，属引擎本体性质，不受采样与模型换代影响。

**REQ-3 世界书注入的检索质量**
- 操作定义：给定 gold 查询集，注入结果相对基线的召回与误召回。
- 测量：precision@k、recall@k、MRR、nDCG@k，k 取实际 `max_entries`，基线为 SQLite FTS5 BM25 与本地 embedding 各一条。
- 判据：关键词方案 recall@8 不低于 BM25 的 90%，否则给出混合方案（关键词保底加 BM25 补位）或条目改写清单。
- 样本量：真实指令语料不少于 300 条查询。
- 失效边界：gold 集只覆盖已有剧本题材，跨题材外推须另测。

**REQ-4 注入预算硬不变量**
- 操作定义：任意条目配置下，单轮注入总量不超过声明预算。
- 测量：property 测试随机条目集合（含常量比例、条目长度、引用深度三个维度），以模型 tokenizer 计数。
- 判据：常量与关键词命中共同受预算约束，超限裁剪策略确定且可预测，并在 `wb_meta` 可见。
- 失效边界：预算值本身随模型上下文窗口配置，须写入 `config.json` 而非源码常量。

**REQ-5 依赖闭包语义明确化**
- 操作定义：`#name#` 引用在配额压力下是否保底，语义唯一且与文档一致。
- 测量：Hypothesis 随机依赖图（含链式、菱形、含环）加随机配额，断言保底行为与声明一致，断言无环或存在确定不动点。
- 判据：文档与测试口径一致，环检测存在，引用展开终止可证。
- 失效边界：G6 的裁决（保底或明说不保底）须先由作者定夺，属设计决策。

**REQ-6 可复现性与可重放**
- 操作定义：同一探针脚本重跑结果一致，或差异只来自显式声明的采样分布。
- 测量：确定性层 temperature=0 加 seed 加 `vcrpy` cassette，分布层每配置 n 次采样并记录采样指纹与模型权重哈希。
- 判据：确定性层 100% 一致，分布层只允许以均值加区间出结论。
- 失效边界：上游模型权重或推理端版本变更即作废基线，须重新定位。

**REQ-7 长会话事实保真**
- 操作定义：`compress_history` 之后，跨轮事实问答正确率不低于阈值。
- 测量：自建 LoCoMo 式五类问答（单跳、多跳、时序、开放域、对抗），随会话轮数递增逐档测。
- 判据：40 轮内单跳与时序不低于 90%，80 轮内不低于 80%，对抗类误答率不超过 10%。
- 失效边界：阈值属产品决策，需作者确认；数值不得沿用已作废的 5300 阈值。

**REQ-8 退化拐点重新定位**
- 操作定义：叙事质量随上下文长度与注入位置的拐点位置及不确定区间。
- 测量：因子设计（轮数 乘 注入位置三档 乘 注入量三档），每格随机化顺序且 n 不低于 20，指标为已标定的复读率、长度、点名出场分布、秘密翻转正确率，用 `ruptures` 变点检测加 bootstrap 区间。
- 判据：给出拐点位置区间与效应量，明确「长度」与「位置」哪个是主因。
- 失效边界：结论与模型强绑定，换模型须重跑。

**REQ-9 机制贡献消融**
- 操作定义：五项机制各自对结局指标的净贡献。
- 测量：逐项关闭，同剧本同初始、随机顺序、每格不少于 30 会话，配对比较，效应量加 FDR 校正。
- 判据：每项机制要么给出正效应量加区间，要么承认无 measurable 贡献并考虑简化。
- 失效边界：只测已有机制，不评估未实现的搁置项。

**REQ-10 判据阈值标定**
- 操作定义：复读、露骨度、出场判定等自动判据的 FPR 与 FNR。
- 测量：在标注样本上画 ROC 与 PR 曲线，按 FPR 不超过 5% 选阈值，报 AUC。
- 判据：所有阈值外置配置、可复算、可被第三方复现。
- 失效边界：阈值与模型家族相关，跨家族须重标定。

**REQ-11 安全与分发完整性**
- 操作定义：G9 与 G10 的全部判据。
- 测量：安全回归测试六类输入、崩溃注入、并发写、`bandit` 与 `semgrep` 与 `pip-audit`、锁版加哈希加 SBOM、产物 SHA-256 加署名。
- 判据：ASVS Level 2 相关条目全部通过，无高危静态扫描结果，任一 zip 哈希可校验。
- 失效边界：无。属发布前必过项。

**REQ-12 体验与可用性**
- 操作定义：目标用户能独立完成开局、推演、编辑剧本、恢复会话四项核心任务。
- 测量：Nielsen 启发式走查（2 至 3 名评审、严重度评级）、5 至 8 名被试任务式测试加 SUS 或 UMUX-Lite 加 NASA-TLX、axe-core 自动可访问性检查、本地遥测漏斗。
- 判据：严重度 3 与 4 问题清零，SUS 与已发表常模比较不低于 70，axe 自动通过率 100%。
- 失效边界：被试样本为便利抽样时不外推到全体用户群体。

---

## 7 落地顺序（按可执行性排，不按重要性）

1. 第 1 至 2 天：给 `store.py` 与 `script_refiner` 写路径加安全 ID 与原子写，补六类安全输入测试。这是唯一一条「现在就存在风险」的项，其余都是证据升级。
2. 第 2 至 3 天：给现有探针脚本统一加采样指纹、n 次重复、Wilson 区间输出，把 DEVLOG 与 TODO 里的历史裸计数标注为「观察值，非结论」。
3. 第 3 至 5 天：REQ-4 与 REQ-5 的 property 测试，先把 G5 与 G6 两个已复核事实钉成测试。
4. 第 6 至 10 天：REQ-1 的标注集建设，先做 60 轮标注与双标注一致性，这是后面一切结论的地基。
5. 之后：REQ-2 的形式化、REQ-3 的检索评测与基线、REQ-8 的拐点重测、REQ-9 的消融、REQ-12 的体验测量。

---

## 8 本次现场复核的两条事实（可复现）

复核脚本只用标准库，直接 import 引擎的 `world.py`（该模块仅依赖 `re`）：

```powershell
# 复核 A：配额压力下引用链是否保底
& "<python>" -c @'
import sys; sys.path.insert(0, r"D:\codes\personae\engine")
import world
mk = lambda n,keys,cont,**kw: dict(name=n,keys=keys,content=cont,enabled=True,**kw)
entries = [mk("A",["甲"],"见 #B# 与 #C#  [A]",priority=100),
           mk("B",[],"[B]",priority=90), mk("C",[],"[C]",priority=80),
           mk("D",["甲"],"[D]",priority=70), mk("E",["甲"],"[E]",priority=60),
           mk("F",["甲"],"[F]",priority=50), mk("G",["甲"],"[G]",priority=40),
           mk("H",["甲"],"[H]",priority=30), mk("I",["甲"],"[I]",priority=20)]
out = world.scan(entries, ["甲"], "甲", max_entries=8, include_secret=False)
print([e["name"] for e in out])
'@
```

实际输出 `['A', 'D', 'E', 'F', 'G', 'H', 'I', 'B']`：被 `#B#` 与 `#C#` 引用的两条中，B 保住、C 被静默截掉。

```powershell
# 复核 B：常量条目是否受 max_entries 约束
& "<python>" -c @'
import sys; sys.path.insert(0, r"D:\codes\personae\engine")
import world
ents = [dict(name=f"C{i}",keys=[],content="X"*400,enabled=True,constant=True) for i in range(40)]
out = world.scan(ents, ["甲"], "甲", max_entries=8, include_secret=False)
print(len(out), sum(len(e["content"]) for e in out))
'@
```

实际输出 `40 16000`：40 条常量全部注入，`max_entries` 对常量不设上限。

两处均是对既有实现的事实描述，不构成「必须改」的结论。改法属设计裁决，见 REQ-4 与 REQ-5。

---

## 9 术语与出处备查

- 统计：Wilson 1927 区间、Clopper-Pearson 1934 精确区间、McNemar 1947 配对检验、Wilcoxon-Mann-Whitney U、Cliff 1993 delta、Benjamini-Hochberg 1995 FDR、Efron 1979 bootstrap、Krippendorff 系数 alpha（约定不低于 0.80 为可信、0.667 为试探可用）。
- LLM 评测：Zheng 等 2023（MT-Bench 与 Chatbot Arena，judge 偏差与人类一致率）、Liu 等 2023（G-Eval）、Kim 等 2024（Prometheus 2）、Tan 等 2024（JudgeBench）、Laban 等 2025（多轮对话退化）、Liu 等 2023（Lost in the Middle）、Bai 等 2023/2024（LongBench 与 LongBench v2）、NVIDIA 2024（RULER）、2025（NoLiMa）、OpenAI 2025（MRCR）、Maharana 等 2024（LoCoMo）、Goyal 等 2023（TACL，自动故事生成评估）、Wu 等 2023（CharacterEval）、2024（PersonaGym）、Wang 等 2024（RoleBench）、PLAUD 2024（NeurIPS Datasets and Benchmarks）、Thakrar 等 2024（BEIR 类零样本检索参照）。
- 交互叙事：Riedl 与 Bulitko 2013（AI Magazine 综述）、Nelson（Matryoshka）、Mateas 与 Stern（Façade 与其评估方法）、Genette（聚焦）、Chatman（story 与 discourse）、Propp（故事形态学 31 项功能）、ITC-GDUE 与 GEQ、Brooke 1996（SUS）、Lewis 等 2018（UMUX-Lite）、Hart & Staveland 1988（NASA-TLX）、Nielsen 1992（启发式评估与被试饱和数）。
- 形式化：Kripke 语义、S5、public announcement logic、DEL、muddy children 谜题族、MCMAS 与 NuSMV 模型检查、Z3 SMT 求解器。
- 工程与合规：SemVer 2.0.0、Keep a Changelog 1.1.0、SPDX、CycloneDX、CWE Top 10、OWASP ASVS、ISO/IEC 25010:2023、ISO/IEC 25023:2021、ISO/IEC/IEEE 29119、IEEE 1012:2016、WCAG 2.2、EN 301 549、BCP 14、ECMA-402、CLDR、ASTM F2575-17、MQM 与 DQF、LISA QA Model 2012、OpenSSF Best Practices、SLSA v1.0、OpenTelemetry GenAI semantic conventions、NIST AI RMF 1.0。

以上条目名与年份用于可检索定位，具体数值判据以本项目实际测量为准。凡引用二手数据（如他人论文里的一致率、下降比例）在用于本项目决策前须自行复算。
