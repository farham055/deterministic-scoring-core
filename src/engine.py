"""Deterministic scoring engine (Section 4.3 of the paper).

No third-party dependencies, no randomness, no I/O. All sums are integers. Every reported
metric is stored as an integer numerator and denominator in the canonical forms below; the
single division per metric is the conversion of that pair to a one-decimal display string,
which uses integer arithmetic with rounding half up.

Canonical forms (A = assessed, P = applicable, U = unassessed indicators of a group):
  risk R            = 25 * sum(I*G over A)                    / sum(I over A)
  coverage C        = 100 * sum(I over A)                     / sum(I over P)
  upper bound       = 25 * (sum(I*G over A) + 4*sum(I over U)) / sum(I over P)
  indicator ECI     = 100 * s                                  / 15          (12 in equal-weight mode)
  group ECI         = 100 * sum(I*s over A)                    / (15 * sum(I over A))   (12 in equal mode)
  with s = 2*eV + eC + eR + eT (weighted mode) or eV + eC + eR + eT (equal mode).
"""

GAP_OPTIONS = {
    "fully_implemented": 0,
    "mostly_implemented": 1,
    "partially_implemented": 2,
    "implemented_minimally": 3,
    "not_implemented": 4,
}
ALL_OPTIONS = set(GAP_OPTIONS) | {"unknown", "not_applicable"}
# Indicators that Table A3 does not mark "Always applicable" and for which a
# not-applicable answer is therefore accepted, with the context flag that must be false.
NA_ALLOWED = {"SG-04": "supplier_used", "SC-04": "customer_keys_offered", "SO-05": "endpoints_used", "PG-05": None}
DECLARATIONS = ("yes", "no", "undetermined")
NO_PD_JUSTIFICATION = "No personal data processing was declared"
NOTICE = ("Decision support that requires human review. The output supports a readiness assessment "
          "and makes no claim of legal compliance.")
DIMENSIONS = ("verification", "completeness", "relevance", "recency")


class InputError(ValueError):
    pass


def fmt1(num, den):
    """num/den (num >= 0, den > 0) as a one-decimal string, rounding half up, integer arithmetic only.
    Returns (text, exact_tie) where exact_tie marks values lying exactly on a rounding boundary."""
    if den <= 0 or num < 0:
        raise InputError("invalid fraction")
    tenths = (20 * num + den) // (2 * den)
    tie = (20 * num) % (2 * den) == den
    return "%d.%d" % (tenths // 10, tenths % 10), tie


def _metric(num, den):
    text, tie = fmt1(num, den)
    return {"num": num, "den": den, "display": text, "exact_rounding_tie": tie}


def _eci_score(ev, mode):
    e = [ev[d] for d in DIMENSIONS]
    if mode == "weighted":
        return 2 * e[0] + e[1] + e[2] + e[3]
    return e[0] + e[1] + e[2] + e[3]


def _resolve_indicator(ind, ans, scenario, declaration, mode):
    """Returns a dict describing status, gap and evidence of one indicator."""
    k = ind["id"]
    base = {"id": k, "domain": ind["domain"], "scope": ind["scope"], "weight": ind["weight"],
            "status": None, "gap": None, "justification": None, "evidence": None, "s": None, "note": None}
    if ind["scope"] == "personal_data":
        if declaration == "no":
            base.update(status="not_applicable", justification=NO_PD_JUSTIFICATION)
            return base
        if declaration == "undetermined":
            base.update(status="excluded_undetermined")
            return base
    opt = (ans or {}).get("option", "unknown")
    if opt not in ALL_OPTIONS:
        raise InputError("%s: unknown answer option %r" % (k, opt))
    ctx = scenario.get("context", {})
    if opt == "not_applicable":
        just = (ans.get("justification") or "").strip()
        if not just:
            raise InputError("%s: not applicable requires a written justification" % k)
        if k not in NA_ALLOWED:
            raise InputError("%s: not applicable is not accepted for an indicator that is always applicable" % k)
        flag = NA_ALLOWED[k]
        if flag is not None and ctx.get(flag, True):
            raise InputError("%s: not applicable conflicts with context flag %s" % (k, flag))
        if k == "PG-05" and ans.get("screening") != "not_high_risk":
            raise InputError("PG-05: not applicable requires a documented screening that found no likely high risk")
        base.update(status="not_applicable", justification=just)
        return base
    if k == "PG-05":
        screening = ans.get("screening")
        if screening not in ("high_risk", "not_high_risk"):
            base.update(status="unassessed", note="screening not performed or outcome unknown")
            return base
    if opt == "unknown":
        base.update(status="unassessed")
        return base
    g = GAP_OPTIONS[opt]
    ev = (ans or {}).get("evidence")
    if ev is None:
        ev = {d: 0 for d in DIMENSIONS}
    for d in DIMENSIONS:
        v = ev.get(d)
        if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= 3:
            raise InputError("%s: evidence rating %s must be an integer from 0 to 3" % (k, d))
    base.update(status="assessed", gap=g, evidence={d: ev[d] for d in DIMENSIONS}, s=_eci_score(ev, mode))
    return base


def _group(label, members, scope, declaration, den_eci):
    P = [m for m in members if m["status"] in ("assessed", "unassessed")]
    A = [m for m in P if m["status"] == "assessed"]
    U = [m for m in P if m["status"] == "unassessed"]
    out = {"group": label, "n_applicable": len(P), "n_assessed": len(A), "n_unassessed": len(U)}
    if scope == "personal_data" and declaration == "undetermined":
        out.update(state="undetermined", risk=None, coverage=None, upper_bound=None, eci=None)
        out.update(n_applicable=None, n_assessed=None, n_unassessed=None)
        return out
    if not P:
        out.update(state="not_applicable", risk=None, coverage=None, upper_bound=None, eci=None)
        return out
    sum_p = sum(m["weight"] for m in P)
    sum_a = sum(m["weight"] for m in A)
    sum_u = sum(m["weight"] for m in U)
    sum_ig = sum(m["weight"] * m["gap"] for m in A)
    out["coverage"] = _metric(100 * sum_a, sum_p)
    out["upper_bound"] = _metric(25 * (sum_ig + 4 * sum_u), sum_p)
    if not A:
        out.update(state="not_assessed", risk=None, eci=None)
        return out
    out["state"] = "computed"
    out["risk"] = _metric(25 * sum_ig, sum_a)
    out["eci"] = _metric(100 * sum(m["weight"] * m["s"] for m in A), den_eci * sum_a)
    return out


def evaluate(repo, scenario, declaration, weights=None, eci_mode="weighted"):
    """Evaluates one scenario. `weights` optionally maps indicator id -> integer 1..5 (sensitivity analysis)."""
    if declaration not in DECLARATIONS:
        raise InputError("declaration must be one of %r" % (DECLARATIONS,))
    if eci_mode not in ("weighted", "equal"):
        raise InputError("eci_mode must be 'weighted' or 'equal'")
    den_eci = 15 if eci_mode == "weighted" else 12
    answers = scenario["answers"]
    resolved = []
    for ind in repo["indicators"]:
        ind = dict(ind)
        if weights and ind["id"] in weights:
            w = weights[ind["id"]]
            if not isinstance(w, int) or not 1 <= w <= 5:
                raise InputError("weight of %s outside 1..5" % ind["id"])
            ind["weight"] = w
        r = _resolve_indicator(ind, answers.get(ind["id"]), scenario, declaration, eci_mode)
        r["sources"] = ind["sources"]
        r["relationship_term"] = ind["relationship_term"]
        r["relationship_note"] = ind["relationship_note"]
        if r["status"] == "assessed":
            r["eci"] = {"num": 100 * r["s"], "den": den_eci, "display": fmt1(100 * r["s"], den_eci)[0]}
            r["priority"] = r["weight"] * r["gap"]
        resolved.append(r)
    resolved.sort(key=lambda m: m["id"])
    groups = {}
    for code, d in sorted(repo["domains"].items()):
        mem = [m for m in resolved if m["domain"] == code]
        groups[code] = _group(code, mem, d["scope"], declaration, den_eci)
    for scope in ("security", "personal_data"):
        mem = [m for m in resolved if m["scope"] == scope]
        groups[scope] = _group(scope, mem, scope, declaration, den_eci)
    ranked = sorted((m for m in resolved if m["status"] == "assessed"), key=lambda m: (-m["priority"], m["id"]))
    ranking = [{"position": i + 1, "id": m["id"], "weight": m["weight"], "gap": m["gap"], "priority": m["priority"]}
               for i, m in enumerate(ranked)]
    return {"scenario_id": scenario["scenario_id"], "scenario_version": scenario["version"],
            "synthetic": True, "declaration": declaration, "eci_mode": eci_mode,
            "repository_version": repo["version"], "groups": groups, "indicators": resolved,
            "ranking": ranking, "notice": NOTICE}


def serialize(result):
    import json
    return json.dumps(result, sort_keys=True, separators=(",", ":"))
