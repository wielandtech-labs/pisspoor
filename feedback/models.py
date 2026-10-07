"""Bathroom ratings and maintenance requests from people who scanned."""

from __future__ import annotations

from datetime import timedelta

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from venues.models import Placement

MAX_REPORTS_PER_HOUR = 3


class Rating(models.Model):
    placement = models.ForeignKey(Placement, on_delete=models.CASCADE, related_name="ratings")
    stars = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.CharField(max_length=280, blank=True)
    visitor_hash = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.stars}/5 @ {self.placement}"


class MaintenanceRequest(models.Model):
    class Issue(models.TextChoices):
        NO_TP = "no_tp", "Out of toilet paper"
        NO_SOAP = "no_soap", "Out of soap"
        NO_TOWELS = "no_towels", "No paper towels / dryer broken"
        CLOG = "clog", "Clogged or overflowing"
        SPILL = "spill", "Wet floor / mess"
        BROKEN = "broken", "Something's broken (lock, flush, light)"
        OTHER = "other", "Something else"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ACK = "ack", "On it"
        RESOLVED = "resolved", "Resolved"

    placement = models.ForeignKey(
        Placement, on_delete=models.CASCADE, related_name="maintenance_requests"
    )
    issue = models.CharField(max_length=20, choices=Issue.choices)
    note = models.CharField(max_length=280, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    visitor_hash = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.get_issue_display()} @ {self.placement}"


def already_rated_today(placement: Placement, visitor: str) -> bool:
    start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    return Rating.objects.filter(
        placement=placement, visitor_hash=visitor, created_at__gte=start
    ).exists()


def report_limit_reached(visitor: str) -> bool:
    since = timezone.now() - timedelta(hours=1)
    recent = MaintenanceRequest.objects.filter(visitor_hash=visitor, created_at__gte=since)
    return recent.count() >= MAX_REPORTS_PER_HOUR
