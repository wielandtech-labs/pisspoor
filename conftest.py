"""Project-wide pytest configuration."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _plain_static_storage(settings):
    """Serve static files without a manifest during tests.

    Production uses ``CompressedManifestStaticFilesStorage``, which resolves
    ``{% static %}`` through a manifest that only exists after ``collectstatic``
    - the Dockerfile runs that at build time. Tests never run it, so any
    template referencing a static file would fail with "Missing staticfiles
    manifest entry". The manifest path itself is exercised by the image build,
    which fails loudly if a referenced file is missing.
    """
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }


@pytest.fixture
def venue(db):
    from datetime import date

    from venues.models import Venue

    return Venue.objects.create(
        name="The Rusty Tap",
        slug="rusty",
        instagram_url="https://instagram.com/rusty",
        agreement_signed_on=date(2026, 1, 1),
    )


@pytest.fixture
def placement(venue):
    from venues.models import Placement

    return Placement.objects.create(venue=venue, label="Stall 1")


PHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) Safari/604.1"
