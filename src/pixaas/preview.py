"""Optional local preview: ``python -m pixaas.preview art.py``.

Only this module loads the watcher/server. Authoring scripts expose
``preview_assets`` as a Sprite, a name-to-Sprite mapping, or a zero-argument
function returning either. Their __main__ export blocks are not executed.
"""
from __future__ import annotations

import argparse
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import threading
import traceback

from .sdk import Sprite


def collect_assets(script: Path) -> dict:
    """Execute once in the worker and serialize native-resolution previews."""
    sys.path.insert(0, str(script.parent))
    sys.argv = [str(script)]
    namespace = runpy.run_path(str(script), run_name="__pixaas_preview__")
    assets = namespace.get("preview_assets")
    if callable(assets):
        assets = assets()
    if isinstance(assets, Sprite):
        assets = {assets.name: assets}
    if not isinstance(assets, dict) or not assets:
        raise ValueError("Expose preview_assets as a Sprite or a nonempty dict of named Sprites "
                         "(or a zero-argument function returning either).")
    result = {}
    for name, sprite in assets.items():
        if not isinstance(name, str) or not isinstance(sprite, Sprite):
            raise ValueError("preview_assets must map string names to Sprite objects")
        frames = []
        for i, frame in enumerate(sprite.frames):
            image = BytesIO()
            sprite.render(frame=i).save(image, format="PNG")
            frames.append({
                "name": frame.name, "duration_ms": frame.duration_ms,
                "image": "data:image/png;base64," + base64.b64encode(image.getvalue()).decode(),
            })
        result[name] = {
            "width": sprite.width, "height": sprite.height, "frames": frames,
            "tags": [
                {"name": tag.name, "indices": tag.frame_indices(), "loop": tag.loop}
                for tag in sprite._data.tags
            ],
        }
    return result


IGNORED = {".git", ".venv", "venv", "__pycache__", "node_modules", "out", "build", "dist"}


def fingerprints(roots: tuple[Path, ...]) -> dict[str, tuple[int, int]]:
    """Watch Python sources, including additions/deletions, without reading outputs."""
    files = {}
    for root in roots:
        if root.is_file():
            candidates = [root]
        else:
            candidates = []
            for directory, dirs, names in os.walk(root):
                dirs[:] = [name for name in dirs if name not in IGNORED and not name.startswith(".")]
                candidates.extend(Path(directory) / name for name in names if name.endswith(".py"))
        for path in candidates:
            try:
                stat = path.stat()
                files[str(path)] = (stat.st_mtime_ns, stat.st_size)
            except FileNotFoundError:
                pass
    return files


class Preview:
    def __init__(self, script: Path, roots: tuple[Path, ...], *, timeout: float = 30):
        self.script, self.roots, self.timeout = script, roots, timeout
        self.lock = threading.Lock()
        self.state = {"revision": 0, "assets": {}, "error": None, "building": True}
        self.stopped = threading.Event()

    def snapshot(self) -> dict:
        with self.lock:
            return dict(self.state)

    def rebuild(self) -> None:
        with self.lock:
            self.state["building"] = True
        try:
            with tempfile.TemporaryDirectory(prefix="pixaas-preview-") as directory:
                output = Path(directory) / "preview.json"
                # A fresh process avoids stale imports and accumulated authoring state.
                # A fresh bytecode cache also catches same-size edits in one second.
                env = {**os.environ, "PYTHONPYCACHEPREFIX": str(Path(directory) / "pycache")}
                completed = subprocess.run(
                    [sys.executable, "-m", "pixaas.preview", "--worker", str(self.script), str(output)],
                    capture_output=True, text=True, timeout=self.timeout, env=env,
                )
                if completed.returncode:
                    raise RuntimeError((completed.stderr or completed.stdout or "Script failed")[-16000:])
                assets = json.loads(output.read_text())
            with self.lock:
                self.state.update(assets=assets, error=None)
        except Exception as error:
            with self.lock:
                self.state["error"] = str(error)
        finally:
            with self.lock:
                self.state["revision"] += 1
                self.state["building"] = False

    def watch(self) -> None:
        previous = None
        while not self.stopped.is_set():
            current = fingerprints(self.roots)
            if current != previous:
                # Wait for a short quiet period before executing files being saved.
                if self.stopped.wait(0.15):
                    break
                settled = fingerprints(self.roots)
                if settled != current:
                    continue
                previous = current
                self.rebuild()
            self.stopped.wait(0.25)


def make_server(preview: Preview, port: int) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/":
                content = Path(__file__).with_name("preview.html").read_bytes()
                content_type = "text/html; charset=utf-8"
            elif self.path == "/state":
                content = json.dumps(preview.snapshot()).encode()
                content_type = "application/json"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, *args):
            pass

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "--worker":
        try:
            Path(args[2]).write_text(json.dumps(collect_assets(Path(args[1]))))
        except BaseException:
            traceback.print_exc()
            raise SystemExit(1)
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("script", type=Path)
    parser.add_argument("--port", type=int, default=8765, help="localhost port (default: 8765)")
    parser.add_argument("--sprite", help="initial preview asset name")
    parser.add_argument("--watch", type=Path, action="append", default=[],
                        help="additional source file/directory to watch; repeatable")
    options = parser.parse_args(args)
    script = options.script.resolve()
    if not script.is_file():
        parser.error(f"no script at {script}")
    root = Path.cwd() if script.is_relative_to(Path.cwd()) else script.parent
    preview = Preview(script, (root, *(path.resolve() for path in options.watch)))
    server = make_server(preview, options.port)
    worker = threading.Thread(target=preview.watch, daemon=True)
    worker.start()
    from urllib.parse import urlencode

    query = "?" + urlencode({"sprite": options.sprite}) if options.sprite else ""
    print(f"PixaaS preview: http://127.0.0.1:{server.server_port}/{query}", flush=True)
    print(f"Watching {root} — Ctrl-C to stop", flush=True)
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        preview.stopped.set()
        server.server_close()
        worker.join(timeout=preview.timeout + 1)


if __name__ == "__main__":
    main()
