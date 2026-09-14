import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {setImmediate as flush} from "node:timers/promises";
import {pixelAt, neighbor, advance, retainPose, selection, mountPreview} from "../src/pixaac/preview.mjs";

test("native coordinates at all zooms, corners, scrolled origins and asset sizes", () => {
  for (const zoom of [1, 2, 4, 8, 12, 16]) {
    for (const [width, height] of [[40, 40], [24, 24], [96, 64]]) {
      for (const [left, top] of [[24, 140], [-173.5, -251.25]]) {
        const rect = {left, top, width: width * zoom, height: height * zoom};
        assert.deepEqual(pixelAt(left, top, rect, width, height), [0, 0]);
        assert.deepEqual(pixelAt(left + rect.width - .01, top, rect, width, height), [width - 1, 0]);
        assert.deepEqual(pixelAt(left, top + rect.height - .01, rect, width, height), [0, height - 1]);
        assert.deepEqual(pixelAt(left + rect.width - .01, top + rect.height - .01, rect, width, height), [width - 1, height - 1]);
        assert.deepEqual(pixelAt(left + 13.5 * zoom, top + 15.5 * zoom, rect, width, height), [13, 15]);
        for (const [x, y] of [[left - .01, top], [left, top - .01], [left + rect.width, top], [left, top + rect.height]]) {
          assert.equal(pixelAt(x, y, rect, width, height), null);
        }
      }
    }
  }
  assert.equal(pixelAt(0, 0, {left: 0, top: 0, width: 0, height: 0}, 40, 40), null);
  const image = {left: -100, top: -100, width: 640, height: 640};
  const viewport = {left: 24, top: 140, width: 300, height: 300};
  assert.equal(pixelAt(25, 100, image, 40, 40, viewport), null); // Image is clipped by its scroll pane.
  assert.deepEqual(pixelAt(28, 156, image, 40, 40, viewport), [8, 16]);
});

test("neighbors follow nonzero-start forward, reverse and pingpong playback", () => {
  for (const indices of [[1, 2, 3], [3, 2, 1], [1, 2, 3, 2]]) {
    for (const loop of [true, false]) {
      for (let i = 0; i < indices.length; i++) {
        assert.equal(neighbor(indices, i, -1, loop),
          i > 0 ? indices[i - 1] : loop ? indices.at(-1) : null);
        assert.equal(neighbor(indices, i, 1, loop),
          i < indices.length - 1 ? indices[i + 1] : loop ? indices[0] : null);
      }
    }
  }
  for (const loop of [true, false]) {
    for (const delta of [-1, 1]) {
      assert.equal(neighbor([2], 0, delta, loop), null);
      assert.equal(neighbor([], 0, delta, loop), null);
    }
  }
  assert.equal(advance([3, 2, 1], 0, -1, false), 0);
  assert.equal(advance([3, 2, 1], 2, 1, false), 2);
  assert.equal(advance([3, 2, 1], 2, 1, true), 0);
});

test("rebuild selections retain frame names and pingpong occurrence, or fall back", () => {
  const frames = ["idle", "inhale", "blink", "exhale"].map(name => ({name}));
  assert.equal(retainPose(frames, [0, 1, 2, 1], "inhale", 3), 3);
  assert.equal(retainPose(frames, [3, 2, 1], "blink", 0), 1);
  assert.equal(retainPose([frames[2], frames[0]], [0, 1], "idle", 0), 1);
  assert.equal(retainPose(frames, [0, 1], "deleted", 3), 0);
  assert.equal(retainPose([], [], "idle", 0), 0);
  assert.equal(selection(["fox", "arctic fox / 雪?&+#"], "arctic fox / 雪?&+#"), "arctic fox / 雪?&+#");
  assert.equal(selection(["fox", "mint"], "removed"), "fox");
  assert.equal(selection([], "removed"), "");
});

// A small DOM adapter exercises the real controller without a browser dependency.
// It verifies state/event behavior, not CSS layout, image rendering or hit testing.
function documentFixture() {
  const html = readFileSync(new URL("../src/pixaac/preview.html", import.meta.url), "utf8");
  function element() {
    return {
      value: "", checked: false, hidden: false, textContent: "", children: [],
      clientLeft: 0, clientTop: 0, clientWidth: 1000, clientHeight: 600,
      style: {setProperty(key, value) { this[key] = value; }},
      classList: {toggle() {}},
      listeners: {},
      addEventListener(type, callback) { this.listeners[type] = callback; },
      replaceChildren(...children) { this.children = children; },
      removeAttribute(key) { delete this[key]; },
      getBoundingClientRect() { return this.rect || {left: 24, top: 100, width: parseInt(this.style.width), height: parseInt(this.style.height)}; },
    };
  }
  const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map(match => match[1]);
  assert.equal(new Set(ids).size, ids.length, "HTML IDs must be unique");
  const elements = Object.fromEntries(ids.map(id => [id, element()]));
  elements.zoom.value = "8"; elements.opacity.value = "25";
  return {
    elements, defaultView: element(), createElement: element,
    getElementById(id) { assert.ok(elements[id], `HTML element ${id} exists`); return elements[id]; },
  };
}

function sprite(name, width = 40, height = 40, names = ["idle", "inhale", "blink", "exhale"]) {
  return {width, height, frames: names.map((pose, i) => ({name: pose, duration_ms: 100 + i * 20, image: `${name}/${pose}`})),
    tags: names.length > 1 ? [
      {name: "reverse", indices: [3, 2, 1], loop: false},
      {name: "pingpong", indices: [1, 2, 3, 2], loop: true},
    ] : []};
}

test("controller playback, overlays, independent panes, rebuilds and error recovery", async t => {
  t.mock.timers.enable({apis: ["setTimeout"]});
  const doc = documentFixture(), e = doc.elements;
  const encodedName = "arctic fox / 雪?&+#";
  let state = {revision: 1, assets: {fox: sprite("fox"), [encodedName]: sprite("arctic"),
    mint: sprite("mint", 24, 24, ["still"]), shop: sprite("shop", 96, 64)}, building: false, error: null};
  let disconnected = false;
  mountPreview(doc, {search: `?${new URLSearchParams({sprite: encodedName})}`}, async () => {
    if (disconnected) throw Error("offline");
    return {ok: true, json: async () => state};
  });
  await flush();
  assert.equal(e.sprite.value, encodedName);
  assert.equal(e.image.src, "arctic/idle");
  assert.equal(e.comparison.hidden, true);
  assert.match(e.frame.textContent, /idle · 100 ms/);
  e.sprite.value = "fox"; e.sprite.onchange();
  e["show-previous"].checked = true; e["show-previous"].oninput();
  e["show-next"].checked = true; e["show-next"].oninput();
  assert.equal(e["onion-previous"].src, "fox/exhale");
  assert.equal(e["onion-next"].src, "fox/inhale");
  e.opacity.value = "60"; e.opacity.oninput();
  assert.equal(e["onion-next"].style.opacity, .6);
  e.tag.value = "reverse"; e.tag.onchange();
  assert.equal(e.image.src, "fox/exhale");
  assert.equal(e["onion-previous"].hidden, true);
  assert.equal(e["onion-next"].src, "fox/blink");
  e.next.onclick();
  assert.equal(e.image.src, "fox/blink");
  e.next.onclick();
  assert.equal(e.image.src, "fox/inhale");
  assert.equal(e.next.disabled, true);
  assert.equal(e["onion-next"].hidden, true);
  e.play.onclick(); // Restart a completed one-shot, then stop on its last pose.
  assert.equal(e.image.src, "fox/exhale");
  t.mock.timers.tick(160);
  assert.equal(e.image.src, "fox/blink");
  assert.equal(e["onion-previous"].src, "fox/exhale"); // Skins update during playback.
  t.mock.timers.tick(140);
  assert.equal(e.image.src, "fox/inhale");
  t.mock.timers.tick(120);
  assert.equal(e.play.textContent, "Play");
  await flush();
  e.tag.value = "pingpong"; e.tag.onchange();
  e.pose.value = "3"; e.pose.onchange();
  assert.equal(e.image.src, "fox/blink");
  assert.equal(e["onion-previous"].src, "fox/exhale");
  assert.equal(e["onion-next"].src, "fox/inhale");
  e.play.onclick();
  t.mock.timers.tick(140);
  assert.equal(e.image.src, "fox/inhale");
  e.play.onclick(); // Pause cancels future advancement.
  t.mock.timers.tick(150);
  assert.equal(e.image.src, "fox/inhale");
  await flush();
  e.grid.checked = true; e.grid.onchange();
  e.zoom.value = "16"; e.zoom.onchange();
  e.compare.checked = true; e.compare.onchange();
  e["comparison-sprite"].value = "shop"; e["comparison-sprite"].onchange();
  e["comparison-frame"].value = "2"; e["comparison-frame"].onchange();
  assert.equal(e.surface.style.width, "640px");
  assert.equal(e["comparison-surface"].style.width, "1536px");
  assert.equal(e["comparison-surface"].style.height, "1024px");
  assert.equal(e["comparison-image"].src, "shop/blink");
  assert.match(e["comparison-caption"].textContent, /shop · 3\/4 · blink · 140 ms/);
  assert.equal(e["comparison-grid"].hidden, false);
  e["comparison-sprite"].value = "fox"; e["comparison-sprite"].onchange();
  e["comparison-frame"].value = "2"; e["comparison-frame"].onchange();
  assert.equal(e["comparison-image"].src, "fox/blink");
  assert.equal(e.image.src, "fox/inhale"); // Two independent poses of one asset.
  e["comparison-sprite"].value = "shop"; e["comparison-sprite"].onchange();
  e["comparison-frame"].value = "2"; e["comparison-frame"].onchange();
  e.stage.listeners.pointermove({clientX: 24 + 13.5 * 16, clientY: 100 + 15.5 * 16});
  assert.equal(e.coordinates.textContent, "Pixel: (13, 15)");
  e.surface.rect = {left: -8, top: 84, width: 640, height: 640};
  e.stage.listeners.scroll();
  assert.equal(e.coordinates.textContent, "Pixel: (15, 16)");
  e.stage.listeners.pointerleave();
  assert.equal(e.coordinates.textContent, "Pixel: —");
  e.pose.value = "3"; e.pose.onchange();
  // Reorder frames in the comparison, preserve named poses and view settings.
  state = { ...state, revision: 2, assets: {...state.assets, fox: sprite("new-fox"), shop: sprite("new-shop", 96, 64, ["blink", "idle"])} };
  t.mock.timers.tick(400); await flush();
  assert.equal(e.pose.value, "3");
  assert.equal(e.image.src, "new-fox/blink");
  assert.equal(e["onion-previous"].src, "new-fox/exhale");
  assert.equal(e.tag.value, "pingpong");
  assert.equal(e.zoom.value, "16");
  assert.equal(e["pixel-grid"].hidden, false);
  assert.equal(e["comparison-frame"].value, "0");
  assert.equal(e["comparison-image"].src, "new-shop/blink");
  e["show-previous"].checked = false; e["show-previous"].oninput();
  e["show-next"].checked = false; e["show-next"].oninput();
  assert.equal(e["onion-previous"].hidden, true);
  assert.equal(e["onion-next"].hidden, true);
  assert.equal(e.image.src, "new-fox/blink");
  state = {...state, revision: 3, error: "SyntaxError: invalid syntax"};
  t.mock.timers.tick(400); await flush();
  assert.equal(e.error.hidden, false);
  assert.match(e.status.textContent, /last successful preview/);
  assert.equal(e["comparison-image"].src, "new-shop/blink");
  state = {...state, revision: 4, error: null, assets: {mint: sprite("updated", 24, 24, ["still"])}};
  t.mock.timers.tick(400); await flush();
  assert.equal(e.error.hidden, true);
  assert.equal(e.sprite.value, "mint");
  assert.match(e.status.textContent, /Sprite “fox” is unavailable/);
  assert.equal(e["comparison-sprite"].value, "mint");
  assert.equal(e.image.src, "updated/still");
  assert.equal(e["comparison-image"].src, "updated/still");
  assert.equal(e.surface.style.width, "384px");
  assert.equal(e["onion-previous"].hidden, true);
  assert.equal(e["onion-next"].hidden, true);
  disconnected = true; t.mock.timers.tick(400); await flush();
  assert.match(e.status.textContent, /disconnected/);
  disconnected = false; t.mock.timers.tick(400); await flush();
  assert.match(e.status.textContent, /unavailable/);
  state = {...state, revision: 5, assets: {}};
  t.mock.timers.tick(400); await flush();
  assert.equal(e.surface.hidden, true);
  assert.equal(e["comparison-surface"].hidden, true);
  assert.equal(e.image.src, undefined);
  assert.equal(e["comparison-image"].src, undefined);
  assert.equal(e.play.disabled, true);
});

test("missing initial asset falls back to first asset with a visible explanation", async t => {
  t.mock.timers.enable({apis: ["setTimeout"]});
  const doc = documentFixture();
  mountPreview(doc, {search: "?sprite=missing"}, async () => ({
    ok: true, json: async () => ({revision: 1, assets: {fox: sprite("fox")}, building: false, error: null}),
  }));
  await flush();
  assert.equal(doc.elements.sprite.value, "fox");
  assert.equal(doc.elements.image.src, "fox/idle");
  assert.match(doc.elements.status.textContent, /Sprite “missing” is unavailable. Showing “fox”/);
});
