import base64
from io import BytesIO
import threading
import time

from PIL import Image

from pixaas.preview import Preview, fingerprints


def wait_until(predicate):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.025)
    raise AssertionError("preview did not update within 10 seconds")


def test_watch_local_modules_errors_and_recovery(tmp_path):
    module = tmp_path / "colors.py"
    module.write_text('COLOR = "#f00"\n')
    script = tmp_path / "art.py"
    script.write_text('''from pixaas import Sprite
from colors import COLOR

def preview_assets():
    s = Sprite(2, 2, palette={"r": COLOR})
    s.layer().pixel(0, 0, "r")
    s.add_frame("blink", copy_from=0, duration_ms=140)
    s.tag("reverse", 0, 1, direction="reverse", loop=False)
    return {"one": s, "two": s.copy()}

if __name__ == "__main__":
    raise RuntimeError("batch exports must not run")
''')
    preview = Preview(script, (tmp_path,))
    thread = threading.Thread(target=preview.watch)
    thread.start()
    try:
        wait_until(lambda: preview.snapshot()["revision"] >= 1)
        first = preview.snapshot()
        assert first["error"] is None
        assert list(first["assets"]) == ["one", "two"]
        sprite = first["assets"]["one"]
        assert sprite["frames"][1]["duration_ms"] == 140
        assert sprite["tags"] == [{"name": "reverse", "indices": [1, 0], "loop": False}]
        module.write_text('COLOR = "#00f"\n')  # Same size; no stale module/bytecode cache.
        wait_until(lambda: preview.snapshot()["revision"] >= 2)
        second = preview.snapshot()
        assert second["error"] is None
        image = second["assets"]["one"]["frames"][0]["image"]
        with Image.open(BytesIO(base64.b64decode(image.split(",")[1]))) as png:
            assert png.getpixel((0, 0)) == (0, 0, 255, 255)
        script.write_text(script.read_text().replace("duration_ms=140", "duration_ms=180"))
        wait_until(lambda: preview.snapshot()["revision"] >= 3)
        second = preview.snapshot()
        assert second["assets"]["one"]["frames"][1]["duration_ms"] == 180
        module.write_text('COLOR =\n')
        wait_until(lambda: preview.snapshot()["revision"] >= 4)
        failed = preview.snapshot()
        assert "SyntaxError" in failed["error"]
        assert failed["assets"] == second["assets"]
        module.write_text('COLOR = "#0f0"\n')
        wait_until(lambda: preview.snapshot()["revision"] >= 5)
        assert preview.snapshot()["error"] is None
        assert preview.snapshot()["assets"] != second["assets"]
    finally:
        preview.stopped.set()
        thread.join(timeout=35)
    assert not thread.is_alive()


def test_missing_asset_contract_and_timeout(tmp_path):
    script = tmp_path / "art.py"
    script.write_text("pass")
    preview = Preview(script, (tmp_path,))
    preview.rebuild()
    assert "Expose preview_assets" in preview.snapshot()["error"]
    script.write_text("import time; time.sleep(10)")
    preview.timeout = 0.1
    preview.rebuild()
    assert "timed out" in preview.snapshot()["error"]
    assert preview.snapshot()["assets"] == {}


def test_watch_tracks_added_and_deleted_sources_but_ignores_outputs(tmp_path):
    before = fingerprints((tmp_path,))
    source = tmp_path / "new.py"
    source.write_text("pass")
    assert fingerprints((tmp_path,)) != before
    source.unlink()
    assert fingerprints((tmp_path,)) == before
    for directory in (".venv", "out", "__pycache__"):
        (tmp_path / directory).mkdir()
        (tmp_path / directory / "ignored.py").write_text("pass")
    assert fingerprints((tmp_path,)) == before
