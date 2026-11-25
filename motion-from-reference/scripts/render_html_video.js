#!/usr/bin/env node
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");

function arg(flag, fallback) {
  const i = process.argv.indexOf(flag);
  if (i === -1) return fallback;
  const v = process.argv[i + 1];
  if (v === undefined || v.startsWith("--")) return true;
  return v;
}

function has(flag) {
  return process.argv.includes(flag);
}

function findChrome() {
  const explicit = arg("--chrome") || process.env.CHROME || process.env.CHROME_PATH;
  if (explicit && explicit !== true) return explicit;
  const candidates = [
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  ];
  for (const c of candidates) {
    if (fs.existsSync(c)) return c;
  }
  return undefined;
}

function loadPlaywright() {
  const tries = ["playwright-core", "playwright"];
  for (const name of tries) {
    try {
      return require(name);
    } catch (_) {}
    const fromSkill = path.resolve(__dirname, "..", "..", "..", "node_modules", name);
    try {
      return require(fromSkill);
    } catch (_) {}
  }
  throw new Error("install playwright or playwright-core to render HTML timelines");
}

function cleanDir(dir) {
  fs.rmSync(dir, { recursive: true, force: true });
  fs.mkdirSync(dir, { recursive: true });
}

function toFileUrl(p) {
  const abs = path.resolve(p);
  return "file://" + abs;
}

async function main() {
  const html = arg("--html");
  const out = arg("--out");
  if (!html || !out || html === true || out === true) {
    console.error("usage: render_html_video.js --html PAGE.html --out OUT.mp4 [--fps 60] [--duration 5.8] [--width 1080] [--height 1080] [--dpr 1] [--chrome PATH] [--tmp DIR] [--sheet CONTACT.png]");
    process.exit(2);
  }
  const fps = Number(arg("--fps", "60"));
  const width = Number(arg("--width", "1080"));
  const height = Number(arg("--height", "1080"));
  const dpr = Number(arg("--dpr", "1"));
  const tmp = arg("--tmp", path.join(path.dirname(path.resolve(out)), ".render-frames"));
  const sheet = arg("--sheet");
  const chrome = findChrome();
  const { chromium } = loadPlaywright();
  const browser = await chromium.launch({
    executablePath: chrome,
    args: ["--no-sandbox", "--disable-gpu-sandbox", "--headless=new"],
  });
  const evenW = width % 2 === 0 ? width : width + 1;
  const evenH = height % 2 === 0 ? height : height + 1;
  const page = await browser.newPage({
    viewport: { width: evenW, height: evenH },
    deviceScaleFactor: dpr,
  });
  const htmlPath = path.resolve(html);
  if (!fs.existsSync(htmlPath)) {
    throw new Error("html not found: " + htmlPath);
  }
  await page.goto(toFileUrl(htmlPath), { waitUntil: "load" });
  await page.evaluate(() => (document.fonts ? document.fonts.ready : Promise.resolve()));
  await page.waitForFunction(() => window.__ready !== false, { timeout: 10000 }).catch(() => {});
  const durationMs = Number(
    arg(
      "--duration",
      await page.evaluate(() => {
        if (typeof window.DURATION_MS === "number") return window.DURATION_MS;
        const meta = document.querySelector('meta[name="duration-ms"]');
        return meta ? Number(meta.getAttribute("content")) : 0;
      })
    )
  );
  if (!durationMs) {
    throw new Error("pass --duration seconds or set window.DURATION_MS / meta[name=duration-ms]");
  }
  const durMs = durationMs < 100 ? durationMs * 1000 : durationMs;
  const totalFrames = Math.round((durMs / 1000) * fps);
  cleanDir(tmp);
  for (let f = 0; f < totalFrames; f++) {
    const tMs = (f / fps) * 1000;
    await page.evaluate((ms) => {
      if (typeof window.renderAt === "function") {
        window.renderAt(ms);
        return;
      }
      const anims = document.getAnimations();
      for (let i = 0; i < anims.length; i++) {
        anims[i].pause();
        anims[i].currentTime = ms;
      }
    }, tMs);
    const framePath = path.join(tmp, "f_" + String(f).padStart(4, "0") + ".png");
    await page.screenshot({ path: framePath, omitBackground: false });
  }
  await browser.close();
  const outDir = path.dirname(path.resolve(out));
  fs.mkdirSync(outDir, { recursive: true });
  execFileSync(
    "ffmpeg",
    [
      "-y",
      "-framerate",
      String(fps),
      "-i",
      path.join(tmp, "f_%04d.png"),
      "-c:v",
      "libx264",
      "-pix_fmt",
      "yuv420p",
      "-crf",
      "18",
      "-movflags",
      "+faststart",
      path.resolve(out),
    ],
    { stdio: "inherit" }
  );
  console.log("wrote " + path.resolve(out) + " (" + totalFrames + " frames, " + fps + " fps)");
  if (sheet && sheet !== true) {
    const cols = Math.ceil(Math.sqrt(totalFrames * 1.7));
    const rows = Math.ceil(totalFrames / cols);
    execFileSync(
      "ffmpeg",
      [
        "-y",
        "-i",
        path.resolve(out),
        "-vf",
        "scale=160:-1,tile=" + cols + "x" + rows + ":padding=2:margin=2",
        "-update",
        "1",
        "-frames:v",
        "1",
        path.resolve(sheet),
      ],
      { stdio: "inherit" }
    );
    console.log("wrote " + path.resolve(sheet));
  }
  if (!has("--keep-frames")) {
    fs.rmSync(tmp, { recursive: true, force: true });
  }
}

main().catch((err) => {
  console.error(err && err.stack ? err.stack : String(err));
  process.exit(1);
});
