#!/usr/bin/env python3
import argparse
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path


def ffprobe_info(path):
    raw = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
    )
    data = json.loads(raw)
    stream = next(s for s in data["streams"] if s.get("codec_type") == "video")
    num, den = (stream.get("r_frame_rate") or "0/1").split("/")
    fps = float(num) / float(den) if float(den) else 0.0
    duration = float(data["format"].get("duration") or stream.get("duration") or 0.0)
    nb = stream.get("nb_frames")
    if nb and nb != "N/A":
        nframes = int(nb)
    else:
        nframes = int(round(duration * fps)) if fps else 0
    return {
        "path": str(Path(path).resolve()),
        "width": int(stream["width"]),
        "height": int(stream["height"]),
        "fps": fps,
        "r_frame_rate": stream.get("r_frame_rate"),
        "avg_frame_rate": stream.get("avg_frame_rate"),
        "duration": duration,
        "nb_frames": nframes,
        "codec_name": stream.get("codec_name"),
        "pix_fmt": stream.get("pix_fmt"),
        "size": int(float(data["format"].get("size") or 0)),
        "bit_rate": data["format"].get("bit_rate"),
    }


def find_font():
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return None


def escape_filter_path(p):
    return str(p).replace("\\", "\\\\").replace(":", "\\:").replace("'", r"\'")


def list_frames(frames_dir):
    frames = sorted(Path(frames_dir).glob("*.png"))
    if not frames:
        frames = sorted(Path(frames_dir).glob("*.jpg"))
    return frames


def cmd_probe(args):
    info = ffprobe_info(args.input)
    text = json.dumps(info, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n")
    return 0


def cmd_extract(args):
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    vf = []
    if args.every and args.every > 1:
        vf.append(f"select='not(mod(n,{int(args.every)}))'")
    if args.width:
        vf.append(f"scale={int(args.width)}:-1")
    cmd = ["ffmpeg", "-y", "-i", str(args.input)]
    if vf:
        cmd += ["-vf", ",".join(vf)]
        if args.every and args.every > 1:
            cmd += ["-vsync", "vfr"]
    cmd.append(str(out_dir / "frame_%04d.png"))
    subprocess.run(cmd, check=True)
    frames = list_frames(out_dir)
    print(f"extracted {len(frames)} frames -> {out_dir}")
    return 0


def choose_grid(n, cols, rows):
    if cols and rows:
        if cols * rows < n:
            raise SystemExit(f"tile grid {cols}x{rows} holds {cols * rows} cells but there are {n} frames")
        return cols, rows
    if cols:
        return cols, math.ceil(n / cols)
    if rows:
        return math.ceil(n / rows), rows
    cols = max(1, math.ceil(math.sqrt(n * 1.7)))
    rows = max(1, math.ceil(n / cols))
    return cols, rows


def cmd_tile(args):
    frames = list_frames(args.frames_dir)
    if not frames:
        raise SystemExit(f"no frames in {args.frames_dir}")
    n = len(frames)
    step = 1
    picked = frames
    if args.max_tiles and n > args.max_tiles:
        step = math.ceil(n / args.max_tiles)
        picked = frames[::step]
        if picked[-1] is not frames[-1]:
            picked.append(frames[-1])
    cols, rows = choose_grid(len(picked), args.cols, args.rows)
    work = Path(args.output).resolve().parent / ".contact_sheet_tmp"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True, exist_ok=True)
    try:
        font = find_font()
        fps = float(args.fps) if args.fps else 30.0
        every = int(args.every) if args.every else step
        for i, src in enumerate(picked):
            idx = frames.index(src)
            frame_i = idx * (int(args.source_every) if args.source_every else 1)
            t_ms = int(round(frame_i / fps * 1000.0))
            dest = work / f"t_{i:04d}.png"
            scale = f"scale={int(args.tile_width)}:-1"
            if font:
                label = f"{frame_i}  {t_ms}ms"
                draw = (
                    f"drawtext=fontfile={escape_filter_path(font)}:"
                    f"text='{label}':fontsize={int(args.fontsize)}:"
                    "fontcolor=white:box=1:boxcolor=black@0.65:boxborderw=3:x=4:y=4"
                )
                vf = f"{scale},{draw}"
            else:
                vf = scale
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(src), "-vf", vf, str(dest)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(work / "t_%04d.png"),
                "-vf",
                f"tile={cols}x{rows}:padding=2:margin=2",
                "-update",
                "1",
                "-frames:v",
                "1",
                str(args.output),
            ],
            check=True,
        )
        print(
            f"wrote {args.output} ({len(picked)} tiles, {cols}x{rows}"
            + (f", sampled every {every} of {n}" if every > 1 or len(picked) < n else "")
            + ")"
        )
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return 0


def build_parser():
    p = argparse.ArgumentParser(prog="contact_sheet.py")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("probe", help="print ffprobe facts as JSON")
    sp.add_argument("--input", required=True)
    sp.add_argument("--out")
    sp.set_defaults(func=cmd_probe)

    se = sub.add_parser("extract", help="extract PNG frames from a video")
    se.add_argument("--input", required=True)
    se.add_argument("--out-dir", required=True)
    se.add_argument("--width", type=int, default=512)
    se.add_argument("--every", type=int, default=1)
    se.set_defaults(func=cmd_extract)

    st = sub.add_parser("tile", help="build a labeled contact sheet from a frame folder")
    st.add_argument("--frames-dir", required=True)
    st.add_argument("--output", required=True)
    st.add_argument("--fps", type=float)
    st.add_argument("--cols", type=int)
    st.add_argument("--rows", type=int)
    st.add_argument("--tile-width", type=int, default=160)
    st.add_argument("--fontsize", type=int, default=12)
    st.add_argument("--max-tiles", type=int, default=180)
    st.add_argument("--every", type=int)
    st.add_argument("--source-every", type=int, default=1, help="frame-index multiplier if the folder itself was subsampled")
    st.set_defaults(func=cmd_tile)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
