"""Leave-one-out check: score main.forecast on practice cases (truth from other cases' comparables) and on every comparable."""
import json, math, glob, sys, copy
from datetime import timedelta
sys.path.insert(0, ".")
import main as M

def loss(fc, truth):
    tot = n = 0
    for r in fc["hours"]:
        y = max(1, truth[r["hour"]])
        for t, q in zip(M.LEVELS, r["q"]):
            d = math.log(y) - math.log(q); tot += 2 * max(t * d, (t - 1) * d); n += 1
    return tot / n

cases = [json.load(open(f)) for f in sorted(glob.glob(sys.argv[1] + "/p*.in"))]
allc = {c["name"]: c for k in cases for c in k["comparables"]}
# practice truth: a practice game appears as a comparable in the other practice cases
res = []
for k in cases:
    g = k["game"]["name"]; src = next((c for o in cases for c in o["comparables"] if c["name"] == g), None)
    if not src: continue
    m = M.series(src["hourly"]); ds = M.ts(k["day_start"])
    truth = {h: m.get(ds + timedelta(hours=h - 1)) for h in range(2, 25)}
    fc = M.forecast(k)
    base = {"hours": [{"hour": h, "q": [k["known"][0]["viewers"] * math.exp(z * .15 * math.sqrt(h - 1)) for z in (-1.645, -.674, 0, .674, 1.645)]} for h in range(2, 25)]}
    res.append((g, loss(fc, truth), loss(base, truth)))
for r in res: print("practice %-28s model %.4f  baseline %.4f" % r)
if res: print("practice mean model %.4f baseline %.4f" % (sum(r[1] for r in res) / len(res), sum(r[2] for r in res) / len(res)))
# LOO over comparables usable as targets
base_case = cases[0]; ls = []
for a in M.analogues({"comparables": list(allc.values())}):
    c = allc[a[0]]; m = M.series(c["hourly"]); ds = M.ts(c["day_start"])
    k = {"known": [{"viewers": m[ds]}], "day_start": c["day_start"], "history_hourly": c["hourly"], "comparables": list(allc.values())}
    truth = {h: m[ds + timedelta(hours=h - 1)] for h in range(2, 25)}
    p = m[ds]; base = {"hours": [{"hour": h, "q": [p * math.exp(z * .15 * math.sqrt(h - 1)) for z in (-1.645, -.674, 0, .674, 1.645)]} for h in range(2, 25)]}
    ls.append((a[0], a[1][len(M.FEAT_LAGS)], loss(M.forecast(k, exclude={a[0]}), truth), loss(base, truth)))
for r in ls: print("  %-28s live=%5.2f model %.3f base %.3f" % r)
live = [r for r in ls if r[1] > 0.3]
print("LOO all n=%d model %.4f base %.4f" % (len(ls), sum(r[2] for r in ls)/len(ls), sum(r[3] for r in ls)/len(ls)))
print("LOO live-at-h1 n=%d model %.4f base %.4f" % (len(live), sum(r[2] for r in live)/len(live), sum(r[3] for r in live)/len(live)))
