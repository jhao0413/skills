#!/usr/bin/env python3
import argparse
import csv
import re
import subprocess
import sys
from pathlib import Path


def parse_scene_scores(text):
    rows = []
    frame = None
    pts_time = None
    for line in text.splitlines():
        m = re.search(r"frame:(\d+)", line)
        if m:
            frame = int(m.group(1))
            pts_time = None
            continue
        m = re.search(r"pts_time:([0-9.]+)", line)
        if m:
            pts_time = float(m.group(1))
            continue
        m = re.search(r"lavfi\.scene_score=([0-9.eE+-]+)", line)
        if m and frame is not None:
            rows.append({"frame": frame, "t_s": pts_time, "score": float(m.group(1))})
            frame = None
            pts_time = None
    return rows


def cmd_scenes(args):
    out_dir = Path(args.out_dir)
    scenes = out_dir / "scenes"
    diffs = out_dir / "diffs"
    scenes.mkdir(parents=True, exist_ok=True)
    diffs.mkdir(parents=True, exist_ok=True)
    score_file = scenes / "scores.raw.txt"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(args.input),
            "-vf",
            f"select='gte(scene,0)',metadata=print:file={score_file}",
            "-f",
            "null",
            "-",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    rows = parse_scene_scores(score_file.read_text(errors="replace"))
    csv_path = scenes / "scores.csv"
    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["frame", "t_s", "t_ms", "score"])
        w.writeheader()
        for r in rows:
            t_s = r["t_s"] if r["t_s"] is not None else ""
            t_ms = "" if t_s == "" else int(round(float(t_s) * 1000.0))
            w.writerow({"frame": r["frame"], "t_s": t_s, "t_ms": t_ms, "score": f"{r['score']:.6f}"})
    cuts = [r for r in rows if r["score"] >= args.threshold]
    if cuts:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(args.input),
                "-vf",
                f"select='gt(scene,{args.threshold})',scale={args.width}:-1",
                "-vsync",
                "vfr",
                str(scenes / "cut_%04d.png"),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    print(f"scene scores: {len(rows)} frames, {len(cuts)} cuts >= {args.threshold} -> {csv_path}")

    frames_dir = Path(args.frames_dir) if args.frames_dir else None
    if frames_dir and frames_dir.exists():
        write_energy(frames_dir, diffs / "energy.csv")
    return 0


def write_energy(frames_dir, out_csv):
    try:
        from PIL import Image
    except ImportError as exc:
        raise SystemExit("Pillow is required for frame-difference energy") from exc

    frames = sorted(Path(frames_dir).glob("*.png")) or sorted(Path(frames_dir).glob("*.jpg"))
    if len(frames) < 2:
        raise SystemExit(f"need at least 2 frames in {frames_dir}")
    prev = None
    rows = []
    peak = (0, 0.0)
    for i, path in enumerate(frames):
        im = Image.open(path).convert("RGB")
        px = list(im.getdata())
        if prev is None:
            mae = 0.0
        else:
            total = 0
            for (r1, g1, b1), (r0, g0, b0) in zip(px, prev):
                total += abs(r1 - r0) + abs(g1 - g0) + abs(b1 - b0)
            mae = total / (len(px) * 3.0)
        rows.append((i, path.name, mae))
        if mae > peak[1]:
            peak = (i, mae)
        prev = px
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["index", "file", "mae"])
        w.writerows(rows)
    print(f"frame-diff energy: {len(rows)} frames, peak mae={peak[1]:.3f} at index {peak[0]} -> {out_csv}")


def build_parser():
    p = argparse.ArgumentParser(prog="detect_scenes.py")
    p.add_argument("--input", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--threshold", type=float, default=0.3)
    p.add_argument("--width", type=int, default=512)
    p.add_argument("--frames-dir", help="optional extracted frames for MAE energy")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return cmd_scenes(args)


if __name__ == "__main__":
    sys.exit(main())
