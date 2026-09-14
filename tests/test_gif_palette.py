from PIL import Image

from pixaac import Sprite
from pixaac.render import _to_gif_frame


def test_gif_preserves_close_colors_across_frame_palettes(tmp_path):
    sprite = Sprite(3, 1, palette={"a": "#6b788a", "b": "#62738a", "c": "#63738a"})
    sprite.layer().set_grid("ab.")
    sprite.add_frame("next", duration_ms=120).layer("base").set_grid(".ca")
    path = sprite.export_gif(tmp_path / "colors.gif")
    with Image.open(path) as image:
        assert image.n_frames == 2
        for index in range(2):
            image.seek(index)
            assert image.convert("RGBA").tobytes() == sprite.render(frame=index).tobytes()


def test_exact_palette_ignores_hidden_rgb_and_supports_255_visible_colors():
    image = Image.new("RGBA", (510, 1))
    visible = [(i, 1, 2, 255) for i in range(255)]
    hidden = [(i, 50, 70, 0) for i in range(255)]
    image.putdata(visible + hidden)
    decoded = _to_gif_frame(image).convert("RGBA")
    assert list(decoded.get_flattened_data())[:255] == visible
    assert all(pixel[3] == 0 for pixel in list(decoded.get_flattened_data())[255:])


def test_gif_alpha_threshold_and_all_transparent_image():
    image = Image.new("RGBA", (3, 1))
    image.putdata([(20, 30, 40, 127), (20, 30, 40, 128), (20, 30, 40, 255)])
    assert list(_to_gif_frame(image).convert("RGBA").get_flattened_data()) == [
        (0, 0, 0, 0), (20, 30, 40, 255), (20, 30, 40, 255)]
    empty = Image.new("RGBA", (2, 2))
    assert _to_gif_frame(empty).convert("RGBA").tobytes() == empty.tobytes()


def test_large_palette_falls_back_to_quantization_with_transparency():
    image = Image.new("RGBA", (257, 1))
    image.putdata([(i, (i * 3) % 256, 20, 255) for i in range(256)] + [(0, 0, 0, 0)])
    result = _to_gif_frame(image)
    assert len(result.getcolors()) <= 256
    rgba = result.convert("RGBA")
    assert rgba.getpixel((256, 0))[3] == 0
    assert all(rgba.getpixel((x, 0))[3] == 255 for x in range(256))
