"""LLM 降级（fallback）机制单测。

覆盖点：
- 主配置产出前失败 -> 自动切本地兜底成功
- 主配置成功 -> 不触发兜底
- 显式指定 base_url/model -> 不降级（尊重调用方意图）
- 全部候选失败 -> 抛出最后一个异常
- complete 路径同样支持降级
所有网络请求 mock requests.post，自给自足，不依赖磁盘剧本/真实后端。
"""
import llm


_CFG = {
    "base_url": "https://api.siliconflow.cn/v1",
    "api_key": "sk-primary",
    "model": "deepseek-ai/DeepSeek-V4-Flash",
    "enable_thinking": False,
    "fallback": {
        "base_url": "http://127.0.0.1:1234/v1",
        "api_key": "",
        "model": "local.gguf",
    },
}


class _FakeStreamResp:
    def __init__(self, url, content, fail=False):
        self._url = url
        self._content = content
        self._fail = fail
        self.encoding = "utf-8"

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def raise_for_status(self):
        if self._fail:
            raise RuntimeError("primary down")

    def iter_lines(self, decode_unicode=True):
        import json
        yield "data: " + json.dumps({"choices": [{"delta": {"content": self._content}}]})
        yield "data: [DONE]"


class _FakeCompleteResp:
    def __init__(self, url, content, fail=False):
        self._url = url
        self._content = content
        self._fail = fail
        self.encoding = "utf-8"

    def raise_for_status(self):
        if self._fail:
            raise RuntimeError("primary down")

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


def _install(monkeypatch, primary_ok, content="OUT"):
    calls = []

    def fake_post(url, json=None, headers=None, stream=False, timeout=None):
        calls.append(url)
        is_primary = "siliconflow" in url
        if stream:
            return _FakeStreamResp(url, content, fail=(not primary_ok and is_primary))
        return _FakeCompleteResp(url, content, fail=(not primary_ok and is_primary))

    monkeypatch.setattr(llm.requests, "post", fake_post)
    monkeypatch.setattr(llm, "_file_config", lambda: dict(_CFG))
    return calls


def test_stream_fallback_on_primary_failure(monkeypatch):
    calls = _install(monkeypatch, primary_ok=False, content="本地兜底")
    out = "".join(llm.stream([{"role": "user", "content": "hi"}]))
    assert out == "本地兜底"
    assert len(calls) == 2  # 主 + 兜底
    assert "1234" in calls[1]


def test_stream_no_fallback_when_primary_ok(monkeypatch):
    calls = _install(monkeypatch, primary_ok=True, content="主")
    out = "".join(llm.stream([{"role": "user", "content": "hi"}]))
    assert out == "主"
    assert len(calls) == 1  # 只打了主


def test_stream_no_fallback_when_model_explicit(monkeypatch):
    calls = _install(monkeypatch, primary_ok=False)
    try:
        list(llm.stream([{"role": "user", "content": "hi"}], model="forced-model"))
        assert False, "应抛出（单后端失败且未降级）"
    except RuntimeError:
        pass
    assert len(calls) == 1  # 显式 model 不触发兜底


def test_stream_all_fail_raises(monkeypatch):
    calls = []

    def fake_post(url, **kw):
        calls.append(url)
        return _FakeStreamResp(url, "", fail=True)

    monkeypatch.setattr(llm.requests, "post", fake_post)
    monkeypatch.setattr(llm, "_file_config", lambda: dict(_CFG))
    try:
        list(llm.stream([{"role": "user", "content": "hi"}]))
        assert False
    except RuntimeError:
        pass
    assert len(calls) == 2


def test_complete_fallback_on_primary_failure(monkeypatch):
    calls = _install(monkeypatch, primary_ok=False, content="兜底文本")
    out = llm.complete([{"role": "user", "content": "hi"}])
    assert out == "兜底文本"
    assert len(calls) == 2


def test_chain_configs_default_includes_fallback():
    monkey = None  # 直接测纯函数，先 mock _file_config
    import llm as _l
    # 用一个临时 monkeypatch 上下文
    import _pytest.monkeypatch as mp
    m = mp.MonkeyPatch()
    try:
        m.setattr(_l, "_file_config", lambda: dict(_CFG))
        cands = _l._chain_configs(None, None, None)
        assert cands[0][0] == "https://api.siliconflow.cn/v1"
        assert cands[-1][0] == "http://127.0.0.1:1234/v1"
        assert len(cands) == 2
    finally:
        m.undo()


def test_chain_configs_explicit_excludes_fallback():
    import llm as _l
    import _pytest.monkeypatch as mp
    m = mp.MonkeyPatch()
    try:
        m.setattr(_l, "_file_config", lambda: dict(_CFG))
        cands = _l._chain_configs(None, None, "explicit-model")
        assert len(cands) == 1  # 显式 model -> 不降级
    finally:
        m.undo()
