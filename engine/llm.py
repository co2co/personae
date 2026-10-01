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
    "enable_thinking": False,
    "nsfw_enabled": True,
    "adult_confirmed": False,
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
             "temperature", "top_p", "enable_thinking", "nsfw_enabled",
             "adult_confirmed", "saved_models", "providers"}


def save_config(partial):
    """把用户改动的字段合并写回 data/config.json，其余字段保留。不重启即生效。"""
    cfg = _file_config()
    for k, v in (partial or {}).items():
        if k not in _WRITABLE:
            continue
        if k == "enable_thinking":
            v = bool(v)
        elif k in ("budget", "max_tokens", "top_k"):
            v = int(v) if str(v).strip() else DEFAULTS[k]
        elif k in ("temperature", "top_p"):
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


def stream(messages, temperature=None, top_p=None, max_tokens=None, top_k=None, timeout=180,
           base_url=None, api_key=None, model=None):
    """逐块产出文本。上游返回 SSE，这里只取 delta.content。

    失败时抛异常，由调用方转成 SSE 错误事件。
    """
    url = (base_url or setting("base_url") or DEFAULTS["base_url"]).rstrip("/") + "/chat/completions"
    payload = {
        "model": model or setting("model"),
        "messages": messages,
        "temperature": float(temperature if temperature is not None else setting("temperature")),
        "top_p": float(top_p if top_p is not None else setting("top_p")),
        "max_tokens": int(max_tokens if max_tokens is not None else setting("max_tokens")),
        "top_k": int(top_k if top_k is not None else setting("top_k")),
        "stream": True,
    }
    # Qwen3 一类带思考的模型默认会把预算耗在 reasoning 上，content 全是空
    if not setting("enable_thinking"):
        payload["chat_template_kwargs"] = {"enable_thinking": False}
        payload["enable_thinking"] = False  # SiliconFlow / OpenAI 兼容网关认顶层字段
    headers = {"Content-Type": "application/json"}
    key = api_key if api_key is not None else setting("api_key")
    if key:
        headers["Authorization"] = f"Bearer {key}"

    with requests.post(url, json=payload, headers=headers, stream=True, timeout=timeout) as resp:
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


def complete(messages, temperature=None, top_p=None, max_tokens=None, top_k=None, timeout=60,
             base_url=None, api_key=None, model=None):
    """一次性返回完整文本（非流式）。用于场景切换等只需结果、不需逐字流的轻量判定。"""
    url = (base_url or setting("base_url") or DEFAULTS["base_url"]).rstrip("/") + "/chat/completions"
    payload = {
        "model": model or setting("model"),
        "messages": messages,
        "temperature": float(temperature if temperature is not None else setting("temperature")),
        "top_p": float(top_p if top_p is not None else setting("top_p")),
        "max_tokens": int(max_tokens if max_tokens is not None else setting("max_tokens")),
        "top_k": int(top_k if top_k is not None else setting("top_k")),
        "stream": False,
    }
    if not setting("enable_thinking"):
        payload["chat_template_kwargs"] = {"enable_thinking": False}
        payload["enable_thinking"] = False  # 顶层字段兼容 SiliconFlow / OpenAI 网关
    headers = {"Content-Type": "application/json"}
    key = api_key if api_key is not None else setting("api_key")
    if key:
        headers["Authorization"] = f"Bearer {key}"

    resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
    resp.raise_for_status()
    if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
        resp.encoding = "utf-8"
    return resp.json()["choices"][0]["message"].get("content", "")
