"""Every sticker's QR must actually scan, including the Bullseye's holed one.

The symbol is rasterised from the same matrix, skip mask and ring geometry
the SVG renderer uses, then decoded with ZXing. The rings are painted in
mid-grey (what the red reads as in luminance), the worst case for a decoder.
"""

import pytest
import zxingcpp
from PIL import Image, ImageDraw

from venues.printing import (
    QUIET_ZONE,
    bullseye_hole,
    in_bullseye,
    qr_matrix,
    qr_payload,
)

PX = 10  # pixels per module

URLS = [
    "https://pisspooridea.lol/k7qx2m",
    "https://pisspooridea.lol/",
    # Longest realistic payload: a review app with a three-digit PR.
    "https://pr-999-pisspoor.review.wielandtech.com/zzzzzz",
]


def rasterise(matrix, holed: bool) -> Image.Image:
    n = len(matrix)
    side = (n + 2 * QUIET_ZONE) * PX
    image = Image.new("L", (side, side), 255)
    draw = ImageDraw.Draw(image)
    skip = in_bullseye(n) if holed else (lambda r, c: False)
    for r, row in enumerate(matrix):
        for c, dark in enumerate(row):
            if dark and not skip(r, c):
                x, y = (c + QUIET_ZONE) * PX, (r + QUIET_ZONE) * PX
                draw.rectangle([x, y, x + PX - 1, y + PX - 1], fill=0)
    if holed:
        hx, hy, hr = bullseye_hole(n)
        cx, cy = (hx + QUIET_ZONE) * PX, (hy + QUIET_ZONE) * PX
        for k, shade in ((1.0, 124), (0.78, 255), (0.56, 124), (0.34, 255), (0.14, 124)):
            rad = hr * PX * k
            draw.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=shade)
    return image


@pytest.mark.parametrize("url", URLS)
@pytest.mark.parametrize(("error", "holed"), [("m", False), ("h", True)])
def test_sticker_qr_decodes(url, error, holed):
    image = rasterise(qr_matrix(url, error=error), holed)
    results = zxingcpp.read_barcodes(image)
    assert [r.text for r in results] == [qr_payload(url)]
