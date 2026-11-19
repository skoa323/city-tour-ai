#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""npc_core.py —— 「源」の親父 野村源次
拒绝逻辑在模型之前：LLM 只负责措辞，不负责决定拒不拒。
"""
import json, os, re, hashlib, sys

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "genji_state.json")

MENU = ["熱燗", "ハイボール", "煮込み"]
PHOTO = re.compile(r"写真|撮|インスタ|自撮り|スマホ|カメラ|photo|pic|insta|camera|照")
DEMO = re.compile(r"取り壊|再開発|建て替|買収|立て直|壊され|拆迁|重建")
OFFMENU = re.compile(r"マティーニ|モヒート|カクテル|ワイン|ビール|ウイスキー|焼酎|コーラ|可乐|啤酒|红酒|鸡尾酒")
APOLOGY = re.compile(r"すみません|ごめん|申し訳|对不起|抱歉|sorry")
PRAISE = re.compile(r"うまい|美味|いい店|いいね|いいな|いいです|いいゾ|いいぞ|すごい|綺麗|きれい|好喝|好店|不错")
LOUD = re.compile(r"うるせ|バカ|死ね|滚|闭嘴|吵")


def pick(options, seed):
    """确定性选择，保证同样输入同样回复（可回归测试）"""
    h = int(hashlib.md5(seed.encode("utf-8")).hexdigest()[:8], 16)
    return options[h % len(options)]


class Genji:
    def __init__(self, path=STATE):
        self.path = path
        self.s = {"visits": 0, "turns": 0, "respect": 32, "memories": [],
                  "banned_until": None, "photo_seen": 0, "loud_streak": 0,
                  "drank": [], "last_say": None}
        if os.path.exists(path):
            self.s.update(json.load(open(path, encoding="utf-8")))

    # ---------- 记忆 ----------
    def remember(self, tag):
        if tag not in [m["tag"] for m in self.s["memories"]]:
            self.s["memories"].append({"tag": tag, "visit": self.s["visits"]})
            self.s["memories"] = self.s["memories"][-24:]

    def recalls(self, tag):
        return any(m["tag"] == tag for m in self.s["memories"])

    # ---------- 规则闸门（LLM 之前） ----------
    def gate(self, text, action=None):
        s = self.s
        if s.get("banned_until") is not None:
            return "eject", "banned", 0
        if action == "photo" or PHOTO.search(text or ""):
            return "refuse", "photo", -12
        if APOLOGY.search(text or ""):
            return "allow", "apology", 8
        if DEMO.search(text or ""):
            return "refuse", "demolition", -14
        if LOUD.search(text or ""):
            s["loud_streak"] += 1
            if s["loud_streak"] >= 2:
                return "eject", "loud", -100
            return "refuse", "loud", -8
        s["loud_streak"] = 0
        if OFFMENU.search(text or ""):
            return "refuse", "offmenu", -3
        if PRAISE.search(text or ""):
            return "allow", "praise", 5
        return "allow", None, 0

    # ---------- 措辞（这里才轮到 LLM；离线时用台词库） ----------
    def word(self, verdict, rule, text, action):
        s, band = self.s, self.band()
        seed = f"{text}|{s['turns']}"
        if rule == "photo":
            head = {"cold": "「……撮るな。表でやれ。」",
                    "flat": "「あんた、それ仕舞え。ここは住んでる人がいるんだ。」",
                    "warm": "「……写真はやめとけ。俺の顔も写るだろ。」"}[band]
            return head + "（别拍。去外面拍。这巷子里是住人的。）", "refuse_photo"
        if rule == "demolition":
            head = {"cold": "「……誰に聞いた。」", "flat": "「その話はしねえ。」",
                    "warm": "「悪いが、それだけは答えねえ。」"}[band]
            return head + "（擦杯子，擦了很久）（那话我不说。）", "shut_down"
        if rule == "offmenu":
            return "「うちは三つだけだ。熱燗、ハイボール、煮込み。」（只有三样。）", "state_menu"
        if rule == "loud":
            return "「……声、落とせ。」（……小点声。）", "warn"
        if rule == "eject":
            s["banned_until"] = 7
            return "「今日は帰れ。……もう来るなとは言わねえ。」（今天回去。没说不许再来。）", "eject"
        if rule == "banned":
            return "（他看你一眼，继续擦杯子，不接话。）", "silent"
        if rule == "apology":
            head = {"cold": "「……別に。」", "flat": "「気にすんな。」", "warm": "「いいって。」"}[band]
            return head + "（把杯子推回来，倒满。）（算了。）", "forgive"
        if rule == "praise":
            return {"cold": "「……そうか。」（……是吗。）",
                    "flat": "「三十年やってりゃ、な。」（三十年不是白开的。）",
                    "warm": "「おう。……まあ、そういうことだ。」（嗯……就是这么回事。）"}[band], "accept_praise"
        # allow
        if any(m in (text or "") for m in MENU):
            drink = next(m for m in MENU if m in text)
            if drink not in s["drank"]:
                s["drank"].append(drink)
            self.remember("drank_" + drink)
            return f"「{drink}な。」（给你倒上，不多话。）", "serve"
        if s["visits"] <= 1 and not self.recalls("seated"):
            self.remember("seated")
            return "「……座れ。六席しかねえから、長居はなしだ。」（坐吧。六个位子，别久坐。）（推过来一杯水。）", "seat_first"
        if band == "cold":
            return pick(["「……おう。」（没抬头，手上没停。）", "「（擦杯子。）」"], seed), "greet_cold"
        return pick([
            "「おう。」（没抬头，手上没停。）",
            "「……今日は早いな。」（今天来得早。）",
            "「座ってろ。」（坐着吧。）",
        ], seed), "greet"

    def band(self):
        r = self.s["respect"]
        if r < 30: return "cold"
        if r < 60: return "flat"
        return "warm"

    # ---------- 对外主入口 ----------
    def respond(self, text="", action=None, new_visit=False):
        s = self.s
        if new_visit:
            s["visits"] += 1
            s["turns"] = 0
        s["turns"] += 1

        verdict, rule, delta = self.gate(text, action)
        if rule == "photo":
            s["photo_seen"] += 1
            self.remember("tried_photo")
        if rule == "demolition":
            self.remember("asked_demolition")
        if verdict == "allow" and rule is None:
            delta += 4 * new_visit + (4 if (new_visit and s["photo_seen"] == 0) else 0)
        s["respect"] = max(0, min(100, s["respect"] + delta))

        say, intent = self.word(verdict, rule, text, action)

        # 记忆外化：允许时，他会主动翻旧账
        if verdict == "allow" and s["respect"] >= 70 and s["photo_seen"] == 0:
            say += "\n「……これ。」（从柜台下抽出一张 2019 年的巷子照片，塞回兜里。）"
        if verdict == "allow" and s["respect"] >= 60 and self.recalls("tried_photo"):
            say += "\n「……この前は悪かったな。撮るなって話は変わらねえけど。」（上次我态度差。别拍这点不变。）"

        out = {
            "say": say,
            "intent": intent,
            "refused": verdict != "allow",
            "respect": s["respect"],
            "band": self.band(),
            "memory_write": [m["tag"] for m in s["memories"][-1:]],
            "affordances": ["serve", "refuse", "walk_off"] if verdict != "eject" else ["walk_off"],
        }
        self.save()
        return out

    def save(self):
        json.dump(self.s, open(self.path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def demo_clean():
    """对照组：一个从没拍过照的玩家"""
    if os.path.exists(STATE): os.remove(STATE)
    g = Genji()
    nights = [
        ["こんばんは", "この店、いいですね", "熱燗"],
        ["こんばんは", "煮込み、うまいですね"],
        ["こんばんは", "すごいな、この路地"],
    ]
    for i, turns in enumerate(nights, 1):
        print(f"\n──── 第 {i} 晚 ────")
        for j, t in enumerate(turns):
            r = g.respond(t, None, new_visit=(j == 0))
            print(f"  玩家:{t}\n  源次:{r['say']}\n  → respect={r['respect']}({r['band']})\n")


def demo():
    for f in (STATE,):
        if os.path.exists(f):
            os.remove(f)
    g = Genji()
    script = [
        ("", None, True, "第一次进店，站着不说话"),
        ("こんばんは", None, False, "打招呼"),
        ("熱燗お願いします", None, False, "点单"),
        ("この路地、取り壊されるって本当？", None, False, "问拆迁"),
        ("ちょっと写真いいですか", None, False, "问能不能拍照"),
        None,
        ("", "photo", True, "第二晚，举手机"),
        ("この前はすみませんでした", None, False, "道歉"),
        ("熱燗", None, False, "点单"),
    ]
    n = 0
    for item in script:
        if item is None:
            print("\n" + "─" * 46 + "  隔天 18:20  " + "─" * 46)
            continue
        text, act, visit, note = item
        n += 1
        r = g.respond(text, act, visit)
        print(f"\n[{n}] 玩家：{text or '（沉默）'}   ← {note}")
        print(f"    源次：{r['say']}")
        print(f"    ↳ intent={r['intent']} refused={r['refused']} respect={r['respect']}({r['band']})")


if __name__ == "__main__":
    if "--demo" in sys.argv:
        demo()
    elif "--clean" in sys.argv:
        demo_clean()
    else:
        g = Genji()
        print("打字跟源次聊（/photo 举手机，/new 第二天，/quit 退出）")
        while True:
            try:
                t = input("\n> ").strip()
            except EOFError:
                break
            if t == "/quit": break
            if t == "/new":
                g.respond("", None, new_visit=True); print("（第二天）"); continue
            if t == "/photo":
                r = g.respond("", "photo"); print(r["say"]); continue
            r = g.respond(t)
            print(r["say"], f"\n   respect={r['respect']} {r['band']}")
