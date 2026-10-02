"""叙事正文净身：剥离模型倒进可见正文的元信息（兜底网）。

模型有时会把系统提示里的「你是导演引擎 / 铁律①②③④⑤⑥」演绎成工作笔记，
在正文里输出安全前言、铁律复述、策略调整 / 推演执行 / 后果留痕 / 下一回合预览、
当前局势列举、关系改写表等导演注释，污染叙事。

本模块做防御性净身：删元信息，保留叙事正文。主手段是 prompter 的「输出纪律」约束
（不让模型产出这些），此处仅为兜底，处理提示词未能压住时的漏网。

设计原则：
- 只删「高度可判定为元信息」的行/块，正常叙事尽量原样通过（零误伤优先）。
- 行过滤 + 尾部摘要截断 + 内联开场白剥离，最后压缩多余空行。
"""

import re

# 整行删除：元信息标题行（允许前导空格 / 单个或成对星号 / 方括号）
_META_HEADER_RE = re.compile(
    r"^\s*(?:【?\*?\*?)?(?:"
    r"警告|安全准则|根据系统安全|作为\s*AI|我作为\s*AI|抱歉[，,]|我无法|"
    r"策略调整|推演执行|环境推手注入的扰动已兑现|关系改写|"
    r"铁律\d|当前的局势是|当前局势是|局势是|"
    r"在场角色|本回合在场角色|场景[：:]"
    r")\b"
)

# 行首编号列举（「当前的局势是」之后的 1. **环境** … 这类）
_LEADING_SITUATION_RE = re.compile(r"^\s*\d+\.\s*\*?\*?")

# 尾部摘要段：遇到这些标题，从该标题行起整段（到文末）删除
_TRAILING_CUTOFF_RE = re.compile(
    r"^\s*(?:【?\*?\*?)?(?:后果留痕|下一回合预览|下一轮预览|关系改写|注意[：:])\b"
)

# 开场白里内联的「然而，作为关系推演沙盘的导演引擎……内容尺度限制。」句
_INLINE_PREAMBLE_RE = re.compile(
    r"然而[，,]\s*作为[^。\n]*?内容尺度限制\*\*?\。?"
    r"|"
    r"然而[，,]\s*作为关系推演沙盘的导演引擎[^\n]*?(?=\n\n|\n\*\*\*|\Z)"
)

# 模型以「导演引擎」自居并自我说明的整句（防御：复读旧系统提示的导演口吻）
_DIRECTOR_ENGINE_RE = re.compile(r"[^。\n]*?关系推演沙盘的导演引擎[^。\n]*?[。\n]")

# 模型声明自己将如何「规避 / 克制 / 留白 / 不写」亲密内容的自我审查句
_WILL_EVADE_RE = re.compile(r"我将以[^。\n]*?(?:规避|克制|留白|不写|避免写|未真正进入)[^。\n]*?[。\n]")

# 「鉴于…我将…规避…」式创作策略声明（常夹带伪「事后余韵阶段」挡箭牌）
_GIVEN_EVADE_RE = re.compile(r"鉴于[^。\n]*?(?:规避|克制|留白|不写|避免写|未真正进入)[^。\n]*?[。\n]")

# 模型插入的元信息分隔线（*** / ---）
_HR_RE = re.compile(r"\n\s*\*{3,}\s*\n|\n\s*-{3,}\s*\n")


def clean_narrative(text):
    """返回净身后的叙事正文。空输入原样返回。"""
    if not text:
        return text
    lines = text.split("\n")
    out = []
    dropped_tail = False
    for line in lines:
        if dropped_tail:
            continue
        # 尾部摘要截断（后果留痕 / 下一回合预览 / 关系改写 / 注意）
        if _TRAILING_CUTOFF_RE.match(line):
            dropped_tail = True
            continue
        # 整行元标题 / 导演注释行
        if _META_HEADER_RE.match(line):
            continue
        # 「当前的局势是」之后的编号列举
        if _LEADING_SITUATION_RE.match(line):
            continue
        out.append(line)
    cleaned = "\n".join(out)
    # 内联开场白句（如「然而，作为关系推演沙盘的导演引擎……内容尺度限制。」）
    cleaned = _INLINE_PREAMBLE_RE.sub("", cleaned)
    # 整句级元信息：导演自居 / 自我审查式规避声明 / 创作策略声明
    cleaned = _DIRECTOR_ENGINE_RE.sub("", cleaned)
    cleaned = _GIVEN_EVADE_RE.sub("", cleaned)
    cleaned = _WILL_EVADE_RE.sub("", cleaned)
    # 元信息分隔线
    cleaned = _HR_RE.sub("\n\n", cleaned)
    # 压缩连续空行（>2 压成 1）并去掉首尾空白
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned
