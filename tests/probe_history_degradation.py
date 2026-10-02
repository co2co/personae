"""T1 梯度探测：定位长上下文导致叙事衰退的拐点（轮次 / token 上下文大小）。

方法：固定快照与当前指令，只递增注入 history 轮数（每轮 = 1 user 指令 + 1 assistant 叙事），
真实调用 llm.stream 生成，记录回复长度、点名焦点率、推进动作密度、与上一档长度比。
目的：找出"开始叙事衰退"的轮次/上下文位置，作为滑动窗口阈值依据。

不依赖 pytest（文件名非 test_ 前缀）。运行需本地 LLM 在 127.0.0.1:1234 监听，且清代理。
"""

import sys
import time

sys.path.insert(0, "engine")
import prompter
import llm

CHARS = ["老周", "苏曼", "阿杰", "林晚", "高洋"]
cards_present = {n: {"name": n} for n in CHARS}
directive = "苏曼在路边拦下一辆军车，试图打听女儿下落，老周上前劝阻"
world_hits = []
nsfw_prompt = "NSFW 已解锁，按尺度自然推进。"
opp_level = "半步"
focus = {"subjects": ["苏曼", "老周"]}
snap = {
    "scene": {"round": 1, "place": "城东道路", "time": "夜", "weather": ""},
    "relations": {"老周 → 苏曼": "暗中保护", "阿杰 → 高洋": "握有把柄(咬伤事件)"},
    "ledger": [{"account": "R5 阿杰与高洋发生亲密越线，关系改写（把柄）"}],
    "secrets": [
        {"owner": "高洋", "state": "暴露", "holders": ["阿杰", "林晚"], "content": "高洋挪用货款并咬伤林晚"},
        {"owner": "苏曼", "state": "潜伏", "holders": [], "content": "苏曼女儿已死于避难所外"},
    ],
    "intimacy_phase": None,
    "goals": {n: "" for n in CHARS},
    "present": CHARS,
}

PLACES = ["城东道路", "废弃加油站", "避难所外围", "坍塌高架", "河堤营地", "地下车库", "断桥南岸", "旧货运站台"]
ACT_VERBS = set("走说看拿推跑躲找问回转换拉开提端抱贴压按吻脱骑跨坐舔含顶抱握扶靠站蹲躺卧".split())


def gen_directive(i):
    return f"第{i}轮：小队沿{PLACES[i % len(PLACES)]}前进，遭遇零星尸群与物资争夺，须决定下一步"


def gen_reply(i):
    p = PLACES[i % len(PLACES)]
    c = CHARS[i % len(CHARS)]
    d = CHARS[(i + 2) % len(CHARS)]
    return (
        f"夜色如墨，小队沿着{p}一路向西，脚下的碎石被踩得咯吱作响。{c}走在最前，"
        f"手电的光柱在雾里割出一道惨白，照见墙根蜷着的黑影一闪又没了。\n"
        f"风从废弃楼群的缝隙里穿出来，带着陈年的尘土与某种说不清的腥气。老周压低嗓子，"
        f"要所有人都别出声——尸群对声音比对学生还敏感，一声咳嗽就能引来半条街。\n"
        f"{d}靠在锈蚀的护栏上喘气，背包带勒进肩肉，露出底下那道早已结痂的咬伤。{c}瞥见，"
        f"移开目光，像是怕被牵连，又像是想起了什么不敢提的旧账。\n"
        f"苏曼第{i}次回头张望，像在等谁从黑暗里走出来。她女儿走丢那夜也是这样的风，"
        f"也是这样惨白的路灯光。她攥紧胸前的吊坠，指节发白，却一句话也不肯说。\n"
        f"阿杰摸出怀里的东西——半截被血浸透的绷带，那是高洋咬伤林晚那晚留下的。他把它塞回去，"
        f"假装什么都没发生，可目光扫过林晚时还是僵了一下。把柄在他手里，沉得像块石头。\n"
        f"前方传来玻璃碎裂的声响，紧接着是拖沓的脚步。{c}立刻抬手示意停下，"
        f"所有人贴着墙根屏息。尸群的轮廓在雾里晃，近了，又因风转向别处。\n"
        f"等危险过去，高洋才敢开口，说这地方不能久留，仓库里还有他们要的药品。{d}没接话，"
        f"只是把咬伤往袖子里又塞了塞，仿佛那样就能把秘密也塞回去。\n"
        f"老周看了看苏曼，又看了看黑沉沉的路，终于点了头。小队重新挪动，"
        f"像一截被水流推着的浮木，谁也不知道下一个拐角等着什么。\n"
    )


def metrics(reply):
    rlen = len(reply)
    named = sum(1 for ch in focus["subjects"] if ch in reply)
    acts = sum(1 for ch in reply if ch in ACT_VERBS)
    return rlen, named, acts


def run():
    rounds_list = [0, 8, 16, 24, 32, 40, 50, 60]
    print(f"{'R':>2} {'tok':>6} {'reply':>5} {'named':>5} {'acts':>4} {'dt':>5}")
    base_len = None
    for R in rounds_list:
        hist = []
        for i in range(R):
            hist.append({"role": "user", "content": "【导演指令】" + gen_directive(i)})
            hist.append({"role": "assistant", "content": gen_reply(i)})
        msgs = prompter.build_session(
            cards_present, directive, world_hits, snap, nsfw_prompt, opp_level,
            history=hist, focus=focus)
        tok = sum(prompter.count_tokens(m.get("content", "")) for m in msgs)
        t0 = time.time()
        reply = "".join(llm.stream(msgs, max_tokens=4096, temperature=0.9, timeout=240))
        dt = time.time() - t0
        rlen, named, acts = metrics(reply)
        if base_len is None:
            base_len = rlen
        drop = round((1 - rlen / base_len) * 100, 1) if base_len else 0
        print(f"{R:>2} {tok:>6} {rlen:>5} {named:>5} {acts:>4} {dt:>5.1f}  | len_drop={drop}%")
        sys.stdout.flush()


if __name__ == "__main__":
    run()
