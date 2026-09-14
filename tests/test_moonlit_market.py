from pathlib import Path
import runpy

from pixaac import Sprite


def assets():
    script = Path(__file__).resolve().parents[1] / "examples" / "moonlit_market.py"
    return runpy.run_path(str(script))["preview_assets"]()


def test_market_assets_reproduce_and_round_trip(tmp_path):
    originals, repeated = assets(), assets()
    assert list(originals) == ["fox", "arctic", "mint", "rose", "amber", "shop"]
    for name, sprite in originals.items():
        assert sprite.validate() == []
        snapshot = tmp_path / f"{name}.sprite.json"
        sprite.save(snapshot)
        sheet, _ = sprite.export_sheet(tmp_path / f"{name}.png", columns=4, padding=1)
        restored = Sprite.load(snapshot)
        assert restored.layer_names() == sprite.layer_names()
        for candidate in (restored, Sprite.from_png(sheet), repeated[name]):
            assert [(frame.name, frame.duration_ms) for frame in candidate.frames] == [
                (frame.name, frame.duration_ms) for frame in sprite.frames]
            for i in range(len(sprite.frames)):
                assert candidate.render(frame=i).tobytes() == sprite.render(frame=i).tobytes()


def test_fox_material_roles_and_independent_motion():
    variants = assets()
    fox, arctic = variants["fox"], variants["arctic"]
    for i in range(len(fox.frames)):
        fox_image, arctic_image = fox.render(frame=i), arctic.render(frame=i)
        # Accessory pixels retain both their geometry and light colors across palettes.
        lantern = fox.frame(i).get_layer("lantern").rows()
        assert lantern == arctic.frame(i).get_layer("lantern").rows()
        for y, row in enumerate(lantern):
            for x, key in enumerate(row):
                if key != ".":
                    assert fox_image.getpixel((x, y)) == arctic_image.getpixel((x, y))
        for layer in ("feet", "shadow"):
            assert fox.frame(i).get_layer(layer).rows() == fox.frame(0).get_layer(layer).rows()
    # The inhalation reshapes the tail; it is not a rigid body translation.
    original_tail = fox.frame(0).get_layer("tail").rows()
    curled_tail = fox.frame("breathe-in").get_layer("tail").rows()
    assert sum(key != "." for row in original_tail for key in row) != sum(
        key != "." for row in curled_tail for key in row)
    assert fox.frame("exhale").get_layer("scarf").rows() != fox.frame(0).get_layer("scarf").rows()
