"""重复惩罚（repeat_penalty / repeat_last_n）机制单测。

背景（v0.21.1）：会话 606e6b9a 出现整段剧情重发（25 段 / 1087 字 = 全文 33%）。
实测根因是请求体**从未发送 repeat_penalty**——llama.cpp 吃服务端缺省 1.0（=无惩罚），
在 temperature=1.0 / top_k=40 的高熵档下，长输出到千字量级有可观概率 n-gram 回卷。
对照组实测：不传 → 重复 1.5%；传 1.1 → 0%。

本文件锁死以下契约：
1. 中性值（repeat_penalty=1.0）不发字段——各后端缺省即中性，发过去无增益且可能被严格网关判未知参数。
2. 显式偏离中性值时才发，且 repeat_last_n 与 repeat_penalty 配对。
3. 网关不认该扩展（4xx）时自动剥离并重试一次，不让整轮生成失败。
4. 字段可经 config 持久化（_WRITABLE + 类型转换）。

v0.21.2 追加：min_p（动态截断，抗长输出语义坍缩）+ temperature 出厂默认降到 0.85。
5. min_p 缺省 0.02 会发送；显式 0 则不发；与 repeat_penalty 相互独立。
6. _EXT_FIELDS 是 4xx 剥离重试的唯一判据来源，新增扩展字段必须登记在此。

所有网络请求 mock requests.post，自给自足，不依赖磁盘剧本/真实后端。
"""
import llm


_CFG = {
    "base_url": "http://127.0.0.1:1234/v1",
    "api_key": "",
    "model": "local.gguf",
    "enable_thinking": False,
}


# ---------- 1/2：字段发送规则 ----------

def test_neutral_penalty_not_sent():
    """中性值 1.0 不发惩罚字段：缺省即无惩罚，且避免被严格网关判未知参数。

    注：min_p 与 repeat_penalty 独立，缺省 0.02 仍会发（v0.21.2 起），
    故此处只断言惩罚两类字段缺席。
    """
    out = llm._penalty_params(1.0, 256)
    assert "repeat_penalty" not in out
    assert "repeat_last_n" not in out


def test_default_penalty_sent():
    """偏离中性值时发送，且 repeat_last_n 配对带出。"""
    out = llm._penalty_params(1.1, 256)
    assert out["repeat_penalty"] == 1.1
    assert out["repeat_last_n"] == 256


def test_repeat_last_n_zero_omitted():
    """repeat_last_n=0 表示不管范围，只发 repeat_penalty（用后端缺省范围）。"""
    out = llm._penalty_params(1.15, 0)
    assert out["repeat_penalty"] == 1.15
    assert "repeat_last_n" not in out


def test_penalty_garbage_falls_back_to_default():
    """非法值不应崩或发出垃圾，回落 DEFAULTS。"""
    out = llm._penalty_params("abc", "xyz")
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
    # 中性 repeat_penalty 也不发，但 min_p=0 时整个扩展集应为空
    assert out == {}


def test_min_p_garbage_falls_back():
    out = llm._penalty_params(1.0, 256, min_p="坏值")
    assert out["min_p"] == llm.DEFAULTS["min_p"]


def test_min_p_independent_of_repeat_penalty():
    """两者独立：rp 中性不发，mp 仍发；反之亦然。"""
    out = llm._penalty_params(1.0, 0, min_p=0.05)
    assert "repeat_penalty" not in out and "repeat_last_n" not in out
    assert out["min_p"] == 0.05


def test_strip_penalty_removes_all_ext_fields():
    """网关拒收时须把三类扩展字段全剥掉，否则重试仍会 400。"""
    p = {"model": "m", "repeat_penalty": 1.1, "repeat_last_n": 256, "min_p": 0.02,
         "temperature": 0.85}
    out = llm._strip_penalty(dict(p))
    for k in llm._EXT_FIELDS:
        assert k not in out
    assert out["temperature"] == 0.85  # 标准字段不受影响


def test_ext_fields_cover_repeat_and_min_p():
    """_EXT_FIELDS 是 4xx 剥离重试的唯一判据来源，新增扩展必须登记在此。"""
    assert set(llm._EXT_FIELDS) == {"repeat_penalty", "repeat_last_n", "min_p"}


# ---------- 出厂默认（v0.21.2：温度下调 + min_p）----------

def test_defaults_temperature_lowered():
    """temperature 出厂默认 0.85：1.0 属高熵档，实测长输出有 30% 概率中途语义坍缩。"""
    assert llm.DEFAULTS["temperature"] == 0.85


def test_defaults_min_p_conservative():
    assert llm.DEFAULTS["min_p"] == 0.02


# ---------- setting() 的 null 兜底（v0.21.2）----------

def test_setting_null_falls_back_to_default(monkeypatch, tmp_path):
    """config 里存 null 应与「键缺失」同义，回退出厂默认。

    前端 save_config 对清空的输入框给 parseFloat('')=NaN，落盘即 null。
    若不兜住，float(None) 会崩 / None 被当有效值传给后端。
    """
    cfg = tmp_path / "config.json"
    cfg.write_text('{"min_p": null, "temperature": null}', encoding="utf-8")
    monkeypatch.setattr(llm, "CONFIG_FILE", cfg)
    assert llm.setting("min_p") == llm.DEFAULTS["min_p"]
    assert llm.setting("temperature") == llm.DEFAULTS["temperature"]


def test_setting_missing_key_still_falls_back(monkeypatch, tmp_path):
    """回归：键缺失的原有行为不变。"""
    cfg = tmp_path / "config.json"
    cfg.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(llm, "CONFIG_FILE", cfg)
    assert llm.setting("min_p") == llm.DEFAULTS["min_p"]


def test_setting_valid_value_wins(monkeypatch, tmp_path):
    """回归：有效值照常生效，不被 null 兜底逻辑误伤。"""
    cfg = tmp_path / "config.json"
    cfg.write_text('{"min_p": 0.05}', encoding="utf-8")
    monkeypatch.setattr(llm, "CONFIG_FILE", cfg)
    assert llm.setting("min_p") == 0.05


def test_save_config_garbage_string_falls_back(monkeypatch, tmp_path):
    """非法字符串不得让整次保存 500（float('abc') 会抛 ValueError 穿透）。"""
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


# ---------- 3：网关不认扩展时剥离重试 ----------

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


def test_gateway_rejects_penalty_then_retries_without(monkeypatch):
    """首个请求带惩罚被网关 4xx 拒收 -> 自动剥离后重试一次并成功。"""
    sent = []

    def fake_post(url, json=None, headers=None, stream=False, timeout=None):
        sent.append(json)
        if "repeat_penalty" in json:
            return _Resp(status=400)
        return _Resp(status=200, content="成功")

    monkeypatch.setattr(llm.requests, "post", fake_post)
    monkeypatch.setattr(llm, "_file_config", lambda: dict(_CFG))
    out = "".join(llm.stream([{"role": "user", "content": "hi"}]))
    assert out == "成功"
    assert len(sent) == 2
    assert "repeat_penalty" in sent[0]
    assert "repeat_penalty" not in sent[1]  # 重试时已剥离
    assert "repeat_last_n" not in sent[1]


def test_no_penalty_no_extra_retry(monkeypatch):
    """中性值下请求本就干净，4xx 不触发剥离重试（不掩盖真实错误）。"""
    calls = []

    def fake_post(url, json=None, headers=None, stream=False, timeout=None):
        calls.append(json)
        return _Resp(status=400)

    monkeypatch.setattr(llm.requests, "post", fake_post)
    monkeypatch.setattr(llm, "_file_config", lambda: dict(_CFG))
    try:
        list(llm.stream([{"role": "user", "content": "hi"}],
                        repeat_penalty=1.0, min_p=0.0))
        assert False, "应抛出"
    except RuntimeError:
        pass
    # 扩展字段全缺席 -> 请求本就干净，4xx 不触发剥离重试（不掩盖真实错误）
    assert len(calls) == 1
    assert not any(k in calls[0] for k in llm._EXT_FIELDS)


# ---------- 4：配置持久化 ----------

def test_penalty_writable_and_typed(monkeypatch, tmp_path):
    """两个字段可经 save_config 持久化，且按正确类型落盘。"""
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(llm, "CONFIG_FILE", cfg_path)
    # 关掉「model 为空则去后端取第一个」的自动补全，避免真实网络
    monkeypatch.setattr(llm, "list_models", lambda *a, **k: [])
    llm.save_config({"repeat_penalty": "1.15", "repeat_last_n": "128", "model": "m"})
    import json
    saved = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert saved["repeat_penalty"] == 1.15
    assert saved["repeat_last_n"] == 128
    assert isinstance(saved["repeat_penalty"], float)
    assert isinstance(saved["repeat_last_n"], int)


def test_min_p_writable_and_typed(monkeypatch, tmp_path):
    """min_p 也可经 save_config 持久化为 float。"""
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
    """出厂默认须是保守档：1.1 / 256。过高会让用词僵硬、丧失随机性。"""
    assert llm.DEFAULTS["repeat_penalty"] == 1.1
    assert llm.DEFAULTS["repeat_last_n"] == 256
