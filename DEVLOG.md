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
