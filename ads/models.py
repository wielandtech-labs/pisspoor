"""Sponsor campaigns shown on the scan landing page."""

from __future__ import annotations

import random

from django.db import models
from django.db.models import Q
from django.utils import timezone

from venues.models import Placement


class CampaignQuerySet(models.QuerySet):
    def live(self):
        today = timezone.localdate()
        return self.filter(active=True, starts_on__lte=today).filter(
            Q(ends_on__isnull=True) | Q(ends_on__gte=today)
        )


class Campaign(models.Model):
    advertiser = models.CharField(max_length=120)
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

    objects = CampaignQuerySet.as_manager()

    class Meta:
        ordering = ["advertiser", "headline"]

    def __str__(self) -> str:
        return f"{self.advertiser}: {self.headline}"


class AdClick(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="clicks")
    placement = models.ForeignKey(Placement, on_delete=models.CASCADE, related_name="ad_clicks")
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    visitor_hash = models.CharField(max_length=64)

    def __str__(self) -> str:
        return f"{self.campaign} via {self.placement.code}"


def pick_campaign(rng: random.Random | None = None) -> Campaign | None:
    campaigns = [c for c in Campaign.objects.live() if c.weight > 0]
    if not campaigns:
        return None
    return (rng or random).choices(campaigns, weights=[c.weight for c in campaigns])[0]
