"""重复惩罚（repeat_penalty / repeat_last_n）机制单测。

背景（v0.21.1）：会话 606e6b9a 出现整段剧情重发（25 段 / 1087 字 = 全文 33%）。
实测根因是请求体**从未发送 repeat_penalty**——llama.cpp 吃服务端缺省 1.0（=无惩罚），
在 temperature=1.0 / top_k=40 的高熵档下，长输出到千字量级有可观概率 n-gram 回卷。
对照组实测：不传 → 重复 1.5%；传 1.1 → 0%。

本文件锁死四条契约：
1. 中性值（1.0）不发字段——各后端缺省即中性，发过去无增益且可能被严格网关判未知参数。
2. 显式偏离中性值时才发，且 repeat_last_n 与 repeat_penalty 配对。
3. 网关不认该扩展（4xx）时自动剥离并重试一次，不让整轮生成失败。
4. 两个字段可经 config 持久化（_WRITABLE + 类型转换）。

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
    """中性值 1.0 不发字段：缺省即无惩罚，且避免被严格网关判未知参数。"""
    assert llm._penalty_params(1.0, 256) == {}


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
        list(llm.stream([{"role": "user", "content": "hi"}], repeat_penalty=1.0))
        assert False, "应抛出"
    except RuntimeError:
        pass
    assert len(calls) == 1


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


def test_defaults_are_conservative():
    """出厂默认须是保守档：1.1 / 256。过高会让用词僵硬、丧失随机性。"""
    assert llm.DEFAULTS["repeat_penalty"] == 1.1
    assert llm.DEFAULTS["repeat_last_n"] == 256
