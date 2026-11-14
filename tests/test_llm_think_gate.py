"""思考块兜底闸 + 生成插桩的单测（2026-11-15，从 nsfw 线手工重做）。

背景：
  - master 此前对「模型把思考吐进 content」零防线。脏文穿过净身落进 chat.jsonl，就成了
    下一轮的 assistant 示范，泄漏自我复制；极端形态是整条回复只有标记、正文 0 字。
  - 请求侧关不掉：preserve_thinking 在顶层与 chat_template_kwargs 两种放法下都被后端
    静默丢弃（prompt_tokens delta 恒 0，六臂对照见 nsfw 线 DEVLOG），故正文防线只能收在
    「取 delta.content」这一层。

本文件锁死以下契约：
  1. 无标记正文逐字透传，不增不减（含空白）。
  2. 标记跨 SSE 分片到达也整段吞掉，切在哪一片都一样。
  3. 未闭合的思考块整段丢弃并置 truncated：「整轮只有 think」必须落到 0 字，
     由 app.py 既有的「净身后为空即重试」接住。
  4. 只认 think / thinking 标记，正文里的中文「思考」与裸英文 think 不受影响。
  5. 块外空白不归本闸管：标记删掉后前后文本原样接上，空行交给 narrative_clean 收口。
  6. 孤立的闭标记（无开标记）只删标记本身，前置文本必须保留——模板给 assistant 的
     前缀是「<think>\\n\\n</think>\\n\\n」，模型照抄时可能只吐后半截。
  7. 非流式路径（complete）同样剥，且剥出来的计数进 stats。
  8. 要 stats 才发 stream_options；不要时请求体逐字节不变。stream_options 已登记进
     _VENDOR_FIELDS，严格网关 400 时能被降级链路剥掉重试。

不调真实后端：requests.post 全部 mock。
"""
import json

import llm

_CFG = {
    "base_url": "http://127.0.0.1:1234/v1",
    "api_key": "",
    "model": "local.gguf",
    "enable_thinking": False,
}


def _run(*pieces):
    """把若干片喂过闸，返回 (外发文本, 命中块数, 是否未闭合)。"""
    gate = llm._ThinkGate()
    out = "".join(gate.feed(p) for p in pieces)
    out += gate.flush()
    return out, gate.stripped, gate.truncated


# ---------- 1 / 4：零误伤 ----------

def test_plain_text_passes_untouched():
    assert _run("她站起来，没有说话。") == ("她站起来，没有说话。", 0, False)


def test_plain_word_think_is_not_a_marker():
    """中文「思考」与裸英文 think 出现在正文里都不该触发剥离。"""
    text = "他思考了一会儿，又 think 了一句。"
    assert _run(text) == (text, 0, False)


def test_partial_open_marker_is_held_not_emitted():
    """开标记被切在两片之间时，前半段必须扣住，不能先吐出去再后悔。"""
    gate = llm._ThinkGate()
    assert gate.feed("前段<thi") == "前段"
    assert gate.feed("nk>想的") == ""     # 确认进块：扣住的内容一并不外发
    assert gate.feed("正文") == ""        # 仍在块内
    assert gate.feed("\n</think>\n\n后段") == "\n\n后段"
    assert gate.flush() == ""
    assert gate.stripped == 1


# ---------- 2 / 3 / 5：整段吞掉，块外空白原样保留 ----------

def test_block_inside_single_chunk():
    assert _run("前段<think>想了一路\n</think>\n后段") == ("前段\n后段", 1, False)


def test_markers_split_across_many_chunks():
    """开标记、思考文本、闭标记各被切在别处——整段仍必须消失。"""
    pieces = ["\n用", "户要求我写第", "26幕\n\n", "他", "<thi", "nk>",
              "\n</th", "inking>", ""]
    assert _run(*pieces) == ("\n用户要求我写第26幕\n\n他", 1, False)


def test_unclosed_block_is_swallowed_and_flagged():
    """被 max_tokens 切在思考里：一个字都不能外发，否则脏文进历史。"""
    assert _run("正文", "<think>只想到一半") == ("正文", 1, True)


def test_two_blocks_keep_the_text_between_them():
    got, n, _ = _run("甲<think>一\n</think>\n乙\n</think>\n丙")
    assert got == "甲\n乙\n\n丙" and n == 2


def test_template_prefix_shape_is_neutralized():
    """模板前缀的真实形状：<think>\\n\\n</think>\\n\\n + 正文。只剩正文。"""
    got, n = llm.strip_think("<think>\n\n</think>\n\n他推门进来。")
    assert got.strip() == "他推门进来。" and n == 1


# ---------- 6：孤立闭标记 ----------

def test_orphan_close_marker_removed_but_text_kept():
    """只有闭标记、没有开标记：标记删掉，正文一个字都不能少。"""
    got, n = llm.strip_think("</think>\n\n他推门进来。")
    assert got.strip() == "他推门进来。" and n == 1


def test_orphan_close_marker_split_across_chunks():
    """孤立闭标记同样可能被切在多片里，必须照样删干净。"""
    got, n, _ = _run("正文。\n</th", "inking", ">\n\n后文。")
    assert "think" not in got.lower()
    assert got.replace("\n", "") == "正文。后文。" and n == 1


# ---------- 7 / 8：stats 与请求体 ----------

class _StreamResp:
    """最小流式响应桩：按顺序吐若干 SSE 帧，末尾给一帧 usage + [DONE]。"""

    def __init__(self, chunks, usage=None):
        self.status_code = 200
        self.encoding = "utf-8"
        self._chunks = chunks
        self._usage = usage

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def close(self):
        pass

    def raise_for_status(self):
        pass

    def iter_lines(self, decode_unicode=True):
        for c in self._chunks:
            yield "data: " + json.dumps({"choices": [{"delta": {"content": c}}]})
        if self._usage is not None:
            # usage 那一帧 choices 是空数组——真实后端就是这样，采计顺序错一格就读不到
            yield "data: " + json.dumps({"choices": [], "usage": self._usage})
        yield "data: [DONE]"


def _patch_post(monkeypatch, resp, sent):
    def fake_post(url, json=None, headers=None, stream=False, timeout=None):
        sent.append(json)
        return resp

    monkeypatch.setattr(llm.requests, "post", fake_post)
    monkeypatch.setattr(llm, "_file_config", lambda: dict(_CFG))


def test_stream_fills_stats(monkeypatch):
    """stats 必须带回 prompt/completion token 与思考块拦截计数。"""
    sent = []
    usage = {"prompt_tokens": 1234, "completion_tokens": 56, "total_tokens": 1290,
             "timings": {"predicted_n": 56, "draft_n_accepted": 7}}
    _patch_post(monkeypatch, _StreamResp(["正文", "<think>想", "\n</think>\n\n收尾"], usage), sent)
    stats = {}
    out = "".join(llm.stream([{"role": "user", "content": "hi"}], stats=stats))
    assert out.replace("\n", "") == "正文收尾"
    assert "think" not in out.lower()
    assert stats["prompt_tokens"] == 1234
    assert stats["completion_tokens"] == 56
    assert stats["think_stripped"] == 1
    assert stats["think_truncated"] is False
    # 要 stats 才发 stream_options（多一个字段多一次被严格网关拒的可能）
    assert sent[0]["stream_options"] == {"include_usage": True}


def test_stream_without_stats_keeps_old_payload(monkeypatch):
    """不传 stats 时请求体不额外带 stream_options（默认路径逐字节不变）。"""
    sent = []
    _patch_post(monkeypatch, _StreamResp(["无标记正文"]), sent)
    out = "".join(llm.stream([{"role": "user", "content": "hi"}]))
    assert out == "无标记正文"
    assert "stream_options" not in sent[0]


def test_stream_options_registered_as_vendor_field():
    """stream_options 必须在 _VENDOR_FIELDS 里，严格网关 400 时才剥得掉。"""
    assert "stream_options" in llm._VENDOR_FIELDS


def test_complete_strips_think_and_counts(monkeypatch):
    """非流式路径同样过闸：reflect 这类 JSON 输出被思考文本夹住会直接解析失败。"""
    sent = []

    class _Resp:
        status_code = 200
        encoding = "utf-8"

        def close(self):
            pass

        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {
                "content": "<think>\n\n</think>\n\n{\"ok\": true}"}}]}

    def fake_post(url, json=None, headers=None, stream=False, timeout=None):
        sent.append(json)
        return _Resp()

    monkeypatch.setattr(llm.requests, "post", fake_post)
    monkeypatch.setattr(llm, "_file_config", lambda: dict(_CFG))
    stats = {}
    out = llm.complete([{"role": "user", "content": "hi"}], stats=stats)
    assert out.strip() == "{\"ok\": true}"
    assert stats["think_stripped"] == 1
    # 非流式不发 stream_options（它是流式帧的采计开关，发过去没有意义）
    assert "stream_options" not in sent[0]
