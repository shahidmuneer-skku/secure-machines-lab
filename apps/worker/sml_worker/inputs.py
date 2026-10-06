"""What the model scripts are given: images in a format they cannot read are converted to PNG first.

The upload check accepts AVIF (sml.media.validation), but the detector scripts read only the formats
below: given an .avif file most of them stop with "unsupported input format". The PNG copy keeps the
decoded pixels exactly; the metadata check still reads the original file.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

# Every detector script reads these as they are.
SCRIPT_IMAGE_FORMATS = {"jpg", "jpeg", "png", "webp", "bmp"}
# Image formats that are converted (anything else, e.g. a video, is handed over unchanged).
CONVERTED_IMAGE_FORMATS = {"avif", "heic", "heif", "tif", "tiff", "gif"}


def script_input(path: Path) -> Path:
    """`path` itself, or a lossless PNG copy next to it when the scripts cannot read its format.
    Animated files give their first frame; 16-bit, CMYK and palette images become 8-bit RGB(A)."""
    if path.suffix.lower().lstrip(".") not in CONVERTED_IMAGE_FORMATS:
        return path
    out = path.with_name(f"{path.stem}.png")
    with Image.open(path) as im:
        im.seek(0)
        frame = im
        if im.mode == "P":
            frame = im.convert("RGBA" if "transparency" in im.info else "RGB")
        elif im.mode not in ("RGB", "RGBA", "L", "LA"):
            frame = im.convert("RGBA" if "A" in im.getbands() else "RGB")
        frame.save(out, format="PNG")
    return out
