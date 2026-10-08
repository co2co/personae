"""后端适配：只支持 OpenAI 兼容协议一种，其余协议（Claude / Ollama / Kobold）全部砍掉。

如果以后要接别的，只需替换 stream() 的实现，上层 prompter 和 app 都不用动。

配置优先级：调用参数 > 环境变量 > data/config.json > 代码默认值。
改 data/config.json 不需要重启服务，每次请求都会重新读。
"""

import json
import os
from pathlib import Path

import requests

CONFIG_FILE = Path(__file__).parent / "data" / "config.json"

DEFAULTS = {
    "base_url": "http://127.0.0.1:1234/v1",
    "api_key": "sk-local",
    "model": "local",
    "budget": 4096,
    "max_tokens": 4096,
    "temperature": 0.9,
    "top_p": 0.95,
    "top_k": 40,
    # 重复惩罚：抑制长输出末尾的 n-gram 回卷（同一段剧情被整段重发）。
    # 1.0 = 不惩罚（llama.cpp 服务端默认，也是 OpenAI 兼容网关的缺省行为）。
    # 实测本地 27B 在 temperature=1.0 / top_k=40 下，输出到千字量级有可观概率整段复读；
    # 1.1 起明显收敛。取值过高会让用词僵硬、丧失随机性，故默认取 1.1（保守档）。
    "repeat_penalty": 1.1,
    # 惩罚作用范围：只对最近 N 个 token 生效（llama.cpp 的 repeat_last_n）。
    # 0 = 惩罚全部上下文。256 足够覆盖「复读的段落在数千 token 内」这一实际场景，
    # 又不必让惩罚波及很早的剧情事实（那里重复是合理的，如角色名、场景描写）。
    "repeat_last_n": 256,
    "enable_thinking": False,
    "saved_models": [],
}


# 刚部署（config.json 无 providers 字段）时默认空列表，
# 由用户在前端自行新增 / 管理 LLM 提供商（见「模型与生成」组）。
DEFAULT_PROVIDERS = []


def _clean_providers(raw):
    """把前端传来的 providers 归一化为可持久化的列表，剔除非法/重复项。"""
    if not isinstance(raw, (list, tuple)):
        return []
    clean, seen = [], set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        clean.append({
            "key": key,
            "name": str(item.get("name") or key),
            "base_url": str(item.get("base_url") or ""),
            "api_key": str(item.get("api_key") or ""),
            "model": str(item.get("model") or ""),
        })
    return clean


def _file_config():
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def setting(name):
    env = os.getenv("LLM_" + name.upper())
    if env:
        return env
    return _file_config().get(name, DEFAULTS[name])


def config_view():
    """给 /api/config 用。本地单用户工具，直接返回真实配置（含密钥），便于前端回填。"""
    cfg = dict(DEFAULTS)
    cfg.update(_file_config())
    # providers 缺省时为空列表（刚部署）；用户增删后的列表已持久化则直接用
    cfg.setdefault("providers", [])
    return cfg


# 用户可通过 UI 改动的字段；其余内部字段不暴露
_WRITABLE = {"base_url", "api_key", "model", "budget", "max_tokens", "top_k",
             "temperature", "top_p", "repeat_penalty", "repeat_last_n",
             "enable_thinking", "saved_models", "providers"}


def save_config(partial):
    """把用户改动的字段合并写回 data/config.json，其余字段保留。不重启即生效。"""
    cfg = _file_config()
    for k, v in (partial or {}).items():
        if k not in _WRITABLE:
            continue
        if k == "enable_thinking":
            v = bool(v)
        elif k in ("budget", "max_tokens", "top_k", "repeat_last_n"):
            v = int(v) if str(v).strip() else DEFAULTS[k]
        elif k in ("temperature", "top_p", "repeat_penalty"):
            v = float(v) if str(v).strip() else DEFAULTS[k]
        elif k == "saved_models":
            v = list(v) if isinstance(v, (list, tuple)) else []
        elif k == "providers":
            v = _clean_providers(v)
        cfg[k] = v
    # 模型留空时尝试从后端自动取第一个，避免发出空 model 字段
    if not str(cfg.get("model", "")).strip():
        try:
            models = list_models(cfg.get("base_url"), cfg.get("api_key"))
            if models:
                cfg["model"] = models[0]
        except Exception:
            pass
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return config_view()


def list_models(base_url=None, api_key=None):
    """连后端 /v1/models，成功返回模型 id 列表，失败抛异常。供连接测试与模型下拉用。"""
    url = (base_url or setting("base_url") or DEFAULTS["base_url"]).rstrip("/") + "/models"
    key = api_key if api_key is not None else setting("api_key")
    headers = {}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return [m.get("id") for m in data.get("data", [])]


def _fallback_config():
    """读取 config.json 的 fallback 段（兜底模型，如本地 llama.cpp）。未配置或非法返回 None。"""
    fb = _file_config().get("fallback")
    if not isinstance(fb, dict):
        return None
    bu = str(fb.get("base_url") or "").strip()
    if not bu:
        return None
    return {
        "base_url": bu,
        "api_key": str(fb.get("api_key") or ""),
        "model": str(fb.get("model") or ""),
    }


def _chain_configs(base_url, api_key, model):
    """本次调用要依次尝试的 (base_url, api_key, model) 候选序列。

    默认调用（未显式指定 base_url/model）：先主配置；若配置了 fallback 且与主配置不同，追加为兜底。
    显式指定 base_url 或 model 时：保持单后端，不降级（尊重调用方意图，如测试/指定 provider）。
    """
    primary = (
        (base_url or setting("base_url") or DEFAULTS["base_url"]),
        (api_key if api_key is not None else setting("api_key")),
        (model or setting("model")),
    )
    cands = [primary]
    if base_url is None and model is None:
        fb = _fallback_config()
        if fb and (fb["base_url"].rstrip("/") != primary[0].rstrip("/") or fb["model"] != primary[2]):
            cands.append((fb["base_url"], fb["api_key"], fb["model"]))
    return cands


def _penalty_params(repeat_penalty, repeat_last_n):
    """重复惩罚字段。仅在用户显式偏离中性值时才发——中性值与各后端缺省行为一致，
    发过去没有增益，却可能被严格校验的 OpenAI 兼容网关（vLLM/DeepSeek 等）判为
    未知参数而 400。故默认 1.0 / 0 一律不发。
    """
    out = {}
    try:
        rp = float(repeat_penalty)
    except (TypeError, ValueError):
        rp = DEFAULTS["repeat_penalty"]
    try:
        rn = int(repeat_last_n)
    except (TypeError, ValueError):
        rn = DEFAULTS["repeat_last_n"]
    if rp != 1.0:
        out["repeat_penalty"] = rp
        # repeat_last_n 是 llama.cpp 扩展，与 repeat_penalty 配对才有意义；
        # 网关若认 repeat_penalty 也通常认这个，但没给出值时用后端缺省更稳。
        if rn:
            out["repeat_last_n"] = rn
    return out


def _base_payload(messages, temperature, top_p, max_tokens, top_k, base_model,
                  repeat_penalty, repeat_last_n):
    """流式/非流式共用的请求体（采样参数 + 重复惩罚 + 思考开关）。"""
    payload = {
        "model": base_model,
        "messages": messages,
        "temperature": float(temperature if temperature is not None else setting("temperature")),
        "top_p": float(top_p if top_p is not None else setting("top_p")),
        "max_tokens": int(max_tokens if max_tokens is not None else setting("max_tokens")),
        "top_k": int(top_k if top_k is not None else setting("top_k")),
    }
    payload.update(_penalty_params(repeat_penalty, repeat_last_n))
    # Qwen3 一类带思考的模型默认会把预算耗在 reasoning 上，content 全是空
    if not setting("enable_thinking"):
        payload["chat_template_kwargs"] = {"enable_thinking": False}
        payload["enable_thinking"] = False  # SiliconFlow / OpenAI 兼容网关认顶层字段
    return payload


def _strip_penalty(payload):
    payload.pop("repeat_penalty", None)
    payload.pop("repeat_last_n", None)
    return payload


def _stream_once(messages, temperature, top_p, max_tokens, top_k, timeout, base_url, api_key, model,
                 repeat_penalty=None, repeat_last_n=None):
    """单次后端请求（流式）。产出前失败抛异常，由 stream() 决定是否降级。"""
    url = base_url.rstrip("/") + "/chat/completions"
    if repeat_penalty is None:
        repeat_penalty = setting("repeat_penalty")
    if repeat_last_n is None:
        repeat_last_n = setting("repeat_last_n")
    payload = _base_payload(messages, temperature, top_p, max_tokens, top_k, model,
                            repeat_penalty, repeat_last_n)
    payload["stream"] = True
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    def _post(p):
        return requests.post(url, json=p, headers=headers, stream=True, timeout=timeout)

    resp = _post(payload)
    # 网关不认 repeat_penalty/repeat_last_n（非标准扩展）时会 4xx。
    # 此时去掉这两个字段重试一次：宁可退回该后端的缺省惩罚，也不能整轮生成失败。
    # getattr 兜底：测试桩/非常规响应对象可能没有 status_code，此时不重试。
    if (getattr(resp, "status_code", 200) in (400, 404, 422)
            and ("repeat_penalty" in payload or "repeat_last_n" in payload)):
        resp.close()
        payload = _strip_penalty(dict(payload))
        payload["stream"] = True
        resp = _post(payload)
    with resp:
        resp.raise_for_status()
        # 上游不返回 charset 时 requests 会按 latin-1 解码，中文直接变乱码
        if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
            resp.encoding = "utf-8"
        for raw in resp.iter_lines(decode_unicode=True):
            if not raw or not raw.startswith("data:"):
                continue
            data = raw[5:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue
            choices = chunk.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            text = delta.get("content")
            if text:
                yield text


def stream(messages, temperature=None, top_p=None, max_tokens=None, top_k=None, timeout=180,
           base_url=None, api_key=None, model=None,
           repeat_penalty=None, repeat_last_n=None):
    """逐块产出文本。上游返回 SSE，这里只取 delta.content。

    默认调用支持降级：主配置在**产出首块前**失败时自动切到 fallback 重试；
    一旦已流出内容再失败则原样抛异常，绝不二次切换（避免重复文本）。
    显式指定 base_url/model 时不降级。全部候选失败抛最后一个异常。
    """
    cands = _chain_configs(base_url, api_key, model)
    last_exc = None
    for bu, key, mdl in cands:
        produced = False
        try:
            for text in _stream_once(messages, temperature, top_p, max_tokens, top_k, timeout,
                                     bu, key, mdl, repeat_penalty, repeat_last_n):
                produced = True
                yield text
            return
        except Exception as exc:
            last_exc = exc
            if produced:
                raise
    if last_exc is not None:
        raise last_exc


def _complete_once(messages, temperature, top_p, max_tokens, top_k, timeout, base_url, api_key, model,
                   repeat_penalty=None, repeat_last_n=None):
    """单次后端请求（非流式）。失败抛异常，由 complete() 决定是否降级。"""
    url = base_url.rstrip("/") + "/chat/completions"
    if repeat_penalty is None:
        repeat_penalty = setting("repeat_penalty")
    if repeat_last_n is None:
        repeat_last_n = setting("repeat_last_n")
    payload = _base_payload(messages, temperature, top_p, max_tokens, top_k, model,
                            repeat_penalty, repeat_last_n)
    payload["stream"] = False
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
    # 与流式同：网关不认重复惩罚扩展字段时去掉重试一次，不让整次判定失败。
    if (getattr(resp, "status_code", 200) in (400, 404, 422)
            and ("repeat_penalty" in payload or "repeat_last_n" in payload)):
        resp.close()
        payload = _strip_penalty(dict(payload))
        payload["stream"] = False
        resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
    resp.raise_for_status()
    if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
        resp.encoding = "utf-8"
    return resp.json()["choices"][0]["message"].get("content", "")


def complete(messages, temperature=None, top_p=None, max_tokens=None, top_k=None, timeout=60,
             base_url=None, api_key=None, model=None,
             repeat_penalty=None, repeat_last_n=None):
    """一次性返回完整文本（非流式）。用于场景切换等只需结果、不需逐字流的轻量判定。

    默认调用支持降级：主配置失败时自动切到 fallback 重试；显式指定 base_url/model 时不降级。
    """
    cands = _chain_configs(base_url, api_key, model)
    last_exc = None
    for bu, key, mdl in cands:
        try:
            return _complete_once(messages, temperature, top_p, max_tokens, top_k, timeout,
                                  bu, key, mdl, repeat_penalty, repeat_last_n)
        except Exception as exc:
            last_exc = exc
    if last_exc is not None:
        raise last_exc
