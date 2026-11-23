"""Independent reference calculation for the manual comparison (S2, S6, S7, declaration Yes).
Uses only the locked specification text and exact rational arithmetic. It imports nothing from src/ and
does not read repository.json, scenarios/*.json or any engine output."""
import json, re, sys, hashlib, datetime
from fractions import Fraction as F
from math import floor
sec4 = open("spec/section4_locked.txt", encoding="utf-8").read()
sec5 = open("spec/section5_locked.txt", encoding="utf-8").read()
def table(txt, title):
    i = txt.index(title); out = []
    for l in txt[i:].split("\n")[2:]:
        if not l.startswith("|"):
            if out: break
            continue
        c = [x.strip() for x in l.strip().strip("|").split("|")]
        if set(c[0]) <= set("- "): continue
        out.append(c)
    return out[1:]
W = {r[0]: int(r[3]) for r in table(sec4, "Table A2.")}
B1 = table(sec5, "Table B1. Scenario answer matrix.")
col = {f"S{i}": i for i in range(1, 9)}
PROF = {"A": (3,3,3,3), "B": (2,2,3,2), "C": (2,2,2,1), "D": (1,1,2,1), "E": (0,0,0,0)}
EXC = {"S2": ("D", {"SI-01": "E", "SI-02": "E"}), "S6": ("C", {}),
       "S7": ("B", {"PG-01": "E", "PG-02": "E", "PG-03": "E", "PG-05": "E"})}
DOM = lambda k: k[:2]
SCOPE = lambda k: "personal_data" if k[:2] in ("PG", "PD") else "security"
def r1(x):  # one decimal, half up
    return str(F(floor(x * 10 + F(1, 2)), 10).limit_denominator(10)) if False else "%d.%d" % divmod(floor(x * 10 + F(1, 2)), 10)
def run(sid):
    ans = {r[0]: r[col[sid]] for r in B1}
    prof, exc = EXC[sid]
    ind = {}
    for k, v in ans.items():
        if v == "N": ind[k] = ("NA", None, None)
        elif v == "U": ind[k] = ("U", None, None)
        else:
            e = PROF[exc.get(k, prof)]
            ind[k] = ("A", int(v), 2 * e[0] + e[1] + e[2] + e[3])
    groups = {}
    for name, sel in [(d, (lambda k, d=d: DOM(k) == d)) for d in ["SG","SI","SC","SO","SR","PG","PD"]] + \
                     [(s, (lambda k, s=s: SCOPE(k) == s)) for s in ["security", "personal_data"]]:
        P = [k for k in ind if sel(k) and ind[k][0] in ("A", "U")]
        A = [k for k in P if ind[k][0] == "A"]; U = [k for k in P if ind[k][0] == "U"]
        g = {"applicable": len(P), "assessed": len(A), "unassessed": len(U)}
        if not P: g["state"] = "not_applicable"
        else:
            sp = sum(W[k] for k in P); sa = sum(W[k] for k in A); su = sum(W[k] for k in U)
            sig = sum(W[k] * ind[k][1] for k in A)
            c = F(100 * sa, sp); ub = F(25 * (sig + 4 * su), sp)
            g["coverage"] = [str(c), r1(c)]; g["upper_bound"] = [str(ub), r1(ub)]
            if not A: g["state"] = "not_assessed"
            else:
                R = F(25 * sig, sa); eci = F(100 * sum(W[k] * ind[k][2] for k in A), 15 * sa)
                g["state"] = "computed"; g["risk"] = [str(R), r1(R)]; g["eci"] = [str(eci), r1(eci)]
        groups[name] = g
    inds = {k: {"status": v[0], "gap": v[1], "s": v[2], "eci": (None if v[0] != "A" else [str(F(100 * v[2], 15)), r1(F(100 * v[2], 15))])} for k, v in ind.items()}
    rank = sorted([k for k in ind if ind[k][0] == "A"], key=lambda k: (-W[k] * ind[k][1], k))
    return {"groups": groups, "indicators": inds, "ranking": [[k, W[k] * ind[k][1]] for k in rank]}
out = {"produced_by": "independent reference calculation (exact rational arithmetic), not a hand calculation by the researcher",
       "produced_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
       "declaration": "yes", "scenarios": {s: run(s) for s in ("S2", "S6", "S7")}}
fn = "manual/hand_results_" + out["produced_at_utc"][:10] + ".json"
json.dump(out, open(fn, "w"), indent=1, sort_keys=True)
print(fn, hashlib.sha256(open(fn, "rb").read()).hexdigest())
