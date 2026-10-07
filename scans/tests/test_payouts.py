from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from scans.models import RevenuePeriod, Scan
from scans.payouts import (
    build_report,
    month_bounds,
    split_revenue,
    unique_scans_by_venue,
)
from venues.models import Placement, Venue

D = Decimal


@pytest.mark.parametrize(
    ("gross", "cut", "counts", "shares", "house"),
    [
        # The homepage example.
        ("1000", "0.1", {"a": 600, "b": 300, "c": 100}, {"a": "540", "b": "270", "c": "90"}, "100"),
        # No traffic: nobody to pay, everything stays with the house.
        ("500", "0.1", {}, {}, "500"),
        ("500", "0.1", {"a": 0}, {"a": "0"}, "500"),
        # No revenue: everyone gets zero.
        ("0", "0.1", {"a": 5}, {"a": "0"}, "0"),
        # Single venue takes the whole pool.
        ("123.45", "0.1", {"a": 7}, {"a": "111.10"}, "12.35"),
        # Thirds round down; the leftover cents go to the house, never lost.
        ("100", "0.1", {"a": 1, "b": 1, "c": 1}, {"a": "30", "b": "30", "c": "30"}, "10"),
        ("10", "0", {"a": 1, "b": 1, "c": 1}, {"a": "3.33", "b": "3.33", "c": "3.33"}, "0.01"),
    ],
)
def test_split_revenue(gross, cut, counts, shares, house):
    got_shares, got_house = split_revenue(D(gross), D(cut), counts)
    assert got_shares == {k: D(v) for k, v in shares.items()}
    assert got_house == D(house)
    assert sum(got_shares.values()) + got_house == D(gross)


def test_split_never_overpays_on_awkward_numbers():
    counts = {i: i * 7 + 3 for i in range(1, 30)}
    shares, house = split_revenue(D("9876.54"), D("0.1"), counts)
    assert sum(shares.values()) + house == D("9876.54")
    assert house >= D("987.65")


def _scan(placement, visitor, when, bot=False):
    return Scan.objects.create(
        placement=placement, visitor_hash=visitor, created_at=when, is_bot=bot
    )


@pytest.mark.django_db
def test_unique_scans_dedup_by_visitor_placement_and_day(placement, venue):
    other = Placement.objects.create(venue=venue, label="Stall 2")
    now = timezone.now().replace(hour=12)
    _scan(placement, "v1", now)
    _scan(placement, "v1", now + timedelta(minutes=5))  # same day, same sticker
    _scan(other, "v1", now)  # different sticker counts
    _scan(placement, "v1", now - timedelta(days=1))  # different day counts
    _scan(placement, "bot", now, bot=True)  # bots never count
    counts = unique_scans_by_venue(now - timedelta(days=2), now + timedelta(days=1))
    assert counts == {venue.pk: 3}


@pytest.mark.django_db
def test_build_report_splits_by_venue(placement, venue):
    second = Venue.objects.create(name="Taco Libre", slug="tacos")
    taco_placement = Placement.objects.create(venue=second, label="Stall")
    period = RevenuePeriod.objects.create(month=date(2026, 3, 1), gross_revenue=D("100"))
    start, _ = month_bounds(period.month)
    for n in range(3):
        _scan(placement, f"r{n}", start + timedelta(hours=1))
    _scan(taco_placement, "t1", start + timedelta(hours=1))
    _scan(placement, "outside", start - timedelta(hours=1))  # previous month
    report = build_report(period)
    assert [(line.venue_name, line.unique_scans, line.amount) for line in report.lines] == [
        ("The Rusty Tap", 3, D("67.50")),
        ("Taco Libre", 1, D("22.50")),
    ]
    assert report.house == D("10.00")


def test_month_bounds_cover_whole_month():
    start, end = month_bounds(date(2026, 2, 14))
    assert (start.day, start.month) == (1, 2)
    assert (end.day, end.month) == (1, 3)


@pytest.mark.django_db
def test_unique_scans_can_be_limited_to_one_venue(placement, venue):
    other = Placement.objects.create(venue=Venue.objects.create(name="B", slug="b"), label="x")
    now = timezone.now()
    _scan(placement, "v1", now)
    _scan(other, "v2", now)
    counts = unique_scans_by_venue(now - timedelta(hours=1), now + timedelta(hours=1), venue.pk)
    assert counts == {venue.pk: 1}


@pytest.mark.django_db
def test_revenue_period_month_is_normalized_so_a_month_cannot_pay_twice():
    from django.core.exceptions import ValidationError

    RevenuePeriod.objects.create(month=date(2026, 3, 1), gross_revenue=D("10"))
    duplicate = RevenuePeriod(month=date(2026, 3, 15), gross_revenue=D("5"))
    with pytest.raises(ValidationError):
        duplicate.full_clean()
    assert duplicate.month == date(2026, 3, 1)


@pytest.mark.parametrize("cut", ["-0.1", "1.5"])
def test_house_cut_must_be_a_fraction(cut):
    from django.core.exceptions import ValidationError

    period = RevenuePeriod(month=date(2026, 4, 1), gross_revenue=D("10"), house_cut=D(cut))
    with pytest.raises(ValidationError):
        period.full_clean(validate_unique=False)
