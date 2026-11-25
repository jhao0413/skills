#!/usr/bin/env python3
import argparse
import json
import re
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError as exc:
    raise SystemExit("Pillow is required") from exc


GRID_2X3 = ["TL", "TR", "ML", "MR", "BL", "BR"]


def list_frames(frames_dir):
    frames = sorted(Path(frames_dir).glob("*.png"))
    if not frames:
        frames = sorted(Path(frames_dir).glob("*.jpg"))
    return frames


def parse_pair(text, default=(0, 0)):
    if not text:
        return default
    parts = [int(p) for p in re.split(r"[x,]", text) if p != ""]
    if len(parts) != 2:
        raise SystemExit(f"expected two integers, got {text!r}")
    return parts[0], parts[1]


def parse_quad(text):
    if not text:
        return (0, 0, 0, 0)
    parts = [int(p) for p in text.split(",") if p != ""]
    if len(parts) != 4:
        raise SystemExit(f"expected L,T,R,B, got {text!r}")
    return tuple(parts)


def parse_cells(text):
    cells = []
    for chunk in text.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "=" not in chunk:
            raise SystemExit(f"cell must look like NAME=x,y,w,h: {chunk!r}")
        name, rect = chunk.split("=", 1)
        parts = [int(p) for p in rect.split(",")]
        if len(parts) != 4:
            raise SystemExit(f"cell rect must be x,y,w,h: {chunk!r}")
        x, y, w, h = parts
        cells.append((name.strip(), x, y, w, h))
    if not cells:
        raise SystemExit("no cells parsed")
    return cells


def cells_from_grid(width, height, grid, inset, gap):
    cols, rows = parse_pair(grid, (0, 0))
    if cols < 1 or rows < 1:
        raise SystemExit(f"invalid --grid {grid!r}")
    L, T, R, B = inset
    gx, gy = gap
    inner_w = width - L - R
    inner_h = height - T - B
    cell_w = (inner_w - gx * (cols - 1)) // cols
    cell_h = (inner_h - gy * (rows - 1)) // rows
    names = GRID_2X3 if (cols, rows) == (2, 3) else [f"r{r}c{c}" for r in range(rows) for c in range(cols)]
    cells = []
    i = 0
    for r in range(rows):
        for c in range(cols):
            x = L + c * (cell_w + gx)
            y = T + r * (cell_h + gy)
            cells.append((names[i], x, y, cell_w, cell_h))
            i += 1
    return cells


def main(argv=None):
    p = argparse.ArgumentParser(prog="split_grid.py")
    p.add_argument("--frames-dir", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--grid", help="COLSxROWS, e.g. 2x3")
    p.add_argument("--inset", default="0,0,0,0", help="L,T,R,B crop of the frame before dividing")
    p.add_argument("--gap", default="0,0", help="GX,GY gap between cells")
    p.add_argument("--cells", help="NAME=x,y,w,h;NAME=x,y,w,h in frame pixels")
    args = p.parse_args(argv)

    frames = list_frames(args.frames_dir)
    if not frames:
        raise SystemExit(f"no frames in {args.frames_dir}")
    with Image.open(frames[0]) as probe:
        width, height = probe.size

    if args.cells:
        cells = parse_cells(args.cells)
    elif args.grid:
        cells = cells_from_grid(width, height, args.grid, parse_quad(args.inset), parse_pair(args.gap))
    else:
        raise SystemExit("pass --grid COLSxROWS or --cells NAME=x,y,w,h;...")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "cells.json").write_text(
        json.dumps(
            {"frame_size": [width, height], "cells": [{"name": n, "x": x, "y": y, "w": w, "h": h} for n, x, y, w, h in cells]},
            indent=2,
        )
        + "\n"
    )

    for name, x, y, w, h in cells:
        dest = out_dir / name
        dest.mkdir(parents=True, exist_ok=True)
        for src in frames:
            with Image.open(src) as im:
                crop = im.crop((x, y, x + w, y + h))
                crop.save(dest / src.name)
        print(f"{name}: {w}x{h} at ({x},{y}) -> {dest} ({len(frames)} frames)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
