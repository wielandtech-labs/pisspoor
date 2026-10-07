"""Scans and the monthly revenue they split."""

from __future__ import annotations

from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from venues.models import Placement


class Scan(models.Model):
    """One hit on a sticker's short link.

    ``visitor_hash`` is an HMAC of IP + user agent + date, so the same phone
    scanning twice in a day counts once and nothing identifying is stored.
    """

    placement = models.ForeignKey(Placement, on_delete=models.PROTECT, related_name="scans")
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    visitor_hash = models.CharField(max_length=64, db_index=True)
    is_bot = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.placement.code} @ {self.created_at:%Y-%m-%d %H:%M}"


class RevenuePeriod(models.Model):
    """A month of ad revenue, entered by hand, split across venues by traffic."""

    month = models.DateField(unique=True, help_text="First day of the month.")
    gross_revenue = models.DecimalField(max_digits=10, decimal_places=2)
    house_cut = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        default=Decimal("0.100"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("1"))],
        help_text="0.100 = 10%.",
    )
    closed = models.BooleanField(
        default=False, help_text="Tick once paid out; the report is then for the record."
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-month"]

    def __str__(self) -> str:
        return self.month.strftime("%B %Y")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def clean(self):
        # Any date means its whole month (see payouts.month_bounds), so store
        # day 1: otherwise Mar 1 and Mar 15 are two "unique" periods that
        # both pay out March. clean() runs before validate_unique, so the
        # admin reports the duplicate instead of a 500.
        if self.month:
            self.month = self.month.replace(day=1)
