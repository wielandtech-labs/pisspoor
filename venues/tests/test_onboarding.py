import pytest
from django.core import mail

from conftest import PHONE
from venues.models import AgreementAcceptance, Placement, SamplePackRequest, Venue
from venues.onboarding import AGREEMENT_VERSION, agreement_sha256

pytestmark = pytest.mark.django_db

# Pinned on purpose: editing the agreement template without bumping
# AGREEMENT_VERSION would change what new venues sign under an old version
# label. Change the text -> bump the version -> update this hash.
SIGNED_TEXTS = {
    "2026-10-v1": "1d831476229cba0ae3c4faaa211fb42ccdd68e197b9b12392edd315be21eaff6",
}


def signup(**overrides):
    data = {
        "venue_name": "The Rusty Tap",
        "address": "123 Main St",
        "contact_name": "Sam",
        "contact_email": "sam@rustytap.example",
        "phone": "555-0100",
        "instagram_url": "https://instagram.com/rustytap",
        "pack": "starter",
        "count_large": "2",
        "count_branded": "1",
        "count_urinal_target": "1",
        "ship_to_name": "Sam",
        "ship_to_address": "123 Main St",
        "show_on_leaderboard": "on",
        "signer_name": "Sam Owner",
        "signer_title": "Owner",
        "authorized": "on",
        "agree": "on",
    }
    data.update(overrides)
    return {k: v for k, v in data.items() if v is not None}


def post(client, data):
    return client.post("/venues/join", data, HTTP_USER_AGENT=PHONE)


def test_agreement_text_matches_its_version():
    assert SIGNED_TEXTS[AGREEMENT_VERSION] == agreement_sha256()


def test_join_page_shows_the_agreement(client):
    body = client.get("/venues/join").content.decode()
    assert "Revenue share" in body and AGREEMENT_VERSION in body


def test_public_opt_ins_start_unticked(client):
    body = client.get("/venues/join").content.decode()
    for name in ("show_on_leaderboard", "allow_political_ads"):
        tag = body[body.index(f'name="{name}"') - 120 : body.index(f'name="{name}"') + 60]
        assert "checked" not in tag


def test_signup_creates_inactive_venue_pack_and_signed_record(
    client, django_capture_on_commit_callbacks, settings
):
    settings.OWNER_EMAIL = "owner@pisspooridea.example"
    with django_capture_on_commit_callbacks(execute=True):
        response = post(client, signup())
    venue = Venue.objects.get()
    assert response["Location"] == f"/venues/join/done/{venue.board_token}"
    assert not venue.active and venue.agreement_signed_on
    assert venue.show_on_leaderboard and not venue.allow_political_ads
    assert sorted(venue.placements.values_list("label", flat=True)) == [
        "Big Splash 1",
        "Big Splash 2",
        "Branded 1",
        "Bullseye 1",
    ]
    acceptance = AgreementAcceptance.objects.get()
    assert acceptance.signer_name == "Sam Owner" and acceptance.version == AGREEMENT_VERSION
    assert acceptance.text_sha256 == agreement_sha256()
    assert "Revenue share" in acceptance.text
    assert SamplePackRequest.objects.get().status == SamplePackRequest.Status.REQUESTED
    recipients = sorted(address for m in mail.outbox for address in m.to)
    assert recipients == ["owner@pisspooridea.example", "sam@rustytap.example"]
    welcome = next(m for m in mail.outbox if m.to == ["sam@rustytap.example"])
    assert f"/b/{venue.board_token}" in welcome.body


def test_unverified_venue_stickers_do_not_resolve_or_print(client, admin_client):
    post(client, signup())
    placement = Placement.objects.first()
    assert client.get(f"/{placement.code}").status_code == 404
    response = admin_client.get(f"/print/{placement.code}.svg")
    assert response.status_code == 403 and b"verified" in response.content


def test_admin_verify_activates_and_allows_printing(client, admin_client):
    post(client, signup())
    pack = SamplePackRequest.objects.get()
    admin_client.post(
        "/admin/venues/samplepackrequest/", {"action": "verify", "_selected_action": [pack.pk]}
    )
    pack.refresh_from_db()
    assert pack.status == SamplePackRequest.Status.VERIFIED and pack.verified_at
    assert pack.venue.active is True
    response = admin_client.post(
        "/admin/venues/samplepackrequest/", {"action": "print_pack", "_selected_action": [pack.pk]}
    )
    assert response.status_code == 302 and "/print/sheet?codes=" in response["Location"]
    assert admin_client.get(response["Location"]).status_code == 200


def test_board_is_reachable_before_verification(client):
    post(client, signup())
    venue = Venue.objects.get()
    assert client.get(f"/b/{venue.board_token}").status_code == 200


@pytest.mark.parametrize("missing", ["agree", "authorized", "signer_name"])
def test_agreement_must_be_signed(client, missing):
    response = post(client, signup(**{missing: None}))
    assert response.status_code == 200
    assert not Venue.objects.exists()


def test_custom_pack_counts_and_limits(client):
    post(client, signup(pack="custom", count_large="0", count_branded="0", count_urinal_target="3"))
    assert list(Placement.objects.values_list("label", flat=True).order_by("label")) == [
        "Bullseye 1",
        "Bullseye 2",
        "Bullseye 3",
    ]


@pytest.mark.parametrize("counts", [("0", "0", "0"), ("6", "6", "1")])
def test_custom_pack_rejects_empty_or_oversized(client, counts):
    large, branded, urinal = counts
    post(
        client,
        signup(pack="custom", count_large=large, count_branded=branded, count_urinal_target=urinal),
    )
    assert not Venue.objects.exists()


def test_one_signup_per_visitor_per_hour(client):
    post(client, signup())
    response = post(client, signup(venue_name="Second Bar"))
    assert response.status_code == 200
    assert b"Give us an hour" in response.content
    assert Venue.objects.count() == 1


def test_honeypot_creates_nothing(client):
    post(client, signup(fax_number="spam"))
    assert not Venue.objects.exists()


def test_duplicate_names_get_unique_slugs(client):
    from venues.onboarding import unique_slug

    Venue.objects.create(name="The Rusty Tap", slug="the-rusty-tap")
    assert unique_slug("The Rusty Tap") == "the-rusty-tap-2"
