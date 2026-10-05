"""S3 剧本→设定 提炼器单元测试。

覆盖：JSON 提取（包裹/前后缀）、白名单沙箱、秘密元字段、防注入、world 回写、缺 name 抛错，
以及用 monkeypatch 模拟 llm.complete 的端到端 refine。

真实线上 LLM 提炼已在 2026-10-02 用矽基流动 DeepSeek-V4-Flash 多次验证
（多种题材剧本，角色/世界书字段与 secret 标记均正确），
故此处不重复消耗额度，仅留一个手动跳过的真实 e2e 占位。
"""
import sys
import json

sys.path.insert(0, "engine")

import script_refiner as r
import llm


def test_extract_wrapped():
    assert r.extract_json('```json\n{"world":{"name":"X","entries":[]},"characters":[]}\n```')["world"]["name"] == "X"


def test_extract_embedded():
    t = '前缀文本\n{"world":{"name":"X","entries":[]},"characters":[]}\n后缀文本'
    assert r.extract_json(t)["world"]["name"] == "X"


def test_extract_invalid_raises():
    import pytest
    with pytest.raises(ValueError):
        r.extract_json("这不是 JSON 也没有对象")


def test_sanitize_drops_extra_fields():
    raw = {"world": {"name": "M", "entries": [{"keys": ["k"], "content": "c", "priority": 10,
                                                 "constant": False, "position": "after", "__evil__": "rm -rf /"}]},
           "characters": [{"name": "坏", "__evil__": "exec"}]}
    out = r.sanitize_refiner(raw)
    assert "__evil__" not in str(out)


def test_secret_keeps_meta():
    raw = {"world": {"name": "S", "entries": [{"keys": ["k"], "content": "c", "priority": 50,
                                               "constant": False, "position": "after", "secret": True,
                                               "character": "甲", "bottom_line": "暴露则死"}]},
           "characters": []}
    e = r.sanitize_refiner(raw)["world"]["entries"][0]
    assert e["secret"] and e["character"] == "甲" and e["bottom_line"] == "暴露则死"


def test_non_secret_drops_meta():
    raw = {"world": {"name": "N", "entries": [{"keys": ["k"], "content": "c", "priority": 50,
                                               "constant": False, "position": "after", "secret": False,
                                               "character": "x", "bottom_line": "y"}]},
           "characters": []}
    e = r.sanitize_refiner(raw)["world"]["entries"][0]
    assert "secret" not in e and "character" not in e and "bottom_line" not in e


def test_missing_name_raises():
    import pytest
    with pytest.raises(ValueError):
        r.sanitize_refiner({"world": {}, "characters": [{"description": "无 name"}]})


def test_world_name_backfill():
    raw = {"world": {"name": "W", "entries": []}, "characters": [{"name": "a", "description": "d"}]}
    c = r.sanitize_refiner(raw)["characters"][0]
    assert c["world"] == "W"


def test_refine_with_mock(monkeypatch):
    fake = ('{"world":{"name":"W","entries":[{"keys":["k"],"content":"c","priority":90,'
            '"constant":true,"position":"before"}]},'
            '"characters":[{"name":"甲","world":"W","description":"d","personality":"p",'
            '"short_goal":"g","relations":{"乙":"友"},'
            '"core_desire":"有","core_fear":"怕"}]}')
    monkeypatch.setattr(llm, "complete", lambda *a, **k: fake)
    out = r.refine_script("任意剧本文本")
    assert out["world"]["name"] == "W"
    assert out["characters"][0]["name"] == "甲"
    assert set(out["characters"][0].keys()) <= set(r.CHARACTER_FIELDS)
    assert "nsfw" not in out["characters"][0]


def test_refine_injection_dropped(monkeypatch):
    # LLM 若越权返回白名单外字段，应被沙箱丢弃
    fake = ('{"world":{"name":"W","entries":[{"keys":["k"],"content":"c","priority":10,'
            '"constant":false,"position":"after","__evil__":"drop table"}]},'
            '"characters":[{"name":"a","__evil__":"x"}]}')
    monkeypatch.setattr(llm, "complete", lambda *a, **k: fake)
    out = r.refine_script("剧本")
    assert "__evil__" not in str(out)


import pytest
@pytest.mark.skip(reason="需线上 LLM，手动跑：POST /api/import/from-script 真实剧本验证")
def test_real_e2e_against_live():
    out = r.refine_script("一座小城陷入混乱，退役兵老秦带着养女小满躲进地下车库……")
    assert out["world"]["name"]
    assert out["characters"]
