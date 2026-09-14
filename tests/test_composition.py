import pytest

from pixaac import Sprite, SpriteError


def test_blit_imports_material_roles_without_mutating_source():
    source = Sprite(3, 2, palette={"F": "#abc", "L": "#abc", "s": "#1238"})
    source.layer().set_grid("FL.\n.s.")
    target = Sprite(5, 3)
    assert target.layer().blit(source.layer(), x=1, y=1) == 3
    assert target.layer().rows() == [".....", ".FL..", "..s.."]
    assert target.palette.rgba("s") == (17, 34, 51, 136)
    target.palette.set("F", "#fff")
    target.layer().pixel(1, 1, ".")
    assert source.layer().rows() == ["FL.", ".s."]
    assert source.palette.rgba("F") == (170, 187, 204, 255)
    assert target.palette.rgba("L") == (170, 187, 204, 255)


def test_conflict_is_atomic_and_explicit_mapping_preserves_or_recolors():
    source = Sprite(2, 1, palette={"a": "#f00", "b": "#0f0"})
    source.layer().set_grid("ab")
    target = Sprite(2, 1, palette={"b": "#00f"})
    target.layer().set_grid("bb")
    original_palette = target.palette.to_json()
    with pytest.raises(SpriteError, match="palette conflict"):
        target.layer().blit(source.layer())
    assert target.palette.to_json() == original_palette
    assert target.layer().rows() == ["bb"]
    # A new mapped key imports source color; an existing mapped key recolors.
    assert target.layer().blit(source.layer(), mapping={"b": "G"}) == 2
    assert target.render().tobytes() == source.render().tobytes()
    target.layer().blit(source.layer(), mapping={"a": "b", "b": "b"})
    assert target.layer().rows() == ["bb"]


def test_clipping_transparency_and_overlapping_self_copy():
    source = Sprite(4, 1, palette={"a": "#f00", "b": "#0f0", "z": "#1230"})
    source.layer().set_grid("abz.")
    target = Sprite(4, 1, palette={"c": "#00f"})
    target.layer().set_grid("cccc")
    assert target.layer().blit(source.layer(), x=-1) == 1
    assert target.layer().rows() == ["bccc"]
    assert "a" not in target.palette.colors  # Clipped keys are not imported.
    assert target.layer().blit(source.layer(), x=-1, overwrite=True) == 3
    assert target.layer().rows() == ["b..c"]
    assert target.layer().blit(source.layer(), y=10) == 0
    assert source.layer().blit(source.layer(), x=1, overwrite=True) == 3
    assert source.layer().rows() == ["aab."]


@pytest.mark.parametrize("options", [
    {"x": 0.5}, {"y": True}, {"mapping": {"a": "two"}},
    {"mapping": {"missing": "a"}}, {"mapping": {".": "a"}},
])
def test_invalid_blit_options_do_not_write(options):
    source = Sprite(1, 1, palette={"a": "#fff"})
    source.layer().pixel(0, 0, "a")
    target = Sprite(1, 1)
    with pytest.raises(SpriteError):
        target.layer().blit(source.layer(), **options)
    assert target.palette.to_json() == {".": None}
    assert target.layer().rows() == ["."]


def test_blit_rejects_removed_handles():
    sprite = Sprite(1, 1)
    removed = sprite.layer("temporary")
    sprite.remove_layer("temporary")
    with pytest.raises(SpriteError, match="removed"):
        sprite.layer().blit(removed)
    with pytest.raises(SpriteError, match="removed"):
        removed.blit(sprite.layer())
