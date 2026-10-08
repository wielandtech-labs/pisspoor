"""Venues and the stickers placed in them.

A ``Placement`` is one physical sticker. Its short code is what the QR encodes,
so it is generated once and never edited: a sticker on a wall cannot be
reprinted by changing a database row.
"""

from __future__ import annotations

import secrets

from django.conf import settings
from django.db import models

# No 0/o, 1/l/i: codes get read aloud and typed (venue staff quoting the board,
# support). Lowercase only; QR payloads upper-case them (see
# venues.printing.qr_payload) and the route accepts either case.
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


def new_ntfy_topic() -> str:
    # ntfy topics allow [A-Za-z0-9_-]; the random part is what keeps a venue's
    # alerts private, since anyone may read a pp-* topic they can name.
    return f"pp-{secrets.token_urlsafe(16)}"


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
    allow_political_ads = models.BooleanField(
        default=False,
        help_text="Off by default: the venue's name sits next to every ad, so it opts in.",
    )
    active = models.BooleanField(default=True)
    # Secret link to the venue's maintenance board. Regenerate it (blank the
    # field in the shell) if the venue leaks it.
    board_token = models.CharField(
        max_length=64, unique=True, default=new_board_token, editable=False
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # Maintenance alerts (feedback/alerts.py). The venue manages these from
    # its board; notify_email falls back to contact_email when blank.
    notify_email = models.EmailField(blank=True)
    email_alerts = models.BooleanField(default=True)
    push_alerts = models.BooleanField(default=True)
    show_on_leaderboard = models.BooleanField(
        default=False, help_text="Opt-in: list this venue on the public cleanest-bathrooms page."
    )
    ntfy_topic = models.CharField(
        max_length=64, unique=True, default=new_ntfy_topic, editable=False
    )

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @property
    def has_agreement(self) -> bool:
        return self.agreement_signed_on is not None

    @property
    def alert_email(self) -> str:
        return self.notify_email or self.contact_email

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


class AgreementAcceptance(models.Model):
    """A click-through signature: who accepted which exact text, and when.

    The full text is stored alongside its hash, so a later edit to the
    template can never change what a venue is on record as having signed.
    """

    venue = models.ForeignKey(Venue, on_delete=models.PROTECT, related_name="acceptances")
    version = models.CharField(max_length=20)
    text = models.TextField()
    text_sha256 = models.CharField(max_length=64)
    signer_name = models.CharField(max_length=120)
    signer_title = models.CharField(max_length=120)
    signer_email = models.EmailField()
    visitor_hash = models.CharField(max_length=64, db_index=True)
    accepted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-accepted_at"]

    def __str__(self) -> str:
        return f"{self.venue} · {self.version} · {self.signer_name}"


class SamplePackRequest(models.Model):
    """The shipping queue for a new venue's first stickers.

    Nothing prints until the owner verifies the signer really runs the venue
    (status VERIFIED activates the venue): otherwise anyone could "onboard" a
    bar they don't own and receive stickers to put up there.
    """

    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested (verify the signer)"
        VERIFIED = "verified", "Verified"
        PRINTED = "printed", "Printed"
        SHIPPED = "shipped", "Shipped"

    venue = models.ForeignKey(Venue, on_delete=models.PROTECT, related_name="sample_packs")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.REQUESTED)
    ship_to_name = models.CharField(max_length=120)
    ship_to_address = models.TextField()
    phone = models.CharField(max_length=40, blank=True)
    tracking_number = models.CharField(max_length=80, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.venue} · {self.get_status_display()}"
