"""Automated verification V1-V11. Expected values are derived by hand from Section 4.3 and are written
as literals (integer numerator and denominator in the canonical form of src/engine.py, plus the
one-decimal display value). They are not computed by the engine and were written before the first run."""
import glob, json, os, sys
from fractions import Fraction
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import engine
from engine import evaluate, serialize, InputError

REPO = json.load(open(os.path.join(ROOT, "repository.json")))
SCEN = {os.path.basename(p)[:-5]: json.load(open(p)) for p in sorted(glob.glob(os.path.join(ROOT, "scenarios", "S*.json")))}
EV0 = {"verification": 0, "completeness": 0, "relevance": 0, "recency": 0}
EV3 = {d: 3 for d in EV0}


def mini(spec, domains=None):
    """spec: list of (id, domain, scope, weight)."""
    domains = domains or {}
    doms = {}
    for i, d, s, w in spec:
        doms.setdefault(d, {"name": d, "scope": s})
    return {"version": "mini", "domains": doms, "indicators": [
        {"id": i, "domain": d, "scope": s, "weight": w, "sources": {}, "relationship_term": "Supports",
         "relationship_note": ""} for i, d, s, w in spec]}


def scen(answers, ctx=None):
    return {"scenario_id": "T", "version": "t", "context": ctx or {}, "answers": answers}


def A(gap, ev=None):
    names = ["fully_implemented", "mostly_implemented", "partially_implemented", "implemented_minimally", "not_implemented"]
    return {"option": names[gap], "evidence": ev or EV0}


def check(metric, num, den, display):
    assert (metric["num"], metric["den"], metric["display"]) == (num, den, display)


# ---------------------------------------------------------------- V1
@pytest.mark.parametrize("option,gap", [("fully_implemented", 0), ("mostly_implemented", 1), ("partially_implemented", 2),
                                        ("implemented_minimally", 3), ("not_implemented", 4)])
def test_v1_gap_options(option, gap):
    r = evaluate(mini([("SG-01", "SG", "security", 3)]), scen({"SG-01": {"option": option, "evidence": EV0}}), "yes")
    ind = r["indicators"][0]
    assert (ind["status"], ind["gap"]) == ("assessed", gap)


def test_v1_unknown_unanswered_and_not_applicable():
    repo = mini([("SG-01", "SG", "security", 3), ("SC-04", "SC", "security", 3)])
    r = evaluate(repo, scen({"SG-01": {"option": "unknown"}, "SC-04": {"option": "not_applicable", "justification": "x"}},
                            {"customer_keys_offered": False}), "yes")
    st = {i["id"]: (i["status"], i["gap"]) for i in r["indicators"]}
    assert st == {"SG-01": ("unassessed", None), "SC-04": ("not_applicable", None)}
    r = evaluate(repo, scen({}, {"customer_keys_offered": False}), "yes")  # unanswered
    assert {i["id"]: i["status"] for i in r["indicators"]} == {"SG-01": "unassessed", "SC-04": "unassessed"}


# ---------------------------------------------------------------- V2
def test_v2_illustrative_example_of_section_4_3():
    repo = mini([("SG-01", "SG", "security", 5), ("SG-02", "SG", "security", 3), ("SG-03", "SG", "security", 4), ("SG-04", "SG", "security", 2)])
    ev = {"verification": 3, "completeness": 2, "relevance": 3, "recency": 1}   # s = 2*3+2+3+1 = 12
    r = evaluate(repo, scen({"SG-01": A(2, ev), "SG-02": A(0, ev), "SG-03": A(4, ev), "SG-04": {"option": "unknown"}}), "yes")
    g = r["groups"]["SG"]
    # sum(I*G) = 5*2 + 3*0 + 4*4 = 26 ; assessed weight 12 ; applicable weight 14 ; unassessed weight 2
    check(g["risk"], 650, 12, "54.2")            # 25*26/12 = 54.1667
    check(g["coverage"], 1200, 14, "85.7")       # 100*12/14 = 85.714
    check(g["upper_bound"], 850, 14, "60.7")     # 25*(26+8)/14 = 60.714
    ind = {i["id"]: i for i in r["indicators"]}["SG-01"]
    assert (ind["s"], ind["eci"]["num"], ind["eci"]["den"], ind["eci"]["display"]) == (12, 1200, 15, "80.0")


def test_v2_second_case():
    repo = mini([("SG-01", "SG", "security", 2), ("SG-02", "SG", "security", 3), ("SG-03", "SG", "security", 5)])
    r = evaluate(repo, scen({"SG-01": A(1), "SG-02": A(3), "SG-03": {"option": "unknown"}}), "yes")
    g = r["groups"]["SG"]
    # sum(I*G) = 2*1 + 3*3 = 11 ; assessed weight 5 ; applicable weight 10 ; unassessed weight 5
    check(g["risk"], 275, 5, "55.0")
    check(g["coverage"], 500, 10, "50.0")
    check(g["upper_bound"], 775, 10, "77.5")


# ---------------------------------------------------------------- V3
def test_v3_empty_assessed_set():
    repo = mini([("SG-01", "SG", "security", 3), ("SG-02", "SG", "security", 2)])
    g = evaluate(repo, scen({}), "yes")["groups"]["SG"]
    assert g["state"] == "not_assessed" and g["risk"] is None and g["eci"] is None
    check(g["coverage"], 0, 5, "0.0")
    check(g["upper_bound"], 500, 5, "100.0")      # 25*(0 + 4*5)/5


def test_v3_full_coverage():
    repo = mini([("SG-01", "SG", "security", 4), ("SG-02", "SG", "security", 1)])
    g = evaluate(repo, scen({"SG-01": A(2), "SG-02": A(4)}), "yes")["groups"]["SG"]
    # sum(I*G) = 4*2 + 1*4 = 12 ; weight 5
    check(g["risk"], 300, 5, "60.0")
    check(g["coverage"], 500, 5, "100.0")
    check(g["upper_bound"], 300, 5, "60.0")


def test_v3_all_applicable_unassessed_in_a_scope():
    repo = mini([("SG-01", "SG", "security", 3), ("SI-01", "SI", "security", 4)])
    r = evaluate(repo, scen({}), "yes")
    s = r["groups"]["security"]
    assert (s["state"], s["n_applicable"], s["n_assessed"], s["n_unassessed"]) == ("not_assessed", 2, 0, 2)
    check(s["upper_bound"], 700, 7, "100.0")


# ---------------------------------------------------------------- V4 (Table 8)
PDREPO = mini([("SG-01", "SG", "security", 3), ("PG-01", "PG", "personal_data", 4), ("PD-01", "PD", "personal_data", 4)])


def test_v4_empty_applicable_set_all_not_applicable():
    r = evaluate(PDREPO, scen({"SG-01": A(1)}), "no")
    for k in ("PG", "PD", "personal_data"):
        g = r["groups"][k]
        assert g["state"] == "not_applicable"
        assert g["risk"] is None and g["coverage"] is None and g["upper_bound"] is None and g["eci"] is None
    for i in r["indicators"]:
        if i["scope"] == "personal_data":
            assert i["status"] == "not_applicable" and i["justification"] == "No personal data processing was declared"


def test_v4_applicable_but_none_assessed():
    g = evaluate(PDREPO, scen({"SG-01": A(1)}), "yes")["groups"]["PG"]
    assert g["state"] == "not_assessed" and g["risk"] is None and g["eci"] is None
    check(g["coverage"], 0, 4, "0.0")
    check(g["upper_bound"], 400, 4, "100.0")


def test_v4_computed_row():
    g = evaluate(PDREPO, scen({"SG-01": A(1), "PG-01": A(2, EV3), "PD-01": A(0, EV3)}), "yes")["groups"]["personal_data"]
    # sum(I*G) = 4*2 + 4*0 = 8 ; weight 8 ; s = 15 for both
    assert g["state"] == "computed"
    check(g["risk"], 200, 8, "25.0")
    check(g["coverage"], 800, 8, "100.0")
    check(g["upper_bound"], 200, 8, "25.0")
    check(g["eci"], 100 * (4 * 15 + 4 * 15), 15 * 8, "100.0")


def test_v4_undetermined_row():
    r = evaluate(PDREPO, scen({"SG-01": A(1), "PG-01": A(2), "PD-01": A(2)}), "undetermined")
    for k in ("PG", "PD", "personal_data"):
        g = r["groups"][k]
        assert g["state"] == "undetermined"
        assert g["risk"] is None and g["coverage"] is None and g["upper_bound"] is None and g["eci"] is None
    assert all(i["status"] == "excluded_undetermined" for i in r["indicators"] if i["scope"] == "personal_data")
    assert r["groups"]["security"]["state"] == "computed"
    assert "inactive" not in json.dumps(r).lower()


# ---------------------------------------------------------------- V5
def exact(m):
    return Fraction(m["num"], m["den"])


def relation_holds(g):
    if g["state"] != "computed":
        return True
    R, C, UB = exact(g["risk"]), exact(g["coverage"]), exact(g["upper_bound"])
    return UB == R * C / 100 + (100 - C) and UB >= R and 0 <= R <= 100 and 0 <= C <= 100 and UB <= 100


def test_v5_relation_on_scenarios_and_cases():
    cases = [evaluate(REPO, s, d) for s in SCEN.values() for d in engine.DECLARATIONS]
    cases.append(evaluate(mini([("SG-01", "SG", "security", 5), ("SG-02", "SG", "security", 3), ("SG-03", "SG", "security", 4), ("SG-04", "SG", "security", 2)]),
                          scen({"SG-01": A(2), "SG-02": A(0), "SG-03": A(4), "SG-04": {"option": "unknown"}}), "yes"))
    n = 0
    for r in cases:
        for g in r["groups"].values():
            assert relation_holds(g)
            n += g["state"] == "computed"
    assert n > 100


# ---------------------------------------------------------------- V6
# (eV, eC, eR, eT, s, indicator ECI) for the 16 end-value combinations, derived by hand: s = 2*eV + eC + eR + eT
SIXTEEN = [
    (0, 0, 0, 0, 0, "0.0"), (0, 0, 0, 3, 3, "20.0"), (0, 0, 3, 0, 3, "20.0"), (0, 0, 3, 3, 6, "40.0"),
    (0, 3, 0, 0, 3, "20.0"), (0, 3, 0, 3, 6, "40.0"), (0, 3, 3, 0, 6, "40.0"), (0, 3, 3, 3, 9, "60.0"),
    (3, 0, 0, 0, 6, "40.0"), (3, 0, 0, 3, 9, "60.0"), (3, 0, 3, 0, 9, "60.0"), (3, 0, 3, 3, 12, "80.0"),
    (3, 3, 0, 0, 9, "60.0"), (3, 3, 0, 3, 12, "80.0"), (3, 3, 3, 0, 12, "80.0"), (3, 3, 3, 3, 15, "100.0"),
]


@pytest.mark.parametrize("ev,ec,er,et,s,disp", SIXTEEN)
def test_v6_sixteen_end_value_combinations(ev, ec, er, et, s, disp):
    repo = mini([("SG-01", "SG", "security", 3)])
    ratings = {"verification": ev, "completeness": ec, "relevance": er, "recency": et}
    r = evaluate(repo, scen({"SG-01": A(1, ratings)}), "yes")
    i = r["indicators"][0]
    assert (i["s"], i["eci"]["num"], i["eci"]["den"], i["eci"]["display"]) == (s, 100 * s, 15, disp)
    g = r["groups"]["SG"]["eci"]                      # single indicator: group ECI equals the indicator ECI
    assert (g["num"], g["den"], g["display"]) == (100 * 3 * s, 15 * 3, disp)


# Table 12 profiles: (eV, eC, eR, eT) -> s, ECI
PROFILES = {"A": ((3, 3, 3, 3), 15, "100.0"), "B": ((2, 2, 3, 2), 11, "73.3"), "C": ((2, 2, 2, 1), 9, "60.0"),
            "D": ((1, 1, 2, 1), 6, "40.0"), "E": ((0, 0, 0, 0), 0, "0.0")}


@pytest.mark.parametrize("p", list(PROFILES))
def test_v6_table_12_profiles(p):
    (ev, ec, er, et), s, disp = PROFILES[p]
    repo = mini([("SG-01", "SG", "security", 2)])
    r = evaluate(repo, scen({"SG-01": A(0, {"verification": ev, "completeness": ec, "relevance": er, "recency": et})}), "yes")
    i = r["indicators"][0]
    assert (i["s"], i["eci"]["display"]) == (s, disp)


def test_v6_group_level_eci_and_equal_weight_variant():
    repo = mini([("SG-01", "SG", "security", 4), ("SG-02", "SG", "security", 2)])
    a = {"SG-01": A(1, EV3), "SG-02": A(1, {"verification": 1, "completeness": 1, "relevance": 2, "recency": 1})}  # s = 15 and 6
    g = evaluate(repo, scen(a), "yes")["groups"]["SG"]["eci"]
    check(g, 100 * (4 * 15 + 2 * 6), 15 * 6, "80.0")                  # 7200/90
    g = evaluate(repo, scen(a), "yes", eci_mode="equal")["groups"]["SG"]["eci"]
    # equal weights: s = 12 and 5 ; 100*(4*12 + 2*5)/(12*6) = 5800/72 = 80.555...
    check(g, 100 * (4 * 12 + 2 * 5), 12 * 6, "80.6")
    ind = evaluate(repo, scen({"SG-01": A(1, {"verification": 2, "completeness": 2, "relevance": 3, "recency": 2}), "SG-02": A(1)}), "yes",
                   eci_mode="equal")["indicators"][0]
    assert (ind["s"], ind["eci"]["num"], ind["eci"]["den"], ind["eci"]["display"]) == (9, 900, 12, "75.0")


def test_v6_missing_evidence_gives_zero_and_never_changes_gap():
    repo = mini([("SG-01", "SG", "security", 3)])
    r = evaluate(repo, scen({"SG-01": {"option": "partially_implemented"}}), "yes")
    i = r["indicators"][0]
    assert (i["gap"], i["s"], i["eci"]["display"]) == (2, 0, "0.0")


def test_v6_invalid_rating_rejected():
    repo = mini([("SG-01", "SG", "security", 3)])
    for bad in (4, -1, 1.5, True):
        with pytest.raises(InputError):
            evaluate(repo, scen({"SG-01": A(1, {"verification": bad, "completeness": 0, "relevance": 0, "recency": 0})}), "yes")


# ---------------------------------------------------------------- V7
@pytest.mark.parametrize("just", [None, "", "   "])
def test_v7_not_applicable_requires_justification(just):
    repo = mini([("SC-04", "SC", "security", 3)])
    a = {"option": "not_applicable"}
    if just is not None:
        a["justification"] = just
    with pytest.raises(InputError):
        evaluate(repo, scen({"SC-04": a}, {"customer_keys_offered": False}), "yes")


def test_v7_not_applicable_rejected_for_always_applicable_indicator():
    repo = mini([("SG-01", "SG", "security", 3)])
    with pytest.raises(InputError):
        evaluate(repo, scen({"SG-01": {"option": "not_applicable", "justification": "x"}}), "yes")


def test_v7_not_applicable_rejected_when_context_says_applicable():
    repo = mini([("SC-04", "SC", "security", 3)])
    with pytest.raises(InputError):
        evaluate(repo, scen({"SC-04": {"option": "not_applicable", "justification": "x"}}, {"customer_keys_offered": True}), "yes")


# ---------------------------------------------------------------- V8 (PG-05)
PG5 = mini([("PG-05", "PG", "personal_data", 3), ("PG-01", "PG", "personal_data", 4)])


def pg5(opt, screening, just=None, decl="yes"):
    a = {"option": opt, "screening": screening, "evidence": EV0}
    if just:
        a["justification"] = just
    return evaluate(PG5, scen({"PG-05": a, "PG-01": A(1)}), decl)


def test_v8_applicable_when_screening_found_high_risk():
    i = {x["id"]: x for x in pg5("partially_implemented", "high_risk")["indicators"]}["PG-05"]
    assert (i["status"], i["gap"]) == ("assessed", 2)


def test_v8_not_applicable_only_with_documented_screening():
    r = pg5("not_applicable", "not_high_risk", "documented screening")
    i = {x["id"]: x for x in r["indicators"]}["PG-05"]
    assert i["status"] == "not_applicable"
    assert r["groups"]["PG"]["n_applicable"] == 1               # PG-05 left the applicable set
    for bad in ("unknown", None, "high_risk"):
        with pytest.raises(InputError):
            pg5("not_applicable", bad, "j")


@pytest.mark.parametrize("screening", ["unknown", None])
def test_v8_unassessed_when_screening_missing_or_unknown(screening):
    r = pg5("partially_implemented", screening)
    i = {x["id"]: x for x in r["indicators"]}["PG-05"]
    assert i["status"] == "unassessed" and i["gap"] is None
    assert r["groups"]["PG"]["n_applicable"] == 2 and r["groups"]["PG"]["n_unassessed"] == 1


def test_v8_declaration_no_and_undetermined_override():
    for decl, status in (("no", "not_applicable"), ("undetermined", "excluded_undetermined")):
        i = {x["id"]: x for x in pg5("unknown", "unknown", decl=decl)["indicators"]}["PG-05"]
        assert i["status"] == status


# ---------------------------------------------------------------- V9
def test_v9_priority_and_tie_break():
    repo = mini([("SG-01", "SG", "security", 2), ("SG-02", "SG", "security", 4), ("SG-03", "SG", "security", 3),
                 ("SG-04", "SG", "security", 2), ("SG-05", "SG", "security", 1), ("SG-06", "SG", "security", 5)])
    # SG-01: 2*4 = 8 ; SG-02: 4*3 = 12 ; SG-03: 3*2 = 6 ; SG-04: 2*3 = 6 ; SG-05: 1*4 = 4 ; SG-06: 5*0 = 0
    r = evaluate(repo, scen({"SG-01": A(4), "SG-02": A(3), "SG-03": A(2), "SG-04": A(3), "SG-05": A(4), "SG-06": A(0)}), "yes")
    assert [(x["id"], x["priority"]) for x in r["ranking"]] == [("SG-02", 12), ("SG-01", 8), ("SG-03", 6), ("SG-04", 6), ("SG-05", 4), ("SG-06", 0)]
    assert [x["position"] for x in r["ranking"]] == [1, 2, 3, 4, 5, 6]


def test_v9_ranking_excludes_unassessed_not_applicable_and_undetermined():
    r = evaluate(PDREPO, scen({"SG-01": A(2), "PG-01": A(4), "PD-01": {"option": "unknown"}}), "yes")
    assert [x["id"] for x in r["ranking"]] == ["PG-01", "SG-01"]
    r = evaluate(PDREPO, scen({"SG-01": A(2), "PG-01": A(4)}), "undetermined")
    assert [x["id"] for x in r["ranking"]] == ["SG-01"]


# ---------------------------------------------------------------- V10
@pytest.mark.parametrize("sid", sorted(SCEN))
def test_v10_repeatability(sid):
    outs = {serialize(evaluate(REPO, SCEN[sid], "yes")) for _ in range(10)}
    assert len(outs) == 1


# ---------------------------------------------------------------- V11
def sec_view(r):
    keys = ["SG", "SI", "SC", "SO", "SR", "security"]
    sec_ids = {i["id"] for i in r["indicators"] if i["scope"] == "security"}
    return (json.dumps({k: r["groups"][k] for k in keys}, sort_keys=True),
            json.dumps([{k: x[k] for k in ("id", "weight", "gap", "priority")} for x in r["ranking"] if x["id"] in sec_ids], sort_keys=True),
            json.dumps([i for i in r["indicators"] if i["scope"] == "security"], sort_keys=True))


@pytest.mark.parametrize("sid", sorted(SCEN))
def test_v11_security_independent_of_declaration(sid):
    views = {d: sec_view(evaluate(REPO, SCEN[sid], d)) for d in engine.DECLARATIONS}
    assert views["yes"] == views["no"] == views["undetermined"]


def test_v11_security_independent_of_personal_data_answers():
    base = SCEN["S3"]
    mutated = json.loads(json.dumps(base))
    for k, a in mutated["answers"].items():
        if k[:2] in ("PG", "PD"):
            a.update({"option": "not_implemented", "evidence": dict(EV3)}) if a["option"] != "not_applicable" else None
    assert sec_view(evaluate(REPO, base, "yes")) == sec_view(evaluate(REPO, mutated, "yes"))
