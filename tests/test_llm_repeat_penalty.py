"""重复惩罚机制单测（v0.22.x 起：OpenAI 标准字段优先 + llama.cpp 后备）。

背景（v0.21.1）：会话 606e6b9a 出现整段剧情重发（25 段 / 1087 字 = 全文 33%）。
当时根因是请求体从未发送 repeat_penalty，llama.cpp 吃服务端缺省 1.0。

v0.22.x 泛用性重构（会话 87e4ac46 复读根因排查后）：
  repeat_penalty 是 llama.cpp 私有扩展，ninfer 等后端会**静默忽略**（返回 200
  但采样层不生效），导致零防护。而 frequency_penalty / presence_penalty 是
  OpenAI Chat Completions 官方字段，所有自称「OpenAI 兼容」的后端都支持。
  故默认改用标准字段，repeat_penalty 降为「后端连标准字段都不认」时的后备。

本文件锁死以下契约：
1. 默认发 frequency_penalty（偏离 0.0 中性值时），presence_penalty 中性（0.0）不发。
2. repeat_penalty 不再由 _penalty_params 默认发送，改由 _repeat_fallback_params 在后备链路使用。
3. 网关 4xx 时三级降级：标准字段 -> repeat_penalty -> 全剥。
4. 字段可经 config 持久化（_WRITABLE + 类型转换）。
5. min_p 缺省 0.02 发送；显式 0 不发；与惩罚字段独立。
6. _STD_FIELDS / _EXT_FIELDS 是降级判据来源，新增字段必须登记。

所有网络请求 mock requests.post，自给自足，不依赖磁盘剧本/真实后端。
"""
import llm


_CFG = {
    "base_url": "http://127.0.0.1:1234/v1",
    "api_key": "",
    "model": "local.gguf",
    "enable_thinking": False,
}


# ---------- 1/2：字段发送规则（标准字段优先）----------

def test_neutral_penalty_not_sent():
    """中性值不发惩罚字段：frequency/presence 中性为 0.0，repeat 中性为 1.0。

    注：min_p 与惩罚字段独立，缺省 0.02 仍会发，故此处只断言惩罚字段缺席。
    用 monkeypatch 把 frequency/presence 都置 0（中性），验证不发。
    """
    import llm as _llm
    _orig = _llm.setting
    def _neutral(name):
        if name in ("frequency_penalty", "presence_penalty"):
            return 0.0
        return _orig(name)
    _llm.setting = _neutral
    try:
        out = _llm._penalty_params(1.0, 256)
    finally:
        _llm.setting = _orig
    assert "frequency_penalty" not in out
    assert "presence_penalty" not in out
    assert "repeat_penalty" not in out
    assert "repeat_last_n" not in out


def test_frequency_penalty_sent_by_default():
    """出厂默认 frequency_penalty=0.3 非中性，默认就会发送（泛用防复读主力）。"""
    out = llm._penalty_params(1.0, 256)
    assert out["frequency_penalty"] == llm.DEFAULTS["frequency_penalty"]


def test_presence_penalty_neutral_not_sent():
    """presence_penalty 出厂默认 0.0（中性），不发送。"""
    out = llm._penalty_params(1.0, 256)
    assert "presence_penalty" not in out


def test_repeat_penalty_not_sent_by_default():
    """repeat_penalty 不再是默认字段（改由后备链路使用）。"""
    out = llm._penalty_params(1.1, 256)
    assert "repeat_penalty" not in out
    assert "repeat_last_n" not in out


def test_repeat_fallback_params_pairs():
    """后备链路：repeat_penalty 偏离 1.0 时发，repeat_last_n 配对带出。"""
    out = llm._repeat_fallback_params(1.1, 256)
    assert out["repeat_penalty"] == 1.1
    assert out["repeat_last_n"] == 256


def test_repeat_fallback_last_n_zero_omitted():
    """repeat_last_n=0 表示不管范围，只发 repeat_penalty。"""
    out = llm._repeat_fallback_params(1.15, 0)
    assert out["repeat_penalty"] == 1.15
    assert "repeat_last_n" not in out


def test_penalty_garbage_falls_back_to_default():
    """非法值不应崩或发出垃圾，回落 DEFAULTS。"""
    out = llm._repeat_fallback_params("abc", "xyz")
    assert out["repeat_penalty"] == llm.DEFAULTS["repeat_penalty"]
    assert out["repeat_last_n"] == llm.DEFAULTS["repeat_last_n"]


# ---------- min_p：动态截断（v0.21.2）----------

def test_min_p_sent_by_default():
    """min_p 缺省 0.02 非中性，默认就会发送（是本次抗退化的主力参数）。"""
    assert llm._penalty_params(1.0, 256)["min_p"] == 0.02


def test_min_p_zero_omitted():
    """显式填 0 = 不启用动态截断，不发该字段（交后端缺省）。"""
    out = llm._penalty_params(1.0, 256, min_p=0.0)
    assert "min_p" not in out


def test_min_p_garbage_falls_back():
    out = llm._penalty_params(1.0, 256, min_p="坏值")
    assert out["min_p"] == llm.DEFAULTS["min_p"]


def test_min_p_independent_of_repeat_penalty():
    """min_p 与惩罚字段独立：惩罚中性不发，mp 仍发。"""
    out = llm._penalty_params(1.0, 0, min_p=0.05)
    assert out["min_p"] == 0.05


def test_strip_penalty_removes_all_penalty_fields():
    """网关拒收时须把标准 + 扩展字段全剥掉，否则重试仍会 400。"""
    p = {"model": "m", "frequency_penalty": 0.3, "presence_penalty": 0.2,
         "repeat_penalty": 1.1, "repeat_last_n": 256, "min_p": 0.02,
         "temperature": 0.85}
    out = llm._strip_penalty(dict(p))
    for k in (*llm._STD_FIELDS, *llm._EXT_FIELDS):
        assert k not in out
    assert out["temperature"] == 0.85  # 标准字段不受影响


def test_std_fields_cover_frequency_presence():
    """_STD_FIELDS 是标准字段降级判据来源。"""
    assert set(llm._STD_FIELDS) == {"frequency_penalty", "presence_penalty"}


def test_ext_fields_cover_repeat_and_min_p():
    """_EXT_FIELDS 是 llama.cpp 后备 + min_p 的剥离判据来源。"""
    assert set(llm._EXT_FIELDS) == {"repeat_penalty", "repeat_last_n", "min_p"}


# ---------- 出厂默认 ----------

def test_defaults_temperature_user_preferred():
    """temperature 出厂默认 1.0：v0.24.0 对齐 simon 当前满意值（原 0.85 上调）。"""
    assert llm.DEFAULTS["temperature"] == 1.0


def test_defaults_min_p_conservative():
    assert llm.DEFAULTS["min_p"] == 0.02


def test_defaults_frequency_penalty_conservative():
    """frequency_penalty 出厂 0.3：能压复读又不伤合理重复（1.5 起会提前收尾）。"""
    assert llm.DEFAULTS["frequency_penalty"] == 0.3


# ---------- setting() 的 null 兜底 ----------

def test_setting_null_falls_back_to_default(monkeypatch, tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text('{"min_p": null, "temperature": null}', encoding="utf-8")
    monkeypatch.setattr(llm, "CONFIG_FILE", cfg)
    assert llm.setting("min_p") == llm.DEFAULTS["min_p"]
    assert llm.setting("temperature") == llm.DEFAULTS["temperature"]


def test_setting_missing_key_still_falls_back(monkeypatch, tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(llm, "CONFIG_FILE", cfg)
    assert llm.setting("min_p") == llm.DEFAULTS["min_p"]


def test_setting_valid_value_wins(monkeypatch, tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text('{"min_p": 0.05}', encoding="utf-8")
    monkeypatch.setattr(llm, "CONFIG_FILE", cfg)
    assert llm.setting("min_p") == 0.05


def test_save_config_garbage_string_falls_back(monkeypatch, tmp_path):
    cfg = tmp_path / "config.json"
    cfg.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(llm, "CONFIG_FILE", cfg)
    monkeypatch.setattr(llm, "list_models", lambda *a, **k: [])
    llm.save_config({"min_p": "abc", "temperature": "", "top_k": "xyz", "model": "m"})
    import json
    saved = json.loads(cfg.read_text(encoding="utf-8"))
    assert saved["min_p"] == llm.DEFAULTS["min_p"]
    assert saved["temperature"] == llm.DEFAULTS["temperature"]
    assert saved["top_k"] == llm.DEFAULTS["top_k"]


# ---------- 3：网关不认字段时的三级降级 ----------

class _Resp:
    """最小可用的流式响应桩。"""

    def __init__(self, status=200, content="OUT"):
        self.status_code = status
        self._content = content
        self.encoding = "utf-8"

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def close(self):
        pass

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("HTTP %d" % self.status_code)

    def iter_lines(self, decode_unicode=True):
        import json
        yield "data: " + json.dumps({"choices": [{"delta": {"content": self._content}}]})
        yield "data: [DONE]"


def test_gateway_rejects_std_fields_then_repeat_fallback(monkeypatch):
    """首个请求带标准字段被 4xx -> 降级到 repeat_penalty 重试成功。"""
    sent = []

    def fake_post(url, json=None, headers=None, stream=False, timeout=None):
        sent.append(json)
        if "frequency_penalty" in json or "presence_penalty" in json:
            return _Resp(status=400)
        return _Resp(status=200, content="成功")

    monkeypatch.setattr(llm.requests, "post", fake_post)
    monkeypatch.setattr(llm, "_file_config", lambda: dict(_CFG))
    out = "".join(llm.stream([{"role": "user", "content": "hi"}],
                             repeat_penalty=1.1, repeat_last_n=256))
    assert out == "成功"
    assert len(sent) == 2
    assert "frequency_penalty" in sent[0]
    assert "repeat_penalty" in sent[1]  # 降级后改发 repeat_penalty
    assert "frequency_penalty" not in sent[1]


def test_gateway_rejects_all_then_stripped(monkeypatch):
    """连 repeat_penalty 也 4xx -> 全剥，退回后端缺省。"""
    sent = []

    def fake_post(url, json=None, headers=None, stream=False, timeout=None):
        sent.append(json)
        return _Resp(status=400)

    monkeypatch.setattr(llm.requests, "post", fake_post)
    monkeypatch.setattr(llm, "_file_config", lambda: dict(_CFG))
    try:
        list(llm.stream([{"role": "user", "content": "hi"}],
                        repeat_penalty=1.1, repeat_last_n=256))
        assert False, "应抛出"
    except RuntimeError:
        pass
    # 三级降级：标准 -> repeat -> 全剥，共 3 次请求
    assert len(sent) == 3
    assert "frequency_penalty" in sent[0]
    assert "repeat_penalty" in sent[1]
    assert not any(k in sent[2] for k in (*llm._STD_FIELDS, *llm._EXT_FIELDS))


def test_no_penalty_no_extra_retry(monkeypatch):
    """请求体无任何惩罚字段时，4xx 直接抛，不做降级重试（不掩盖真实错误）。"""
    calls = []

    def fake_post(url, json=None, headers=None, stream=False, timeout=None):
        calls.append(json)
        return _Resp(status=400)

    monkeypatch.setattr(llm.requests, "post", fake_post)
    monkeypatch.setattr(llm, "_file_config", lambda: dict(_CFG))
    # 把 frequency/presence 都置中性，使请求体不含任何惩罚字段
    orig = llm.setting
    def _neutral(name):
        if name in ("frequency_penalty", "presence_penalty"):
            return 0.0
        return orig(name)
    monkeypatch.setattr(llm, "setting", _neutral)
    try:
        list(llm.stream([{"role": "user", "content": "hi"}], min_p=0.0))
        assert False, "应抛出"
    except RuntimeError:
        pass
    assert len(calls) == 1
    assert not any(k in calls[0] for k in (*llm._STD_FIELDS, *llm._EXT_FIELDS))


# ---------- 4：配置持久化 ----------

def test_penalty_writable_and_typed(monkeypatch, tmp_path):
    """频率/存在惩罚字段可经 save_config 持久化，且按正确类型落盘。

    v0.22.x 起 repeat_penalty / repeat_last_n 从 _WRITABLE 移除（降为纯内部后备，
    用户只面对「重复度惩罚」= frequency_penalty），故此处断言它们不被写入。
    """
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(llm, "CONFIG_FILE", cfg_path)
    monkeypatch.setattr(llm, "list_models", lambda *a, **k: [])
    llm.save_config({"frequency_penalty": "0.4", "presence_penalty": "0.1",
                     "repeat_penalty": "1.15", "repeat_last_n": "128", "model": "m"})
    import json
    saved = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert saved["frequency_penalty"] == 0.4
    assert saved["presence_penalty"] == 0.1
    # repeat_* 已不在 _WRITABLE，须被忽略、不落盘
    assert "repeat_penalty" not in saved
    assert "repeat_last_n" not in saved
    assert isinstance(saved["frequency_penalty"], float)
    assert isinstance(saved["presence_penalty"], float)


def test_min_p_writable_and_typed(monkeypatch, tmp_path):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(llm, "CONFIG_FILE", cfg_path)
    monkeypatch.setattr(llm, "list_models", lambda *a, **k: [])
    llm.save_config({"min_p": "0.05", "model": "m"})
    import json
    saved = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert saved["min_p"] == 0.05
    assert isinstance(saved["min_p"], float)


def test_defaults_are_conservative():
    """出厂默认须是保守档。repeat_penalty 保留作后备，仍取 1.1 / 256。"""
    assert llm.DEFAULTS["repeat_penalty"] == 1.1
    assert llm.DEFAULTS["repeat_last_n"] == 256
