#!/usr/bin/env python3
import argparse
import csv
import json
import math
import sys
from pathlib import Path


KNOWN = {
    "linear": (0.0, 0.0, 1.0, 1.0),
    "ease": (0.25, 0.1, 0.25, 1.0),
    "ease-in": (0.42, 0.0, 1.0, 1.0),
    "ease-out": (0.0, 0.0, 0.58, 1.0),
    "ease-in-out": (0.42, 0.0, 0.58, 1.0),
    "stagger-out": (0.22, 1.0, 0.36, 1.0),
    "part-expand": (0.2, 0.1, 0.05, 1.0),
    "clip-reveal": (0.6, 0.0, 0.2, 1.0),
    "ui-reposition": (0.5, 0.0, 0.2, 1.0),
    "breath": (0.45, 0.05, 0.55, 0.95),
}


def load_series(path, column):
    with Path(path).open(newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit(f"empty curve {path}")
    if column not in rows[0]:
        raise SystemExit(f"column {column!r} not in {list(rows[0].keys())}")
    xs = []
    ys = []
    for i, row in enumerate(rows):
        raw = row[column]
        if raw == "" or raw is None:
            continue
        if row.get("t_ms") not in (None, ""):
            xs.append(float(row["t_ms"]))
        else:
            xs.append(float(i))
        ys.append(float(raw))
    if len(ys) < 4:
        raise SystemExit("need at least 4 samples")
    t0, t1 = xs[0], xs[-1]
    span = t1 - t0 if t1 != t0 else 1.0
    ts = [(x - t0) / span for x in xs]
    y0, y1 = ys[0], ys[-1]
    yspan = y1 - y0
    if abs(yspan) < 1e-9:
        norm = [0.0 for _ in ys]
        invert = False
    else:
        invert = yspan < 0
        norm = [(y - y0) / yspan for y in ys]
    return {
        "t_raw": xs,
        "y_raw": ys,
        "t": ts,
        "y": norm,
        "t0": t0,
        "t1": t1,
        "y0": y0,
        "y1": y1,
        "invert": invert,
    }


def bez_xy(x1, y1, x2, y2, u):
    omu = 1.0 - u
    x = 3 * omu * omu * u * x1 + 3 * omu * u * u * x2 + u * u * u
    y = 3 * omu * omu * u * y1 + 3 * omu * u * u * y2 + u * u * u
    return x, y


def bezier_at(x1, y1, x2, y2, t):
    lo, hi = 0.0, 1.0
    y = 0.0
    for _ in range(24):
        mid = (lo + hi) * 0.5
        x, y = bez_xy(x1, y1, x2, y2, mid)
        if x < t:
            lo = mid
        else:
            hi = mid
    return y


def rmse_bezier(params, series):
    x1, y1, x2, y2 = params
    if not (0.0 <= x1 <= 1.0 and 0.0 <= x2 <= 1.0):
        return 1e9
    err = 0.0
    n = 0
    for t, y in zip(series["t"], series["y"]):
        pred = bezier_at(x1, y1, x2, y2, t)
        d = pred - y
        err += d * d
        n += 1
    return math.sqrt(err / n)


def fit_bezier(series):
    best = None
    for name, params in KNOWN.items():
        err = rmse_bezier(params, series)
        rec = {"kind": "cubic-bezier", "name": name, "params": list(params), "rmse": err}
        if best is None or err < best["rmse"]:
            best = rec
    grid = [i / 8.0 for i in range(9)]
    ygrid = [-0.2, 0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.5]
    for x1 in grid:
        for x2 in grid:
            for y1 in ygrid:
                for y2 in ygrid:
                    params = (x1, y1, x2, y2)
                    err = rmse_bezier(params, series)
                    if best is None or err < best["rmse"]:
                        best = {
                            "kind": "cubic-bezier",
                            "name": "fit",
                            "params": [round(x1, 3), round(y1, 3), round(x2, 3), round(y2, 3)],
                            "rmse": err,
                        }
    cx1, cy1, cx2, cy2 = best["params"]
    step = 0.05
    improved = True
    while improved:
        improved = False
        for dx1 in (-step, 0, step):
            for dy1 in (-step, 0, step):
                for dx2 in (-step, 0, step):
                    for dy2 in (-step, 0, step):
                        params = (
                            min(1.0, max(0.0, cx1 + dx1)),
                            cy1 + dy1,
                            min(1.0, max(0.0, cx2 + dx2)),
                            cy2 + dy2,
                        )
                        err = rmse_bezier(params, series)
                        if err + 1e-7 < best["rmse"]:
                            best = {
                                "kind": "cubic-bezier",
                                "name": "fit",
                                "params": [round(v, 3) for v in params],
                                "rmse": err,
                            }
                            cx1, cy1, cx2, cy2 = params
                            improved = True
        step *= 0.5
        if step < 0.01:
            break
    best["css"] = "cubic-bezier({:.2f}, {:.2f}, {:.2f}, {:.2f})".format(*best["params"])
    best["rmse"] = round(best["rmse"], 5)
    known_best = min(
        ({"kind": "cubic-bezier", "name": n, "params": list(p), "rmse": rmse_bezier(p, series), "css": "cubic-bezier({:.2f}, {:.2f}, {:.2f}, {:.2f})".format(*p)} for n, p in KNOWN.items()),
        key=lambda r: r["rmse"],
    )
    known_best["rmse"] = round(known_best["rmse"], 5)
    return best, known_best


def simulate_spring(k, c, mass, y0, v0, ts, target=0.0):
    if not ts:
        return []
    t_end = ts[-1]
    dt = min(0.001, max(1e-4, t_end / 2000.0))
    y, v = float(y0), float(v0)
    t = 0.0
    out = []
    ti = 0
    while ti < len(ts):
        while t + 1e-12 < ts[ti]:
            a = (-k * (y - target) - c * v) / mass
            v += a * dt
            y += v * dt
            t += dt
        out.append(y)
        ti += 1
    return out


def overshoot_and_crossings(ys):
    if not ys:
        return 0.0, 0
    end = ys[-1]
    start = ys[0]
    direction = 1.0 if end >= start else -1.0
    overshoot = 0.0
    crossings = 0
    prev = start - end
    for y in ys:
        rel = y - end
        if rel * direction > overshoot:
            overshoot = rel * direction
        if prev == 0:
            prev = rel
            continue
        if rel == 0 or (prev < 0 < rel) or (prev > 0 > rel):
            crossings += 1
        prev = rel
    span = abs(end - start) or 1.0
    return overshoot / span, crossings


def fit_spring(series):
    t_s = [(x - series["t0"]) / 1000.0 if series["t1"] > 20 else (x - series["t0"]) for x in series["t_raw"]]
    if t_s[-1] <= 0:
        t_s = series["t"][:]
    ys = series["y"]
    y0 = ys[0]
    target = ys[-1]
    best = None
    for k in range(80, 801, 20):
        for c in range(8, 41, 2):
            pred = simulate_spring(float(k), float(c), 1.0, y0, 0.0, t_s, target=target)
            if len(pred) != len(ys):
                continue
            err = math.sqrt(sum((a - b) ** 2 for a, b in zip(pred, ys)) / len(ys))
            rec = {
                "kind": "spring",
                "stiffness": k,
                "damping": c,
                "mass": 1.0,
                "y0": y0,
                "target": target,
                "v0": 0.0,
                "rmse": err,
            }
            if best is None or err < best["rmse"]:
                best = rec
    if best is None:
        return {"kind": "spring", "rmse": None}
    k, c = best["stiffness"], best["damping"]
    for dk in (-10, 0, 10):
        for dc in (-1, 0, 1):
            kk, cc = k + dk, c + dc
            if kk < 20 or cc < 1:
                continue
            pred = simulate_spring(float(kk), float(cc), 1.0, y0, 0.0, t_s, target=target)
            err = math.sqrt(sum((a - b) ** 2 for a, b in zip(pred, ys)) / len(ys))
            if err < best["rmse"]:
                best = {
                    "kind": "spring",
                    "stiffness": kk,
                    "damping": cc,
                    "mass": 1.0,
                    "y0": y0,
                    "target": target,
                    "v0": 0.0,
                    "rmse": err,
                }
    best["rmse"] = round(best["rmse"], 5)
    return best


def recommend(series, bezier, known, spring):
    overshoot, crossings = overshoot_and_crossings(series["y_raw"])
    use_spring = overshoot > 0.08 or crossings >= 2
    if use_spring and spring.get("rmse") is not None:
        choice = "spring"
        reason = f"overshoot={overshoot:.3f}, zero-crossings={crossings}; prefer a spring over a bezier bounce"
    else:
        if known["rmse"] <= bezier["rmse"] * 1.08:
            choice = "cubic-bezier"
            reason = f"no material bounce (overshoot={overshoot:.3f}); closest named curve is {known['name']}"
        else:
            choice = "cubic-bezier"
            reason = f"no material bounce (overshoot={overshoot:.3f}); use the fitted curve"
    return {
        "choice": choice,
        "reason": reason,
        "overshoot": round(overshoot, 4),
        "zero_crossings_after_start": crossings,
        "bezier": bezier,
        "closest_named_bezier": known,
        "spring": spring,
    }


def draw_plot(series, report, path, bezier, spring):
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return
    W, H, pad = 720, 280, 36
    im = Image.new("RGB", (W, H), (248, 250, 252))
    d = ImageDraw.Draw(im)
    d.rectangle([pad, pad, W - pad, H - pad], outline=(203, 213, 225), fill=(255, 255, 255))
    iw, ih = W - 2 * pad, H - 2 * pad

    def pt(t, y):
        return (pad + t * iw, pad + (1.0 - y) * ih)

    def polyline(ts, ys, color, width=2):
        pts = [pt(t, y) for t, y in zip(ts, ys)]
        if len(pts) >= 2:
            d.line(pts, fill=color, width=width)

    polyline(series["t"], series["y"], (15, 23, 42), 2)
    bx1, by1, bx2, by2 = bezier["params"]
    bt = [i / 80.0 for i in range(81)]
    by = [bezier_at(bx1, by1, bx2, by2, t) for t in bt]
    polyline(bt, by, (37, 99, 235), 2)
    if spring.get("rmse") is not None:
        t_s = [(x - series["t0"]) / 1000.0 if series["t1"] > 20 else (x - series["t0"]) for x in series["t_raw"]]
        pred = simulate_spring(
            float(spring["stiffness"]),
            float(spring["damping"]),
            float(spring["mass"]),
            spring["y0"],
            spring.get("v0") or 0.0,
            t_s,
            target=spring["target"],
        )
        polyline(series["t"][: len(pred)], pred, (249, 115, 22), 2)
    d.line([pt(0, 0), pt(1, 0)], fill=(226, 232, 240), width=1)
    d.line([pt(0, 1), pt(1, 1)], fill=(226, 232, 240), width=1)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    im.save(path)


def main(argv=None):
    p = argparse.ArgumentParser(prog="fit_curves.py")
    p.add_argument("--curve", required=True)
    p.add_argument("--column", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--plot")
    args = p.parse_args(argv)

    series = load_series(args.curve, args.column)
    bezier, known = fit_bezier(series)
    spring = fit_spring(series)
    report = recommend(series, bezier, known, spring)
    report["column"] = args.column
    report["samples"] = len(series["y"])
    report["t_range"] = [series["t0"], series["t1"]]
    report["y_range"] = [series["y0"], series["y1"]]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    if args.plot:
        draw_plot(series, report, args.plot, bezier, spring)
        report["plot"] = args.plot
        out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
