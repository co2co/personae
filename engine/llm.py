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
    # 出厂默认温度：由 0.85 上调至 1.0（实测对长输出创意/多样性更友好）。
    # 「恢复默认」按钮回填的就是这里，故出厂值以本表为唯一真相源。
    "temperature": 1.0,
    "top_p": 0.95,
    # top_k：由 40 下调至 20——ninfer(KVMem) 只接受 top_k ∈ [0,20]，40 会被 400 拒绝。
    # 20 对 llama.cpp 等后端同样安全。
    # 「恢复默认采样参数」按钮回填的就是本表，故出厂值以本表为唯一真相源。
    "top_k": 20,
    # min_p：动态截断——先按概率排序，只保留「概率 ≥ min_p × 最高概率」的候选。
    # 比固定 top_p 更抗长输出退化：top_p 是绝对阈值，遇到分布尖锐的 token 序列
    # 会放行过多候选（实测本地 27B 在 temperature=1.0 下有 30% 概率输出中途
    # 语义坍缩——「不可+动词」机械接龙后吐 EOS 收尾，表现为正文断在半句）。
    # 0.02 是 llama.cpp 自身缺省值，属保守档；0.05 以上会明显压缩随机性。
    "min_p": 0.02,
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
    val = _file_config().get(name)
    # null 与「键缺失」同义：都回退出厂默认。
    # 前端 save_config 对空输入框会给 parseFloat('')=NaN -> json 落盘为 null，
    # 若不兜住，setting() 会把 None 当有效值传下去（如 float(None) 崩溃 /
    # 采样参数变 None 被后端当缺省）。这跟「键不存在」必须等价。
    if val is None:
        return DEFAULTS[name]
    return val


# 前端「恢复默认」要回填的采样参数键（纯出厂值）。
# 单独成表而非内联：sampling_defaults 必须只含 DEFAULTS 出厂值，不能被 file 覆盖，
# 否则「恢复默认」会把用户当前已改的值再写回去，失去意义。
_SAMPLING_DEFAULT_KEYS = ("temperature", "top_p", "top_k", "min_p",
                          "max_tokens", "repeat_penalty", "repeat_last_n")


def config_view():
    """给 /api/config 用。本地单用户工具，直接返回真实配置（含密钥），便于前端回填。

    额外下发 sampling_defaults：纯 llm.DEFAULTS 的出厂采样参数（不被 file 覆盖），
    供前端「恢复默认」按钮一键回填，避免前端硬编码出厂值。
    """
    cfg = dict(DEFAULTS)
    cfg.update(_file_config())
    # providers 缺省时为空列表（刚部署）；用户增删后的列表已持久化则直接用
    cfg.setdefault("providers", [])
    cfg["sampling_defaults"] = {k: DEFAULTS[k] for k in _SAMPLING_DEFAULT_KEYS}
    return cfg


# 用户可通过 UI 改动的字段；其余内部字段不暴露
_WRITABLE = {"base_url", "api_key", "model", "budget", "max_tokens", "top_k",
             "temperature", "top_p", "min_p", "repeat_penalty", "repeat_last_n",
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
            v = _num(v, k, int)
        elif k in ("temperature", "top_p", "min_p", "repeat_penalty"):
            v = _num(v, k, float)
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


def _num(value, key, cast):
    """把配置值转成目标类型，非法/空值回退 DEFAULTS。"""
    try:
        return cast(value)
    except (TypeError, ValueError):
        return DEFAULTS[key]


def _penalty_params(repeat_penalty, repeat_last_n, min_p=None):
    """非标准采样扩展（重复惩罚 + min_p）。

    两者都只在**偏离中性值**时才发：中性值与各后端缺省行为一致，发过去没有增益，
    却可能被严格校验的 OpenAI 兼容网关（vLLM / DeepSeek 等）判为未知参数而 400。
    - repeat_penalty：1.0 为中性（= 不惩罚）
    - min_p：0 为中性（= 不启用动态截断，交后端缺省）
    """
    out = {}
    rp = _num(repeat_penalty, "repeat_penalty", float)
    if rp != 1.0:
        out["repeat_penalty"] = rp
        # repeat_last_n 是 llama.cpp 扩展，与 repeat_penalty 配对才有意义；
        # 网关若认 repeat_penalty 也通常认这个，但没给出值时用后端缺省更稳。
        rn = _num(repeat_last_n, "repeat_last_n", int)
        if rn:
            out["repeat_last_n"] = rn
    # min_p 走独立分支：默认 0.02 非中性，故正常会发送；显式填 0 才不发。
    mp = _num(setting("min_p") if min_p is None else min_p, "min_p", float)
    if mp > 0.0:
        out["min_p"] = mp
    return out


def _base_payload(messages, temperature, top_p, max_tokens, top_k, base_model,
                  repeat_penalty, repeat_last_n, min_p=None):
    """流式/非流式共用的请求体（采样参数 + 重复惩罚 + 思考开关）。"""
    payload = {
        "model": base_model,
        "messages": messages,
        "temperature": float(temperature if temperature is not None else setting("temperature")),
        "top_p": float(top_p if top_p is not None else setting("top_p")),
        "max_tokens": int(max_tokens if max_tokens is not None else setting("max_tokens")),
        "top_k": int(top_k if top_k is not None else setting("top_k")),
    }
    payload.update(_penalty_params(repeat_penalty, repeat_last_n, min_p))
    # Qwen3 一类带思考的模型默认会把预算耗在 reasoning 上，content 全是空
    if not setting("enable_thinking"):
        payload["chat_template_kwargs"] = {"enable_thinking": False}
        payload["enable_thinking"] = False  # SiliconFlow / OpenAI 兼容网关认顶层字段
    return payload


# 网关不认时需剥离的非标准扩展字段（repeat_* 与 min_p 同属 llama.cpp 扩展）
_EXT_FIELDS = ("repeat_penalty", "repeat_last_n", "min_p")


def _strip_penalty(payload):
    for k in _EXT_FIELDS:
        payload.pop(k, None)
    return payload


def _stream_once(messages, temperature, top_p, max_tokens, top_k, timeout, base_url, api_key, model,
                 repeat_penalty=None, repeat_last_n=None, min_p=None):
    """单次后端请求（流式）。产出前失败抛异常。"""
    url = base_url.rstrip("/") + "/chat/completions"
    if repeat_penalty is None:
        repeat_penalty = setting("repeat_penalty")
    if repeat_last_n is None:
        repeat_last_n = setting("repeat_last_n")
    payload = _base_payload(messages, temperature, top_p, max_tokens, top_k, model,
                            repeat_penalty, repeat_last_n, min_p)
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
            and any(k in payload for k in _EXT_FIELDS)):
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
           repeat_penalty=None, repeat_last_n=None, min_p=None):
    """逐块产出文本。上游返回 SSE，这里只取 delta.content。

    单后端直连：只使用主配置（显式传参时覆盖），失败直接抛出异常，不做降级回落。
    """
    bu = base_url or setting("base_url") or DEFAULTS["base_url"]
    key = api_key if api_key is not None else setting("api_key")
    mdl = model or setting("model")
    for text in _stream_once(messages, temperature, top_p, max_tokens, top_k, timeout,
                             bu, key, mdl, repeat_penalty, repeat_last_n, min_p):
        yield text


def _complete_once(messages, temperature, top_p, max_tokens, top_k, timeout, base_url, api_key, model,
                   repeat_penalty=None, repeat_last_n=None, min_p=None):
    """单次后端请求（非流式）。失败抛异常。"""
    url = base_url.rstrip("/") + "/chat/completions"
    if repeat_penalty is None:
        repeat_penalty = setting("repeat_penalty")
    if repeat_last_n is None:
        repeat_last_n = setting("repeat_last_n")
    payload = _base_payload(messages, temperature, top_p, max_tokens, top_k, model,
                            repeat_penalty, repeat_last_n, min_p)
    payload["stream"] = False
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
    # 与流式同：网关不认重复惩罚扩展字段时去掉重试一次，不让整次判定失败。
    if (getattr(resp, "status_code", 200) in (400, 404, 422)
            and any(k in payload for k in _EXT_FIELDS)):
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
             repeat_penalty=None, repeat_last_n=None, min_p=None):
    """一次性返回完整文本（非流式）。用于场景切换等只需结果、不需逐字流的轻量判定。

    单后端直连：只使用主配置（显式传参时覆盖），失败直接抛出异常，不做降级回落。
    """
    bu = base_url or setting("base_url") or DEFAULTS["base_url"]
    key = api_key if api_key is not None else setting("api_key")
    mdl = model or setting("model")
    return _complete_once(messages, temperature, top_p, max_tokens, top_k, timeout,
                          bu, key, mdl, repeat_penalty, repeat_last_n, min_p)
