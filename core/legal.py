"""Versioned legal texts: render, hash, and record exactly what was accepted.

Each accepted document (venue agreement, advertiser terms) is a template
include whose rendered text is stored with its SHA-256 at acceptance time.
Tests pin each version's hash, so editing a template without bumping its
version fails CI instead of silently changing what people are on record as
having agreed to.

The operator's legal name and notice address come from settings
(OPERATOR_LEGAL_NAME, LEGAL_EMAIL) because the entity is configured, not
hard-coded; the stored text records whatever was rendered at the time.
"""

from __future__ import annotations

import hashlib

from django.conf import settings
from django.template.loader import render_to_string


def legal_context() -> dict[str, str]:
    return {"operator": settings.OPERATOR_LEGAL_NAME, "legal_email": settings.LEGAL_EMAIL}


def render_legal(template: str) -> str:
    return render_to_string(template, legal_context()).strip()


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()
