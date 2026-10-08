import pytest

from venues.models import RESERVED_CODES, Placement, Venue, new_short_code
from venues.printing import (
    NotPrintable,
    preview_sticker,
    qr_matrix,
    qr_payload,
    qr_svg,
    render_sticker,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def staff_client(client, django_user_model):
    user = django_user_model.objects.create_user("staff", password="pw", is_staff=True)
    client.force_login(user)
    return client


@pytest.mark.parametrize("product", Placement.Product.values)
def test_every_product_renders_at_physical_size_with_its_url(venue, product, settings):
    settings.PUBLIC_BASE_URL = "https://pisspooridea.lol"
    placement = Placement.objects.create(venue=venue, label="x", product=product)
    svg = render_sticker(placement).svg()
    assert svg.startswith("<svg") and 'in" height="' in svg
    assert "pisspooridea" not in svg.lower()  # no printed URL: QR and pictures only


def test_unsigned_venue_cannot_print(db):
    venue = Venue.objects.create(name="No Contract", slug="nope")
    placement = Placement.objects.create(venue=venue, label="x")
    with pytest.raises(NotPrintable):
        render_sticker(placement)


def test_venue_name_is_escaped_in_artwork(db):
    from datetime import date

    venue = Venue.objects.create(name="<script>Bar", slug="x", agreement_signed_on=date.today())
    placement = Placement.objects.create(venue=venue, label="x", product="branded")
    svg = render_sticker(placement).svg()
    assert "<script>" not in svg and "&lt;SCRIPT&gt;" in svg


def test_qr_svg_is_one_path_inside_the_box():
    svg = qr_svg(qr_matrix("https://pisspooridea.lol/abc234"), 10, 20, 100)
    assert svg.count("<path") == 1 and "translate(10 20)" in svg


def test_qr_payload_uses_alphanumeric_mode():
    assert qr_payload("https://pisspooridea.lol/k7qx2m") == "HTTPS://PISSPOORIDEA.LOL/K7QX2M"


def test_preview_sticker_needs_no_database():
    assert preview_sticker("urinal_target", "https://pisspooridea.lol").svg().startswith("<svg")


def test_short_codes_avoid_reserved_words_and_confusables():
    for _ in range(500):
        code = new_short_code()
        assert code not in RESERVED_CODES
        assert not set(code) & set("01loi")


def test_print_views_are_staff_only(client, placement):
    response = client.get(f"/print/{placement.code}.svg")
    assert response.status_code == 302 and "/admin/login" in response["Location"]


def test_staff_can_download_svg(staff_client, placement):
    response = staff_client.get(f"/print/{placement.code}.svg?download=1")
    assert response.status_code == 200
    assert response["Content-Type"] == "image/svg+xml"
    assert "attachment" in response["Content-Disposition"]


def test_print_sheet_refuses_unsigned_venue(staff_client, placement):
    unsigned = Venue.objects.create(name="Pending Pub", slug="pending")
    other = Placement.objects.create(venue=unsigned, label="x")
    response = staff_client.get(f"/print/sheet?codes={placement.code},{other.code}")
    assert response.status_code == 403
    assert b"Pending Pub" in response.content


def test_print_sheet_renders(staff_client, placement):
    response = staff_client.get(f"/print/sheet?codes={placement.code}")
    assert response.status_code == 200
    assert placement.code.encode() in response.content
