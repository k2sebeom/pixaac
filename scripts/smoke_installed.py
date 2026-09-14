"""Run with an isolated wheel installation; no checkout imports are needed."""
from importlib.resources import files
from pathlib import Path
import tempfile
from threading import Thread
from urllib.request import urlopen

import pixaac
from pixaac import Sprite
from pixaac.preview import Preview, make_server


def main():
    checkout = Path(__file__).resolve().parents[1]
    assert not Path(pixaac.__file__).resolve().is_relative_to(checkout), (
        "run this check against an isolated installed wheel, not the source tree"
    )
    for filename in ("preview.html", "preview.mjs"):
        assert files("pixaac").joinpath(filename).read_bytes(), filename
    with tempfile.TemporaryDirectory(prefix="pixaac-release-") as directory:
        root = Path(directory)
        source = Sprite(2, 2, palette={"a": "#6b788a", "b": "#62738a"})
        source.layer().set_grid("ab\n..")
        sprite = Sprite(4, 4)
        sprite.layer().blit(source.layer(), x=1, y=1)
        sprite.add_frame("raised", copy_from=0).layer("base").shift(0, -1)
        sprite.tag("idle", 0, 1)
        path, _ = sprite.export_sheet(root / "sheet.png", padding=1, extrude=1)
        restored = Sprite.from_png(path)
        for index in range(2):
            assert restored.render(frame=index).tobytes() == sprite.render(frame=index).tobytes()
        sprite.export_gif(root / "idle.gif")
        sprite.export_apng(root / "idle.png")
        script = root / "art.py"
        script.write_text(
            "from pixaac import Sprite\n"
            "preview_assets = {'release asset': Sprite(2, 2)}\n",
            encoding="utf-8",
        )
        preview = Preview(script, (root,))
        preview.rebuild()
        state = preview.snapshot()
        assert state["error"] is None, state["error"]
        assert "release asset" in state["assets"]
        server = make_server(preview, 0)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}"
            for route in ("/?sprite=release%20asset", "/preview.mjs", "/state"):
                with urlopen(base + route, timeout=5) as response:
                    assert response.status == 200
                    assert response.read()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
    print("Installed wheel: authoring, exports, preview worker, HTTP, and resources passed.")


if __name__ == "__main__":
    main()
