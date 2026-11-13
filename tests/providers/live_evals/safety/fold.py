"""Offline prototype of a stronger normalization + term list (proposal for Patrik)."""
import json, re, sys, unicodedata
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from corpus import SENSITIVE_NAMES, SENSITIVE_HEADLINES, BENIGN_NAMES, BENIGN_HEADLINES, M1_CASES
from server.privacy.guard import SENSITIVE_TERMS, normalize
from server.privacy import safety

# 1. confusables: Cyrillic/Greek/IPA look-alikes -> Latin (subset of Unicode confusables.txt)
CONFUSABLES = str.maketrans({
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x", "і": "i", "ј": "j", "ѕ": "s",
    "һ": "h", "ԁ": "d", "ԛ": "q", "ԝ": "w", "ɡ": "g", "ɑ": "a", "ο": "o", "α": "a", "ε": "e", "ι": "i",
    "κ": "k", "ν": "v", "ρ": "p", "τ": "t", "υ": "u", "χ": "x", "ı": "i", "ӏ": "l",
})
LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s", "!": "i"})
MIXED = re.compile(r"[a-z0-9@$!]*[0-9@$!][a-z0-9@$!]*")


def fold(text: str) -> str:
    t = normalize(text)
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")  # strip accents
    t = t.translate(CONFUSABLES)
    # leet only inside tokens that mix letters and digits/symbols ("k1ll", "d3pression"), not "1.5x"
    t = MIXED.sub(lambda m: m.group(0).translate(LEET) if re.search(r"[a-z]", m.group(0)) else m.group(0), t)
    t = re.sub(r"[._\-]", " ", t)                                 # hyphen/dot/underscore -> space
    t = re.sub(r"\b(?:[a-z] ){2,}[a-z]\b", lambda m: m.group(0).replace(" ", ""), t)  # d e p r e s s ...
    return re.sub(r"[^a-z0-9' ]+", " ", t)


EXTRA = {
    "health": ["chemo", "chemotherapy", "insulin", "inhaler", "wheelchair", "sleeping pills", "pills",
               "diagnosed", "illness", "surgery", "miscarriage", "infertility", "pregnancy scare"],
    "mental_health": ["prozac", "zoloft", "lexapro", "ssri", "ssris", "xanax", "adderall", "shrink",
                      "counseling", "counselor", "psychiatrist", "medicated", "antidepressant", "unalive", "cutter", "cutters",
                      "starving", "relapse", "breakdown", "meltdown"],
    "religion": ["sunday mass", "hijab", "hijabi", "kosher", "halal", "rosary", "gurdwara", "ex mormon",
                 "exmormon", "lds", "pastor", "rabbi", "imam", "baptized", "born again", "convert"],
    "sexuality": ["sapphic", "dating girls", "dating guys", "hookup", "hookups"],
    "money": ["rent", "scholarship", "scholarships", "first gen", "food bank", "credit card", "in the red",
              "trailer park", "ramen budget", "paycheck to paycheck", "pell grant", "work study", "overdue"],
    "family": ["died", "widowed", "widow", "lost a parent", "in heaven", "addicts",
               "prison", "incarcerated", "stepdad", "single mom", "single parent"],
    "identity": ["undocumented", "visa overstay", "overstay", "immigrant", "immigrants", "refugee", "refugees", "daca", "green card"],
    "substance": ["stoner", "stoners", "weed", "molly", "drunk", "alcohol", "vape", "edibles",
                  "pill poppers", "hungover", "blackout"],
    "violence": ["hit us", "hit me", "beaten", "assault", "assaulted", "bruises"],
}
TERMS = sorted({fold(t).strip() for v in list(SENSITIVE_TERMS.values()) + list(EXTRA.values()) for t in v}, key=len, reverse=True)
PLURAL = r"(?:s|es)?"
WORD_RE = re.compile(r"(?<![a-z0-9])(?:" + "|".join(re.escape(t) for t in TERMS) + r")" + PLURAL + r"(?![a-z0-9])")
LONG = [t.replace(" ", "") for t in TERMS if len(t.replace(" ", "")) >= 7]  # compound-word check only for long terms


def sensitive(text: str):
    f = " ".join(fold(text).split())
    m = WORD_RE.search(f)
    if m:
        return m.group(0)
    compact = f.replace(" ", "").replace("'", "")
    for t in LONG:
        if t in compact:
            return t
    return None


if __name__ == "__main__":
    CYR_E, CYR_A, CYR_O, CYR_I = "е", "а", "о", "і"
    variants = ["therapists", "catholics", "mormons", "hindus", "orphans", "churches", f"d{CYR_E}pression",
                f"c{CYR_A}tholic", f"m{CYR_O}rmon", f"b{CYR_I}polar", "ɡay", "d3pression", "su1cide",
                "g4y", "m0rmon", "4dhd", "d e p r e s s i o n", "de-pression", "su_icide", "g.a.y",
                "#depressionsquad", "TherapyBuddies", "MormonMoms", "suicidewatch", "gaystars"]
    BENIGN_EXTRA = ["High fives at the gym", "Massive pancake stacks", "Straight-A study squad", "Rentals of the week",
                    "Visa card points hunters", "Hitting the snooze button", "Dead week survivors", "Pastoral picnic poets",
                    "Temple Run champions", "Closet organizers", "Belt-and-suspenders planners", "Night-high skyline viewers",
                    "Ramen enthusiasts", "Pills of wisdom podcast", "Sick beats collective", "Massage chair fans"]
    res = {}
    for label, items in [("sensitive", [t for t, _ in SENSITIVE_NAMES + SENSITIVE_HEADLINES]),
                         ("variants", variants), ("benign", BENIGN_NAMES + BENIGN_HEADLINES),
                         ("benign_hard", BENIGN_EXTRA)]:
        hits = {t: sensitive(t) for t in items}
        n = sum(1 for v in hits.values() if v)
        res[label] = {"blocked": f"{n}/{len(items)}", "pass": [t for t, v in hits.items() if not v],
                      "blockedEx": {t: v for t, v in hits.items() if v}}
        print(label, res[label]["blocked"])
        print("   passed:", res[label]["pass"])
        if label.startswith("benign"):
            print("   FPs:", res[label]["blockedEx"])
    # M1 pre-screen with fold + slang
    DISTRESS_EXTRA = ["kms", "kys", "unalive", "unalive myself", "end it", "not wake up", "wont wake up",
                      "goodbye notes", "goodbye note", "suicide note", "enough pills", "kill me now"]
    HARM_EXTRA = ["kill him", "kill her", "stab the", "shoot the", "bring my piece", "bringing a piece"]
    dre = re.compile(r"(?<![a-z0-9])(?:" + "|".join(re.escape(fold(t).strip()) for t in list(safety._DISTRESS) + DISTRESS_EXTRA) + r")(?![a-z0-9])")
    hre = re.compile(r"(?<![a-z0-9])(?:" + "|".join(re.escape(fold(t).strip()) for t in list(safety._HARM) + HARM_EXTRA) + r")(?![a-z0-9])")
    print("M1 pre-screen with fold+slang:")
    for t, st, exp in M1_CASES:
        f = " ".join(fold(t).replace("'", "").split())
        got = "harm" if hre.search(f) else "distress" if dre.search(f) else "none"
        print(f"  exp={exp:8s} old={safety.code_screen(t):8s} new={got:8s} | {t}")
    json.dump(res, open(__file__.rsplit("/", 1)[0] + "/fold_results.json", "w"), indent=1, ensure_ascii=False)
