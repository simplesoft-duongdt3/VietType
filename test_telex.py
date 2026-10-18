#!/usr/bin/env /usr/bin/python3
from telex_engine import TelexEngine

def type_word(keys):
    e = TelexEngine()
    w = ''
    for k in keys:
        h, nw = e.process(w, k)
        w = nw if h else w + k
    return w

cases = [
    # cơ bản
    ("as", "á"), ("af", "à"), ("ar", "ả"), ("ax", "ã"), ("aj", "ạ"),
    ("aas", "ấ"), ("aws", "ắ"), ("dd", "đ"), ("DD", "Đ"),
    ("ees", "ế"), ("oos", "ố"), ("ows", "ớ"), ("uws", "ứ"), ("tw", "tư"),
    ("Vieetj", "Việt"), ("Tieengs", "Tiếng"), ("Dduwowcj", "Được"),
    ("tooi", "tôi"), ("ngonj", "ngọn"), ("hoafn", "hoàn"),
    ("azz", "azz"), ("asz", "a"), ("awz", "a"),
    # gõ lặp undo kiểu GoTV/OpenKey: ww -> w, tư+w -> tw, ă+w -> aw
    ("ww", "w"), ("WW", "W"), ("Ww", "W"), ("uw", "ư"),
    ("tuww", "tw"), ("aww", "aw"), ("oww", "ow"), ("maww", "maw"),
    # gõ lặp phím dấu: ass -> as, rồi s nữa -> ás
    ("ass", "as"), ("aff", "af"), ("ajj", "aj"), ("asss", "ás"),
    ("arx", "ã"),
    # gõ lặp d/a/e/o: ddd -> dd, aaa -> aa, ấ+a -> áa
    ("ddd", "dd"), ("DDD", "DD"), ("aaa", "aa"), ("eee", "ee"), ("ooo", "oo"),
    ("aasa", "áa"),
]
fails = 0
for raw, exp in cases:
    got = type_word(raw)
    ok = got == exp
    fails += (not ok)
    print(f"{'PASS' if ok else 'FAIL'}  {raw:10s} -> {got:10s} (expect {exp})")
print("FAIL:", fails)
raise SystemExit(1 if fails else 0)
