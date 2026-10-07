import pytest

from feedback.models import MaintenanceRequest

pytestmark = pytest.mark.django_db


@pytest.fixture
def ticket(placement):
    return MaintenanceRequest.objects.create(
        placement=placement, issue="no_tp", note="stall 1", visitor_hash="v"
    )


def test_board_shows_open_requests(client, venue, ticket):
    response = client.get(f"/b/{venue.board_token}")
    assert response.status_code == 200
    assert b"Out of toilet paper" in response.content
    assert response["X-Robots-Tag"] == "noindex"


def test_wrong_token_404s(client, venue):
    assert client.get("/b/not-the-token").status_code == 404


def test_resolve_and_reopen(client, venue, ticket):
    url = f"/b/{venue.board_token}/requests/{ticket.pk}"
    assert client.post(url, {"action": "resolve"}).status_code == 302
    ticket.refresh_from_db()
    assert ticket.status == "resolved" and ticket.resolved_at is not None
    client.post(url, {"action": "reopen"})
    ticket.refresh_from_db()
    assert ticket.status == "open" and ticket.resolved_at is None


def test_cannot_touch_another_venues_ticket(client, venue, ticket):
    from venues.models import Venue

    other = Venue.objects.create(name="Other", slug="other")
    response = client.post(f"/b/{other.board_token}/requests/{ticket.pk}", {"action": "resolve"})
    assert response.status_code == 404
    ticket.refresh_from_db()
    assert ticket.status == "open"
