import hashlib, json, glob, sys, datetime
files = ["repository.json"] + sorted(glob.glob("scenarios/*.json"))
m = {f: hashlib.sha256(open(f, "rb").read()).hexdigest() for f in files}
json.dump({"frozen_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "sha256": m},
          open("FREEZE_MANIFEST.json", "w"), indent=1, sort_keys=True)
print(json.dumps(m, indent=1))
