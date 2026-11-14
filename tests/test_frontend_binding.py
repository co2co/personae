"""前端主流程绑定守护（T0 级回归）。

起因：v0.17.0 移除事实表时，误把 `send()` 整个函数和三条按钮绑定
（`#start.onclick` / `sendBtn.onclick` / Enter 键）一起删掉了。
后果是首页「开始」和「注入扰动」两个按钮点了完全没反应，
浏览器控制台也不报错——纯靠点页面很难第一时间联想到是绑定丢失。

这类缺陷对 pytest 完全不可见：它不碰 Python。所以本文件用静态解析 +
JS 沙箱双层检查，把「主流程按钮必须有绑定」固化成可回归的测试。

不依赖 node/puppeteer：node 缺失时第二层自动跳过，只保留静态层。
"""
import os
import re
import shutil
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "engine", "static", "index.html")
CHECK_JS = os.path.join(ROOT, "tests", "_frontend_binding_check.js")

# 主流程入口：每个 (标识串, 说明) 都必须在 index.html 中存在。
# 只收「会因缺失而让界面完全不可用」的关键项，不做穷举。
MAIN_FLOW_PROBES = [
    ("async function send()", "注入扰动的发送逻辑 send()"),
    ("fetch('/api/act'", "send() 调用 /api/act"),
    ("getElementById('start').onclick = startSession", "「开始」按钮绑定"),
    ("sendBtn.onclick = send", "「注入扰动」按钮绑定"),
    ("addEventListener('keydown'", "输入框 Enter 键绑定"),
    ("let cfgProviders = []", "系统设置的提供商清单变量声明"),
    # v0.28.2 剧本库整合：原「角色库/世界书」两入口合并为「剧本库」单入口
    ("id=\"open-dramas\"", "「剧本库」顶栏入口"),
    ("id=\"drama-modal\"", "剧本库模态"),
    ("async function refreshDramas", "剧本库列表聚合逻辑"),
    ("async function selectDrama", "选中剧本的联动加载"),
    ("id=\"d-tab-world\"", "世界书设定 tab 按钮"),
    ("id=\"d-tab-chars\"", "角色表 tab 按钮"),
    # v0.28.3 剧本级导入/导出：按钮从角色表 tab 提到剧本详情头部（删除剧本左侧）
    ("id=\"d-export\"", "剧本导出 JSON 按钮"),
    ("id=\"d-import\"", "剧本导入 JSON 按钮"),
    ("id=\"drama-import\"", "剧本导入文件选择器"),
    # v0.28.5 删除剧本走剧本级端点（世界书 + 全部角色卡一并删除），不再走旧的 /api/world DELETE
    ("getElementById('w-del').onclick = async", "「删除剧本」按钮绑定"),
    ("'/api/drama/'+encodeURIComponent(name)+'/delete'", "删除剧本调用剧本级删除端点"),
    # 世界书页只剩一组条目（作者自写）：引擎不再向世界书播种条目，故没有引擎分组、
    # 没有「恢复默认」入口。2026-11-14 撤净，反向断言见 test_worldbook_has_no_engine_default_ui。
    ("id=\"w-entries-author\"", "世界书条目容器（唯一一组）"),
    ("function showToast", "轻量提示框工具函数"),
    ("await loadWorld(DRAFT_WORLD)", "选中剧本后加载其世界书"),
    # 分组后的两条排序约束：跨组拖拽无效、常量段恒定置顶（否则保存重载后位置弹回）
    ("dragSrc.parentElement !== box", "拖拽禁止跨组"),
    ("Math.min(k, constCount) : Math.max(k, constCount)", "常量段恒定置顶：拖拽插入点钳制"),
    # 角色名册（v2.1.0）：present 改为建局名册，面板按位置分场渲染
    ("function rosterHtml", "角色名册按位置分组渲染"),
    ("角色名册 / 场景", "左栏面板标题已改为角色名册"),
    ("rosterHtml(snap, chipOf)", "名册面板使用分场渲染"),
]


def _read_index():
    with open(INDEX, encoding="utf-8") as f:
        return f.read()


def _js_balance(js):
    """统计「真代码」括号配平：跳过字符串、正则字面量、模板串（${} 插值递归计数）、
    行注释、块注释。返回 {括号: 净差}，全 0 即配平。

    起因：i18n 词典是纯数据串，英文译文合法带 ASCII 括号（"(unnamed)"、
    "Session resumed" 等），raw count 会把数据里的括号计入而误报「编辑截断」。
    真配平只筛代码结构损坏——它比 raw count 更准，不削弱守卫。
    正则字面量必须单独识别（escHtml 里有 `/"/g`）：把正则里的引号当字符串
    起点会吞掉后续真代码括号，产生假偏差。
    """
    bal = {"(": 0, "{": 0, "[": 0, ")": 0, "}": 0, "]": 0}
    openers = {"(", "{", "["}
    closers = {")", "}", "]"}
    # 允许正则字面量出现在这些前导符号之后（JS 常规正则上下文）
    regex_prev = set("(,=:[!&|?{};+-*%~^<>/")
    n = len(js)

    def walk(i, prev_sig, stop_char):
        """扫描代码上下文；遇到 stop_char（未被本层消费）时不消费它，返回其位置。"""
        while i < n:
            c = js[i]
            if stop_char and c == stop_char:
                return i, prev_sig
            if c == "/" and i + 1 < n and js[i + 1] == "/":
                j = js.find("\n", i)
                return (n if j < 0 else j), prev_sig  # 行注释止于换行前，交外层继续
            if c == "/" and i + 1 < n and js[i + 1] == "*":
                j = js.find("*/", i)
                i = n if j < 0 else j + 2
                prev_sig = "*"
                continue
            if c == "/" and (prev_sig == "" or prev_sig in regex_prev):
                # 正则字面量（引号、括号都在其内部，不计数）
                i += 1
                in_cls = False
                while i < n:
                    d = js[i]
                    if d == "\\":
                        i += 2
                        continue
                    if d == "\n" and not in_cls:
                        break
                    if d == "[":
                        in_cls = True
                    elif d == "]":
                        in_cls = False
                    elif d == "/" and not in_cls:
                        i += 1
                        while i < n and js[i].isalpha():
                            i += 1
                        break
                    i += 1
                prev_sig = "/"
                continue
            if c in "\"'":
                q = c
                i += 1
                while i < n:
                    if js[i] == "\\":
                        i += 2
                        continue
                    if js[i] == q:
                        i += 1
                        break
                    if js[i] == "\n":
                        break
                    i += 1
                prev_sig = q
                continue
            if c == "`":
                i += 1
                while i < n:
                    if js[i] == "\\":
                        i += 2
                        continue
                    if js[i] == "`":
                        i += 1
                        break
                    if js[i] == "$" and i + 1 < n and js[i + 1] == "{":
                        bal["{"] += 1
                        i, prev_sig = walk(i + 2, "", "}")
                        if i < n and js[i] == "}":
                            bal["}"] += 1
                            i += 1
                        prev_sig = "}"
                        continue
                    i += 1
                prev_sig = "`"
                continue
            if c in openers:
                bal[c] += 1
            elif c in closers:
                bal[c] += 1
            if not c.isspace():
                prev_sig = c
            i += 1
        return i, prev_sig

    walk(0, "", None)
    return {k: bal[k] - bal[v] for k, v in (("(", ")"), ("{", "}"), ("[", "]"))}


class TestFrontendMainFlowBound(unittest.TestCase):
    """index.html 必须包含主流程的全部绑定代码。"""

    def test_main_flow_probes_present(self):
        html = _read_index()
        missing = [desc for probe, desc in MAIN_FLOW_PROBES if probe not in html]
        self.assertEqual(
            missing, [],
            "index.html 丢失主流程代码：%s。"
            "删除面板/功能时误删相邻函数是本项目的既往事故，"
            "改完请跑本文件与 _frontend_binding_check.js。" % "、".join(missing),
        )

    def test_inline_script_parses(self):
        """内联 <script> 必须能抽出且「真代码」括号配平（粗筛结构性损坏）。

        配平统计跳过字符串/注释（见 _js_balance）：i18n 词典等纯数据串
        合法带 ASCII 括号，raw count 会误报；真配平只筛代码结构损坏。
        """
        html = _read_index()
        m = re.search(r"<script>([\s\S]*?)</script>", html)
        self.assertIsNotNone(m, "index.html 内联 script 块缺失或标签不匹配")
        js = m.group(1)
        bal = _js_balance(js)
        for left in ("(", "{", "["):
            self.assertEqual(
                bal[left], 0,
                "内联脚本 %s 真代码计数不配平（%d），疑似编辑截断" % (left, bal[left]),
            )

    def test_world_entry_ui_preserves_hidden_flags(self):
        """世界书条目卡片必须回传 demo / first_round。

        起因：旧版 entryCard 不渲染、collectWorldEntries 也不回传 demo 与
        first_round，任何一次「保存整份」都会把 demo=true 静默抹掉——条目从
        few-shot 通道退回普通设定注入，无报错、无提示，只能靠对比提示词才发现。
        这两个字段在界面上没有输入控件，因此必须靠 dataset 原样往返。
        （origin 曾一并往返，随 2026-11-14 撤净「引擎默认条目」层退出保存链路。）
        """
        html = _read_index()
        m = re.search(r"function collectWorldEntries\(\)\s*\{(.*?)\n\}", html, re.S)
        self.assertIsNotNone(m, "collectWorldEntries() 缺失")
        body = m.group(1)
        for probe, desc in (
            ("el.dataset.demo", "demo 示范标志"),
            ("el.dataset.firstRound", "first_round 首轮标志"),
        ):
            self.assertIn(
                probe, body,
                "世界书保存链路丢失%s——界面上没有对应控件，一旦不回传就被永久抹掉" % desc,
            )

    def test_worldbook_has_no_engine_default_ui(self):
        """反向断言：世界书界面里不再有「引擎默认条目」这一层。

        世界书为剧本服务，不为引擎服务：引擎不往剧本的数据文件里塞自己的条目，
        也就不需要「哪条是系统给的」「删了会不会补回来」这类界面概念。
        一旦这些标识重新出现，说明播种层或恢复入口被悄悄带回来了。
        """
        html = _read_index()
        for absent, desc in (
            ("w-entries-engine", "引擎条目容器"),
            ("w-engine-restore", "「恢复默认」按钮"),
            ("w-engine-toggle", "引擎组折叠开关"),
            ("badge-engine", "「引擎默认」徽标"),
            ("restore-defaults", "恢复端点调用"),
            ("data-origin", "条目来源标记渲染"),
        ):
            self.assertNotIn(absent, html, "世界书界面重新出现了%s" % desc)

    def test_world_entry_priority_preserved_on_save(self):
        """保存世界书不得无条件重算 priority（2026-10-23 修）。

        起因：旧版 collectWorldEntries 用 `100 - idx * 5` 按列表位置重算，
        于是只要在界面上点一次保存，作者手写的 priority 阶梯就被整体抹平——
        「一个字没改」也会让 sync_drama 的一致性守卫（当年是三态，2026-11-15 起两方）
        判世界书不一致，而条目内容
        其实分毫未动。更隐蔽的是：界面上没有 priority 控件，作者根本看不出
        自己的注入次序被改写了。

        修法与 demo / first_round 一致：priority 也走 dataset 原样往返；
        顺序真变了（拖拽落位、勾选常量导致移段）由 renumberGroup 在改动现场
        就地重排。本测试锁住四条链路，任何一环断掉都会让「无条件重排」复活。
        """
        html = _read_index()
        # 1) 渲染必须把 priority 落到 dataset，否则保存时读不到原值。
        self.assertRegex(
            html, r'data-priority="\$\{e\.priority',
            "entryCard 未渲染 data-priority——保存链路读不到原优先级",
        )
        m = re.search(r"function collectWorldEntries\(\)\s*\{(.*?)\n\}", html, re.S)
        self.assertIsNotNone(m, "collectWorldEntries() 缺失")
        body = m.group(1)
        # 2) 保存必须优先取 dataset 原值。
        self.assertIn(
            "el.dataset.priority", body,
            "collectWorldEntries 未读取 dataset.priority——又会按列表序重算",
        )
        # 3) 顺序变更现场必须有就地重排函数。
        self.assertIn("function renumberGroup", html, "renumberGroup() 缺失")
        # 4) 两处顺序变更点都必须调用它：拖拽落位、勾选/取消常量。
        self.assertIn(
            "renumberGroup(card.parentElement)", html,
            "拖拽落位后未重排 priority——保存重载会弹回原位",
        )
        self.assertIn(
            "renumberGroup(box)", html,
            "勾选常量导致移段后未重排 priority——保存重载会弹回原位",
        )
        # 5) 新条目必须只给自己赋值，不得连带重写既有条目。
        self.assertIn(
            "node.dataset.priority", html,
            "新增条目未赋 priority——会落成 0 或继承首条的值",
        )

    def test_setup_cast_is_readonly_roster(self):
        """开场区不再提供角色勾选（v2.1.1）。

        引擎以「剧本全部角色」为簿记定义域：关系基线、秘密归属、亲缘、短期目标都按
        名册建账。少选一个人不会少写一段戏，而是让世界书点名的角色没有卡可依——
        悬空引用不会报错，只会让模型自由发明那个人。故前端只保留只读名册（回答
        「这一局有谁」），不再收集 cast，开局请求交给后端按剧本取全量。
        """
        html = _read_index()
        self.assertNotIn("#npcs input:checked", html, "开场区仍从勾选框收集角色")
        self.assertIn("let NPC_NAMES = [];", html, "登场名册缓存缺失")
        self.assertIn('<span class="chip">', html, "登场名册未渲染为只读 chip")
        self.assertIn("body: JSON.stringify({scene, world})", html,
                      "开局请求仍携带 cast")
        m = re.search(r"async function startSession\(\)\s*\{(.*?)\n\}", html, re.S)
        self.assertIsNotNone(m, "startSession() 缺失")
        self.assertIn("NPC_NAMES.length", m.group(1), "startSession 未校验名册非空")

    def test_no_dangling_dom_ids(self):
        """renderSnapshot 引用的 DOM id 必须在 HTML 里真实存在。

        反向事故：删了面板 HTML 却忘了删 JS 引用，会在渲染时抛
        TypeError（null.innerHTML），同样表现为「界面点了没反应」。
        """
        html = _read_index()
        # 只查左栏快照渲染用到的 id，范围可控、误报低。
        for pid in ("present", "scene-line", "states", "locations", "secrets"):
            self.assertIn('id="%s"' % pid, html, "左栏缺少 #%s 容器" % pid)
        for pid in ("actions", "goals", "facts"):
            self.assertNotIn(
                'id="%s"' % pid, html,
                "#%s 已随面板移除，若 JS 仍在引用会导致渲染抛错" % pid,
            )
            self.assertNotIn(
                "getElementById('%s')" % pid, html,
                "JS 仍引用已移除的 #%s" % pid,
            )

    def test_ui_lang_follows_system_by_default(self):
        """界面语言出厂必须跟随系统，且可被用户手动覆盖。

        守卫三件事：
        1. 默认态是 Auto（跟随 navigator.languages），不能写死某一语种——
           曾出现「默认英文」，中文用户开箱看到英文界面；
        2. 用户选择（zh / en）必须落 localStorage 并覆盖系统语言；
        3. 键名字面量完整性——曾出现 `'personae_ui_lang'` 被误写成含省略号的
           `'personae_…e'`，读写仍自洽所以功能「看起来正常」，但换键后旧偏好静默丢失。
        """
        html = _read_index()
        self.assertRegex(html, r"const UI_LANG_KEY = 'personae_ui_lang';")
        self.assertIn("const UI_LANG_AUTO = 'auto';", html, "缺少 Auto（跟随系统）态常量")
        self.assertIn("localStorage.getItem(UI_LANG_KEY) || UI_LANG_AUTO", html,
                      "无用户偏好时应回落到 Auto，而非写死语种")
        self.assertIn("function _sysLang()", html, "缺少系统语言探测")
        self.assertIn("navigator.languages", html, "系统语言应取自 navigator.languages")
        self.assertIn("indexOf('zh') === 0", html, "zh* 应判为中文")
        self.assertIn("UI_LANG_PREF === UI_LANG_AUTO ? _sysLang() : UI_LANG_PREF", html,
                      "Auto 态应实时取系统语言，显式选择应覆盖它")
        self.assertIn("bAuto.dataset.lang = 'auto'", html, "设置面板缺 Auto 按钮")

    def test_secret_states_have_english_entries(self):
        """秘密簿记的状态词与括号说明必须有英文词条/模板。

        秘密四态由后端以中文字面量下发（潜伏/起疑/暴露/已公开），前端直接渲染。
        漏词条时英文界面会显示「甲：潜伏（已知者：乙）」——半中半英，且不报错，
        属静默退化。这里锁死词条与三条模板的存在。
        """
        html = _read_index()
        for zh, en in (("潜伏", "Latent"), ("起疑", "Suspected"),
                       ("暴露", "Exposed"), ("已公开", "Public")):
            self.assertIn('"%s": "%s"' % (zh, en), html,
                          "秘密状态「%s」缺英文词条" % zh)
        for frag in ("/^（已知者：(.+)）$/, '(known to: $1)'",
                     "/^（起疑：(.+)）$/, '(suspects: $1)'"):
            self.assertIn(frag, html, "秘密簿记括号说明缺英文模板：%s" % frag)


@unittest.skipIf(shutil.which("node") is None, "node 不可用，跳过 JS 沙箱执行")
class TestFrontendSandbox(unittest.TestCase):
    """在最小 DOM mock 里真跑一遍内联脚本，验证绑定确实生效。"""

    def test_binding_sandbox(self):
        proc = subprocess.run(
            ["node", CHECK_JS],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=120,
            cwd=ROOT,
        )
        self.assertEqual(
            proc.returncode, 0,
            "前端绑定沙箱自检失败：\n%s\n%s" % (proc.stdout, proc.stderr),
        )
        self.assertIn("ALL PASS", proc.stdout)


if __name__ == "__main__":
    unittest.main()
