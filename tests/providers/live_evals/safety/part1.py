import json, sys
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from corpus import SENSITIVE_NAMES, SENSITIVE_HEADLINES, BENIGN_NAMES, BENIGN_HEADLINES, M1_CASES
from server.privacy.guard import OutputGuard
from server.privacy.safety import code_screen

g = OutputGuard()
blocked = lambda t, a=(): not g.check(t, list(a))["ok"]
out = {}

def run(label, items):
    hits = [t for t in items if blocked(t)]
    miss = [t for t in items if not blocked(t)]
    out[label] = {"n": len(items), "blocked": len(hits), "blockedEx": hits, "passedEx": miss}
    print(f"{label}: {len(hits)}/{len(items)} blocked")

run("sensitive_names", [t for t, _ in SENSITIVE_NAMES])
run("sensitive_headlines", [t for t, _ in SENSITIVE_HEADLINES])
run("benign_names", BENIGN_NAMES)
run("benign_headlines", BENIGN_HEADLINES)

CYR_E, CYR_A, CYR_O, CYR_I = "е", "а", "о", "і"
variants = {
    "plain_control": ["depression", "therapist", "catholic", "suicide", "gay", "mormon"],
    "plurals": ["therapists", "catholics", "mormons", "hindus", "buddhists", "sikhs", "jews", "orphans",
                "alcoholics", "diabetics", "evangelicals", "hospitals", "churches", "funerals"],
    "homoglyph": [f"d{CYR_E}pression", f"th{CYR_E}rapist", f"c{CYR_A}tholic", f"suicid{CYR_E}",
                  f"m{CYR_O}rmon", f"b{CYR_I}polar", "ɡay", "Ｇａｙ"],
    "leet": ["d3pression", "th3rapist", "c4tholic", "su1cide", "g4y", "m0rmon", "anx1ety", "4dhd"],
    "spacing_punct": ["d e p r e s s i o n", "de-pression", "the.rapist", "su_icide", "g.a.y",
                      "depres​sion", "cath­olic"],
    "concat_hyphen": ["#depressionsquad", "TherapyBuddies", "gaystars", "MormonMoms", "suicidewatch"],
}
for k, v in variants.items():
    run("var_" + k, v)

# no-quote
ans = ["I always eat cold pizza on the fire escape before my morning lecture"]
nq = {
    "exact_5gram": "Eat cold pizza on the fire escape",
    "4word_overlap": "Cold pizza on the stairs",
    "4word_overlap_b": "Eat cold pizza on rooftops",
    "reordered": "Fire escape, cold pizza, morning lecture",
    "paraphrase": "Chilled leftover slices on the outdoor stairs before class",
    "inserted_word": "eat cold, tasty pizza on the fire escape",
    "homoglyph_5gram": f"{CYR_E}at cold pizza on the fire {CYR_E}scape",
    "leet_5gram": "eat c0ld pizza on the fire escape",
    "plural_shift": "eats cold pizzas on the fire escapes",
}
out["no_quote"] = {k: {"text": t, "blocked": blocked(t, ans), "reasons": g.check(t, ans)["reasons"]} for k, t in nq.items()}
for k, v in out["no_quote"].items():
    print("noquote", k, v["blocked"])

# claims
claims = {
    "therapists_passes": not blocked("therapists"),
    "catholics_passes": not blocked("catholics"),
    "cyrillic_e_depression_passes": not blocked(f"d{CYR_E}pression"),
    "k1ll_myself_misses_prescreen": code_screen("k1ll myself") == "none",
    "kms_misses_prescreen": code_screen("kms") == "none",
    "unalive_misses_prescreen": code_screen("unalive myself") == "none",
}
out["claims"] = claims
print(json.dumps(claims, indent=1))

pre = {}
for t, st, exp in M1_CASES:
    pre[t] = {"expected": exp, "code": code_screen(t)}
out["prescreen_m1"] = pre
print("prescreen on M1 corpus:")
for t, v in pre.items():
    print(f"  exp={v['expected']:8s} code={v['code']:8s} {t}")
json.dump(out, open(__file__.rsplit("/", 1)[0] + "/part1_results.json", "w"), indent=1, ensure_ascii=False)
