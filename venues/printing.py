"""Print-ready sticker artwork, one self-contained SVG per placement.

Each SVG is drawn at its physical size (``width="4.5in"``) so the makerspace
printer or vinyl cutter gets the dimensions right without guessing at DPI.
Coordinates are in hundredths of an inch.

Stickers carry no URL or instructions, just the QR code and pictures: a
star (rate it), a toilet roll (restock) and a wrench (fix it).

QR payloads are upper-cased on purpose. ``HTTPS://PISSPOORIDEA.LOL/K7QX2M``
fits QR alphanumeric mode, which needs a smaller symbol than byte mode, so
each module prints bigger and scans more easily. Scheme and host are
case-insensitive, and the short-code route accepts upper case.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from types import SimpleNamespace

import segno
from django.utils.html import escape

from .models import Placement

FONT = "'Arial Black', 'Helvetica Neue', Arial, sans-serif"
INK = "#1d1a16"
YELLOW = "#ffd23f"
RED = "#e4572e"
QUIET_ZONE = 2  # modules; the sticker border supplies the rest

# Share of the symbol's width the Bullseye's target may cover. Measured with
# ZXing on the production URL: 0.38 still decodes, 0.40 does not. 0.32 keeps
# headroom for the scuffs and splashes a urinal sticker will get. The decode
# test (venues/tests/test_qr_decodes.py) pins it; re-measure before raising.
BULLSEYE_DIAMETER = 0.32


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


def qr_payload(url: str) -> str:
    return url.upper()


def qr_matrix(url: str, error: str = "m") -> list[list[bool]]:
    return [[bool(cell) for cell in row] for row in segno.make(qr_payload(url), error=error).matrix]


def bullseye_hole(size: int) -> tuple[float, float, float]:
    """(cx, cy, r) in module units of the cleared target disc for a size x size symbol."""
    center = size / 2
    return center, center, size * BULLSEYE_DIAMETER / 2


def in_bullseye(size: int) -> Callable[[int, int], bool]:
    """True for modules the target covers, including any it only clips."""
    cx, cy, r = bullseye_hole(size)
    reach = r + math.sqrt(0.5)  # a module's far corner, not just its centre
    return lambda row, col: math.hypot(col + 0.5 - cx, row + 0.5 - cy) < reach


def qr_svg(
    matrix: list[list[bool]],
    x: float,
    y: float,
    size: float,
    skip: Callable[[int, int], bool] | None = None,
) -> str:
    """A QR matrix as one <path>, run-length encoded per row, fitted into a square."""
    modules = len(matrix) + 2 * QUIET_ZONE
    scale = size / modules
    parts = []
    for row_index, row in enumerate(matrix):
        col = 0
        while col < len(row):
            if row[col] and not (skip and skip(row_index, col)):
                start = col
                while col < len(row) and row[col] and not (skip and skip(row_index, col)):
                    col += 1
                run = col - start
                parts.append(f"M{start + QUIET_ZONE} {row_index + QUIET_ZONE}h{run}v1h-{run}z")
            else:
                col += 1
    return (
        f'<rect x="{x}" y="{y}" width="{size}" height="{size}" fill="#fff"/>'
        f'<path transform="translate({x} {y}) scale({scale:.5f})" fill="{INK}" '
        f'shape-rendering="crispEdges" d="{"".join(parts)}"/>'
    )


def _icons(cx: float, y: float, gap: float, fill: str = INK, scale: float = 1.0) -> str:
    """Rate / restock / fix, as pictures. Each icon is ~36 units square before scale."""
    star = " ".join(
        f"{18 + (17 if i % 2 == 0 else 7) * math.sin(math.pi * i / 5):.1f},"
        f"{18 - (17 if i % 2 == 0 else 7) * math.cos(math.pi * i / 5):.1f}"
        for i in range(10)
    )
    roll = (
        f'<rect x="4" y="6" width="22" height="26" rx="3" fill="{fill}"/>'
        f'<ellipse cx="26" cy="19" rx="7" ry="13" fill="{fill}"/>'
        '<ellipse cx="26" cy="19" rx="3" ry="6" fill="#fff"/>'
        f'<path d="M4 32h-2v-4" fill="none" stroke="{fill}" stroke-width="3"/>'
    )
    wrench = (
        f'<path d="M8 32l14-14a9 9 0 0 1 11-12l-6 6 1 5 5 1 6-6a9 9 0 0 1-12 11L13 37z" '
        f'fill="{fill}" transform="translate(-3 -3)"/>'
    )
    icons = [f'<polygon points="{star}" fill="{fill}"/>', roll, wrench]
    left = cx - gap - 18 * scale
    return "".join(
        f'<g transform="translate({left + i * gap:.1f} {y}) scale({scale})">{icon}</g>'
        for i, icon in enumerate(icons)
    )


def _text(x, y, content, size, *, weight="normal", fill=INK):
    return (
        f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" '
        f'font-weight="{weight}" fill="{fill}" text-anchor="middle">{escape(content)}</text>'
    )


def _large(p: Placement) -> Sticker:
    # The flagship: inside of the stall door, at seated eye level.
    w, h = 450, 540
    return Sticker(
        w,
        h,
        f'<rect x="4" y="4" width="{w - 8}" height="{h - 8}" rx="28" fill="{YELLOW}" '
        f'stroke="{INK}" stroke-width="8"/>'
        + _text(w / 2, 66, "GOT A MINUTE?", 42, weight="900")
        + qr_svg(qr_matrix(p.short_url), 50, 92, 350)
        + _icons(w / 2, 458, 90, scale=1.5),
    )


def _branded(p: Placement) -> Sticker:
    w, h = 350, 460
    return Sticker(
        w,
        h,
        f'<rect x="4" y="4" width="{w - 8}" height="{h - 8}" rx="22" fill="#fff" '
        f'stroke="{INK}" stroke-width="8"/>'
        f'<path d="M4 26a22 22 0 0 1 22-22h{w - 52}a22 22 0 0 1 22 22v62H4z" fill="{RED}"/>'
        + _text(w / 2, 58, p.venue.name.upper()[:22], 28, weight="900", fill="#fff")
        + qr_svg(qr_matrix(p.short_url), 45, 100, 260)
        + _icons(w / 2, 380, 76, fill=RED, scale=1.3),
    )


def _urinal_target(p: Placement) -> Sticker:
    # The target *is* the QR code: rings sit in a disc cleared from the
    # symbol's centre, recovered by error correction level H.
    w = h = 300
    matrix = qr_matrix(p.short_url, error="h")
    n = len(matrix)
    qr_x = qr_y = 10
    qr_size = w - 20
    unit = qr_size / (n + 2 * QUIET_ZONE)
    hx, hy, hr = bullseye_hole(n)
    cx, cy = qr_x + (hx + QUIET_ZONE) * unit, qr_y + (hy + QUIET_ZONE) * unit
    radius = hr * unit
    rings = "".join(
        f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{radius * k:.2f}" fill="{fill}"/>'
        for k, fill in ((1.0, RED), (0.78, "#fff"), (0.56, RED), (0.34, "#fff"), (0.14, RED))
    )
    return Sticker(
        w,
        h,
        f'<rect x="2" y="2" width="{w - 4}" height="{h - 4}" rx="22" fill="#fff" '
        f'stroke="{RED}" stroke-width="4"/>'
        + qr_svg(matrix, qr_x, qr_y, qr_size, skip=in_bullseye(n))
        + rings,
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
    """Marketing-page artwork for a product, with a QR that leads to the homepage.

    Drawn by the same renderers as real stickers, so the homepage never shows
    a product that the print sheet cannot actually make.
    """
    demo = SimpleNamespace(short_url=f"{base_url}/", venue=SimpleNamespace(name="Your Bar Here"))
    return RENDERERS[product](demo)
