# skills

Reusable [Agent Skills](https://agentskills.io) for motion work: learn a style from a reference clip, and build animated expression sets for a bot or mascot.

Compatible with Claude Code, Codex, Pi, Cursor, and any other host that loads a folder containing `SKILL.md`.

## Skills

| Skill | Use when |
| --- | --- |
| [`motion-from-reference`](motion-from-reference/SKILL.md) | You have a reference video and need to extract its motion language (timings, cubic-bezier vs spring, stagger, no-bounce UI vs character squash), write a motion spec, then render an original deterministic HTML timeline to MP4. |
| [`bot-expression-animation`](bot-expression-animation/SKILL.md) | You need a set of animated expression or state assets for a bot, mascot, or character: self-contained CSS-keyframe SVGs, 256px transparent GIFs, a light/dark preview page, and a grid MP4. |

Each skill folder is self-contained: `SKILL.md` plus the helper scripts that were actually used for this work, generalized under `scripts/`.

## Install

Copy or symlink the skill folder (the directory that contains `SKILL.md`) into your agent's skills path:

```bash
git clone https://github.com/jhao0413/skills.git

cp -R skills/motion-from-reference ~/.claude/skills/
cp -R skills/bot-expression-animation ~/.claude/skills/

cp -R skills/motion-from-reference ~/.codex/skills/
cp -R skills/bot-expression-animation ~/.codex/skills/

cp -R skills/motion-from-reference ~/.pi/agent/skills/
cp -R skills/bot-expression-animation ~/.pi/agent/skills/
```

Cursor and other Agent Skills hosts use whatever skills directory that tool documents; the folder layout is the same. After copying, restart or reload the agent so it picks up the new skills.

## Requirements

- `ffmpeg` and `ffprobe`
- Python 3.10+ with [Pillow](https://pypi.org/project/Pillow/)
- Node.js 18+ with [`playwright`](https://playwright.dev) or `playwright-core`, plus a Chrome or Chromium executable, for HTML-to-MP4 and GIF export

The skills tell the agent how to call the scripts. Point `--chrome` at your browser if it is not at `/usr/bin/google-chrome`.

## Examples

Small stills and a couple of GIFs from runs of these skills live in [`examples/`](examples/). The full videos are not in the repo.

## License

MIT. Copyright Jhao.
