"""极简事件钩子：替代 SillyTavern 的 16 个事件 + 拦截器。

只保留两个真正有用的时机：
    prompt_ready     提示词组装完成，即将发出
                     参数：messages, card
                     返回值里带 messages 就替换，带别的键则合并进 payload
    message_received 收到完整回复
                     参数：reply, card, history
                     返回值里带 reply 就改写最终文本（同时影响落盘）

用法：
    import hooks
    hooks.on("message_received", lambda reply, card, history: {"reply": reply.strip()})
"""

_LISTENERS = {}


def on(event, fn):
    _LISTENERS.setdefault(event, []).append(fn)
    return fn


def emit(event, **payload):
    """按注册顺序依次调用；返回最终的 payload 字典。"""
    for fn in _LISTENERS.get(event, []):
        result = fn(**payload)
        if isinstance(result, dict):
            payload.update(result)
    return payload
