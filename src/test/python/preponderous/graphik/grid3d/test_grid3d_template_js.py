"""The pygbag template's 2D/3D switch, run in Node against a stand-in page
and a stand-in grid relay that behaves as Strata 0.9.0's does (the relay a
game copies with relay.py today). Skipped where there is no `node`.

What the string checks in test_grid3d_web.py can't see: the order things
happen in. A player who turns 3D off while the relay is still loading, then
on again, must get the 3D view (not a blank page with both canvases hidden),
and a relay that finishes loading after 2D was chosen must stop drawing.

Also here: the switch back to 2D when the 3D view stays too slow (only
once the kit can go no lower, only after the game's first message and a
grace period, never remembered, and not again once the player chose 3D
after it), and the button showing both views with the current one lit.
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
const search = process.argv[4] || "";

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
  "graphik3d-note": element("graphik3d-note"), "graphik3d-2d": element("graphik3d-2d"),
  "graphik3d-3d": element("graphik3d-3d")};
let clock = 1000000, stored = null;
// the page's frames: one every `gap` ms, and a stall of `stallMs` (the game's
// Python holding the page) every `stallEvery` ms
const pace = {gap: 16.7, stallEvery: 0, stallMs: 0};
let rafs = [], lastFrame = clock;
function frames() {
  for (;;) {
    let next = lastFrame + pace.gap;
    if (pace.stallEvery && Math.floor(next / pace.stallEvery) > Math.floor(lastFrame / pace.stallEvery)) next += pace.stallMs;
    if (next > clock) return;
    lastFrame = next;
    const due = rafs; rafs = [];
    due.forEach((f) => f(next));
  }
}
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
  // what Strata's kit reports: its tier (0 lowest), pixel density, its own
  // frame-time average (stalls included), and the relay's drawing a frame
  frame: {quality: 2, dpr: 3, dprCap: 2, frameMs: 16, cpuMs: 2},
  stats() { return JSON.stringify(Object.assign({state: this.s}, this.frame)); },
  resets: 0,
  resetStats() { this.resets++; },
  close() { this.running = false; els.relay.hidden = true; if (this.s === "ready") this.s = "idle"; },
};

const window = {
  location: {search}, WebGL2RenderingContext: function () {},
  localStorage: {getItem: () => null, setItem(k, v) { stored = v; }},
  addEventListener() {}, removeEventListener() {},
  requestAnimationFrame(f) { rafs.push(f); return rafs.length; },
};
const document = {
  getElementById: (id) => els[id] || null,
  createElement: () => ({}),
  body: {appendChild(tag) { pendingScripts.push(tag); }},
};
const context = {window, document, URLSearchParams, JSON, String, Number, Math, Date: {now: () => clock},
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
  else if (step === "fail") relay.s = "failed:engine";
  else if (step === "send") window.StrataGridRelay.send("AAAA");
  else if (step === "tick") interval();
  else if (step.frame) Object.assign(relay.frame, step.frame);
  else if (step.pace) Object.assign(pace, step.pace);
  else if (step.wait) {  // the page's frames and its 150 ms check, for that long
    for (let t = 0; t < step.wait; t += 150) { clock += 150; frames(); interval(); }
  }
  log.push({step, state: relay.s, running: relay.running, relayHidden: els.relay.hidden,
    relayVisible: els.relay.style.visibility === "visible", twoD: els.canvas.style.visibility,
    wanted: window.Graphik3D.wanted(), slowed: window.Graphik3D.slowed(), stored,
    note: els["graphik3d-note"].hidden ? "" : els["graphik3d-note"].textContent,
    view: els.graphik3d.attrs["data-view"], pressed: els.graphik3d.attrs["aria-pressed"],
    name: els.graphik3d.attrs["aria-label"], text: els.graphik3d.textContent,
    lit: ["2d", "3d"].filter((v) => /graphik3d-current/.test(els["graphik3d-" + v].className || ""))});
}
console.log(JSON.stringify(log));
"""


def graphikScript(page):
    block = page[page.index("graphik grid3d:"):]
    start = block.index("<script>") + len("<script>")
    return block[start:block.index("</script>", start)]


def run(tmp_path, steps, search=""):
    with open(web.templatePath(), encoding="utf-8") as handle:
        script = graphikScript(handle.read())
    (tmp_path / "block.js").write_text(script, encoding="utf-8")
    (tmp_path / "harness.js").write_text(HARNESS, encoding="utf-8")
    out = subprocess.run([NODE, str(tmp_path / "harness.js"), str(tmp_path / "block.js"), json.dumps(steps), search],
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


# -- too slow: back to 2D

LOWEST = {"quality": 0, "dpr": 1, "dprCap": 1}
# the kit at its lowest, a frame every 90 ms, 40 of them the relay's drawing
SLOW = {"frame": dict(LOWEST, frameMs=90, cpuMs=40)}
SLOW_PACE = {"pace": {"gap": 90, "stallEvery": 0, "stallMs": 0}}
DRAWING = ["scripts", "loaded", "tick", "send", "tick"]


@pytest.mark.skipif(NODE is None, reason="needs node")
def test_3d_that_stays_slow_at_the_lowest_tier_goes_back_to_2d_saying_why(tmp_path):
    log = run(tmp_path, DRAWING + [SLOW_PACE, SLOW, {"wait": 3000}, {"wait": 4800}, {"wait": 600}])
    assert log[4]["twoD"] == "hidden"  # drawing in 3D
    assert not log[-3]["slowed"] and not log[-2]["slowed"]  # grace, then not yet 5 s
    last = log[-1]
    assert last["slowed"] and last["twoD"] == "visible" and not last["relayVisible"]
    assert not last["running"] and not last["wanted"]
    assert last["note"] == "Back to 2D: this device draws the 3D view too slowly. Press 3D to try it again."
    # not a failure: the button still offers 3D, and the switch is not the player's choice
    assert last["view"] == "2d" and last["name"] == "3D view" and last["stored"] is None


@pytest.mark.skipif(NODE is None, reason="needs node")
def test_slow_frames_before_the_kit_has_stepped_down_do_not_count(tmp_path):
    # the kit still has pixel density or a quality tier to give up
    for frame, gap in (({"quality": 1, "dpr": 1, "cpuMs": 150}, 200), ({"quality": 0, "dpr": 2, "cpuMs": 150}, 200),
                       (dict(LOWEST, cpuMs=40), 50)):
        log = run(tmp_path, DRAWING + [{"pace": {"gap": gap}}, {"frame": frame}, {"wait": 20000}])
        assert not log[-1]["slowed"] and log[-1]["twoD"] == "hidden", frame


@pytest.mark.skipif(NODE is None, reason="needs node")
def test_nothing_counts_before_the_games_first_message_to_the_3d_view(tmp_path):
    # pygbag's boot: the relay is loaded and slow, but the game hasn't drawn
    log = run(tmp_path, ["scripts", "loaded", SLOW_PACE, SLOW, "tick", {"wait": 20000}, "send", "tick",
                         {"wait": 2900}])
    assert not log[-1]["slowed"] and log[-1]["twoD"] == "hidden"


@pytest.mark.skipif(NODE is None, reason="needs node")
def test_a_fast_window_starts_the_count_again(tmp_path):
    fast = {"pace": {"gap": 30}}
    log = run(tmp_path, DRAWING + [SLOW_PACE, SLOW, {"wait": 3000}, {"wait": 4500}, fast, {"wait": 1500},
                                   SLOW_PACE, {"wait": 4500}])
    assert not log[-1]["slowed"] and log[-1]["twoD"] == "hidden"


@pytest.mark.skipif(NODE is None, reason="needs node")
def test_slow_0_in_the_address_turns_the_switch_off(tmp_path):
    log = run(tmp_path, DRAWING + [SLOW_PACE, SLOW, {"wait": 30000}], search="?slow=0")
    assert not log[-1]["slowed"] and log[-1]["twoD"] == "hidden" and log[-1]["running"]


@pytest.mark.skipif(NODE is None, reason="needs node")
def test_after_a_slow_switch_the_player_can_choose_3d_and_keep_it(tmp_path):
    log = run(tmp_path, DRAWING + [SLOW_PACE, SLOW, {"wait": 9000}, "click", "send", "tick", {"wait": 30000}])
    last = log[-1]
    assert log[-5]["slowed"]  # it went back to 2D once
    assert last["twoD"] == "hidden" and last["relayVisible"] and last["running"] and last["wanted"]
    assert last["stored"] == "3d"  # the player's own press is remembered, as ever


@pytest.mark.skipif(NODE is None, reason="needs node")
def test_a_game_that_stalls_the_page_while_drawing_is_fast_stays_in_3d(tmp_path):
    # Python building and sending a board stops the page for 180-1800 ms now
    # and then: the kit's own average says 300 ms, but the relay draws a
    # frame in under 3 ms and the typical frame is 16.7 ms
    stalls = {"pace": {"gap": 16.7, "stallEvery": 1200, "stallMs": 900}}
    log = run(tmp_path, DRAWING + [stalls, {"frame": dict(LOWEST, frameMs=300, cpuMs=2.6)}, {"wait": 40000}])
    assert not log[-1]["slowed"] and log[-1]["twoD"] == "hidden" and log[-1]["running"]
    # long stalls between slow frames still don't count as drawing (they're cut)
    longStalls = {"pace": {"gap": 16.7, "stallEvery": 2000, "stallMs": 1800}}
    log = run(tmp_path, DRAWING + [longStalls, {"frame": dict(LOWEST, frameMs=600, cpuMs=2.8)}, {"wait": 40000}])
    assert not log[-1]["slowed"]


@pytest.mark.skipif(NODE is None, reason="needs node")
def test_a_game_slow_every_frame_with_cheap_drawing_stays_in_3d(tmp_path):
    # 2D wouldn't help: the relay's drawing is 3 of the 90 ms
    log = run(tmp_path, DRAWING + [SLOW_PACE, {"frame": dict(LOWEST, frameMs=90, cpuMs=3)}, {"wait": 40000}])
    assert not log[-1]["slowed"] and log[-1]["twoD"] == "hidden"


@pytest.mark.skipif(NODE is None, reason="needs node")
def test_slow_drawing_goes_to_2d_even_with_stalls_between(tmp_path):
    pace = {"pace": {"gap": 120, "stallEvery": 2500, "stallMs": 1500}}
    log = run(tmp_path, DRAWING + [pace, {"frame": dict(LOWEST, frameMs=400, cpuMs=70)}, {"wait": 20000}])
    assert log[-1]["slowed"] and log[-1]["twoD"] == "visible"


@pytest.mark.skipif(NODE is None, reason="needs node")
def test_a_relay_whose_kit_reports_fast_frames_keeps_3d(tmp_path):
    # Slow page frames and costly drawing, but the kit's own average says
    # 16 ms: the switch needs all three. (Browser test harnesses pin the
    # kit's frameMs this way to keep 3D on a machine that draws in software;
    # a check that read only the page's frames and cpuMs sent their games to
    # 2D mid-run.)
    log = run(tmp_path, DRAWING + [SLOW_PACE, {"frame": dict(LOWEST, frameMs=16, cpuMs=300)}, {"wait": 40000}])
    assert not log[-1]["slowed"] and log[-1]["twoD"] == "hidden" and log[-1]["running"]


# -- the button


@pytest.mark.skipif(NODE is None, reason="needs node")
def test_the_button_shows_both_views_with_the_one_on_show_lit(tmp_path):
    log = run(tmp_path, ["scripts", "loaded", "tick", "send", "tick", "click", "click"])
    # loading 3D: the page starts in 3D, so 3D is lit and the switch pressed
    assert log[0]["lit"] == ["3d"] and log[0]["pressed"] == "true" and log[0]["view"] == "3d"
    assert log[0]["name"] == "3D view"
    assert log[5]["lit"] == ["2d"] and log[5]["pressed"] == "false" and log[5]["view"] == "2d"
    assert log[6]["lit"] == ["3d"] and log[6]["pressed"] == "true"


@pytest.mark.skipif(NODE is None, reason="needs node")
def test_a_failed_3d_view_says_unavailable_on_the_button(tmp_path):
    log = run(tmp_path, ["scripts", "loaded", "fail", "tick"])
    last = log[-1]
    assert last["text"] == "3D unavailable" and last["view"] == "unavailable"
    assert last["name"] == "3D view unavailable" and last["pressed"] == "false"
    assert last["twoD"] == "visible" and last["note"].startswith("No 3D view here: the 3D engine failed to start")
