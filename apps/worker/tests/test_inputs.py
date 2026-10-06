"""Model scripts get images in a format they can read (AVIF uploads failed in most detectors)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from sml_worker.inputs import script_input


def test_avif_is_handed_over_as_a_png_with_the_same_pixels(tmp_path: Path) -> None:
    src = tmp_path / "source.avif"
    Image.new("RGB", (64, 48), (200, 30, 90)).save(src, format="AVIF")
    out = script_input(src)
    assert out.suffix == ".png" and out.exists() and src.exists()
    with Image.open(src) as original, Image.open(out) as converted:
        assert converted.format == "PNG" and converted.size == (64, 48)
        assert converted.convert("RGB").tobytes() == original.convert("RGB").tobytes()


def test_formats_the_scripts_read_and_videos_are_handed_over_unchanged(tmp_path: Path) -> None:
    jpg = tmp_path / "source.jpg"
    Image.new("RGB", (8, 8)).save(jpg)
    video = tmp_path / "source.mp4"
    video.write_bytes(b"not decoded")
    assert script_input(jpg) == jpg and script_input(video) == video


def test_palette_images_keep_their_transparency(tmp_path: Path) -> None:
    src = tmp_path / "source.gif"
    im = Image.new("P", (4, 4), 0)
    im.info["transparency"] = 0
    im.save(src, transparency=0)
    with Image.open(script_input(src)) as converted:
        assert converted.mode == "RGBA"
