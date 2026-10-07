"""Sponsor campaigns shown on the scan landing page.

Nothing runs until a person approves it, and approval is tied to the exact
destination URL: change the link and the campaign drops back to pending. The
published rules live in ads/templates/ads/policy.html; the categories below
are the only ones the policy allows. Banned and (at launch) restricted
categories - drugs, sexual services, weapons, alcohol, cannabis, tobacco,
gambling - are deliberately absent, so there is no way to file one.
"""

from __future__ import annotations

import random

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from venues.models import Placement


class CampaignQuerySet(models.QuerySet):
    def live(self):
        today = timezone.localdate()
        return self.filter(
            active=True, status=Campaign.Status.APPROVED, starts_on__lte=today
        ).filter(Q(ends_on__isnull=True) | Q(ends_on__gte=today))


class Campaign(models.Model):
    class Category(models.TextChoices):
        LOCAL_BUSINESS = "local_business", "Local business"
        FOOD = "food", "Food & non-alcoholic drink"
        SERVICES = "services", "Services & trades"
        EVENTS = "events", "Events & entertainment"
        RETAIL = "retail", "Retail"
        WELLNESS = "wellness", "Health & wellness (no medical claims)"
        NONPROFIT = "nonprofit", "Nonprofit & public service"
        POLITICAL = "political", "Political"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    advertiser = models.CharField(max_length=120)
    category = models.CharField(
        max_length=20, choices=Category.choices, default=Category.LOCAL_BUSINESS
    )
    headline = models.CharField(max_length=80)
    body = models.CharField(max_length=200, blank=True)
    cta_label = models.CharField(max_length=30, default="Check it out")
    target_url = models.URLField()
    starts_on = models.DateField(default=timezone.localdate)
    ends_on = models.DateField(null=True, blank=True)
    weight = models.PositiveSmallIntegerField(
        default=1, help_text="Relative share of impressions among live campaigns."
    )
    active = models.BooleanField(default=True)

    # Review. Status changes only through approve()/reject() (admin actions);
    # approved_target_url pins approval to the destination that was reviewed.
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    approved_target_url = models.URLField(blank=True, editable=False)
    review_notes = models.TextField(blank=True)

    # Political ads only. The disclaimer is shown verbatim, e.g. "Paid for by
    # Smith for Council, 123 Main St, Lansing MI". The required wording differs
    # by race (federal/state/local); a human checks it before approving.
    paid_for_by = models.CharField(
        max_length=300, blank=True, help_text="Political ads: the full disclaimer, shown verbatim."
    )
    sponsor_contact = models.CharField(
        max_length=200, blank=True, help_text="Political ads: sponsor address or website."
    )
    ai_generated = models.BooleanField(
        default=False,
        help_text="Political ads: made in whole or substantially with AI (Michigan "
        "requires a disclosure).",
    )

    objects = CampaignQuerySet.as_manager()

    class Meta:
        ordering = ["advertiser", "headline"]

    def __str__(self) -> str:
        return f"{self.advertiser}: {self.headline}"

    def save(self, *args, **kwargs):
        # Approval covers the link that was reviewed, not whatever it points
        # to next week.
        if self.status == self.Status.APPROVED and self.target_url != self.approved_target_url:
            self.status = self.Status.PENDING
        super().save(*args, **kwargs)

    def clean(self):
        if self.is_political:
            missing = {
                field: "Required for political ads."
                for field in ("paid_for_by", "sponsor_contact")
                if not getattr(self, field).strip()
            }
            if missing:
                raise ValidationError(missing)

    @property
    def is_political(self) -> bool:
        return self.category == self.Category.POLITICAL

    def approve(self, notes: str = "") -> None:
        self.full_clean()
        self.status = self.Status.APPROVED
        self.approved_target_url = self.target_url
        if notes:
            self.review_notes = notes
        self.save()

    def reject(self, notes: str = "") -> None:
        self.status = self.Status.REJECTED
        if notes:
            self.review_notes = notes
        self.save()


class AdClick(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="clicks")
    placement = models.ForeignKey(Placement, on_delete=models.CASCADE, related_name="ad_clicks")
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    visitor_hash = models.CharField(max_length=64)

    def __str__(self) -> str:
        return f"{self.campaign} via {self.placement.code}"


def pick_campaign(venue, rng: random.Random | None = None) -> Campaign | None:
    """A weighted pick among live campaigns this venue accepts."""
    live = Campaign.objects.live()
    if not venue.allow_political_ads:
        live = live.exclude(category=Campaign.Category.POLITICAL)
    campaigns = [c for c in live if c.weight > 0]
    if not campaigns:
        return None
    return (rng or random).choices(campaigns, weights=[c.weight for c in campaigns])[0]
