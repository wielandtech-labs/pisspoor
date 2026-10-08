"""Advertiser Terms: the versioned text advertisers accept on submission."""

from __future__ import annotations

from core.legal import render_legal, sha256

ADVERTISER_TERMS_VERSION = "2026-10-v1"
ADVERTISER_TERMS_TEMPLATE = "ads/advertiser_terms_v1.html"


def advertiser_terms_text() -> str:
    return render_legal(ADVERTISER_TERMS_TEMPLATE)


def advertiser_terms_sha256() -> str:
    return sha256(advertiser_terms_text())
