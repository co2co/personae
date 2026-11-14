"""分发包内 config.json 的洗白与定型契约守护（移植自 nsfw 线 307e7b6）。

锁两件事，都因为「失败会静默」才单独写文件：
  1. 包内 config 的形状（键序 + 键集合）由引擎侧 llm.DEFAULTS 决定，与工作树那份解耦。
     形状一旦跟着工作树漂，同一条发布线两次打包的 zip 字节就不同，历史包不能逐字节比对。
  2. 洗白失败只许当场停，绝不退回「把未洗白的原始 config 原样打进包」——那条路径在
     master 上仍然存在（except Exception: z.write(full, arcname)），且全程不报错，
     后果是本地 base_url / api_key / provider 连接随包外流。

全部走 tmp_path，不碰 dist/；除可复现性那两条真打包外，其余只调纯函数。
"""
import importlib.util
import json
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CONFIG_ARCNAME = "engine/data/config.json"


@pytest.fixture(scope="module")
def pkg():
    spec = importlib.util.spec_from_file_location("_pkg_scrub", ROOT / "package.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def defaults(pkg):
    return pkg._ENGINE_DEFAULTS


def _shuffled(cfg):
    """把 dict 键序打乱成另一种插入序：内容等价，形状不同。"""
    return {k: cfg[k] for k in reversed(list(cfg))}


def test_same_content_different_insertion_order_yields_identical_bytes(pkg, defaults):
    """这次收口的正题：包内 config 不该跟着工作树的键序走。"""
    dev = {"model": "qwen", "base_url": "http://127.0.0.1:8080/v1", "api_key": "sk-x",
           "providers": [{"key": "p1"}], "max_tokens": 4096, "temperature": 0.9,
           "top_p": 0.95, "top_k": 40, "min_p": 0.02, "frequency_penalty": 0.3,
           "saved_models": [], "enable_thinking": False}
    a = json.dumps(pkg._factory_config(dev, defaults), ensure_ascii=False, indent=2)
    b = json.dumps(pkg._factory_config(_shuffled(dev), defaults), ensure_ascii=False, indent=2)
    assert a == b, "内容等价、仅键序不同的 config，打进包应当逐字节相同"


def test_never_carries_endpoint_key_or_model(pkg, defaults):
    cfg = {"base_url": "http://10.0.0.7:1234/v1", "api_key": "sk-secret-real",
           "model": "my-fine-tune", "providers": [{"key": "k", "api_key": "sk-2"}]}
    out = pkg._factory_config(cfg, defaults)
    assert out["base_url"] == "" and out["api_key"] == "" and out["model"] == ""
    assert out["providers"] == []
    assert "sk-secret-real" not in json.dumps(out, ensure_ascii=False)


@pytest.mark.parametrize("wild", ["writer", "fallback", "repeat_penalty", "repeat_last_n",
                                  "debug_flag", "absolute_gguf_path"])
def test_wild_and_retired_fields_never_ship(pkg, defaults, wild):
    """规范骨架是白名单：工作树里躺着什么野字段都不该带进包。"""
    cfg = {"base_url": "x", wild: "personal-content"}
    assert wild not in pkg._factory_config(cfg, defaults)


def test_missing_keys_filled_from_defaults_not_dropped(pkg, defaults):
    """工作树没写的字段补出厂值，而不是让出厂包形状随缺键变化。"""
    assert "saved_models" in defaults, "该断言依赖 DEFAULTS 含 saved_models，变了请同步本用例"
    out = pkg._factory_config({"base_url": "x"}, defaults)
    assert out["saved_models"] == defaults["saved_models"]


def test_shape_follows_defaults_not_a_hardcoded_copy(pkg, defaults):
    """形状必须随 defaults 走——手抄一份键序表，就是下一次漂移的起点。"""
    probe = {"brand_new_field": 42, "repeat_penalty": 1.1}
    probe.update(defaults)
    out = pkg._factory_config({}, probe)
    assert out["brand_new_field"] == 42
    assert "repeat_penalty" not in out
    assert list(out) == ([k for k in probe if k not in pkg._HIDDEN_DEFAULT_KEYS]
                         + list(pkg._FACTORY_EXTRA_KEYS))


def test_engine_defaults_must_be_loadable_or_packaging_refuses(pkg, monkeypatch):
    """出厂真值取不到就停手：返回 {} 会让采样参数整段绕过洗白、骨架塌空还照发（v0.21.2 同型）。"""
    with monkeypatch.context() as mp:
        mp.setattr(pkg, "ENGINE", pkg.Path("does-not-exist"))
        with pytest.raises(RuntimeError):
            pkg._load_engine_defaults()


def test_scrub_failure_refuses_to_ship_and_leaves_no_package(pkg, tmp_path, monkeypatch):
    """洗白失败必须停手并清掉半成品，不能退回原样打包。"""
    out = tmp_path / "boom.zip"

    def _boom(cfg, dflt):
        raise ValueError("simulated scrub failure")

    monkeypatch.setattr(pkg, "_factory_config", _boom)
    with pytest.raises(RuntimeError):
        pkg.build(str(out))
    assert not out.exists(), "半成品包必须删除：它看起来像成品，误发就是夹带个人 config"


def test_shipped_config_is_reproducible_and_scrubbed(pkg, tmp_path):
    """端到端：连打两次，包内 config 必须一模一样，且敏感字段已空。"""
    a, b = tmp_path / "a.zip", tmp_path / "b.zip"
    pkg.build(str(a))
    pkg.build(str(b))

    def raw(p):
        with zipfile.ZipFile(p) as z:
            return z.read(CONFIG_ARCNAME)

    assert raw(a) == raw(b), "同一棵树连打两次，config 字节必须一致"
    cfg = json.loads(raw(a).decode("utf-8"))
    assert cfg["base_url"] == "" and cfg["api_key"] == "" and cfg["model"] == ""
    assert cfg["providers"] == []
    assert not (set(cfg) & {"repeat_penalty", "repeat_last_n", "writer"})
    # 幂等：已定型的形状再过一遍定型，结果不变
    assert pkg._factory_config(cfg, pkg._ENGINE_DEFAULTS) == cfg
