import json, os, sys
from django.conf import settings
from django.http import HttpResponseBadRequest
from django.shortcuts import render, redirect, get_object_or_404
sys.path.insert(0, os.path.join(settings.ROOT, "src"))
import engine
from .models import Assessment

REPO = json.load(open(os.path.join(settings.ROOT, "repository.json")))
QUESTIONS = json.load(open(os.path.join(settings.ROOT, "data", "questions.json")))
OPTIONS = [("fully_implemented", "Fully implemented"), ("mostly_implemented", "Mostly implemented, with minor gaps"),
           ("partially_implemented", "Partially implemented"), ("implemented_minimally", "Implemented only to a minimal extent"),
           ("not_implemented", "Not implemented"), ("unknown", "Unknown or not answered"),
           ("not_applicable", "Not applicable, with written justification")]
DIMS = ["verification", "completeness", "relevance", "recency"]


def form(request):
    items = [dict(i, **QUESTIONS[i["id"]]) for i in REPO["indicators"]]
    if request.method == "GET":
        return render(request, "assess/form.html", {"items": items, "options": OPTIONS, "dims": DIMS, "ratings": range(4)})
    p = request.POST
    answers = {}
    for i in REPO["indicators"]:
        k = i["id"]
        a = {"option": p.get("opt_" + k, "unknown")}
        if p.get("just_" + k, "").strip():
            a["justification"] = p["just_" + k].strip()
        if k == "PG-05":
            a["screening"] = p.get("screening", "unknown")
        if a["option"] in engine.GAP_OPTIONS:
            a["evidence"] = {d: int(p.get("ev_%s_%s" % (d, k), 0)) for d in DIMS}
        answers[k] = a
    scenario = {"scenario_id": "web", "version": "1", "answers": answers,
                "context": {"supplier_used": "ctx_supplier" in p, "endpoints_used": "ctx_endpoints" in p, "customer_keys_offered": "ctx_keys" in p}}
    declaration = p.get("declaration", "undetermined")
    try:
        result = engine.evaluate(REPO, scenario, declaration)
    except (engine.InputError, ValueError) as e:
        return HttpResponseBadRequest("Input error: %s" % e)
    obj = Assessment.objects.create(declaration=declaration, scenario_json=json.dumps(scenario), result_json=engine.serialize(result))
    return redirect("report", pk=obj.pk)


def report(request, pk):
    obj = get_object_or_404(Assessment, pk=pk)
    r = json.loads(obj.result_json)
    order = ["security", "SG", "SI", "SC", "SO", "SR", "personal_data", "PG", "PD"]
    groups = [r["groups"][g] for g in order]
    labels = {"undetermined": "Undetermined: privacy readiness cannot be assessed until the declaration is made",
              "not_applicable": "Not applicable", "not_assessed": "Not assessed", "computed": "Computed"}
    for g in groups:
        g["label"] = labels[g["state"]]
    return render(request, "assess/report.html", {"r": r, "groups": groups, "indicators": r["indicators"], "ranking": r["ranking"]})
