"""Venues and the stickers placed in them.

A ``Placement`` is one physical sticker. Its short code is what the QR encodes,
so it is generated once and never edited: a sticker on a wall cannot be
reprinted by changing a database row.
"""

from __future__ import annotations

import secrets

from django.conf import settings
from django.db import models

# No 0/o, 1/l/i: the code is also printed under the QR for people who would
# rather type it than scan an unexplained QR code in a bathroom.
CODE_ALPHABET = "23456789abcdefghjkmnpqrstuvwxyz"
CODE_LENGTH = 6
CODE_PATTERN = f"[{CODE_ALPHABET}]{{{CODE_LENGTH}}}"

# Codes share the URL root with the site's own pages. Any fixed route whose
# path could match CODE_PATTERN must be listed here so no sticker ever
# shadows it (or is shadowed by it).
RESERVED_CODES = frozenset({"readyz", "static"})


def new_short_code() -> str:
    while True:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        if code not in RESERVED_CODES:
            return code


def new_board_token() -> str:
    return secrets.token_urlsafe(24)


class Venue(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    address = models.TextField(blank=True)
    contact_name = models.CharField(max_length=120, blank=True)
    contact_email = models.EmailField(blank=True)

    website_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    facebook_url = models.URLField(blank=True)
    tiktok_url = models.URLField(blank=True)
    google_reviews_url = models.URLField(blank=True)

    agreement_signed_on = models.DateField(
        null=True,
        blank=True,
        help_text="Date the placement agreement was signed. No agreement, no stickers: "
        "print sheets are refused until this is set.",
    )
    active = models.BooleanField(default=True)
    # Secret link to the venue's maintenance board. Regenerate it (blank the
    # field in the shell) if the venue leaks it.
    board_token = models.CharField(
        max_length=64, unique=True, default=new_board_token, editable=False
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @property
    def has_agreement(self) -> bool:
        return self.agreement_signed_on is not None

    def social_links(self) -> list[tuple[str, str]]:
        links = [
            ("Instagram", self.instagram_url),
            ("Facebook", self.facebook_url),
            ("TikTok", self.tiktok_url),
            ("Google reviews", self.google_reviews_url),
            ("Website", self.website_url),
        ]
        return [(label, url) for label, url in links if url]


class Placement(models.Model):
    class Product(models.TextChoices):
        LARGE = "large", "Big Splash (large sticker)"
        BRANDED = "branded", "Branded sticker (graphic + URL)"
        URINAL_TARGET = "urinal_target", "Bullseye urinal target"

    venue = models.ForeignKey(Venue, on_delete=models.PROTECT, related_name="placements")
    label = models.CharField(max_length=80, help_text='Where it is, e.g. "Men\'s stall 2".')
    product = models.CharField(max_length=20, choices=Product.choices, default=Product.LARGE)
    code = models.CharField(max_length=12, unique=True, default=new_short_code, editable=False)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["venue__name", "label"]

    def __str__(self) -> str:
        return f"{self.venue} / {self.label}"

    def save(self, *args, **kwargs):
        if self._state.adding:
            while Placement.objects.filter(code=self.code).exists():
                self.code = new_short_code()
        super().save(*args, **kwargs)

    @property
    def short_url(self) -> str:
        return f"{settings.PUBLIC_BASE_URL}/{self.code}"

    @property
    def display_url(self) -> str:
        return self.short_url.split("://", 1)[-1]
