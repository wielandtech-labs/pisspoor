"""Traffic-weighted revenue split.

The venues' pool is ``gross * (1 - house_cut)``, divided in proportion to each
venue's unique scans. A unique scan is a distinct (placement, visitor, day)
with bots excluded, so refreshing a page or one regular scanning every stall
on every visit does not tilt the split.

Shares round *down* to the cent and the remainder goes to the house, so the
report always reconciles to the gross exactly and never promises a venue a
cent that does not exist.
"""

from __future__ import annotations

import calendar
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import ROUND_DOWN, Decimal

from django.db.models.functions import TruncDate
from django.utils import timezone

from .models import RevenuePeriod, Scan

CENT = Decimal("0.01")


def split_revenue[K](
    gross: Decimal, house_cut: Decimal, counts: dict[K, int]
) -> tuple[dict[K, Decimal], Decimal]:
    """Return (share per key, house total). Pure; the heart of the payout."""
    total = sum(counts.values())
    if gross <= 0 or total == 0:
        # Nothing to split, or nobody to split it with.
        return {key: Decimal("0.00") for key in counts}, gross.quantize(CENT)
    pool = (gross * (1 - house_cut)).quantize(CENT, rounding=ROUND_DOWN)
    shares = {
        key: (pool * count / total).quantize(CENT, rounding=ROUND_DOWN)
        for key, count in counts.items()
    }
    return shares, gross.quantize(CENT) - sum(shares.values())


def month_bounds(month: date) -> tuple[datetime, datetime]:
    tz = timezone.get_current_timezone()
    first = month.replace(day=1)
    days = calendar.monthrange(first.year, first.month)[1]
    start = datetime.combine(first, time.min, tzinfo=tz)
    end = datetime.combine(date.fromordinal(first.toordinal() + days), time.min, tzinfo=tz)
    return start, end


def unique_scans_by_venue(
    start: datetime, end: datetime, venue_id: int | None = None
) -> Counter[int]:
    scans = Scan.objects.filter(created_at__gte=start, created_at__lt=end, is_bot=False)
    if venue_id is not None:
        scans = scans.filter(placement__venue_id=venue_id)
    rows = (
        scans.annotate(day=TruncDate("created_at"))
        .values_list("placement__venue_id", "placement_id", "visitor_hash", "day")
        # Clear Scan.Meta.ordering: Django adds ORDER BY columns to SELECT
        # DISTINCT, which would make every scan "unique" by its timestamp.
        .order_by()
        .distinct()
    )
    return Counter(venue_id for venue_id, *_ in rows)


@dataclass(frozen=True)
class PayoutLine:
    venue_id: int
    venue_name: str
    unique_scans: int
    amount: Decimal


@dataclass(frozen=True)
class PayoutReport:
    period: RevenuePeriod
    lines: list[PayoutLine]
    house: Decimal
    total_scans: int


def build_report(period: RevenuePeriod) -> PayoutReport:
    from venues.models import Venue

    counts = unique_scans_by_venue(*month_bounds(period.month))
    shares, house = split_revenue(period.gross_revenue, period.house_cut, dict(counts))
    names = dict(Venue.objects.filter(pk__in=counts).values_list("pk", "name"))
    lines = sorted(
        (PayoutLine(vid, names.get(vid, f"#{vid}"), counts[vid], shares[vid]) for vid in counts),
        key=lambda line: (-line.amount, line.venue_name),
    )
    return PayoutReport(period, lines, house, sum(counts.values()))
