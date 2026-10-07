"""Print-ready sticker artwork, one self-contained SVG per placement.

Each SVG is drawn at its physical size (``width="4.5in"``) so the makerspace
printer or vinyl cutter gets the dimensions right without guessing at DPI.
Coordinates are in hundredths of an inch.

The short URL is printed under every QR on purpose: people are rightly wary
of scanning an unexplained QR code, and seeing exactly where it goes is what
makes them scan it.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import segno
from django.utils.html import escape

from .models import Placement

FONT = "'Arial Black', 'Helvetica Neue', Arial, sans-serif"
MONO = "'Courier New', monospace"
INK = "#1d1a16"
YELLOW = "#ffd23f"
RED = "#e4572e"
QUIET_ZONE = 2  # modules; the sticker border supplies the rest


class AgreementMissing(Exception):
    """Raised when asked to print for a venue that has not signed."""


@dataclass(frozen=True)
class Sticker:
    width: int
    height: int
    body: str

    def svg(self) -> str:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width / 100}in" '
            f'height="{self.height / 100}in" viewBox="0 0 {self.width} {self.height}">'
            f"{self.body}</svg>"
        )


def qr_path(data: str, x: float, y: float, size: float) -> str:
    """A QR code as one <path>, run-length encoded per row, fitted into a square."""
    qr = segno.make(data, error="m")
    matrix = [list(row) for row in qr.matrix]
    modules = len(matrix) + 2 * QUIET_ZONE
    scale = size / modules
    parts = []
    for row_index, row in enumerate(matrix):
        col = 0
        while col < len(row):
            if row[col]:
                start = col
                while col < len(row) and row[col]:
                    col += 1
                run = col - start
                mx, my = start + QUIET_ZONE, row_index + QUIET_ZONE
                parts.append(f"M{mx} {my}h{run}v1h-{run}z")
            else:
                col += 1
    return (
        f'<rect x="{x}" y="{y}" width="{size}" height="{size}" fill="#fff"/>'
        f'<path transform="translate({x} {y}) scale({scale:.5f})" fill="{INK}" '
        f'shape-rendering="crispEdges" d="{"".join(parts)}"/>'
    )


def _text(x, y, content, size, *, weight="normal", fill=INK, family=FONT, anchor="middle"):
    return (
        f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" '
        f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{escape(content)}</text>'
    )


def _large(p: Placement) -> Sticker:
    w, h = 450, 560
    return Sticker(
        w,
        h,
        f'<rect x="4" y="4" width="{w - 8}" height="{h - 8}" rx="28" fill="{YELLOW}" '
        f'stroke="{INK}" stroke-width="8"/>'
        + _text(w / 2, 58, "GOT A MINUTE?", 40, weight="900")
        + _text(w / 2, 88, "Scan while you're standing here", 20)
        + qr_path(p.short_url, 50, 105, 350)
        + _text(w / 2, 492, "Rate this restroom · Report a problem", 18)
        + _text(w / 2, 528, p.display_url, 24, weight="bold", family=MONO),
    )


def _branded(p: Placement) -> Sticker:
    w, h = 350, 470
    return Sticker(
        w,
        h,
        f'<rect x="4" y="4" width="{w - 8}" height="{h - 8}" rx="22" fill="#fff" '
        f'stroke="{INK}" stroke-width="8"/>'
        f'<path d="M4 26a22 22 0 0 1 22-22h{w - 52}a22 22 0 0 1 22 22v62H4z" fill="{RED}"/>'
        + _text(w / 2, 58, p.venue.name.upper()[:22], 28, weight="900", fill="#fff")
        + qr_path(p.short_url, 45, 100, 260)
        + _text(w / 2, 392, "Love it? Hate it? Out of TP?", 18, weight="bold")
        + _text(w / 2, 418, "Scan to rate or request service", 16)
        + _text(w / 2, 448, p.display_url, 20, weight="bold", family=MONO),
    )


def _urinal_target(p: Placement) -> Sticker:
    w, h = 250, 340
    cx, cy = w / 2, 120
    rings = "".join(
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}"/>'
        for r, fill in ((110, RED), (86, "#fff"), (62, RED), (38, "#fff"), (16, RED))
    )
    return Sticker(
        w,
        h,
        f'<rect x="3" y="3" width="{w - 6}" height="{h - 6}" rx="20" fill="#fff" '
        f'stroke="{INK}" stroke-width="6"/>'
        + rings
        + _text(cx, cy - 44, "AIM", 18, weight="900", fill="#fff")
        + qr_path(p.short_url, 20, 245, 80)
        + _text(110, 275, "Nice shot.", 18, weight="900", anchor="start")
        + _text(110, 298, p.display_url.rsplit("/", 1)[0] + "/", 11, family=MONO, anchor="start")
        + _text(110, 318, p.code, 18, weight="bold", family=MONO, anchor="start"),
    )


RENDERERS = {
    Placement.Product.LARGE: _large,
    Placement.Product.BRANDED: _branded,
    Placement.Product.URINAL_TARGET: _urinal_target,
}


def render_sticker(placement: Placement) -> Sticker:
    if not placement.venue.has_agreement:
        raise AgreementMissing(f"{placement.venue} has no signed placement agreement.")
    return RENDERERS[placement.product](placement)


def inline(sticker: Sticker, x: float, y: float, width: float) -> str:
    """The sticker as a nested <svg>, for drawing it into a larger scene."""
    height = width * sticker.height / sticker.width
    return (
        f'<svg x="{x}" y="{y}" width="{width}" height="{height:.1f}" '
        f'viewBox="0 0 {sticker.width} {sticker.height}">{sticker.body}</svg>'
    )


def preview_sticker(product: str, base_url: str) -> Sticker:
    """Marketing-page artwork for a product, with a QR that leads back to the pitch.

    Drawn by the same renderers as real stickers, so the homepage never shows
    a product that the print sheet cannot actually make.
    """
    demo = SimpleNamespace(
        short_url=f"{base_url}/#contact",
        display_url=f"{base_url.split('://', 1)[-1]}/yours",
        code="yours",
        venue=SimpleNamespace(name="Your Bar Here"),
    )
    return RENDERERS[product](demo)
