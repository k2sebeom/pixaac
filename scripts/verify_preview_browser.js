// Pass this file's absolute path as `filename` to browser-use's
// browser_run_code_unsafe tool. It evaluates this function with its Page.
// Requires assets/tideglass/build.py to be running in the preview server.
async (page, url = "http://127.0.0.1:8876/?sprite=station") => {
  const passed = [];
  const assert = (condition, message) => {
    if (!condition) throw new Error(message);
  };
  const select = (name, value) =>
    page.getByRole("combobox", {name, exact: true}).selectOption(value);
  const check = (name, checked) =>
    page.getByRole("checkbox", {name, exact: true}).setChecked(checked);
  const button = name => page.getByRole("button", {name, exact: true});
  await page.setViewportSize({width: 1280, height: 900});
  await page.goto(url);
  await page.waitForFunction(() => document.querySelector("#sprite").value === "station");
  assert(await page.locator("#error").isHidden(), "Authoring error on initial load");
  passed.push("printed URL selects station");

  await select("Zoom", "4");
  await button("Next frame").click();
  assert((await page.locator("#frame").innerText()).includes("tide-1"), "Next frame");
  await button("Previous frame").click();
  assert((await page.locator("#frame").innerText()).includes("frame0"), "Previous frame");
  await button("Play").click();
  await page.waitForFunction(() => document.querySelector("#pose").value !== "0");
  await button("Pause").click();
  const paused = await page.locator("#frame").innerText();
  await page.waitForTimeout(550); // More than two 240 ms frames.
  assert(await page.locator("#frame").innerText() === paused, "Pause holds a pose");
  await select("Pose", "0");
  passed.push("play, pause, and frame stepping");

  await check("Pixel grid", true);
  for (const zoom of [1, 2, 4, 8, 12, 16]) {
    await select("Zoom", String(zoom));
    await page.locator("#stage").scrollIntoViewIfNeeded();
    for (const [x, y] of [[0, 0], [159, 0], [0, 95], [159, 95]]) {
      await page.locator("#stage").evaluate((stage, corner) => {
        stage.scrollLeft = corner[0] ? stage.scrollWidth : 0;
        stage.scrollTop = corner[1] ? stage.scrollHeight : 0;
      }, [x, y]);
      const bounds = await page.locator("#surface").boundingBox();
      await page.mouse.move(bounds.x + (x + 0.5) * zoom, bounds.y + (y + 0.5) * zoom);
      assert(await page.locator("#coordinates").innerText() === `Pixel: (${x}, ${y})`,
        `Coordinate (${x}, ${y}) at ${zoom}x`);
    }
    const grid = await page.locator("#pixel-grid").evaluate(element => ({
      size: getComputedStyle(element).backgroundSize,
      image: getComputedStyle(element).backgroundImage,
    }));
    assert(grid.size.split(", ").every(size => size === `${zoom}px ${zoom}px`), "Grid spacing");
    assert((grid.image === "none") === (zoom === 1), "Native grid suppresses interior lines");
  }
  await page.mouse.move(1, 1);
  assert(await page.locator("#coordinates").innerText() === "Pixel: —", "Pointer exit clears");
  passed.push("all four corners at every zoom, scrolling, grid, and pointer exit");

  await select("Sprite", "cutter");
  await select("Zoom", "4");
  await page.locator("#stage").evaluate(stage => { stage.scrollLeft = 0; stage.scrollTop = 0; });
  const smaller = await page.locator("#surface").boundingBox();
  await page.mouse.move(smaller.x + 31.5 * 4, smaller.y + 23.5 * 4);
  assert(await page.locator("#coordinates").innerText() === "Pixel: (31, 23)", "Smaller asset mapping");
  const rendering = await page.locator("#image").evaluate(async image => {
    await image.decode();
    return {width: image.naturalWidth, rendering: getComputedStyle(image).imageRendering};
  });
  assert(rendering.width === 32 && rendering.rendering === "pixelated", "Native pixel rendering");
  passed.push("coordinates after asset size changes and nearest-neighbor rendering");

  await check("Compare", true);
  await select("Compare sprite", "storm-beacon");
  await select("Compare frame", "2");
  await button("Play").click();
  await page.waitForTimeout(550);
  assert((await page.locator("#comparison-caption").innerText()).includes("sweep-2"), "Comparison holds");
  await button("Pause").click();
  await check("Previous pose (pink)", true);
  await check("Next pose (cyan)", true);
  assert(await page.locator("#onion-previous").isVisible(), "Previous skin visible");
  assert(await page.locator("#onion-next").isVisible(), "Next skin visible");
  await page.getByRole("slider", {name: "Onion opacity", exact: true}).fill("40");
  assert(await page.locator("#onion-next").evaluate(e => getComputedStyle(e).opacity) === "0.4",
    "Onion opacity applies");
  passed.push("independent comparison and looping onion skins");

  for (const width of [320, 390, 650, 651, 1280]) {
    await page.setViewportSize({width, height: 900});
    const layout = await page.evaluate(() => ({
      width: document.documentElement.scrollWidth,
      stages: [...document.querySelectorAll(".stage")].map(e => {
        const r = e.getBoundingClientRect();
        return {left: r.left, top: r.top};
      }),
    }));
    assert(layout.width === width, `Document overflows at ${width}px`);
    const [first, second] = layout.stages;
    assert(width <= 650 ? first.left === second.left && second.top > first.top :
      first.top === second.top && second.left > first.left, `Comparison layout at ${width}px`);
  }
  passed.push("responsive layout at 320, 390, 650, 651, and 1280px");

  const missing = await page.evaluate(address => {
    const target = new URL(address);
    target.searchParams.set("sprite", "missing / asset");
    return target.href;
  }, url);
  await page.goto(missing);
  await page.waitForFunction(() => document.querySelector("#status").textContent.includes("unavailable"));
  assert(await page.locator("#sprite").inputValue() === "station", "Missing-name fallback");
  passed.push("encoded missing-name URL falls back with explanation");

  await page.goto(url);
  await page.waitForFunction(() => document.querySelector("#sprite").value === "station");
  await select("Zoom", "4");
  return {passed};
}
