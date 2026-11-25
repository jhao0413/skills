#!/usr/bin/env python3
import argparse
import csv
import json
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError as exc:
    raise SystemExit("Pillow is required") from exc


def list_frames(frames_dir):
    frames = sorted(Path(frames_dir).glob("*.png"))
    if not frames:
        frames = sorted(Path(frames_dir).glob("*.jpg"))
    return frames


def parse_roi(text, width, height):
    if not text:
        return (0, 0, width, height)
    parts = [p.strip() for p in text.split(",")]
    if len(parts) != 4:
        raise SystemExit("ROI must be x,y,w,h (pixels or percentages ending in %)")
    vals = []
    dims = [width, height, width, height]
    for raw, dim in zip(parts, dims):
        if raw.endswith("%"):
            vals.append(int(round(float(raw[:-1]) / 100.0 * dim)))
        else:
            vals.append(int(raw))
    return tuple(vals)


def parse_hex(color):
    c = color.strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) != 6:
        raise SystemExit(f"bad color {color!r}")
    return tuple(int(c[i : i + 2], 16) for i in (0, 2, 4))


def luma(r, g, b):
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def mask_luma(pixels, w, h, min_luma, max_luma):
    bits = []
    for r, g, b in pixels:
        y = luma(r, g, b)
        bits.append(min_luma <= y <= max_luma)
    return bits


def mask_chroma(pixels, target, tolerance):
    tr, tg, tb = target
    bits = []
    for r, g, b in pixels:
        dist = abs(r - tr) + abs(g - tg) + abs(b - tb)
        bits.append(dist <= tolerance)
    return bits


def bbox_and_centroid(bits, w, h, min_area):
    xs = []
    ys = []
    for i, on in enumerate(bits):
        if on:
            xs.append(i % w)
            ys.append(i // w)
    area = len(xs)
    if area < min_area:
        return None
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    cx = sum(xs) / area
    cy = sum(ys) / area
    return {
        "cx": cx,
        "cy": cy,
        "x": minx,
        "y": miny,
        "w": maxx - minx + 1,
        "h": maxy - miny + 1,
        "area": area,
    }


def main(argv=None):
    p = argparse.ArgumentParser(prog="track_motion.py")
    p.add_argument("--frames-dir", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--mode", choices=("luma", "chroma"), default="luma")
    p.add_argument("--min-luma", type=float, default=0.0)
    p.add_argument("--max-luma", type=float, default=40.0)
    p.add_argument("--color", default="#000000")
    p.add_argument("--tolerance", type=int, default=40)
    p.add_argument("--roi")
    p.add_argument("--min-area", type=int, default=8)
    p.add_argument("--fps", type=float, default=0.0)
    p.add_argument("--every", type=int, default=1)
    args = p.parse_args(argv)

    frames = list_frames(args.frames_dir)
    if not frames:
        raise SystemExit(f"no frames in {args.frames_dir}")
    with Image.open(frames[0]) as probe:
        width, height = probe.size
    roi = parse_roi(args.roi, width, height)
    rx, ry, rw, rh = roi
    target = parse_hex(args.color) if args.mode == "chroma" else None

    rows = []
    for i, path in enumerate(frames):
        with Image.open(path) as im:
            crop = im.convert("RGB").crop((rx, ry, rx + rw, ry + rh))
            cw, ch = crop.size
            pixels = list(crop.getdata())
        if args.mode == "luma":
            bits = mask_luma(pixels, cw, ch, args.min_luma, args.max_luma)
        else:
            bits = mask_chroma(pixels, target, args.tolerance)
        hit = bbox_and_centroid(bits, cw, ch, args.min_area)
        t_ms = ""
        if args.fps:
            t_ms = int(round(i * args.every / args.fps * 1000.0))
        rec = {
            "index": i,
            "file": path.name,
            "t_ms": t_ms,
            "cx": "",
            "cy": "",
            "w": "",
            "h": "",
            "area": "",
            "cx_n": "",
            "cy_n": "",
            "w_n": "",
            "h_n": "",
        }
        if hit:
            rec.update(
                {
                    "cx": round(hit["cx"] + rx, 3),
                    "cy": round(hit["cy"] + ry, 3),
                    "w": hit["w"],
                    "h": hit["h"],
                    "area": hit["area"],
                    "cx_n": round(hit["cx"] / cw, 6),
                    "cy_n": round(hit["cy"] / ch, 6),
                    "w_n": round(hit["w"] / cw, 6),
                    "h_n": round(hit["h"] / ch, 6),
                }
            )
        rows.append(rec)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["index", "file", "t_ms", "cx", "cy", "w", "h", "area", "cx_n", "cy_n", "w_n", "h_n"]
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    found = [r for r in rows if r["cx"] != ""]
    summary = {
        "frames": len(rows),
        "hits": len(found),
        "roi": {"x": rx, "y": ry, "w": rw, "h": rh},
        "frame_size": [width, height],
        "out": str(out),
    }
    if found:
        summary["cx_n_range"] = [min(r["cx_n"] for r in found), max(r["cx_n"] for r in found)]
        summary["cy_n_range"] = [min(r["cy_n"] for r in found), max(r["cy_n"] for r in found)]
    (out.with_suffix(".json")).write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
