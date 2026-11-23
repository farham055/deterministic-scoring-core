"""Builds the eight scenario JSON files from Table B1, Table B2, Table 11 and Table 12 of the locked Section 5 text."""
import json, re
txt = open("spec/section5_locked.txt", encoding="utf-8").read()
def table(title):
    i = txt.index(title); out = []
    for l in txt[i:].split("\n")[2:]:
        if not l.startswith("|"):
            if out: break
            continue
        c = [x.strip() for x in l.strip().strip("|").split("|")]
        if set(c[0]) <= set("- "): continue
        out.append(c)
    return out
B1 = table("Table B1. Scenario answer matrix."); hdr, rows = B1[0], B1[1:]
assert hdr == ["ID"] + [f"S{i}" for i in range(1, 9)] and len(rows) == 35
B2 = {r[0]: r for r in table("Table B2. Standard justifications")[1:]}
T12 = {r[0]: [int(x) for x in r[1:5]] for r in table("Table 12. Evidence profiles.")[1:]}
EXC = {  # Table 11, evidence profile column, written out exactly as listed
 "S1": ("A", {"SG-05": "B", "SO-06": "B"}), "S2": ("D", {"SI-01": "E", "SI-02": "E"}),
 "S3": ("C", {"SG-05": "E", "SO-03": "E"}), "S4": ("D", {"SR-02": "E"}),
 "S5": ("D", {"SG-01": "B", "SI-01": "B"}), "S6": ("C", {}),
 "S7": ("B", {"PG-01": "E", "PG-02": "E", "PG-03": "E", "PG-05": "E"}), "S8": ("C", {"SO-02": "E", "SO-06": "E"})}
t11 = {r[0]: r[4] for r in table("Table 11. Scenario set.")[1:]}
for s,(p,e) in EXC.items():
    parts = [p] + [f"{k} at {v}" for k, v in e.items()]
    exp = parts[0] + (", with " + " and ".join(parts[1:]) if len(parts) > 1 else "")
    exp = exp.replace("with SG-05 at B and SO-06 at B","with SG-05 and SO-06 at B")
    # compare loosely: same profile letter and same set of exception indicator ids
    assert t11[s][0] == p and set(re.findall(r"[A-Z]{2}-\d\d", t11[s])) == set(e), (s, t11[s])
OPT = {"0": "fully_implemented", "1": "mostly_implemented", "2": "partially_implemented",
       "3": "implemented_minimally", "4": "not_implemented"}
TITLES = {"S1":"Reference organization","S2":"Identity weaknesses","S3":"Misconfiguration and uncontrolled change",
 "S4":"Ransomware without recoverability","S5":"Third-party reliance and shared responsibility","S6":"Partial assessment",
 "S7":"Weak privacy governance","S8":"Exploitation of unpatched vulnerabilities"}
for col, sid in enumerate(hdr[1:], start=1):
    prof, exc = EXC[sid]
    answers, screening, ctx_keys = {}, "unknown", None
    for r in rows:
        k, v = r[0], r[col]
        if v in OPT:
            a = {"option": OPT[v]}
        elif v == "U":
            a = {"option": "unknown"}
        elif v == "N":
            a = {"option": "not_applicable", "justification": B2["J1" if k == "SC-04" else "J2"][2], "justification_code": "J1" if k == "SC-04" else "J2"}
        else: raise SystemExit(f"bad cell {k} {sid} {v}")
        if k == "PG-05":
            screening = {"N": "not_high_risk", "U": "unknown"}.get(v, "high_risk")
            a["screening"] = screening
            if screening == "high_risk": a["screening_code"] = "J3"
            if screening == "unknown": a["screening_code"] = "J4"
        if a["option"] in OPT.values():
            letter = exc.get(k, prof)
            a["evidence"] = dict(zip(["verification","completeness","relevance","recency"], T12[letter])); a["evidence_profile"] = letter
        answers[k] = a
    sc = {"scenario_id": sid, "version": "1.0", "title": TITLES[sid], "synthetic": True,
          "context": {"supplier_used": True, "endpoints_used": True,
                      "customer_keys_offered": answers["SC-04"]["option"] != "not_applicable"},
          "evidence_profile_default": prof, "evidence_profile_exceptions": exc, "answers": answers}
    json.dump(sc, open(f"scenarios/{sid}.json", "w"), indent=1, sort_keys=True)
print("scenarios written")
