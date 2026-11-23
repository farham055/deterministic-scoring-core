"""Smoke test of the Django layer (not one of V1-V11): the report page shows the engine values for S2 and S6,
the undetermined declaration is shown as a state and not as zero, and a not-applicable answer without a
justification is rejected."""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "webapp")); sys.path.insert(0, os.path.join(ROOT, "src"))
os.environ["DJANGO_SETTINGS_MODULE"] = "settings"
import django
django.setup()
import pytest
from django.test import Client
from django.test.utils import setup_test_environment
import engine


@pytest.fixture(scope="module")
def client():
    setup_test_environment()
    from django.db import connection
    connection.creation.create_test_db(verbosity=0)
    yield Client()


def post_scenario(c, sid, decl):
    sc = json.load(open(os.path.join(ROOT, "scenarios", sid + ".json")))
    d = {"declaration": decl, "ctx_supplier": "on", "ctx_endpoints": "on"}
    if sc["context"]["customer_keys_offered"]:
        d["ctx_keys"] = "on"
    for k, a in sc["answers"].items():
        d["opt_" + k] = a["option"]
        if "justification" in a:
            d["just_" + k] = a["justification"]
        if k == "PG-05":
            d["screening"] = a["screening"]
        for dim, v in a.get("evidence", {}).items():
            d["ev_%s_%s" % (dim, k)] = v
    return c.post("/", d)


def test_report_matches_engine(client):
    repo = json.load(open(os.path.join(ROOT, "repository.json")))
    for sid in ("S2", "S6"):
        sc = json.load(open(os.path.join(ROOT, "scenarios", sid + ".json")))
        r = post_scenario(client, sid, "yes")
        assert r.status_code == 302
        page = client.get(r["Location"]).content.decode()
        ref = engine.evaluate(repo, sc, "yes")
        for g in ref["groups"].values():
            for m in ("risk", "coverage", "upper_bound", "eci"):
                if g[m] is not None:
                    assert g[m]["display"] in page
        assert "human review" in page and "no claim of legal compliance" in page
        assert ref["ranking"][0]["id"] in page


def test_undetermined_shows_state_not_zero(client):
    r = post_scenario(client, "S3", "undetermined")
    page = client.get(r["Location"]).content.decode()
    assert "Undetermined: privacy readiness cannot be assessed" in page


def test_not_applicable_without_justification_is_rejected(client):
    d = {"declaration": "yes", "ctx_supplier": "on", "ctx_endpoints": "on", "opt_SC-04": "not_applicable"}
    assert client.post("/", d).status_code == 400
