// These helpers also run in Node's test runner; the preview needs no JS dependencies.
export function pixelAt(clientX, clientY, rect, width, height, clip = null) {
  if (!rect.width || !rect.height) return null;
  if (clip && (clientX < clip.left || clientY < clip.top ||
      clientX >= clip.left + clip.width || clientY >= clip.top + clip.height)) return null;
  const x = Math.floor((clientX - rect.left) * width / rect.width);
  const y = Math.floor((clientY - rect.top) * height / rect.height);
  return x >= 0 && y >= 0 && x < width && y < height ? [x, y] : null;
}

export function neighbor(indices, position, delta, loop) {
  const target = position + delta;
  if (!indices.length || (!loop && (target < 0 || target >= indices.length))) return null;
  const index = indices[(target + indices.length) % indices.length];
  return index === indices[position] ? null : index;
}

export function advance(indices, position, delta, loop) {
  if (!indices.length) return 0;
  return loop ? (position + delta + indices.length) % indices.length :
    Math.max(0, Math.min(indices.length - 1, position + delta));
}

export function retainPose(frames, indices, name, position = 0) {
  // Keep the occurrence too: a pingpong pose may appear twice in the sequence.
  if (name !== undefined && frames[indices[position]]?.name === name) return position;
  const found = indices.findIndex(index => frames[index]?.name === name);
  return found < 0 ? 0 : found;
}

export function selection(names, desired) {
  return names.includes(desired) ? desired : (names[0] ?? "");
}

export function mountPreview(document, location, fetchState = fetch) {
  const $ = id => document.getElementById(id);
  let assets = {}, revision = -1, position = 0, playing = false, timer;
  let desired = new URLSearchParams(location.search).get("sprite");
  const asset = () => assets[$("sprite").value];
  const compared = () => assets[$("comparison-sprite").value];
  function sequence() {
    const current = asset();
    return current?.tags.find(tag => tag.name === $("tag").value) ||
      {indices: current?.frames.map((_, i) => i) || [], loop: true};
  }
  function options(element, values, selected) {
    element.replaceChildren(...values.map(([value, label]) => {
      const option = document.createElement("option");
      option.value = String(value); option.textContent = label; return option;
    }));
    element.value = selection(values.map(([value]) => String(value)), selected == null ? null : String(selected));
    element.disabled = !values.length;
  }
  function tags() {
    options($("tag"), [["", "All frames"], ...(asset()?.tags || []).map(t => [t.name, t.name])], $("tag").value);
  }
  function poses() {
    options($("pose"), sequence().indices.map((index, i) =>
      [i, `${asset().frames[index].name} (${index + 1})`]), position);
  }
  function comparisonFrames(name, oldPosition = 0) {
    const frames = compared()?.frames || [], indices = frames.map((_, i) => i);
    options($("comparison-frame"), frames.map((frame, i) => [i, frame.name]),
      retainPose(frames, indices, name, oldPosition));
  }
  const pointers = new Map();
  function coordinates(surfaceId, outputId, current) {
    const surface = $(surfaceId), pointer = pointers.get(surfaceId);
    const stage = $(surfaceId === "surface" ? "stage" : "comparison-stage");
    const bounds = stage.getBoundingClientRect();
    const clip = {left: bounds.left + stage.clientLeft, top: bounds.top + stage.clientTop,
      width: stage.clientWidth, height: stage.clientHeight};
    const pixel = current && pointer && !surface.hidden ?
      pixelAt(pointer.x, pointer.y, surface.getBoundingClientRect(), current.width, current.height, clip) : null;
    $(outputId).textContent = pixel ? `Pixel: (${pixel[0]}, ${pixel[1]})` : "Pixel: —";
  }
  function updateCoordinates() {
    coordinates("surface", "coordinates", asset());
    coordinates("comparison-surface", "comparison-coordinates", $("compare").checked ? compared() : null);
  }
  for (const [stageId, surfaceId] of [["stage", "surface"], ["comparison-stage", "comparison-surface"]]) {
    $(stageId).addEventListener("pointermove", event => {
      pointers.set(surfaceId, {x: event.clientX, y: event.clientY}); updateCoordinates();
    });
    $(stageId).addEventListener("pointerleave", () => { pointers.delete(surfaceId); updateCoordinates(); });
    $(stageId).addEventListener("scroll", updateCoordinates);
  }
  // A stationary pointer must be remapped when the page scrolls or layout changes.
  document.defaultView.addEventListener("scroll", updateCoordinates, true);
  document.defaultView.addEventListener("resize", updateCoordinates);

  function pane(surfaceId, imageId, gridId, captionId, name, current, index) {
    const frame = current?.frames[index], surface = $(surfaceId);
    surface.hidden = !frame;
    if (!frame) {
      $(imageId).removeAttribute("src");
      $(captionId).textContent = "No frames available";
      return;
    }
    const zoom = Number($("zoom").value);
    surface.style.width = `${current.width * zoom}px`;
    surface.style.height = `${current.height * zoom}px`;
    surface.style.setProperty("--zoom", `${zoom}px`);
    surface.classList.toggle("native", zoom === 1);
    $(imageId).src = frame.image;
    $(gridId).hidden = !$("grid").checked;
    $(captionId).textContent = `${name} · ${index + 1}/${current.frames.length} · ${frame.name} · ${frame.duration_ms} ms`;
  }
  function overlays() {
    const current = asset(), seq = sequence();
    for (const [side, delta] of [["previous", -1], ["next", 1]]) {
      const image = $(`onion-${side}`);
      const index = neighbor(seq.indices, position, delta, seq.loop);
      image.hidden = !$(`show-${side}`).checked || index === null || !current;
      image.style.opacity = Number($("opacity").value) / 100;
      if (!image.hidden) image.src = current.frames[index].image;
      else image.removeAttribute("src");
    }
    $("opacity-value").textContent = `${$("opacity").value}%`;
  }
  function drawComparison() {
    $("comparison").hidden = !$("compare").checked;
    $("panes").classList.toggle("comparing", $("compare").checked);
    pane("comparison-surface", "comparison-image", "comparison-grid", "comparison-caption",
      $("comparison-sprite").value, compared(), Number($("comparison-frame").value));
    updateCoordinates();
  }
  function draw() {
    clearTimeout(timer);
    const current = asset(), seq = sequence(), available = !!seq.indices.length;
    if (!available) playing = false;
    position = Math.max(0, Math.min(position, seq.indices.length - 1));
    $("play").disabled = !available;
    $("previous").disabled = !available || (!seq.loop && position === 0);
    $("next").disabled = !available || (!seq.loop && position === seq.indices.length - 1);
    $("play").textContent = playing ? "Pause" : "Play";
    $("pose").value = String(position);
    pane("surface", "image", "pixel-grid", "frame", $("sprite").value, current, seq.indices[position]);
    overlays(); drawComparison();
    if (playing) timer = setTimeout(() => {
      if (position === seq.indices.length - 1 && !seq.loop) playing = false;
      else position = advance(seq.indices, position, 1, seq.loop);
      draw();
    }, current.frames[seq.indices[position]].duration_ms);
  }
  $("sprite").onchange = () => { desired = $("sprite").value; position = 0; tags(); poses(); draw(); };
  $("tag").onchange = () => { position = 0; poses(); draw(); };
  $("pose").onchange = () => { playing = false; position = Number($("pose").value); draw(); };
  for (const id of ["zoom", "grid"]) $(id).onchange = draw;
  $("compare").onchange = drawComparison;
  for (const id of ["show-previous", "show-next", "opacity"]) $(id).oninput = overlays;
  $("comparison-sprite").onchange = () => { comparisonFrames(); drawComparison(); };
  $("comparison-frame").onchange = drawComparison;
  $("play").onclick = () => {
    if (!playing && position === sequence().indices.length - 1 && !sequence().loop) position = 0;
    playing = !playing; draw();
  };
  function step(delta) {
    playing = false;
    const seq = sequence();
    position = advance(seq.indices, position, delta, seq.loop); draw();
  }
  $("previous").onclick = () => step(-1);
  $("next").onclick = () => step(1);
  async function poll() {
    try {
      const response = await fetchState("/state", {cache: "no-store"});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const state = await response.json();
      if (state.revision !== revision) {
        const oldName = asset()?.frames[sequence().indices[position]]?.name;
        const oldComparedIndex = Number($("comparison-frame").value);
        const oldComparedName = compared()?.frames[oldComparedIndex]?.name;
        revision = state.revision;
        assets = state.assets;
        const names = Object.keys(assets).map(name => [name, name]);
        options($("sprite"), names, desired);
        options($("comparison-sprite"), names, $("comparison-sprite").value);
        tags();
        position = retainPose(asset()?.frames || [], sequence().indices, oldName, position);
        poses(); comparisonFrames(oldComparedName, oldComparedIndex); draw();
        $("error").hidden = !state.error;
        $("error").textContent = state.error || "";
      }
      const missing = desired && !Object.hasOwn(assets, desired) && Object.keys(assets).length;
      $("status").textContent = state.building ? "Building preview…" :
        state.error ? "Script error — showing the last successful preview." :
        missing ? `Sprite “${desired}” is unavailable. Showing “${$("sprite").value}”; select an available sprite.` :
        "Watching Python sources · save a file to refresh";
    } catch (error) {
      $("status").textContent = "Preview disconnected — retrying…";
    }
    setTimeout(poll, 400);
  }
  draw(); poll();
}

if (typeof document !== "undefined") mountPreview(document, location);
