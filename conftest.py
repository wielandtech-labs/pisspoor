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
