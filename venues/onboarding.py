"""Self-serve venue signup: details, sample pack, click-through agreement."""

from __future__ import annotations

from datetime import timedelta

from django import forms
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from core.legal import render_legal, sha256
from core.notify import notify_owner, send_email
from feedback.alerts import board_url

from .models import AgreementAcceptance, Placement, SamplePackRequest, Venue

# v1 (2026-10-v1) stays on disk: acceptances store their full text anyway.
AGREEMENT_VERSION = "2026-10-v2"
AGREEMENT_TEMPLATE = "venues/agreement_v2.html"

STARTER_PACK = {
    Placement.Product.LARGE: 2,
    Placement.Product.BRANDED: 1,
    Placement.Product.URINAL_TARGET: 1,
}
MAX_PER_PRODUCT = 6
MAX_STICKERS = 12
SHORT_NAMES = {
    Placement.Product.LARGE: "Big Splash",
    Placement.Product.BRANDED: "Branded",
    Placement.Product.URINAL_TARGET: "Bullseye",
}


def agreement_text() -> str:
    return render_legal(AGREEMENT_TEMPLATE)


def agreement_sha256() -> str:
    return sha256(agreement_text())


class VenueSignupForm(forms.Form):
    venue_name = forms.CharField(max_length=120, label="Venue name")
    address = forms.CharField(max_length=300, widget=forms.Textarea(attrs={"rows": 2}))
    contact_name = forms.CharField(max_length=120, label="Your name")
    contact_email = forms.EmailField(label="Email")
    phone = forms.CharField(max_length=40, required=False, label="Phone (we call to verify)")

    website_url = forms.URLField(required=False, label="Website")
    instagram_url = forms.URLField(required=False, label="Instagram")
    facebook_url = forms.URLField(required=False, label="Facebook")
    tiktok_url = forms.URLField(required=False, label="TikTok")
    google_reviews_url = forms.URLField(required=False, label="Google reviews link")

    pack = forms.ChoiceField(
        choices=[("starter", "Starter pack"), ("custom", "Custom")],
        initial="starter",
        widget=forms.RadioSelect,
    )
    count_large = forms.IntegerField(min_value=0, max_value=MAX_PER_PRODUCT, initial=2)
    count_branded = forms.IntegerField(min_value=0, max_value=MAX_PER_PRODUCT, initial=1)
    count_urinal_target = forms.IntegerField(min_value=0, max_value=MAX_PER_PRODUCT, initial=1)
    ship_to_name = forms.CharField(max_length=120, label="Ship to (name)")
    ship_to_address = forms.CharField(
        max_length=300, widget=forms.Textarea(attrs={"rows": 3}), label="Shipping address"
    )

    allow_political_ads = forms.BooleanField(required=False, label="Allow political ads")
    # Opt-in means unticked by default: nobody is listed publicly by accident.
    show_on_leaderboard = forms.BooleanField(
        required=False, label="List us on the cleanest-bathrooms leaderboard"
    )

    signer_name = forms.CharField(max_length=120, label="Your full name (signature)")
    signer_title = forms.CharField(max_length=120, label="Your role (e.g. owner, manager)")
    authorized = forms.BooleanField(label="I'm authorized to sign for this venue")
    agree = forms.BooleanField(label="I agree to the placement agreement above")

    # Honeypot. Not "website": that's a real field here.
    fax_number = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"})
    )

    def clean(self):
        data = super().clean()
        if data.get("pack") == "custom":
            total = sum(data.get(f"count_{p}") or 0 for p in STARTER_PACK)
            if not 1 <= total <= MAX_STICKERS:
                raise forms.ValidationError(f"Pick between 1 and {MAX_STICKERS} stickers.")
        return data

    def counts(self) -> dict[str, int]:
        if self.cleaned_data["pack"] == "starter":
            return dict(STARTER_PACK)
        return {p: self.cleaned_data[f"count_{p}"] or 0 for p in STARTER_PACK}


def recently_signed_up(visitor: str) -> bool:
    since = timezone.now() - timedelta(hours=1)
    return AgreementAcceptance.objects.filter(visitor_hash=visitor, accepted_at__gte=since).exists()


def unique_slug(name: str) -> str:
    base = slugify(name)[:40] or "venue"
    slug, n = base, 2
    while Venue.objects.filter(slug=slug).exists():
        slug, n = f"{base}-{n}", n + 1
    return slug


@transaction.atomic
def create_venue(form: VenueSignupForm, visitor: str) -> Venue:
    data = form.cleaned_data
    venue = Venue.objects.create(
        name=data["venue_name"],
        slug=unique_slug(data["venue_name"]),
        address=data["address"],
        contact_name=data["contact_name"],
        contact_email=data["contact_email"],
        website_url=data["website_url"],
        instagram_url=data["instagram_url"],
        facebook_url=data["facebook_url"],
        tiktok_url=data["tiktok_url"],
        google_reviews_url=data["google_reviews_url"],
        allow_political_ads=data["allow_political_ads"],
        show_on_leaderboard=data["show_on_leaderboard"],
        agreement_signed_on=timezone.localdate(),
        # Inactive until the owner verifies the signer: stickers don't resolve
        # and nothing prints before then.
        active=False,
    )
    AgreementAcceptance.objects.create(
        venue=venue,
        version=AGREEMENT_VERSION,
        text=agreement_text(),
        text_sha256=agreement_sha256(),
        signer_name=data["signer_name"],
        signer_title=data["signer_title"],
        signer_email=data["contact_email"],
        visitor_hash=visitor,
    )
    for product, count in form.counts().items():
        for n in range(1, count + 1):
            Placement.objects.create(
                venue=venue, product=product, label=f"{SHORT_NAMES[product]} {n}"
            )
    SamplePackRequest.objects.create(
        venue=venue,
        ship_to_name=data["ship_to_name"],
        ship_to_address=data["ship_to_address"],
        phone=data["phone"],
    )
    transaction.on_commit(lambda: _announce(venue))
    return venue


def _announce(venue: Venue) -> None:
    link = board_url(venue)
    send_email(
        venue.contact_email,
        f"Welcome to Piss Poor Idea, {venue.name}",
        f"Thanks for signing up {venue.name}.\n\n"
        "What happens next: we'll call or email to confirm you run the venue, then print and "
        "mail your sample pack. Your stickers go live when they arrive.\n\n"
        f"Your private venue board (keep this link to your staff): {link}\n"
        "There you'll see maintenance reports and ratings, and set up alerts.\n\n"
        f"Your signed agreement ({AGREEMENT_VERSION}) is on file; reply to this email for a copy.",
    )
    notify_owner(
        f"New venue signup: {venue.name}",
        f"{venue.name} ({venue.contact_name}, {venue.contact_email}) signed up and wants a "
        "sample pack. Verify the signer, then print and ship.",
        settings.ADMIN_URL,
    )
