---
name: bot-expression-animation
description: Build a set of animated expression or state assets for a bot, mascot, or character from a reference image or written spec. Use when asked for idle, happy, thinking, listening, talking, success, error, surprised, sleepy (or similar) CSS-keyframe SVGs, transparent GIFs, a light/dark preview page, or a grid MP4 of character expressions.
---

# Bot expression animation

Produce a reusable expression set for one character. Start from a reference image or a written description, match proportions faithfully, and adapt motion to that body (eyes, squash/stretch, accent glyphs). Do not invent a second mascot when a reference was given.

Helper scripts live in `scripts/` next to this file. Resolve paths from this skill folder. Requires `ffmpeg`, Python 3, Node.js plus `playwright` or `playwright-core`, and a Chrome/Chromium binary.

Default states, unless the user lists others:

`idle`, `happy`, `thinking`, `listening`, `talking`, `success`, `error`, `surprised`, `sleepy`

## 1. Study the reference

If an image is provided, open it and measure (do not trust a sloppy bounding box that includes badges, shadows, or captions):

- Silhouette and true center / radius (or body outline).
- Eye count, size, tilt, and placement relative to center, as fractions of radius.
- Mouth, antenna, limbs, or other parts — only if they are actually on the character.
- Fill, gloss, and shading (flat, radial, rim).
- Accent colors.

Status badges, app icons, rounded-square tiles, labels, and other UI chrome are not part of the character unless the user says so. You may reuse an accent from a badge (for example a warm orange) on glyphs only.

Draw a clean vector of the idle pose and compare it side by side with the reference on both a light and a dark field. Iterate until placement and proportions match. A tiny or pixelated reference still needs a clean vector, not a traced jaggy.

## 2. Adapt expressions to this body

Write a short motion plan for each state before drawing frames. Expressions should come from features the character actually has:

- Eyes: blink, squint arcs (happy), look up and aside (thinking), widen (surprised), half-close or droop (sleepy), uneven lids (error).
- Body: squash and stretch with baked springs, small leans, highlight or rim shifts on tilt.
- Secondary glyphs, staggered: sparkle, `?`, `!`, `zZ`, check, sound arcs, dots, voice bars. Glyphs start at `opacity: 0` with `animation-fill-mode: both` so a delayed element does not flash on at `t = 0`.
- If there is no mouth, talking and listening use rhythm (body pulse, highlight, sound arcs or bars), not a drawn mouth.
- One-shot states (`success`, `surprised`, and similar): an inner animation with `1 forwards` for the pop, then an outer group with a delayed infinite idle breath so a looping `<img>` does not die on the last frame.

Suggested loop lengths (adjust when the character needs it): idle 2.8s, happy 1.8s, thinking 2.2s, listening 1.6s, talking 1.2s, error 2.2s, sleepy 3.0s; success and surprised are one-shots of about 1.0–1.1s then breath.

## 3. Motion rules

- Character jumps and landings use a spring, not a decorative bezier bounce. Bake the curve into `@keyframes` with `scripts/springs.py` (default starting point: stiffness 380, damping 18, mass 1, landing scale around `1.14 × 0.85`). Emit `animation-timing-function: linear` on those keyframes so the baked samples keep their shape. `linear()` easing is also acceptable when the host supports it.
- UI-like badges and glyphs use ease-out curves such as `cubic-bezier(0.22, 1, 0.36, 1)` and may pop, but they should not wobble like the body spring.
- Keep the character readable on light and dark backgrounds. A solid black body needs a subtle rim light or soft edge; do not rely on a drop shadow that vanishes on dark UI.
- Square SVG, transparent background, `viewBox="0 0 160 160"` unless the user specifies another size.
- Self-contained file: inline CSS `@keyframes`, no JavaScript, works as `<img src="state.svg">`.
- Prefix every class, `@keyframes` name, and `id` (including `url(#id)` refs) with the state name so several SVGs can be inlined on one page without colliding. `scripts/springs.py scope` does this.
- Include `@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }` and, for reduced motion, a still pose with required glyphs already visible (for example a check or `?`).
- No code comments in generated SVG, CSS, HTML, or JS.

## 4. Generate the SVGs

Write one SVG per state under `OUT/svg/<state>.svg`. Use `scripts/springs.py bake` to print jump keyframes, then `scripts/springs.py scope --prefix STATE --input raw.svg --output OUT/svg/STATE.svg`.

Put a `states.json` next to the SVGs (see `templates/states.example.json`) with `id`, `durMs`, `meta`, and `desc` for each state. One-shot states should set `durMs` long enough to include the hold-breath that follows the pop (about 2.4–2.6s) so GIF loops feel complete.

## 5. Preview page

```bash
python scripts/build_preview_page.py --states OUT/states.json --title "Name Expressions" --out OUT/index.html
```

The page must show every state at 160px on a light field and 64px on a dark field (or provide a control to swap). Support `?manual=1&capture=1`. Expose:

- `window.prepareInlineForCapture(svgMap)` — replace `<img>` tags with inlined SVG, re-scoping ids per slot so two sizes of the same state do not clash.
- `window.renderAt(ms)` — `pause()` every entry in `document.getAnimations()` and set `currentTime = ms`.
- A replay control that reloads one-shot `<img>` tags (or `key={state}` in a host app).

## 6. Export GIFs, preview, and grid video

```bash
node scripts/export_assets.js --dir OUT --states OUT/states.json --gif-size 256 --gif-fps 50 --preview-at 420 --grid-fps 60 --grid-seconds 4
```

GIF rules: transparent 256×256, 50 fps (20 ms per frame, which maps to an exact GIF delay of 2 centiseconds), `palettegen=stats_mode=diff:reserve_transparent=1`, then `paletteuse=alpha_threshold=128:dither=none`. Do not use a frame rate whose delay would round unevenly in GIF (for example 60 fps).

The script also writes `preview.png` (full preview page at `--preview-at` ms) and `grid.mp4` (`libx264`, `yuv420p`, even dimensions).

## 7. Self-check

Render a side-by-side of idle versus the reference on light and dark. Open `preview.png`, sampled GIF frames, and a contact sheet of `grid.mp4`. Check:

- Proportions and eye placement against the reference.
- Delayed glyphs do not appear at `t = 0`.
- One-shots pop, then breathe, and do not freeze mid-squash.
- Black (or other dark) bodies still separate from a dark tile.
- 64px siblings stay legible.

Iterate the SVGs and re-export until these pass.

## 8. Package and integration notes

Zip the output directory if the user wants a single archive. Tell the host app:

- Looping states: `<img src="svg/idle.svg" alt="">` or the matching GIF.
- One-shots: remount on change (`key={state}` in React, or re-set `src` with a cache-bust) so the pop plays again.
- Prefer SVG for crisp UI; GIF when the host cannot animate SVG (some chat and email clients).
- Honor `prefers-reduced-motion` in product UI as well as inside the SVG.
