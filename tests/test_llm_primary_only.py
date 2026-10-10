"""LLM 单后端直连（无降级）守护用例。

引擎已移除 fallback 降级机制：stream()/complete() 只打主配置一次，
主配置失败直接抛异常，绝不回落到 config 里的 fallback 段（若仍存在）。
覆盖点：
- 主配置成功 -> 正常产出，只调用一次
- 主配置失败 -> 抛出异常，且只调用一次（即使 config 含 fallback 段也不回落）
- complete 路径同：成功产出 / 失败抛异常且只调用一次
所有网络请求 mock requests.post，自给自足，不依赖磁盘剧本/真实后端。
"""
import llm


_CFG = {
    "base_url": "https://api.siliconflow.cn/v1",
    "api_key": "sk-primary",
    "model": "deepseek-ai/DeepSeek-V4-Flash",
    "enable_thinking": False,
    # 故意保留 fallback 段：验证引擎已不再读取/回落它。
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
        self.status_code = 200 if not fail else 500

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
        self.status_code = 200 if not fail else 500

    def raise_for_status(self):
        if self._fail:
            raise RuntimeError("primary down")

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


def _install(monkeypatch, fail, content="OUT"):
    calls = []

    def fake_post(url, json=None, headers=None, stream=False, timeout=None):
        calls.append(url)
        if stream:
            return _FakeStreamResp(url, content, fail=fail)
        return _FakeCompleteResp(url, content, fail=fail)

    monkeypatch.setattr(llm.requests, "post", fake_post)
    monkeypatch.setattr(llm, "_file_config", lambda: dict(_CFG))
    return calls


def test_stream_success(monkeypatch):
    calls = _install(monkeypatch, fail=False, content="主")
    out = "".join(llm.stream([{"role": "user", "content": "hi"}]))
    assert out == "主"
    assert len(calls) == 1
    assert "siliconflow" in calls[0]


def test_stream_failure_raises_and_no_fallback(monkeypatch):
    calls = _install(monkeypatch, fail=True)
    try:
        list(llm.stream([{"role": "user", "content": "hi"}]))
        assert False, "主配置失败应抛异常"
    except RuntimeError:
        pass
    # 关键：即使 config 含 fallback 段，也只打了一次、绝不回落到 1234。
    assert len(calls) == 1
    assert "1234" not in calls[0]


def test_complete_success(monkeypatch):
    calls = _install(monkeypatch, fail=False, content="完整")
    out = llm.complete([{"role": "user", "content": "hi"}])
    assert out == "完整"
    assert len(calls) == 1
    assert "siliconflow" in calls[0]


def test_complete_failure_raises_and_no_fallback(monkeypatch):
    calls = _install(monkeypatch, fail=True)
    try:
        llm.complete([{"role": "user", "content": "hi"}])
        assert False, "主配置失败应抛异常"
    except RuntimeError:
        pass
    assert len(calls) == 1
    assert "1234" not in calls[0]
