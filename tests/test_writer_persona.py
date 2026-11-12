"""「执笔写手」承载位守护测试（2026-11-12）。

背景：写手这条系统人设曾在三个承载位之间往返，三轮的差别只在**投递位与存储层**，
不在内容：
  ① 系统设置固定块（config.writer，拼进 [导演指令] 之后）——落在 system 中段，实测效力弱。
  ② 世界书引擎默认条目「写手」（constant / after / priority 100）——撤掉分流后退回
     末尾 user 的【世界设定·当前环境】（装配约 76% 处），被读成「此刻有人在要这个」，
     比不投更糟。
  ③ prompter.writer_block() 恒定渲染进 system 第一块，正文仍存 config.writer
     （现行，也是本文件固化的形态）。

本文件要守住的，正是「①的存储 + ③的投递」这个组合——它同时满足两条此前互相牵制
的要求：用户能在系统设置里改写，而投递位始终锁在 system 头部。红线如下：

  1. 写手恒在：config 无 writer 字段、或自述留空，一律回退出厂默认写手，没有「关闭写手」的形态。
  2. 投递位在 system 最前：先于 [世界设定] 与 [导演指令]，且不得被当环境资料投到末尾 user。
  3. 不进世界书：store 不播种任何写手条目，避免同一份引擎政策在每本世界书里留副本。
  4. 只进正文通道：director（纪官回写）与 build_summary（结局总结）不得引用 writer_block。
  5. 出厂正文普适：不含具体剧本角色名与题材词（本文件因正当引用黑名单词，
     登记在 test_universality 的 ALLOW_FILES 白名单内）。
  6. 出厂 guard 必须自带那句冲突裁决：写手口吻不得越过后文未成年红线。
"""

import json
import sys
from pathlib import Path

import pytest

ENGINE = Path(__file__).resolve().parent.parent / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

import app as engine_app      # noqa: E402
import llm                    # noqa: E402
import prompter               # noqa: E402
import store                  # noqa: E402

from fixtures import NAMES, fake_list_characters, make_cards  # noqa: E402

INDEX_HTML = ENGINE / "static" / "index.html"

MIN_SNAP = {
    "scene": {"round": 1, "place": "院子", "time": "", "weather": ""},
    "relations": {}, "ledger": [], "secrets": [],
    "present": list(NAMES),
}


@pytest.fixture
def no_config_writer(monkeypatch):
    """出厂态：config 里没有 writer 字段。测试绝不依赖开发机真实 config。"""
    monkeypatch.setattr(llm, "_file_config", lambda: {})


@pytest.fixture
def cards(monkeypatch):
    monkeypatch.setattr(store, "list_characters", fake_list_characters(NAMES))
    return make_cards(NAMES)


def _system(cards, world_hits=None, after_hits=None):
    msgs = prompter.build_session(cards, "注入一处扰动", world_hits or [], dict(MIN_SNAP),
                                  [], after_hits or [])
    return msgs


# ---------------------------------------------------------------- 恒在与回落

def test_default_writer_injected_when_config_absent(no_config_writer, cards):
    """config 无 writer 字段 → 出厂默认写手仍在 system 里（写手恒在）。"""
    sys_msg = _system(cards)[0]["content"]
    assert "[执笔写手 · 默认写手]" in sys_msg
    assert prompter.DEFAULT_WRITER["content"] in sys_msg


@pytest.mark.parametrize("stored", [
    None,                                        # 字段缺失
    "不是字典",                                   # 形状错误
    {"name": "我的写手", "content": "   "},        # 自述空白
    {"name": "我的写手", "content": None},         # 自述缺失
])
def test_blank_writer_falls_back_to_factory(no_config_writer, cards, monkeypatch, stored):
    """回落到出厂默认正文；名称若有效则保留用户给的名字。"""
    raw = {} if stored is None else {"writer": stored}
    monkeypatch.setattr(llm, "_file_config", lambda: raw)
    sys_msg = _system(cards)[0]["content"]
    assert prompter.DEFAULT_WRITER["content"] in sys_msg
    given = stored.get("name") if isinstance(stored, dict) else None
    expected_name = given or prompter.DEFAULT_WRITER["name"]
    assert ("[执笔写手 · %s]" % expected_name) in sys_msg


def test_custom_writer_replaces_factory(no_config_writer, cards, monkeypatch):
    monkeypatch.setattr(llm, "_file_config", lambda: {"writer": {
        "name": "短句写手", "content": "我写短句，一轮三句话收口。"}})
    sys_msg = _system(cards)[0]["content"]
    assert "[执笔写手 · 短句写手]" in sys_msg
    assert "我写短句，一轮三句话收口。" in sys_msg
    assert prompter.DEFAULT_WRITER["content"] not in sys_msg


# ---------------------------------------------------------------- 投递位

def test_writer_is_first_block_of_system(no_config_writer, cards):
    """投递位红线：写手是 system 的第一块，先于 [世界设定] 与 [导演指令]。

    这条不是「顺手的位置偏好」，而是对照实测的结论（探针件未入库）：同一条措辞恒定
    进 system 头部时稳定生效，整块挪到末尾 user（装配约 76% 处、仍标「强制」）后，
    同一批场景 4 次里 3 次失效——位置是放大器，投递层决定接不接受。把这条写成断言，
    是为了拦住「为了近因把写手搬到末尾」的回退。
    """
    hits = [{"name": "设定条", "content": "世界设定正文"}]
    after = [{"name": "环境条", "content": "当前环境细节"}]
    msgs = _system(cards, world_hits=hits, after_hits=after)
    sys_msg = msgs[0]["content"]
    assert sys_msg.startswith("[执笔写手 ·")
    assert sys_msg.index("[执笔写手") < sys_msg.index("[世界设定]")
    assert sys_msg.index("[执笔写手") < sys_msg.index("[导演指令]")


def test_writer_not_delivered_as_environment(no_config_writer, cards):
    """写手正文不得被当环境资料投到末尾 user（那是 ②的老路）。"""
    msgs = _system(cards, after_hits=[{"name": "环境条", "content": "当前环境细节"}])
    last_user = [m for m in msgs if m.get("role") == "user"][-1]
    assert prompter.DEFAULT_WRITER["content"] not in last_user["content"]


def test_writer_not_in_summary_channel(no_config_writer, cards):
    """结局总结是结构化记账，写手口吻会污染字段稳定性，故不注入。"""
    blob = "\n".join(m["content"] for m in prompter.build_summary(dict(MIN_SNAP), []))
    assert prompter.DEFAULT_WRITER["content"] not in blob
    assert "[执笔写手" not in blob


def test_writer_block_only_reaches_narrative_channel():
    """writer_block / writer_cfg 只能被 prompter 自己调用。

    纪官回写（director.reflect）与结局总结都走 llm.complete，一旦被写手口吻污染，
    模型返回的 JSON 字段就散了。这条静态守卫把「只进正文通道」钉死。
    """
    for py in sorted(ENGINE.glob("*.py")):
        if py.name == "prompter.py":
            continue
        src = py.read_text(encoding="utf-8")
        for sym in ("writer_block(", "writer_cfg("):
            assert sym not in src, "%s 不得调用 %s（写手只进叙事正文通道）" % (py.name, sym)


# ---------------------------------------------------------------- 存储链路

def test_save_config_keeps_writer_and_truncates(tmp_path, monkeypatch):
    """落盘只留 name/content 两字段，并按 60 / 4000 上限截断。"""
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(json.dumps({"base_url": "http://x/v1"}), encoding="utf-8")
    monkeypatch.setattr(llm, "CONFIG_FILE", cfg_file)
    llm.save_config({"writer": {"name": "长" * 200, "content": "写" * 9000, "junk": 1}})
    saved = json.loads(cfg_file.read_text(encoding="utf-8"))["writer"]
    assert set(saved) == {"name", "content"}
    assert len(saved["name"]) == prompter.WRITER_NAME_LIMIT == 60
    assert len(saved["content"]) == prompter.WRITER_LIMIT == 4000


def test_saved_writer_takes_effect_without_restart(tmp_path, monkeypatch, cards):
    """保存即生效：写手每次请求重读 config，不重启也不换进程。"""
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(llm, "CONFIG_FILE", cfg_file)
    llm.save_config({"writer": {"name": "探针写手", "content": "结尾必带 〜。"}})
    sys_msg = _system(cards)[0]["content"]
    assert "[执笔写手 · 探针写手]" in sys_msg and "结尾必带 〜。" in sys_msg


def test_writer_view_shape(no_config_writer):
    v = prompter.writer_view()
    assert v["name"] == prompter.DEFAULT_WRITER["name"]
    assert v["content"] == prompter.DEFAULT_WRITER["content"]
    assert v["count"] == len(prompter.DEFAULT_WRITER["content"])
    assert v["limit"] == prompter.WRITER_LIMIT and v["name_limit"] == prompter.WRITER_NAME_LIMIT
    assert v["guard"] == prompter.WRITER_GUARD
    # 出厂写手 + 四个风格模板
    assert len(v["presets"]) == 5
    assert v["default"] == prompter.DEFAULT_WRITER


def test_api_writer_route(no_config_writer):
    body = engine_app.app.test_client().get("/api/writer").get_json()
    assert body["name"] == prompter.DEFAULT_WRITER["name"]
    assert body["limit"] == prompter.WRITER_LIMIT
    assert len(body["presets"]) == 5


# ---------------------------------------------------------------- 不进世界书

def test_worldbook_does_not_seed_writer(tmp_path, monkeypatch):
    """写手不进世界书：master 从未播种过，也不许未来「补种」回来。

    世界书里的引擎默认条目是每本剧本各存一份的引擎政策副本，撤掉分流后还会退回
    末尾【世界设定·当前环境】。写手走 config，不进这一层。
    """
    d = tmp_path / "data"
    (d / "worlds").mkdir(parents=True)
    monkeypatch.setattr(store, "DATA_DIR", d)
    store._cache.clear()
    store.save_world("甲剧本", [{"name": "自定设定", "content": "x"}])
    names = [e.get("name") for e in store.load_world("甲剧本")]
    assert "写手" not in names
    store.restore_default_entries("甲剧本")
    assert "写手" not in [e.get("name") for e in store.load_world("甲剧本")]
    store._cache.clear()


# ---------------------------------------------------------------- master 口径

def test_writer_guard_keeps_minor_redline():
    """出厂 guard 自带那句裁决：写手口吻不得覆盖未成年红线。"""
    assert "未成年红线" in prompter.WRITER_GUARD
    assert "未成年" in prompter._LAWS_PREFIX


def test_default_writer_has_no_scale_wording():
    """master 的尺度不由引擎预设（2026-10-21 下架）：出厂写手不得夹带尺度措辞。"""
    blob = prompter.DEFAULT_WRITER["content"] + prompter.WRITER_GUARD
    for term in ("尺度", "器官", "性"):
        assert term not in blob, "出厂写手不得预设尺度措辞，命中：%s" % term


BANNED_IN_WRITER = ["丧尸", "末日", "避难所", "尸群",
                    "周牧野", "林梦雅", "周晓杰", "陆沉", "林晚晚"]


def test_factory_writers_are_universal():
    """出厂写手与模板都不得绑定具体剧本角色名 / 题材词（普适性红线）。"""
    for w in prompter.WRITER_PRESETS:
        blob = w["name"] + w["content"]
        for term in BANNED_IN_WRITER:
            assert term not in blob, "出厂写手含具体角色名/题材词：%s" % term


# ---------------------------------------------------------------- 前端入口

def test_frontend_writer_panel_wired():
    """系统设置面板必须有写手入口，且保存 payload 带 writer。

    编辑入口在「系统设置 → 执笔写手」是本轮的显式裁决（投递位在 system 头部由
    prompter 锁死，界面不提供任何调位置的控件）。这里守的是入口不被误删。
    """
    html = INDEX_HTML.read_text(encoding="utf-8")
    for fid in ("cfg-writer-name", "cfg-writer-content", "cfg-writer-presets",
                "cfg-writer-reset", "cfg-writer-preview"):
        assert 'id="%s"' % fid in html, "系统设置缺少写手控件：%s" % fid
    assert "async function loadWriterPanel" in html
    assert "await loadWriterPanel();" in html, "打开系统设置时应拉取写手视图"
    assert "writer: {" in html, "sys-save payload 应携带 writer"
    # 面板没加载成功时不带 writer：宁可保留盘上的写手，也不把空输入框当「用户清空」存下去
    assert "cfgWriterView ? {" in html


def test_frontend_has_no_position_control_for_writer():
    """界面上不得出现「把写手改投别处」的控件——投递位是引擎红线，不交给用户。"""
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert "cfg-writer-position" not in html
    assert "cfg-writer-after" not in html
