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
    # 引擎默认条目来源可见化：分组展示 + 恢复入口 + 折叠开关 + 渲染携带来源标记
    ("class=\"wb-group engine\"", "世界书页「引擎默认条目」独立分组"),
    ("id=\"w-entries-engine\"", "引擎条目独立容器（与剧本条目物理隔离）"),
    ("id=\"w-entries-author\"", "剧本条目独立容器"),
    ("engineCollapsed = true", "引擎组默认折叠"),
    ("getElementById('w-engine-restore').onclick = async", "「恢复默认条目」按钮绑定"),
    ("'/restore-defaults'", "恢复按钮调用恢复端点"),
    ("getElementById('w-engine-toggle').onclick", "引擎默认条目收起/展开绑定"),
    ("data-origin=", "世界书条目渲染携带来源标记"),
    # 分组后的两条排序约束：跨组拖拽无效、常量段恒定置顶（否则保存重载后位置弹回）
    ("dragSrc.parentElement !== box", "拖拽禁止跨组"),
    ("Math.min(k, constCount) : Math.max(k, constCount)", "常量段恒定置顶：拖拽插入点钳制"),
]


def _read_index():
    with open(INDEX, encoding="utf-8") as f:
        return f.read()


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
        """内联 <script> 必须能抽出且括号配平（粗筛结构性损坏）。"""
        html = _read_index()
        m = re.search(r"<script>([\s\S]*?)</script>", html)
        self.assertIsNotNone(m, "index.html 内联 script 块缺失或标签不匹配")
        js = m.group(1)
        for left, right in (("{", "}"), ("(", ")"), ("[", "]")):
            self.assertEqual(
                js.count(left), js.count(right),
                "内联脚本 %s/%s 不配平，疑似编辑截断" % (left, right),
            )

    def test_world_entry_ui_preserves_hidden_flags(self):
        """世界书条目卡片必须回传 origin / demo / first_round。

        起因：旧版 entryCard 不渲染、collectWorldEntries 也不回传 demo 与
        first_round，任何一次「保存整份」都会把 demo=true 静默抹掉——条目从
        few-shot 通道退回普通设定注入，无报错、无提示，只能靠对比提示词才发现。
        这三个字段在界面上没有输入控件，因此必须靠 dataset 原样往返。
        """
        html = _read_index()
        m = re.search(r"function collectWorldEntries\(\)\s*\{(.*?)\n\}", html, re.S)
        self.assertIsNotNone(m, "collectWorldEntries() 缺失")
        body = m.group(1)
        for probe, desc in (
            ("el.dataset.demo", "demo 示范标志"),
            ("el.dataset.firstRound", "first_round 首轮标志"),
            ("el.dataset.origin", "origin 来源标记"),
        ):
            self.assertIn(
                probe, body,
                "世界书保存链路丢失%s——界面上没有对应控件，一旦不回传就被永久抹掉" % desc,
            )

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
