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
  throw new Error("install playwright or playwright-core to export GIFs and grid video");
}

function cleanDir(dir) {
  fs.rmSync(dir, { recursive: true, force: true });
  fs.mkdirSync(dir, { recursive: true });
}

function loadStates(dir, statesPath) {
  const p = statesPath ? path.resolve(statesPath) : path.join(dir, "states.json");
  if (fs.existsSync(p)) {
    const data = JSON.parse(fs.readFileSync(p, "utf8"));
    const list = Array.isArray(data) ? data : data.states;
    if (!list || !list.length) throw new Error("states file is empty: " + p);
    return list;
  }
  const svgDir = path.join(dir, "svg");
  const files = fs.readdirSync(svgDir).filter((n) => n.endsWith(".svg"));
  if (!files.length) throw new Error("no svg/*.svg and no states.json in " + dir);
  return files.map((n) => ({ id: path.basename(n, ".svg"), durMs: 2000 }));
}

async function main() {
  const dir = arg("--dir");
  if (!dir || dir === true) {
    console.error("usage: export_assets.js --dir OUT [--states states.json] [--gif-size 256] [--gif-fps 50] [--preview-at 420] [--grid-fps 60] [--grid-seconds 4] [--viewport 1120] [--chrome PATH] [--skip-gif] [--skip-grid] [--skip-preview]");
    process.exit(2);
  }
  const base = path.resolve(dir);
  const svgDir = path.join(base, "svg");
  const gifDir = path.join(base, "gif");
  const states = loadStates(base, arg("--states") === true ? undefined : arg("--states"));
  const gifSize = Number(arg("--gif-size", "256"));
  const gifFps = Number(arg("--gif-fps", "50"));
  const previewAt = Number(arg("--preview-at", "420"));
  const gridFps = Number(arg("--grid-fps", "60"));
  const gridSeconds = Number(arg("--grid-seconds", "4"));
  const viewportW = Number(arg("--viewport", "1120"));
  const tmp = arg("--tmp", "/tmp/expression-export-frames");
  const chrome = findChrome();
  const { chromium } = loadPlaywright();

  const svgMap = {};
  for (const st of states) {
    const p = path.join(svgDir, st.id + ".svg");
    if (!fs.existsSync(p)) throw new Error("missing " + p);
    svgMap[st.id] = fs.readFileSync(p, "utf8");
  }

  const browser = await chromium.launch({
    executablePath: chrome,
    args: ["--no-sandbox", "--disable-gpu-sandbox", "--headless=new"],
  });

  if (!has("--skip-gif")) {
    fs.mkdirSync(gifDir, { recursive: true });
    const gifPage = await browser.newPage({
      viewport: { width: gifSize, height: gifSize },
      deviceScaleFactor: 1,
    });
    for (const st of states) {
      cleanDir(tmp);
      const durMs = Number(st.durMs || 2000);
      const totalFrames = Math.round((durMs / 1000) * gifFps);
      await gifPage.setContent(
        '<!doctype html><html><body style="margin:0;background:transparent;overflow:hidden;width:' +
          gifSize +
          "px;height:" +
          gifSize +
          'px;display:flex;align-items:center;justify-content:center"><div style="width:' +
          gifSize +
          "px;height:" +
          gifSize +
          'px">' +
          svgMap[st.id] +
          "</div></body></html>"
      );
      await gifPage.evaluate((size) => {
        const svg = document.querySelector("svg");
        if (svg) {
          svg.setAttribute("width", String(size));
          svg.setAttribute("height", String(size));
        }
      }, gifSize);
      for (let f = 0; f < totalFrames; f++) {
        const tMs = (f / gifFps) * 1000;
        await gifPage.evaluate((ms) => {
          const anims = document.getAnimations();
          for (let i = 0; i < anims.length; i++) {
            anims[i].pause();
            anims[i].currentTime = ms;
          }
        }, tMs);
        await gifPage.screenshot({
          path: path.join(tmp, "f_" + String(f).padStart(4, "0") + ".png"),
          omitBackground: true,
        });
      }
      const palettePath = path.join(tmp, "palette.png");
      const outGif = path.join(gifDir, st.id + ".gif");
      execFileSync(
        "ffmpeg",
        [
          "-y",
          "-framerate",
          String(gifFps),
          "-i",
          path.join(tmp, "f_%04d.png"),
          "-vf",
          "palettegen=stats_mode=diff:reserve_transparent=1",
          palettePath,
        ],
        { stdio: "ignore" }
      );
      execFileSync(
        "ffmpeg",
        [
          "-y",
          "-framerate",
          String(gifFps),
          "-i",
          path.join(tmp, "f_%04d.png"),
          "-i",
          palettePath,
          "-lavfi",
          "paletteuse=alpha_threshold=128:dither=none",
          "-loop",
          "0",
          outGif,
        ],
        { stdio: "ignore" }
      );
      console.log("GIF " + st.id + ".gif (" + totalFrames + " frames)");
    }
    await gifPage.close();
  }

  const needPage = !has("--skip-preview") || !has("--skip-grid");
  if (needPage) {
    const indexPath = path.join(base, "index.html");
    if (!fs.existsSync(indexPath)) {
      throw new Error("index.html not found in " + base + " (run build_preview_page.py first)");
    }
    const gridPage = await browser.newPage({
      viewport: { width: viewportW, height: 960 },
      deviceScaleFactor: 1,
    });
    await gridPage.goto("file://" + indexPath + "?manual=1&capture=1", { waitUntil: "load" });
    await gridPage.evaluate((map) => {
      if (typeof window.prepareInlineForCapture === "function") {
        window.prepareInlineForCapture(map);
      }
    }, svgMap);
    await gridPage.evaluate(() => (document.fonts ? document.fonts.ready : Promise.resolve()));
    const fullHeight = await gridPage.evaluate(() => Math.ceil(document.documentElement.scrollHeight));
    const evenH = fullHeight % 2 === 0 ? fullHeight : fullHeight + 1;
    const evenW = viewportW % 2 === 0 ? viewportW : viewportW + 1;
    await gridPage.setViewportSize({ width: evenW, height: evenH });

    if (!has("--skip-preview")) {
      await gridPage.evaluate((ms) => {
        if (typeof window.renderAt === "function") window.renderAt(ms);
      }, previewAt);
      const previewPath = path.join(base, "preview.png");
      await gridPage.screenshot({ path: previewPath });
      console.log("preview.png " + evenW + "x" + evenH);
    }

    if (!has("--skip-grid")) {
      cleanDir(tmp);
      const vidFrames = Math.round(gridSeconds * gridFps);
      for (let f = 0; f < vidFrames; f++) {
        const tMs = (f / gridFps) * 1000;
        await gridPage.evaluate((ms) => {
          if (typeof window.renderAt === "function") window.renderAt(ms);
        }, tMs);
        await gridPage.screenshot({
          path: path.join(tmp, "g_" + String(f).padStart(4, "0") + ".png"),
        });
      }
      const outMp4 = path.join(base, "grid.mp4");
      execFileSync(
        "ffmpeg",
        [
          "-y",
          "-framerate",
          String(gridFps),
          "-i",
          path.join(tmp, "g_%04d.png"),
          "-c:v",
          "libx264",
          "-pix_fmt",
          "yuv420p",
          "-crf",
          "18",
          "-movflags",
          "+faststart",
          outMp4,
        ],
        { stdio: "ignore" }
      );
      console.log("grid.mp4 (" + vidFrames + " frames, " + gridFps + " fps)");
    }
    await gridPage.close();
  }

  await browser.close();
  fs.rmSync(tmp, { recursive: true, force: true });
}

main().catch((err) => {
  console.error(err && err.stack ? err.stack : String(err));
  process.exit(1);
});
