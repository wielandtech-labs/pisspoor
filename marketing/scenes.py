"""Hand-drawn SVG bathroom scenes for the homepage, each wearing a real sticker.

The stickers come from ``venues.printing.preview_sticker``: the same code that
draws the print files, so what the homepage shows is what the makerspace
prints. Scenes are 400x300 user units and scale with their container.
"""

from __future__ import annotations

from functools import cache

from django.utils.safestring import SafeString, mark_safe

from venues.models import Placement
from venues.printing import inline, preview_sticker

TILE = "#e9f1f0"
GROUT = "#c9d8d6"
STEEL = "#9aa7ad"
PORCELAIN = "#fbfbf8"
SHADOW = "#1d1a1620"


def _tiles(width: int, height: int, size: int = 40) -> str:
    lines = [f'<rect width="{width}" height="{height}" fill="{TILE}"/>']
    lines += [
        f'<line x1="0" y1="{y}" x2="{width}" y2="{y}" stroke="{GROUT}" stroke-width="2"/>'
        for y in range(size, height, size)
    ]
    lines += [
        f'<line x1="{x}" y1="0" x2="{x}" y2="{height}" stroke="{GROUT}" stroke-width="2"/>'
        for x in range(size, width, size)
    ]
    return "".join(lines)


def _svg(body: str, label: str) -> SafeString:
    return mark_safe(  # noqa: S308 - built only from constants and our own renderers
        f'<svg viewBox="0 0 400 300" role="img" aria-label="{label}" '
        f'xmlns="http://www.w3.org/2000/svg">{body}</svg>'
    )


def stall_scene(base_url: str) -> SafeString:
    sticker = preview_sticker(Placement.Product.LARGE, base_url)
    return _svg(
        _tiles(400, 300)
        # stall door, slightly ajar, with hinge and latch
        + '<rect x="70" y="0" width="260" height="270" fill="#5b8e7d"/>'
        + '<rect x="70" y="0" width="260" height="270" fill="none" stroke="#3f6b5c" stroke-width="6"/>'
        + '<rect x="78" y="40" width="8" height="26" rx="3" fill="#2d4b41"/>'
        + '<rect x="78" y="200" width="8" height="26" rx="3" fill="#2d4b41"/>'
        + '<rect x="306" y="130" width="16" height="30" rx="4" fill="#d9d9d9"/>'
        + '<rect x="0" y="270" width="400" height="30" fill="#cfc6b8"/>'
        + f'<rect x="150" y="34" width="108" height="134" rx="8" fill="{SHADOW}"/>'
        + inline(sticker, 144, 26, 112)
        + '<text x="200" y="210" text-anchor="middle" font-size="13" '
        'font-family="Georgia, serif" font-style="italic" fill="#e8f0ec">'
        "eye level. captive audience.</text>",
        "A large QR sticker on the inside of a bathroom stall door",
    )


def mirror_scene(base_url: str) -> SafeString:
    sticker = preview_sticker(Placement.Product.BRANDED, base_url)
    return _svg(
        _tiles(400, 300)
        # mirror
        + f'<rect x="30" y="30" width="200" height="130" rx="10" fill="#cfe3ea" stroke="{STEEL}" stroke-width="6"/>'
        + '<path d="M60 50l40 0-60 60 0-40z" fill="#ffffff70"/>'
        # sink + faucet
        + f'<rect x="20" y="186" width="220" height="22" rx="8" fill="{PORCELAIN}" stroke="{STEEL}" stroke-width="3"/>'
        + f'<path d="M40 208h180l-20 46h-140z" fill="{PORCELAIN}" stroke="{STEEL}" stroke-width="3"/>'
        + f'<path d="M126 186v-18h18v6h-10v12z" fill="{STEEL}"/>'
        # hand dryer
        + f'<rect x="282" y="160" width="86" height="64" rx="14" fill="#e3e3e3" stroke="{STEEL}" stroke-width="3"/>'
        + '<rect x="300" y="222" width="50" height="8" rx="3" fill="#bdbdbd"/>'
        + f'<rect x="276" y="22" width="96" height="129" rx="6" fill="{SHADOW}"/>'
        + inline(sticker, 270, 16, 96),
        "A branded QR sticker on the wall between the mirror and the hand dryer",
    )


def urinal_scene(base_url: str) -> SafeString:
    sticker = preview_sticker(Placement.Product.URINAL_TARGET, base_url)
    return _svg(
        _tiles(400, 300)
        + '<rect x="0" y="262" width="400" height="38" fill="#cfc6b8"/>'
        # privacy divider
        + '<rect x="40" y="70" width="14" height="170" rx="5" fill="#8d99a6"/>'
        + '<rect x="346" y="70" width="14" height="170" rx="5" fill="#8d99a6"/>'
        # urinal
        + f'<path d="M120 40h160q20 0 20 20v120q0 50-60 66h-80q-60-16-60-66v-120q0-20 20-20z" '
        f'fill="{PORCELAIN}" stroke="{STEEL}" stroke-width="4"/>'
        + '<path d="M140 120h120q4 70-60 92-64-22-60-92z" fill="#eef2f3"/>'
        + f'<rect x="188" y="14" width="24" height="28" rx="4" fill="{STEEL}"/>'
        + inline(sticker, 164, 104, 72)
        + '<text x="200" y="286" text-anchor="middle" font-size="13" font-family="Georgia, serif" '
        'font-style="italic" fill="#5c6670">aim improves 80%*</text>',
        "A small bullseye target sticker inside the back of a urinal",
    )


@cache
def homepage_scenes(base_url: str) -> dict[str, SafeString]:
    """All homepage scenes. Pure in base_url, so built once per process."""
    return {
        "stall_scene": stall_scene(base_url),
        "mirror_scene": mirror_scene(base_url),
        "urinal_scene": urinal_scene(base_url),
    }
