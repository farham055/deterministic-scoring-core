import json, glob
S = [f"S{i}" for i in range(1, 9)]
R = {s: json.load(open(f"results/run_{s}_yes.json")) for s in S}
ev = json.load(open("results/evaluation_summary.json"))
def cell(g, m):
    return "-" if g.get(m) is None else g[m]["display"]
out = []
def md(title, head, rows):
    out.append(title); out.append("")
    out.append("| " + " | ".join(head) + " |"); out.append("| " + " | ".join(["---"] * len(head)) + " |")
    for r in rows: out.append("| " + " | ".join(str(x) for x in r) + " |")
    out.append("")
for scope, label in (("security", "security scope"), ("personal_data", "personal-data scope")):
    rows = []
    for s in S:
        g = R[s]["groups"][scope]
        rows.append([s, f'{g["n_applicable"]}/{g["n_assessed"]}/{g["n_unassessed"]}', cell(g,"risk"), cell(g,"coverage"), cell(g,"upper_bound"), cell(g,"eci")])
    md(f"Results, {label}, declaration Yes", ["Scenario", "Applicable/assessed/unassessed", "Risk", "Coverage", "Upper bound", "ECI"], rows)
for kind, name in (("risk", "Observed risk"), ("coverage", "Weighted coverage"), ("eci", "ECI")):
    rows = []
    for d in ["SG","SI","SC","SO","SR","PG","PD"]:
        rows.append([d] + [cell(R[s]["groups"][d], kind) for s in S])
    md(f"{name} by domain, declaration Yes (- means not defined)", ["Domain"] + S, rows)
rows = []
for d in ["SG","SI","SC","SO","SR","PG","PD"]:
    rows.append([d] + [f'{R[s]["groups"][d]["n_applicable"]}/{R[s]["groups"][d]["n_assessed"]}' for s in S])
md("Applicable/assessed indicators by domain", ["Domain"] + S, rows)
rows = [[s, "; ".join(f"{i} ({p})" for i, p in ev["scenario_runs"][s]["ranking_top5"])] for s in S]
md("Five highest-ranked indicators", ["Scenario", "Ranking (identifier, priority score)"], rows)
rows = []
for s in S:
    q = ev["rq2_pd_summary_yes"][s]
    rows.append([s, q["applicable"], q["assessed"], q["assessed_gap_ge_3"], q["risk"], q["coverage"], q["upper_bound"], q["eci"], "; ".join(f"{i} ({p})" for i, p in q["top3"])])
md("Personal-data summary", ["Scenario","Applicable","Assessed","Gap >= 3","Risk","Coverage","Upper bound","ECI","Top three personal-data indicators (priority)"], rows)
sens = ev["sensitivity"]
rows = [[s, sens[s]["max_abs_domain_risk_change_weights"], sens[s]["median_abs_domain_risk_change_weights"], sens[s]["min_rho"], sens[s]["n_rho_below_1"], sens[s]["top5_changed"],
         "; ".join(f"{k} {kind} ({v})" for v, kind, k in sens[s]["largest_domain_risk_changes"][:3])] for s in S]
md("Sensitivity", ["Scenario","Max abs. change in domain risk","Median","Min rho","Configs with rho < 1","Top-5 set changed","Largest changes"], rows)
rows = [[s] + [sens[s]["eq_eci_change"].get(g, "-") for g in ["SG","SI","SC","SO","SR","PG","PD","security","personal_data"]] for s in S]
md("Change in ECI under equal dimension weights (EQ)", ["Scenario","SG","SI","SC","SO","SR","PG","PD","security","personal_data"], rows)
open("results/section6_tables.md", "w").write("\n".join(out))
print("\n".join(out))
