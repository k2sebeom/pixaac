from pathlib import Path
import runpy

from PIL import Image

from pixaac import Sprite


def trial():
    script = Path(__file__).resolve().parents[1] / "assets" / "tideglass" / "build.py"
    return runpy.run_path(str(script))


def test_tideglass_delivery_round_trips_and_reproduces(tmp_path):
    factory = trial()["preview_assets"]
    original, rebuilt = factory(), factory()
    for name, sprite in original.items():
        assert sprite.validate() == []
        snapshot = Sprite.load(sprite.save(tmp_path / f"{name}.sprite.json"))
        sheet, _ = sprite.export_sheet(
            tmp_path / f"{name}.png", columns=2, extrude=2, padding=1, scale=2)
        restored = Sprite.from_png(sheet)
        assert snapshot.layer_names() == sprite.layer_names()
        for candidate in (rebuilt[name], snapshot, restored):
            assert [(f.name, f.duration_ms) for f in candidate.frames] == [
                (f.name, f.duration_ms) for f in sprite.frames]
            for index in range(len(sprite.frames)):
                assert candidate.render(frame=index).tobytes() == sprite.render(frame=index).tobytes()
        for kind in ("gif", "apng"):
            path = getattr(sprite, f"export_{kind}")(tmp_path / f"{name}.{kind}")
            with Image.open(path) as image:
                assert image.info["loop"] == 0
                assert image.n_frames == len(sprite.frames)
                for index, frame in enumerate(sprite.frames):
                    image.seek(index)
                    assert image.info["duration"] == frame.duration_ms
                    assert image.convert("RGBA").tobytes() == sprite.render(frame=index).tobytes()


def test_storm_composition_preserves_pixels_and_material_roles():
    module = trial()
    assets = module["preview_assets"]()
    storm, normal = assets["storm-beacon"], assets["lighthouse"]
    target = Sprite(32, 48, palette=module["PALETTE"])
    module["place"](target.frame(), storm, 0, 0, mapping={"L": "Q", "G": "U"})
    assert target.render().tobytes() == storm.render().tobytes()
    assert target.palette.rgba("L") == normal.palette.rgba("L")
    assert target.palette.rgba("Q") == storm.palette.rgba("L")
    for index in range(4):
        for name in ("masonry", "roof", "balcony"):
            assert storm.frame(index).get_layer(name).rows() == normal.frame(index).get_layer(name).rows()
    # A bob changes the silhouette but never clips the cutter at the canvas edge.
    boat = assets["cutter"]
    for index in range(4):
        x0, y0, x1, y1 = boat.render(frame=index).getbbox()
        assert 0 < x0 < x1 < boat.width
        assert 0 < y0 < y1 <= boat.height
