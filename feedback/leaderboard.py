"""The public "Cleanest bathrooms" leaderboard.

Ranking uses a Bayesian average so a venue with two 5-star ratings can't beat
one with two hundred 4.8s: each venue's ratings are blended with C imaginary
ratings at the network-wide mean m,

    score = (C * m + sum of stars) / (C + number of ratings)

and a venue needs MIN_RATINGS in the window to qualify at all. m is computed
over every active venue, opted in or not, so opting in can't move the bar.
Only opted-in venues are listed: nobody is ranked publicly without consent,
and there is no bottom of the table to be shamed on.
"""

from __future__ import annotations

from collections.abc import Hashable, Iterable
from dataclasses import dataclass
from datetime import timedelta

from django.db.models import Count, Sum
from django.utils import timezone

from .models import Rating

WINDOW_DAYS = 90
PRIOR_WEIGHT = 10
MIN_RATINGS = 10
TOP_N = 10


@dataclass(frozen=True)
class Standing:
    key: Hashable
    rank: int
    score: float
    average: float
    count: int


def rank(
    stats: dict[Hashable, tuple[int, int]],
    listed: Iterable[Hashable],
    prior_weight: int = PRIOR_WEIGHT,
    min_ratings: int = MIN_RATINGS,
) -> list[Standing]:
    """Rank `listed` keys by Bayesian score. stats maps key -> (count, total stars). Pure."""
    total_count = sum(count for count, _ in stats.values())
    if not total_count:
        return []
    mean = sum(total for _, total in stats.values()) / total_count
    scored = []
    for key in set(listed):
        count, total = stats.get(key, (0, 0))
        if count < min_ratings:
            continue
        score = (prior_weight * mean + total) / (prior_weight + count)
        scored.append((score, count, key, total / count))
    scored.sort(key=lambda row: (-row[0], -row[1], str(row[2])))
    return [
        Standing(key=key, rank=index, score=score, average=average, count=count)
        for index, (score, count, key, average) in enumerate(scored, start=1)
    ]


def rating_stats() -> dict[int, tuple[int, int]]:
    since = timezone.now() - timedelta(days=WINDOW_DAYS)
    rows = (
        Rating.objects.filter(created_at__gte=since, placement__venue__active=True)
        .values("placement__venue_id")
        .annotate(n=Count("id"), total=Sum("stars"))
        .order_by()
    )
    return {row["placement__venue_id"]: (row["n"], row["total"]) for row in rows}


def standings(stats: dict[int, tuple[int, int]] | None = None) -> list[Standing]:
    from venues.models import Venue

    listed = Venue.objects.filter(active=True, show_on_leaderboard=True).values_list(
        "pk", flat=True
    )
    return rank(rating_stats() if stats is None else stats, listed)


def venue_standing(venue) -> tuple[Standing | None, int]:
    """(this venue's standing if listed, ratings still needed to qualify)."""
    stats = rating_stats()
    count = stats.get(venue.pk, (0, 0))[0]
    needed = max(0, MIN_RATINGS - count)
    if not venue.show_on_leaderboard:
        return None, needed
    found = next((s for s in standings(stats) if s.key == venue.pk), None)
    return found, needed
