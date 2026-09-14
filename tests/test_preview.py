import base64
from io import BytesIO
import json
from pathlib import Path
import queue
import shutil
import signal
import subprocess
import sys
import threading
import time
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import urlopen

from PIL import Image
import pytest

from pixaac.preview import Preview, fingerprints


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
    script.write_text('''from pixaac import Sprite
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


@pytest.mark.parametrize("name", ["fox", "arctic fox / 雪?&+#"])
def test_exact_printed_cli_url(tmp_path, name):
    script = tmp_path / "art.py"
    script.write_text(f'from pixaac import Sprite\npreview_assets = {{{name!r}: Sprite(2, 2)}}\n')
    process = subprocess.Popen(
        [sys.executable, "-m", "pixaac.preview", str(script), "--port", "0", "--sprite", name],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    lines = queue.Queue()
    reader = threading.Thread(target=lambda: [lines.put(line) for line in process.stdout], daemon=True)
    reader.start()
    try:
        printed = lines.get(timeout=10).strip()
        assert printed.startswith("PixaaC preview: "), printed
        url = printed.removeprefix("PixaaC preview: ")
        parsed = urlsplit(url)
        assert parse_qs(parsed.query) == {"sprite": [name]}
        with urlopen(url, timeout=5) as response:
            assert response.status == 200
            assert b'<select id="sprite"' in response.read()
        root = f"{parsed.scheme}://{parsed.netloc}"
        with urlopen(root + "/preview.mjs?cache=1", timeout=5) as response:
            assert response.headers.get_content_type() == "text/javascript"
            assert b"URLSearchParams(location.search)" in response.read()
        with urlopen(root + "/state?cache=1", timeout=5) as response:
            assert "assets" in json.load(response)
        with pytest.raises(HTTPError) as error:
            urlopen(root + "/missing?sprite=fox", timeout=5)
        assert error.value.code == 404
    finally:
        process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        reader.join(timeout=2)
        process.stdout.close()


def test_preview_client_regressions():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js 22+ is needed for preview client tests")
    result = subprocess.run(
        [node, "--test", str(Path(__file__).with_name("preview.test.mjs"))],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
