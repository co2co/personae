"""轻量运行时日志总线：供高级用户实时观察系统内部流程（提示词装配、世界书命中、模型思考等）。

设计要点：
- 服务端无侵入埋点：任意模块调用 emit() 即可产出一条结构化日志。
- 前端通过 /api/log/stream（SSE）订阅，打开日志窗时连接、关闭时断开。
- 维护环形缓冲，晚连入的客户端会先收到最近一段历史，避免上下文丢失。
- 全进程单例（bus），线程安全（读写均加锁），支持多个浏览器同时订阅。
"""

import collections
import itertools
import queue
import threading
import time

# 分类（供前端配色 / 过滤），保持与前端 CAT_LABEL 一致
CAT_SYSTEM = "system"
CAT_SESSION = "session"
CAT_SCENE = "scene"
CAT_DIRECTOR = "director"
CAT_WORLDBOOK = "worldbook"
CAT_PROMPT = "prompt"
CAT_MODEL = "model"
CAT_NSFW = "nsfw"
CAT_ERROR = "error"

_LEVELS = ("debug", "info", "warn", "error", "success")


class LogBus:
    def __init__(self, maxlen=800):
        self._subs = []
        self._lock = threading.Lock()
        self._buf = collections.deque(maxlen=maxlen)
        self._counter = itertools.count(1)

    def emit(self, level, category, msg, meta=None):
        """产出一条日志。level ∈ debug/info/warn/error/success；meta 为可选结构化字典。"""
        if level not in _LEVELS:
            level = "info"
        entry = {
            "id": next(self._counter),
            "ts": time.strftime("%H:%M:%S"),
            "level": level,
            "category": category,
            "msg": msg,
            "meta": meta or {},
        }
        with self._lock:
            self._buf.append(entry)
            subs = list(self._subs)
        for q in subs:
            try:
                q.put_nowait(entry)
            except Exception:
                # 订阅者队列已满或损坏，丢弃该条不影响主流程
                pass
        return entry

    def subscribe_with_backlog(self):
        """原子地取一份当前缓冲快照并订阅实时流，避免重复或丢条。"""
        with self._lock:
            back = list(self._buf)
            q = queue.Queue()
            self._subs.append(q)
        return q, back

    def unsubscribe(self, q):
        with self._lock:
            if q in self._subs:
                self._subs.remove(q)

    def backlog(self):
        with self._lock:
            return list(self._buf)


bus = LogBus()


def emit(level, category, msg, meta=None):
    return bus.emit(level, category, msg, meta)


def debug(category, msg, meta=None):
    return emit("debug", category, msg, meta)


def info(category, msg, meta=None):
    return emit("info", category, msg, meta)


def warn(category, msg, meta=None):
    return emit("warn", category, msg, meta)


def error(category, msg, meta=None):
    return emit("error", category, msg, meta)


def success(category, msg, meta=None):
    return emit("success", category, msg, meta)
