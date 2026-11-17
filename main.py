"""GTA VI launch-day Twitch CCU forecast: analogue-weighted empirical quantiles of log(hour h / hour 1)."""
import glob, json, math, os
from datetime import datetime, timedelta

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
FEAT_LAGS = (1, 2, 4, 8)   # hours before hour 1 used to describe the pre-launch ramp
BW = 2.0                   # kernel bandwidth on feature distance (LOO plateau 1.5-3)
JITTER = 0.25              # log-spread added around each analogue path (scaled by sqrt(h-1))
SIZE_SCALE = 0.5          # log-viewers per unit of feature distance
NGRID = 7                  # normal nodes per analogue


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def series(hourly):
    return {ts(r["from"]): r["viewers"] for r in hourly if r.get("viewers") is not None}


def feats(m, day_start):
    v1 = m.get(day_start)
    if not v1 or v1 <= 0:
        return None
    f = []
    for k in FEAT_LAGS:
        v = m.get(day_start - timedelta(hours=k))
        if v is None or v <= 0:
            return None
        f.append(math.log(v / v1))
    # hour-1 size against the prior week's typical level: launch already on vs. not yet
    week = [m[t] for t in m if day_start - timedelta(days=7) <= t < day_start - timedelta(hours=12) and m[t] > 0]
    f.append(math.log(v1 / (sorted(week)[len(week) // 2] if week else v1)) / 3)
    # absolute size of hour 1: small categories can still explode, big ones mostly decay and rebound
    f.append(math.log(v1) / SIZE_SCALE)
    return f


def analogues(case):
    out = []
    for c in case["comparables"]:
        if "Tier: target-history" in c.get("unlock", "") or "Tier: weak" in c.get("unlock", ""):
            continue
        ds = ts(c["day_start"])
        m = series(c["hourly"])
        f = feats(m, ds)
        if f is None:
            continue
        path = [m.get(ds + timedelta(hours=h - 1)) for h in range(2, 25)]
        if any(p is None or p <= 0 for p in path):
            continue
        out.append((c["name"], f, [math.log(p / m[ds]) for p in path]))
    return out


def wquant(pairs, q):
    pairs = sorted(pairs)
    tot = sum(w for _, w in pairs)
    acc = 0.0
    for x, w in pairs:
        acc += w
        if acc >= q * tot:
            return x
    return pairs[-1][0]


def forecast(case, exclude=()):
    p1 = max(1.0, float(case["known"][0]["viewers"]))
    ds = ts(case["day_start"])
    m = series(case["history_hourly"])
    m[ds] = p1
    f0 = feats(m, ds)
    an = [a for a in analogues(case) if a[0] not in exclude]
    if f0 is None:
        f0 = [0.0] * (len(FEAT_LAGS) + 1) + [math.log(p1) / SIZE_SCALE]
    w = [math.exp(-sum((x - y) ** 2 for x, y in zip(f0, a[1])) / (2 * BW * BW)) + 1e-9 for a in an]
    zs = [(-1.5, 0.067), (-1.0, 0.121), (-0.5, 0.176), (0.0, 0.199), (0.5, 0.176), (1.0, 0.121), (1.5, 0.067)][:NGRID]
    rows = []
    for i, h in enumerate(range(2, 25)):
        sd = JITTER * math.sqrt(h - 1) / 2
        pairs = [(a[2][i] + z * sd, wi * zw) for a, wi in zip(an, w) for z, zw in zs]
        qs, prev = [], 0.0
        for t in LEVELS:
            v = min(1e9, max(0.01, p1 * math.exp(wquant(pairs, t))))
            v = max(v, prev)
            qs.append(round(v, 2))
            prev = v
        rows.append({"hour": h, "q": qs})
    return {"hours": rows}


def main():
    ind = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
    outd = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    for path in sorted(glob.glob(os.path.join(ind, "*.in"))):
        case = json.load(open(path, encoding="utf-8"))
        with open(os.path.join(outd, case["id"] + ".out"), "w", encoding="utf-8") as fh:
            json.dump(forecast(case), fh, separators=(",", ":"))


if __name__ == "__main__":
    main()
