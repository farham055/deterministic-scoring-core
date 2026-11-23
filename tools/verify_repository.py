"""Verifies repository.json against Tables A1, A2, A3 and A4 parsed from the locked Section 4 text."""
import json, re, sys
spec = open("spec/section4_locked.txt", encoding="utf-8").read()
repo = json.load(open("repository.json"))
def table(title):
    i = spec.index(title); lines = spec[i:].split("\n")[2:]
    rows = []
    for l in lines:
        if not l.startswith("|"): 
            if rows: break
            continue
        cells = [c.strip() for c in l.strip().strip("|").split("|")]
        if set(cells[0]) <= set("- "): continue
        rows.append(cells)
    return rows[1:]
A1 = {r[0]: r for r in table("Table A1.")}
A2 = {r[0]: r for r in table("Table A2.")}
A3 = {r[0]: r for r in table("Table A3.")}
A4 = {r[0]: r for r in table("Table A4.")}
errs = []
def split_list(s, pat):
    if s == "None": return []
    return [x.strip() for x in re.split(pat, s)]
ids = [i["id"] for i in repo["indicators"]]
if sorted(ids) != sorted(A2): errs.append("id set mismatch")
for code, r in A1.items():
    d = repo["domains"][code]
    if d["name"] != r[1] or (d["scope"] == "security") != (r[2] == "Security"): errs.append(("domain", code))
    n = sum(1 for i in repo["indicators"] if i["domain"] == code)
    if n != int(r[3]): errs.append(("domain count", code, n))
for ind in repo["indicators"]:
    k = ind["id"]
    if ind["indicator"] != A2[k][1]: errs.append((k, "indicator text"))
    if ind["weight"] != int(A2[k][3]): errs.append((k, "weight", ind["weight"], A2[k][3]))
    if ind["weight_rationale"] != A2[k][4]: errs.append((k, "rationale"))
    a4 = A4[k]
    if ind["sources"]["nist_csf_2_0"] != split_list(a4[1], r",\s*"): errs.append((k, "csf"))
    ccm = [] if a4[2] == "None" else re.findall(r"[A-Z&]+-\d+ \([^)]*\)", a4[2])
    if ind["sources"]["csa_ccm_v4_1"] != ccm: errs.append((k, "ccm", ccm))
    if ind["sources"]["gdpr"] != split_list(a4[3], r",\s*"): errs.append((k, "gdpr"))
    if ind["sources"]["nist_privacy_framework"] != split_list(a4[4], r",\s*"): errs.append((k, "pf"))
    note = a4[5]
    m = re.match(r"^(Supports|Partial)\.\s*(.*)$", note)
    if m: term, rest = m.group(1), m.group(2)
    else: term, rest = "Broader", note
    if ind["relationship_term"] != term: errs.append((k, "term", ind["relationship_term"], term))
    if ind["relationship_note"] != rest: errs.append((k, "note"))
    a3 = A3[k][3]
    exp_scope = "personal_data" if k[:2] in ("PG","PD") else "security"
    if ind["scope"] != exp_scope: errs.append((k, "scope"))
    app = ind["applicability"]
    expected = {"Always applicable":"always",
      "Applicable when at least one cloud provider or other supplier is used":"supplier_used",
      "Applicable if endpoint devices are used to administer or access the system":"endpoints_used",
      "Personal-data scope active":"pd_scope_active"}.get(a3)
    if k == "SC-04": expected = "customer_keys_offered"
    if k == "PG-05": expected = "pd_scope_active_and_high_risk_screening"
    if app != expected: errs.append((k, "applicability", app, expected))
print("indicators:", len(ids), "errors:", len(errs))
for e in errs: print(" ", e)
sys.exit(1 if errs else 0)
