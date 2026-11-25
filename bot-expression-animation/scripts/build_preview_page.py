#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path


HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__TITLE__</title>
<style>
  * {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }

  body {
    min-height: 100vh;
    background: #F4F6FA;
    color: #11141B;
    font-family: 'Geist', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    -webkit-font-smoothing: antialiased;
    padding: 28px;
  }

  body.theme-dark {
    background: #0B0E14;
    color: #F8FAFC;
  }

  .wrap {
    max-width: 1080px;
    margin: 0 auto;
  }

  .topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;
  }

  .brand {
    display: flex;
    align-items: baseline;
    gap: 12px;
  }

  .brand h1 {
    font-size: 24px;
    font-weight: 600;
    letter-spacing: -0.03em;
  }

  .brand span {
    font-size: 13px;
    font-weight: 500;
    color: #64748B;
  }

  .controls {
    display: flex;
    gap: 8px;
  }

  .btn {
    border: 1px solid rgba(15, 23, 42, 0.12);
    background: #FFFFFF;
    color: #11141B;
    font-family: inherit;
    font-size: 13px;
    font-weight: 500;
    padding: 7px 14px;
    border-radius: 999px;
    cursor: pointer;
  }

  body.theme-dark .btn {
    background: #161B26;
    color: #E2E8F0;
    border-color: rgba(255, 255, 255, 0.12);
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
  }

  .card {
    background: #FFFFFF;
    border: 1px solid rgba(15, 23, 42, 0.08);
    border-radius: 20px;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
  }

  body.theme-dark .card {
    background: #131822;
    border-color: rgba(255, 255, 255, 0.08);
  }

  .card-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .state-name {
    font-size: 16px;
    font-weight: 600;
    letter-spacing: -0.02em;
  }

  .state-meta {
    font-family: 'Geist Mono', ui-monospace, monospace;
    font-size: 11px;
    font-weight: 500;
    color: #64748B;
    background: #F1F5F9;
    padding: 3px 8px;
    border-radius: 999px;
  }

  body.theme-dark .state-meta {
    background: #1E2534;
    color: #94A3B8;
  }

  .stage-row {
    display: grid;
    grid-template-columns: 1fr 110px;
    gap: 10px;
    align-items: stretch;
  }

  .slot {
    border-radius: 14px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    position: relative;
    padding: 10px;
  }

  .slot-light {
    background: #F8FAFC;
    border: 1px solid rgba(15, 23, 42, 0.06);
    height: 184px;
  }

  .slot-dark {
    background: #0F131A;
    border: 1px solid rgba(255, 255, 255, 0.08);
    height: 184px;
  }

  body.swap-slots .slot-main {
    background: #0F131A;
    border: 1px solid rgba(255, 255, 255, 0.08);
  }

  body.swap-slots .slot-main .slot-tag {
    color: #CBD5E1;
  }

  body.swap-slots .slot-mini {
    background: #F8FAFC;
    border: 1px solid rgba(15, 23, 42, 0.06);
  }

  body.swap-slots .slot-mini .slot-tag {
    color: #334155;
  }

  .slot-tag {
    position: absolute;
    left: 10px;
    bottom: 8px;
    font-family: 'Geist Mono', ui-monospace, monospace;
    font-size: 10px;
    font-weight: 500;
    opacity: 0.58;
  }

  .slot-light .slot-tag {
    color: #334155;
  }

  .slot-dark .slot-tag {
    color: #CBD5E1;
  }

  .art-160 {
    width: 160px;
    height: 160px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .art-64 {
    width: 64px;
    height: 64px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .art-160 img, .art-160 svg {
    width: 160px;
    height: 160px;
    display: block;
  }

  .art-64 img, .art-64 svg {
    width: 64px;
    height: 64px;
    display: block;
  }

  .desc {
    font-size: 12px;
    color: #64748B;
    line-height: 1.35;
  }

  body.theme-dark .desc {
    color: #94A3B8;
  }

  .capture-mode {
    padding: 24px 28px;
  }
</style>
</head>
<body>
<div class="wrap">
  <div class="topbar">
    <div class="brand">
      <h1>__TITLE__</h1>
      <span>__SUBTITLE__</span>
    </div>
    <div class="controls" id="controls">
      <button class="btn" id="swapBtn" type="button">Swap Light / Dark</button>
      <button class="btn" id="themeBtn" type="button">Toggle Page Theme</button>
      <button class="btn" id="replayBtn" type="button">Replay One-Shots</button>
    </div>
  </div>
  <div class="grid" id="grid"></div>
</div>
<script>
(function () {
  var STATES = __STATES__;

  var grid = document.getElementById("grid");
  var params = new URLSearchParams(window.location.search);
  var isManual = params.has("manual");

  if (params.has("capture")) {
    document.body.classList.add("capture-mode");
    document.getElementById("controls").style.display = "none";
  }

  STATES.forEach(function (st) {
    var card = document.createElement("div");
    card.className = "card";
    card.innerHTML =
      '<div class="card-head">' +
        '<span class="state-name">' + st.id + '</span>' +
        '<span class="state-meta">' + (st.meta || "") + '</span>' +
      '</div>' +
      '<div class="stage-row">' +
        '<div class="slot slot-light slot-main">' +
          '<div class="art-160" data-state="' + st.id + '"><img src="svg/' + st.id + '.svg" alt="' + st.id + ' 160px"></div>' +
          '<span class="slot-tag">160px · light</span>' +
        '</div>' +
        '<div class="slot slot-dark slot-mini">' +
          '<div class="art-64" data-state="' + st.id + '"><img src="svg/' + st.id + '.svg" alt="' + st.id + ' 64px"></div>' +
          '<span class="slot-tag">64px · dark</span>' +
        '</div>' +
      '</div>' +
      '<div class="desc">' + (st.desc || "") + '</div>';
    grid.appendChild(card);
  });

  document.getElementById("swapBtn").addEventListener("click", function () {
    var swapped = document.body.classList.toggle("swap-slots");
    document.querySelectorAll(".slot-main .slot-tag").forEach(function (el) {
      el.textContent = swapped ? "160px · dark" : "160px · light";
    });
    document.querySelectorAll(".slot-mini .slot-tag").forEach(function (el) {
      el.textContent = swapped ? "64px · light" : "64px · dark";
    });
  });

  document.getElementById("themeBtn").addEventListener("click", function () {
    document.body.classList.toggle("theme-dark");
  });

  document.getElementById("replayBtn").addEventListener("click", function () {
    var imgs = document.querySelectorAll(".art-160 img, .art-64 img");
    var ts = Date.now();
    imgs.forEach(function (img) {
      var base = img.getAttribute("src").split("?")[0];
      img.setAttribute("src", base + "?r=" + ts);
    });
  });

  window.prepareInlineForCapture = function (svgMap) {
    var slots = document.querySelectorAll("[data-state]");
    slots.forEach(function (slot, idx) {
      var id = slot.getAttribute("data-state");
      var raw = svgMap[id];
      if (!raw) return;
      var scoped = raw
        .replace(/id="([^"]+)"/g, 'id="s' + idx + '_$1"')
        .replace(/url\\(#([^)]+)\\)/g, 'url(#s' + idx + '_$1)');
      slot.innerHTML = scoped;
    });
  };

  window.renderAt = function (ms) {
    var anims = document.getAnimations();
    for (var i = 0; i < anims.length; i++) {
      anims[i].pause();
      anims[i].currentTime = ms;
    }
  };

  if (isManual) {
    window.__manualReady = true;
  }
})();
</script>
</body>
</html>
"""


def load_states(path):
    data = json.loads(Path(path).read_text())
    if isinstance(data, list):
        return {"title": "Expressions", "subtitle": "animated states", "states": data}
    if "states" not in data:
        raise SystemExit("states JSON must be a list or an object with a states array")
    return data


def main(argv=None):
    p = argparse.ArgumentParser(prog="build_preview_page.py")
    p.add_argument("--states", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--title")
    p.add_argument("--subtitle")
    args = p.parse_args(argv)
    data = load_states(args.states)
    title = args.title or data.get("title") or "Expressions"
    subtitle = args.subtitle or data.get("subtitle") or "animated states · pure CSS SVG + 256px GIF"
    states_js = json.dumps(data["states"], ensure_ascii=True)
    html = (
        HTML.replace("__TITLE__", title)
        .replace("__SUBTITLE__", subtitle)
        .replace("__STATES__", states_js)
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    print(f"wrote {out} ({len(data['states'])} states)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
