from datetime import timedelta

import pytest
from django.utils import timezone

from feedback.leaderboard import rank
from feedback.models import Rating
from venues.models import Placement, Venue


def keys(standings):
    return [s.key for s in standings]


@pytest.mark.parametrize(
    ("stats", "listed", "expected"),
    [
        # Nobody has ratings: empty board.
        ({}, ["a"], []),
        # Below the minimum: not ranked, however perfect.
        ({"a": (9, 45)}, ["a"], []),
        # Many 4.8s beat a handful of 5s (a handful is pulled toward the mean).
        (
            {"many": (200, 960), "few": (10, 50), "meh": (100, 300)},
            ["many", "few", "meh"],
            ["many", "few", "meh"],
        ),
        # Not opted in: not listed, but still counts toward the network mean.
        ({"a": (20, 100), "b": (20, 60)}, ["b"], ["b"]),
        # Ties on score: more ratings first.
        ({"a": (10, 40), "b": (20, 80)}, ["a", "b"], ["b", "a"]),
    ],
)
def test_rank(stats, listed, expected):
    assert keys(rank(stats, listed, prior_weight=10, min_ratings=10)) == expected


def test_rank_numbers_and_positions():
    stats = {"a": (10, 50), "b": (10, 30)}  # network mean 4.0
    standings = rank(stats, ["a", "b"], prior_weight=10, min_ratings=10)
    assert [(s.key, s.rank, s.average, round(s.score, 2)) for s in standings] == [
        ("a", 1, 5.0, 4.5),
        ("b", 2, 3.0, 3.5),
    ]


def test_non_opted_venue_shapes_the_bar_it_isnt_shown_on():
    # A huge, filthy, non-listed venue drags the mean down, which lowers what
    # a small listed venue gets blended toward.
    with_low = rank({"small": (10, 50), "dirty": (500, 500)}, ["small"])
    without = rank({"small": (10, 50)}, ["small"])
    assert with_low[0].score < without[0].score


@pytest.fixture
def rated(db):
    def make(name, stars, count, opted_in=True, active=True, days_ago=1):
        venue = Venue.objects.create(
            name=name, slug=name.lower(), show_on_leaderboard=opted_in, active=active
        )
        placement = Placement.objects.create(venue=venue, label="x")
        when = timezone.now() - timedelta(days=days_ago)
        for i in range(count):
            Rating.objects.create(
                placement=placement, stars=stars, visitor_hash=f"{name}{i}", created_at=when
            )
        return venue

    return make


def test_cleanest_page_lists_only_opted_in_qualifying_venues(client, rated):
    rated("Sparkle", 5, 12)
    rated("Fine", 4, 12)
    rated("Shy", 5, 30, opted_in=False)
    rated("Tiny", 5, 3)
    rated("Stale", 5, 30, days_ago=200)
    body = client.get("/cleanest").content.decode()
    assert body.index("Sparkle") < body.index("Fine")
    for hidden in ("Shy", "Tiny", "Stale"):
        assert hidden not in body


def test_cleanest_page_empty_state(client, db):
    assert "No venue has qualified yet" in client.get("/cleanest").content.decode()


def test_board_shows_rank_and_toggles_opt_in(client, rated):
    venue = rated("Sparkle", 5, 12, opted_in=False)
    board = f"/b/{venue.board_token}"
    assert "Join the leaderboard" in client.get(board).content.decode()
    client.post(f"{board}/leaderboard", {"show": "1"})
    venue.refresh_from_db()
    assert venue.show_on_leaderboard
    assert "You're <strong>#1</strong>" in client.get(board).content.decode()
    client.post(f"{board}/leaderboard", {"show": "0"})
    venue.refresh_from_db()
    assert not venue.show_on_leaderboard


def test_board_counts_ratings_still_needed(client, rated):
    venue = rated("Newbie", 5, 4)
    assert "6 more ratings" in client.get(f"/b/{venue.board_token}").content.decode()


def test_board_aggregates_ratings_once(client, rated, django_assert_max_num_queries):
    from feedback.leaderboard import venue_standing

    venue = rated("Sparkle", 5, 12)
    with django_assert_max_num_queries(2):  # one aggregate + the listed-venues query
        standing, _ = venue_standing(venue)
    assert standing.rank == 1


def test_unverified_venue_is_told_verification_is_the_blocker(client, rated):
    venue = rated("Pending", 5, 12, active=False)
    body = client.get(f"/b/{venue.board_token}").content.decode()
    assert "once your venue is verified" in body
    assert "outside the top 10" not in body
