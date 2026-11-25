#!/usr/bin/env python3
import argparse
import re
import sys
from pathlib import Path


def solve_spring(stiffness, damping, mass, y0, v0, dur_s, dt=0.001):
    steps = int(round(dur_s / dt))
    y, v = float(y0), float(v0)
    pts = []
    for i in range(steps + 1):
        pts.append((i * dt, y, v))
        a = (-stiffness * y - damping * v) / mass
        v += a * dt
        y += v * dt
    return pts


def bake_jump_keyframes(
    dur_s,
    ant_pct=7.0,
    peak_y=-16.0,
    squash_land=(1.14, 0.85),
    stiffness=380.0,
    damping=18.0,
    mass=1.0,
    v0=-520.0,
    samples=24,
):
    pts = solve_spring(
        stiffness,
        damping,
        mass,
        y0=0.0,
        v0=v0,
        dur_s=dur_s * (0.92 - ant_pct / 100.0),
    )
    min_y = min(p[1] for p in pts)
    scale_y_factor = peak_y / min_y if min_y < -1e-6 else 1.0
    stops = [(0.0, 0.0, 1.0, 1.0), (ant_pct, 4.5, 1.09, 0.89)]
    for i in range(1, samples + 1):
        u = i / samples
        idx = min(len(pts) - 1, int(round(u * (len(pts) - 1))))
        _, y_raw, _ = pts[idx]
        y = y_raw * scale_y_factor
        pct = ant_pct + u * (92.0 - ant_pct)
        sx, sy = 1.0, 1.0
        if y > 0.3:
            comp = min(1.0, y / 5.5)
            sx = 1.0 + (squash_land[0] - 1.0) * comp
            sy = 1.0 - (1.0 - squash_land[1]) * comp
            y = y * 0.38
        elif y < -2.0:
            stretch = min(1.0, abs(y) / abs(peak_y))
            sx = 1.0 - 0.08 * stretch
            sy = 1.0 + 0.09 * stretch
        stops.append((pct, y, sx, sy))
    stops.append((100.0, 0.0, 1.0, 1.0))
    return stops


def fmt_stops(stops, indent="  "):
    lines = []
    for pct, y, sx, sy in stops:
        lines.append(
            f"{indent}{pct:.1f}% {{ transform: translate(0px, {y:.2f}px) scale({sx:.3f}, {sy:.3f}); }}"
        )
    return "\n".join(lines)


def keyframes(name, stops, indent=""):
    return f"{indent}@keyframes {name} {{\n{fmt_stops(stops, indent + '  ')}\n{indent}}}"


def scope_svg(prefix, raw, extra_ids=()):
    kf_names = set(re.findall(r"@keyframes\s+([A-Za-z0-9_-]+)", raw))
    for k in sorted(kf_names, key=len, reverse=True):
        raw = re.sub(rf"\b{re.escape(k)}\b", f"{prefix}-{k}", raw)
    cls_names = set()
    for m in re.findall(r'class="([^"]+)"', raw):
        cls_names.update(m.split())
    for c in sorted(cls_names, key=len, reverse=True):
        raw = re.sub(
            rf"(?<![A-Za-z0-9_-])\.{re.escape(c)}(?![A-Za-z0-9_-])",
            f".{prefix}-{c}",
            raw,
        )
    raw = re.sub(
        r'class="([^"]+)"',
        lambda m: 'class="' + " ".join(f"{prefix}-{c}" for c in m.group(1).split()) + '"',
        raw,
    )
    ids = set(re.findall(r'\bid="([^"]+)"', raw))
    ids.update(extra_ids)
    for id_name in sorted(ids, key=len, reverse=True):
        raw = raw.replace(f'id="{id_name}"', f'id="{prefix}-{id_name}"')
        raw = raw.replace(f"url(#{id_name})", f"url(#{prefix}-{id_name})")
    return raw


def cmd_bake(args):
    squash = tuple(float(x) for x in args.squash.split(","))
    if len(squash) != 2:
        raise SystemExit("--squash must be SX,SY")
    stops = bake_jump_keyframes(
        dur_s=args.duration,
        ant_pct=args.ant_pct,
        peak_y=args.peak_y,
        squash_land=squash,
        stiffness=args.stiffness,
        damping=args.damping,
        mass=args.mass,
        v0=args.v0,
        samples=args.samples,
    )
    text = keyframes(args.name, stops)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n")
    return 0


def cmd_scope(args):
    raw = Path(args.input).read_text() if args.input else sys.stdin.read()
    text = scope_svg(args.prefix, raw)
    if args.output:
        Path(args.output).write_text(text)
    else:
        sys.stdout.write(text)
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="springs.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("bake", help="print a baked spring jump as CSS @keyframes")
    b.add_argument("--name", default="hop")
    b.add_argument("--duration", type=float, required=True, help="seconds")
    b.add_argument("--stiffness", type=float, default=380.0)
    b.add_argument("--damping", type=float, default=18.0)
    b.add_argument("--mass", type=float, default=1.0)
    b.add_argument("--v0", type=float, default=-520.0)
    b.add_argument("--peak-y", type=float, default=-16.0)
    b.add_argument("--ant-pct", type=float, default=7.0)
    b.add_argument("--squash", default="1.14,0.85")
    b.add_argument("--samples", type=int, default=24)
    b.add_argument("--out")
    b.set_defaults(func=cmd_bake)
    s = sub.add_parser("scope", help="prefix classes, keyframes, and ids in an SVG")
    s.add_argument("--prefix", required=True)
    s.add_argument("--input")
    s.add_argument("--output")
    s.set_defaults(func=cmd_scope)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
