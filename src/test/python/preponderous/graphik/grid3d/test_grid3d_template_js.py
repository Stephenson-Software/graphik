"""The pygbag template's 2D/3D switch, run in Node against a stand-in page
and a stand-in grid relay that behaves as Strata 0.9.0's does (the relay a
game copies with relay.py today). Skipped where there is no `node`.

What the string checks in test_grid3d_web.py can't see: the order things
happen in. A player who turns 3D off while the relay is still loading, then
on again, must get the 3D view (not a blank page with both canvases hidden),
and a relay that finishes loading after 2D was chosen must stop drawing.
"""

import json
import shutil
import subprocess

import pytest

from preponderous.graphik.grid3d import web

NODE = shutil.which("node")

HARNESS = r"""
const vm = require("vm");
const block = require("fs").readFileSync(process.argv[2], "utf8");
const steps = JSON.parse(process.argv[3]);

function element(id) {
  const listeners = {};
  return {
    id, hidden: id === "relay" || id === "graphik3d-note", style: {}, textContent: "", title: "",
    attrs: {"data-default-view": "3d"},
    getAttribute(n) { return this.attrs[n] || null; }, setAttribute(n, v) { this.attrs[n] = String(v); },
    addEventListener(t, f) { (listeners[t] = listeners[t] || []).push(f); },
    fire(t) { (listeners[t] || []).forEach((f) => f({})); },
    getBoundingClientRect: () => ({left: 700, top: 8, width: 60, height: 36}), focus() {},
  };
}
const els = {canvas: element("canvas"), relay: element("relay"), graphik3d: element("graphik3d"),
  "graphik3d-note": element("graphik3d-note")};
els.canvas.style.visibility = "visible";
let interval = null, pendingScripts = [];

// Strata 0.9.0's grid-relay.js, as far as the page sees it: close() while
// loading hides the canvas but is forgotten when loading ends, and
// request() on a "ready" relay returns without showing the canvas.
const relay = {
  s: "idle", kit: false, running: false, sent: 0,
  request() {
    if (this.s === "loading" || this.s === "ready") return this.s;
    if (this.kit && this.s === "idle") { els.relay.hidden = false; this.s = "ready"; this.running = true; return this.s; }
    this.s = "loading"; els.relay.hidden = false; return this.s;
  },
  finishLoading() { if (this.s === "loading") { this.kit = true; this.s = "ready"; this.running = true; } },
  state() { return this.s; },
  send() { this.sent++; return 0; },
  close() { this.running = false; els.relay.hidden = true; if (this.s === "ready") this.s = "idle"; },
};

const window = {
  location: {search: ""}, WebGL2RenderingContext: function () {},
  localStorage: {getItem: () => null, setItem() {}},
  addEventListener() {}, removeEventListener() {},
};
const document = {
  getElementById: (id) => els[id] || null,
  createElement: () => ({}),
  body: {appendChild(tag) { pendingScripts.push(tag); }},
};
const context = {window, document, URLSearchParams, JSON, String, Number, Math,
  setInterval: (f) => { interval = f; return 1; }, setTimeout: () => 0, clearTimeout() {}};
vm.runInNewContext(block, context);

function loadScripts() {  // the injected scripts load, one after another
  while (pendingScripts.length) {
    const tag = pendingScripts.shift();
    if (tag.src === "grid-relay.js") window.StrataGridRelay = relay;
    tag.onload();
  }
}
const log = [];
for (const step of steps) {
  if (step === "scripts") loadScripts();
  else if (step === "click") els.graphik3d.fire("click");
  else if (step === "loaded") relay.finishLoading();
  else if (step === "send") window.StrataGridRelay.send("AAAA");
  else if (step === "tick") interval();
  log.push({step, state: relay.s, running: relay.running, relayHidden: els.relay.hidden,
    relayVisible: els.relay.style.visibility === "visible", twoD: els.canvas.style.visibility,
    wanted: window.Graphik3D.wanted()});
}
console.log(JSON.stringify(log));
"""


def graphikScript(page):
    block = page[page.index("graphik grid3d:"):]
    start = block.index("<script>") + len("<script>")
    return block[start:block.index("</script>", start)]


def run(tmp_path, steps):
    with open(web.templatePath(), encoding="utf-8") as handle:
        script = graphikScript(handle.read())
    (tmp_path / "block.js").write_text(script, encoding="utf-8")
    (tmp_path / "harness.js").write_text(HARNESS, encoding="utf-8")
    out = subprocess.run([NODE, str(tmp_path / "harness.js"), str(tmp_path / "block.js"), json.dumps(steps)],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


@pytest.mark.skipif(NODE is None, reason="needs node")
def test_3d_turned_off_while_loading_then_on_again_shows_the_3d_view(tmp_path):
    log = run(tmp_path, ["scripts", "click", "loaded", "tick", "click", "send", "tick"])
    last = log[-1]
    # the game is drawing in 3D: the relay's canvas is shown, not just "visible" while hidden
    assert last["state"] == "ready" and last["running"]
    assert last["relayVisible"] and not last["relayHidden"]
    assert last["twoD"] == "hidden"


@pytest.mark.skipif(NODE is None, reason="needs node")
def test_a_relay_that_finishes_loading_after_2d_was_chosen_stops_drawing(tmp_path):
    log = run(tmp_path, ["scripts", "click", "loaded", "tick"])
    last = log[-1]
    assert not last["running"] and last["state"] == "idle"
    assert last["twoD"] == "visible" and not last["wanted"]


@pytest.mark.skipif(NODE is None, reason="needs node")
def test_the_2d_view_stays_until_the_3d_view_is_drawing_the_game(tmp_path):
    log = run(tmp_path, ["scripts", "loaded", "tick", "send", "tick"])
    assert log[2]["twoD"] == "visible"  # loaded, but nothing sent yet
    assert log[4]["twoD"] == "hidden" and log[4]["relayVisible"] and not log[4]["relayHidden"]
