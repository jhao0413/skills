---
name: motion-from-reference
description: Learn a motion style from a reference video and produce an original animated video that follows it. Use when asked to analyze, transcribe, or recreate motion from a clip; extract timings, cubic-bezier easings, or spring parameters; write a motion spec; or render a deterministic HTML timeline to MP4 with ffmpeg.
---

# Motion from reference

Turn a reference clip into a written motion spec, then build an original piece that uses the same language. Do not rotoscope or copy trademarked characters, logos, or copy. Reuse timing, easing, stagger, and rules (for example: UI never bounces, only the character uses spring squash).

Helper scripts live in `scripts/` next to this file. Resolve paths from this skill folder. Requires `ffmpeg`, `ffprobe`, Python 3 with Pillow, and (for the final encode) Node.js plus `playwright` or `playwright-core` and a Chrome/Chromium binary.

## 1. Get the clip and probe it

Save the reference locally (download a public clip, or copy a file the user provided). Then probe:

```bash
python scripts/contact_sheet.py probe --input CLIP.mp4 --out probe.json
```

Record duration, pixel size, `r_frame_rate`, average frame rate, frame count, and pixel format. Use the official frame rate for timestamps (`t = frame_index / fps`).

## 2. Extract frames and a labeled contact sheet

```bash
python scripts/contact_sheet.py extract --input CLIP.mp4 --out-dir WORK/frames --width 512
python scripts/contact_sheet.py extract --input CLIP.mp4 --out-dir WORK/frames-hi --width 1024
python scripts/contact_sheet.py tile --frames-dir WORK/frames --output WORK/contact-sheet.png --fps FPS
```

Every tile must show frame index and time in milliseconds. If the clip is long (more than ~180 frames), pass `--every N` or `--max-tiles 160` so the sheet stays readable; keep a full frame folder at working resolution for measurement.

Open the contact sheet and look at it before writing any numbers.

## 3. Detect cuts and motion peaks

```bash
python scripts/detect_scenes.py --input CLIP.mp4 --out-dir WORK --threshold 0.3
```

This writes scene scores, hard-cut frames, and frame-difference energy. Hard cuts usually score above ~0.3. Dissolves, moving UI, and bounces often sit between 0.05 and 0.22. Use energy peaks to mark launches, landings, and scene changes.

If the clip is a multi-panel wall, full-frame scores mix every cell together and hide structure. Split first, then rerun detection per cell.

## 4. Split multi-panel clips

Measure the cell rectangles on a high-res frame (include gaps and any chrome you must exclude). Then:

```bash
python scripts/split_grid.py --frames-dir WORK/frames-hi --out-dir WORK/cells --grid 2x3 --inset L,T,R,B --gap GX,GY
python scripts/split_grid.py --frames-dir WORK/frames-hi --out-dir WORK/cells --cells 'TL=x,y,w,h;TR=x,y,w,h'
```

Build a contact sheet for each cell. Repeat scene and energy detection inside a cell when cuts or peaks are unclear on the full frame.

## 5. Track and normalize

From the sheets, list who moves and in which frame ranges. Track only those ranges, on the high-res frames (or a cropped cell):

```bash
python scripts/track_motion.py --frames-dir WORK/frames-hi --out WORK/tracks/name.csv --mode luma --max-luma 40 --roi x,y,w,h
```

`--mode chroma --color '#2563EB' --tolerance 48` is better for a flat-colored object. Output is a CSV of centroid, size, and area, plus values normalized to the frame or ROI (0–1 or percentages of the cell). Prefer percentages in the spec so the motion is resolution-independent.

Plot or print the curve. Confirm visually that the tracker followed the right object.

## 6. Fit easing: bezier vs spring

Fit each continuous segment, not the entire clip (cut anticipation, flight, and settle apart when they are different languages).

```bash
python scripts/fit_curves.py --curve WORK/tracks/name.csv --column cy_n --out WORK/fits/name.json --plot WORK/fits/name.png
```

Rules:

- Smooth approach to a rest pose with no overshoot: cubic-bezier. Record `cubic-bezier(x1, y1, x2, y2)` and duration.
- Overshoot, a second oscillation, or squash/stretch on landing: a spring (`stiffness`, `damping`, `mass`), not a bezier forced through the bounce.
- Also compare against well-known easings (`ease-out` expo-ish `[0.22, 1, 0.36, 1]`, clip-reveal `[0.6, 0, 0.2, 1]`, UI reposition `[0.5, 0, 0.2, 1]`) and keep the closer named curve when the error is similar.
- Write measured values as estimates. They are not official project files.

Typical split (reuse only when the reference actually does this): product UI, typography, and logos travel on bezier with zero bounce; only a character or mascot uses spring and landing squash (for example stiffness ~380, damping ~18, land near height 84% / width 114%).

## 7. Write the motion spec

Use `templates/motion-spec.md`. Include:

- Source facts (fps, duration, frame count, canvas).
- Layout in percentages (cells, margins, safe areas).
- The language: which objects may bounce, which may not.
- A beat table: `t0–t1`, who, what, easing, distance, stagger.
- Stagger notes (word-by-word text is often 100–170ms gaps).
- Hard cuts vs continuous reveals (a clipped rectangle translated in Y reads as “rising into view” and is more stable than a scale-up).
- Any reused motifs that reappear later, offset in time.

## 8. Build a deterministic HTML timeline

Create an original composition (new characters, typography, and layout) that obeys the spec. The page must be seekable:

- Expose `window.renderAt(ms)` that pauses every animation and sets `animation.currentTime = ms` (via `document.getAnimations()`, plus any manual transforms you drive from a baked table).
- Do not rely on wall-clock CSS playback for the final encode. Seeking must be enough to reconstruct any frame.
- Wait for fonts (`document.fonts.ready`) and set `window.__ready = true` when the timeline can be sampled.
- Use even pixel width and height. Prefer a square or the aspect the user asked for.
- Bake spring motion as sampled keyframes or as values computed in `renderAt`.

## 9. Render frames to MP4

```bash
node scripts/render_html_video.js --html WORK/piece.html --out WORK/piece.mp4 --fps 60 --duration 5.8 --width 1080 --height 1080
```

The script launches headless Chrome, calls `renderAt` once per frame, writes PNGs, and encodes with `libx264`, `yuv420p`, `-crf 18`, and `+faststart`. Pass `--chrome PATH` if needed. Then build a contact sheet of the result:

```bash
python scripts/contact_sheet.py extract --input WORK/piece.mp4 --out-dir WORK/out-frames --width 320
python scripts/contact_sheet.py tile --frames-dir WORK/out-frames --output WORK/out-contact-sheet.png --fps 60
```

## 10. Self-check and iterate

Open the output contact sheet and compare it to the reference sheet and the spec: peak times, settle time, squash amount, stagger, and whether UI stays bounce-free. Fix the timeline or the easing and re-render until the language matches. Deliver the MP4, the contact sheet, and the motion spec.
