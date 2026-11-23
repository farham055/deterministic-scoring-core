import glob, json, os, sys, platform, hashlib, statistics, sqlite3, datetime
from fractions import Fraction as F
sys.path.insert(0, "src")
import engine
from engine import evaluate, serialize
os.makedirs("results", exist_ok=True)
REPO = json.load(open("repository.json"))
SC = {os.path.basename(p)[:-5]: json.load(open(p)) for p in sorted(glob.glob("scenarios/S*.json"))}
DECL = ["yes", "no", "undetermined"]
SIDS = sorted(SC)
GROUPS = ["SG", "SI", "SC", "SO", "SR", "PG", "PD", "security", "personal_data"]
DOMS = GROUPS[:7]
def fr(m): return None if m is None else F(m["num"], m["den"])
def dump(name, obj): json.dump(obj, open("results/" + name, "w"), indent=1, sort_keys=True)
def r3(x):
    s = -1 if x < 0 else 1; v = abs(x); t = (v * 1000 + F(1, 2)).__floor__()
    return "%s%d.%03d" % ("-" if s < 0 and t else "", t // 1000, t % 1000)
def r1(x): return engine.fmt1(x.numerator, x.denominator)[0]
summary = {}

# ---------------- manifest
files = ["repository.json", "src/engine.py", "tests/test_engine.py", "tests/test_web.py", "data/questions.json"] + sorted(glob.glob("scenarios/*.json")) + sorted(glob.glob("webapp/*.py")) + sorted(glob.glob("webapp/assess/*.py")) + sorted(glob.glob("webapp/assess/templates/assess/*.html"))
dump("run_manifest.json", {"sha256": {f: hashlib.sha256(open(f, "rb").read()).hexdigest() for f in files},
     "python": platform.python_version(), "os": platform.platform(), "sqlite3_library": sqlite3.sqlite_version,
     "django": __import__("django").get_version(), "run_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")})

# ---------------- 5.4 scenario runs (declaration yes) and all declarations
RUN = {(s, d): evaluate(REPO, SC[s], d) for s in SIDS for d in DECL}
for (s, d), r in RUN.items(): dump(f"run_{s}_{d}.json", r)
rows = {}
for s in SIDS:
    r = RUN[(s, "yes")]
    rows[s] = {g: {k: (v if not isinstance(v, dict) else v["display"]) for k, v in r["groups"][g].items()} for g in GROUPS}
    rows[s]["ranking_top5"] = [(x["id"], x["priority"]) for x in r["ranking"][:5]]
summary["scenario_runs"] = rows

# report properties
props = {"all_indicators_list_sources_and_terms": True, "separate_values_no_composite": True, "notice_present": True, "no_compliance_claim": True}
for r in RUN.values():
    for i in r["indicators"]:
        if not i["sources"] or not i["relationship_term"] or "relationship_note" not in i: props["all_indicators_list_sources_and_terms"] = False
    for g in r["groups"].values():
        if set(g) - {"group","n_applicable","n_assessed","n_unassessed","state","risk","coverage","upper_bound","eci"}: props["separate_values_no_composite"] = False
    if "human review" not in r["notice"] or "no claim of legal compliance" not in r["notice"]: props["notice_present"] = False
    if "compliant" in json.dumps(r).lower().replace("no claim of legal compliance",""): props["no_compliance_claim"] = False
summary["report_properties"] = props
# count of exact rounding ties across all runs
ties = []
for (s, d), r in RUN.items():
    for g, v in r["groups"].items():
        for m in ("risk", "coverage", "upper_bound", "eci"):
            if v.get(m) and v[m]["exact_rounding_tie"]: ties.append((s, d, g, m, v[m]["display"]))
    for i in r["indicators"]:
        if i.get("eci") and engine.fmt1(i["eci"]["num"], i["eci"]["den"])[1]: ties.append((s, d, i["id"], "indicator_eci"))
summary["exact_rounding_ties"] = ties

# ---------------- expectations
E = {}
g6 = RUN[("S6","yes")]["groups"]["SR"]
E["1"] = g6["state"] == "not_assessed" and fr(g6["coverage"]) == 0 and fr(g6["upper_bound"]) == 100 and g6["risk"] is None and g6["eci"] is None
g2 = RUN[("S2","yes")]["groups"]["SI"]
E["2"] = g2["state"] == "computed" and fr(g2["risk"]) == 100 and g2["n_assessed"] == 4
r1_ = RUN[("S1","yes")]; ind1 = {i["id"]: i for i in r1_["indicators"]}
E["3"] = (ind1["SC-04"]["status"] == "not_applicable" and ind1["PG-05"]["status"] == "not_applicable"
          and ind1["SC-04"]["justification"] and ind1["PG-05"]["justification"]
          and r1_["groups"]["SC"]["n_applicable"] == 3 and r1_["groups"]["PG"]["n_applicable"] == 5)
ind6 = {i["id"]: i for i in RUN[("S6","yes")]["indicators"]}
E["4"] = ind6["PG-05"]["status"] == "unassessed" and RUN[("S6","yes")]["groups"]["PG"]["n_applicable"] == 6
E["5"] = all(fr(v["upper_bound"]) >= fr(v["risk"]) for r in RUN.values() for v in r["groups"].values() if v["state"] == "computed")
secrisk = {s: fr(RUN[(s,"yes")]["groups"]["security"]["risk"]) for s in SIDS}
E["6"] = all(secrisk["S1"] < secrisk[s] for s in SIDS if s != "S1")
E["7"] = fr(RUN[("S7","yes")]["groups"]["personal_data"]["risk"]) > fr(RUN[("S7","yes")]["groups"]["security"]["risk"])
summary["expectations"] = {k: bool(v) for k, v in E.items()}
summary["security_risk_by_scenario"] = {s: r1(v) for s, v in secrisk.items()}
summary["S7_pd_vs_sec_risk"] = [r1(fr(RUN[("S7","yes")]["groups"]["personal_data"]["risk"])), r1(secrisk["S7"])]

# ---------------- 5.5 paired test
def secview(r):
    ids = {i["id"] for i in r["indicators"] if i["scope"] == "security"}
    return (json.dumps({k: r["groups"][k] for k in ["SG","SI","SC","SO","SR","security"]}, sort_keys=True),
            json.dumps([{k: x[k] for k in ("id","weight","gap","priority")} for x in r["ranking"] if x["id"] in ids], sort_keys=True),
            json.dumps([i for i in r["indicators"] if i["scope"] == "security"], sort_keys=True))
P = {k: {} for k in ("P1","P2","P3","P4","P5")}
PG5 = {"S1":"not_applicable","S4":"not_applicable","S8":"not_applicable","S2":"unassessed","S5":"unassessed","S6":"unassessed","S3":"assessed","S7":"assessed"}
for s in SIDS:
    y, n, u = RUN[(s,"yes")], RUN[(s,"no")], RUN[(s,"undetermined")]
    P["P1"][s] = secview(y) == secview(n) == secview(u)
    pdn = [i for i in n["indicators"] if i["scope"] == "personal_data"]
    P["P2"][s] = (all(i["status"] == "not_applicable" and i["justification"] == "No personal data processing was declared" for i in pdn)
                  and all(n["groups"][g]["state"] == "not_applicable" for g in ("PG","PD","personal_data")))
    pdu = [i for i in u["indicators"] if i["scope"] == "personal_data"]
    P["P3"][s] = (all(i["status"] == "excluded_undetermined" for i in pdu)
                  and all(u["groups"][g]["state"] == "undetermined" and all(u["groups"][g][m] is None for m in ("risk","coverage","upper_bound","eci")) for g in ("PG","PD","personal_data"))
                  and not any(x["id"][:2] in ("PG","PD") for x in u["ranking"])
                  and all(w not in serialize(u).lower() for w in ("inactive", "not active")))
    pdy = {i["id"]: i for i in y["indicators"] if i["scope"] == "personal_data"}
    ok = all(v["status"] in ("assessed","unassessed") for k, v in pdy.items() if k != "PG-05")
    ok = ok and pdy["PG-05"]["status"] in ("assessed","unassessed","not_applicable") and y["groups"]["personal_data"]["state"] == "computed"
    P["P4"][s] = ok
    P["P5"][s] = pdy["PG-05"]["status"] == PG5[s]
summary["paired_checks"] = P
rq2 = {}
for s in SIDS:
    y = RUN[(s,"yes")]; pdi = [i for i in y["indicators"] if i["scope"] == "personal_data"]
    g = y["groups"]["personal_data"]
    rq2[s] = {"applicable": g["n_applicable"], "assessed": g["n_assessed"], "assessed_gap_ge_3": sum(1 for i in pdi if i["status"] == "assessed" and i["gap"] >= 3),
              "risk": g["risk"]["display"], "coverage": g["coverage"]["display"], "upper_bound": g["upper_bound"]["display"], "eci": g["eci"]["display"],
              "top3": [(x["id"], x["priority"]) for x in y["ranking"] if x["id"][:2] in ("PG","PD")][:3]}
summary["rq2_pd_summary_yes"] = rq2

# ---------------- 5.6 sensitivity
def positions(r): return {x["id"]: x["position"] for x in r["ranking"]}
def spearman(a, b):
    n = len(a)
    if n < 2: return None
    d2 = sum((a[k] - b[k]) ** 2 for k in a); den = n * (n * n - 1)
    return F(den - 6 * d2, den)
sens = {}; allrisk = []; per = {}
BASE_W = {i["id"]: i["weight"] for i in REPO["indicators"]}
n_runs = 0
for s in SIDS:
    base = RUN[(s,"yes")]; bpos = positions(base); btop5 = {x["id"] for x in base["ranking"][:5]}
    changes = []; rhos = []; top5chg = 0; cfgs = []; na_effect = []
    configs = [("W-minus", k, BASE_W[k] - 1) for k in sorted(BASE_W)] + [("W-plus", k, BASE_W[k] + 1) for k in sorted(BASE_W) if BASE_W[k] < 5] + [("EQ", None, None)]
    status = {i["id"]: i["status"] for i in base["indicators"]}
    for kind, k, w in configs:
        r = evaluate(REPO, SC[s], "yes", weights=None if kind == "EQ" else {k: w}, eci_mode="equal" if kind == "EQ" else "weighted")
        n_runs += 1
        d = {}
        for g in GROUPS:
            bg, pg = base["groups"][g], r["groups"][g]
            for m in ("risk", "coverage", "upper_bound") + (("eci",) if kind == "EQ" else ()):
                if bg.get(m) is not None and pg.get(m) is not None: d[(g, m)] = fr(pg[m]) - fr(bg[m])
        cfgs.append((kind, k, d))
        if kind != "EQ":
            rho = spearman(bpos, positions(r)); rhos.append((rho, k, kind))
            if {x["id"] for x in r["ranking"][:5]} != btop5: top5chg += 1
            if status[k] == "not_applicable": na_effect.append(all(v == 0 for v in d.values()) and rho == 1)
    domabs = [abs(v) for kind, k, d in cfgs if kind != "EQ" for (g, m), v in d.items() if g in DOMS and m == "risk"]
    domabs_all = [abs(v) for kind, k, d in cfgs for (g, m), v in d.items() if g in DOMS and m == "risk"]
    allrisk += domabs
    largest = sorted(((max([abs(v) for (g, m), v in d.items() if g in DOMS and m == "risk"] or [F(0)]), kind, k) for kind, k, d in cfgs if kind != "EQ"), key=lambda t: (-t[0], t[2]))[:5]
    eq = [c for c in cfgs if c[0] == "EQ"][0][2]
    sens[s] = {"configs": len(configs), "max_abs_domain_risk_change_weights": r3(max(domabs)), "median_abs_domain_risk_change_weights": r3(F(statistics.median(domabs))),
        "min_rho": r3(min(r for r, _, _ in rhos)) if rhos else None, "min_rho_config": [(k, kind) for r, k, kind in rhos if r == min(rr for rr, _, _ in rhos)][:5],
        "n_rho_below_1": sum(1 for r, _, _ in rhos if r < 1), "top5_changed": top5chg,
        "largest_domain_risk_changes": [(r3(v), kind, k) for v, kind, k in largest],
        "eq_eci_change": {g: r3(eq[(g, "eci")]) for g in GROUPS if (g, "eci") in eq},
        "na_perturbations_no_effect": [all(na_effect), len(na_effect)]}
    per[s] = domabs
summary["sensitivity"] = sens
summary["sensitivity_runs"] = n_runs
summary["sensitivity_overall"] = {"max_abs_domain_risk_change": r3(max(allrisk)), "median_abs_domain_risk_change": r3(F(statistics.median(allrisk))),
    "min_rho_overall": min(v["min_rho"] for v in sens.values()), "top5_changed_total": sum(v["top5_changed"] for v in sens.values())}
# two explicit cases
r8 = RUN[("S8","yes")]; p8 = {x["id"]: x for x in r8["ranking"]}
r2r = RUN[("S2","yes")]; p2 = {x["id"]: x for x in r2r["ranking"]}
summary["explicit_cases"] = {"S8": {k: (p8[k]["priority"], p8[k]["position"]) for k in ("SO-06", "SO-01")},
                             "S2_priority6": [(x["id"], x["position"]) for x in r2r["ranking"] if x["priority"] == 6][:8],
                             "S2_SG01_SO06": [(p2[k]["priority"], p2[k]["position"]) for k in ("SG-01", "SO-06")]}

# ---------------- 5.7 manual comparison
hand = json.load(open(sorted(glob.glob("manual/hand_results_*.json"))[0]))
cmpd = 0; disc = []
for s, h in hand["scenarios"].items():
    r = RUN[(s, "yes")]
    for g in GROUPS:
        hg, eg = h["groups"][g], r["groups"][g]
        for key, ekey in (("applicable", "n_applicable"), ("assessed", "n_assessed"), ("unassessed", "n_unassessed")):
            cmpd += 1
            if hg[key] != eg[ekey]: disc.append((s, g, key, hg[key], eg[ekey]))
        cmpd += 1
        if hg["state"] != eg["state"]: disc.append((s, g, "state", hg["state"], eg["state"]))
        for m in ("risk", "coverage", "upper_bound", "eci"):
            cmpd += 1
            hv = hg.get(m); ev = eg.get(m)
            if (hv is None) != (ev is None): disc.append((s, g, m, hv, ev)); continue
            if hv is not None and (hv[0] != str(F(ev["num"], ev["den"])) or hv[1] != ev["display"]): disc.append((s, g, m, hv, [str(F(ev["num"], ev["den"])), ev["display"]]))
    ei = {i["id"]: i for i in r["indicators"]}
    for k, hi in h["indicators"].items():
        cmpd += 1
        st = {"A": "assessed", "U": "unassessed", "NA": "not_applicable"}[hi["status"]]
        if st != ei[k]["status"] or hi["gap"] != ei[k]["gap"]: disc.append((s, k, "status/gap", hi, ei[k]["status"], ei[k]["gap"]))
        if hi["status"] == "A":
            cmpd += 1
            if hi["s"] != ei[k]["s"] or hi["eci"][1] != ei[k]["eci"]["display"] or hi["eci"][0] != str(F(ei[k]["eci"]["num"], ei[k]["eci"]["den"])): disc.append((s, k, "indicator eci"))
    cmpd += 1
    if [[x["id"], x["priority"]] for x in r["ranking"]] != h["ranking"]: disc.append((s, "ranking"))
summary["manual_comparison"] = {"compared_values": cmpd, "discrepancies": disc, "n_discrepancies": len(disc), "hand_file": sorted(glob.glob("manual/hand_results_*.json"))[0]}
dump("evaluation_summary.json", summary)
print(json.dumps(summary, indent=1, sort_keys=True, default=str))
