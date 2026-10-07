import pytest
from django.core.management import call_command

from marketing.models import Lead
from venues.models import Venue

pytestmark = pytest.mark.django_db


def test_homepage_renders_with_product_scenes(client):
    response = client.get("/")
    assert response.status_code == 200
    body = response.content.decode()
    for product in ("The Big Splash", "The Branded", "The Bullseye"):
        assert product in body
    assert body.count("<svg") >= 4  # scenes, each wearing a real sticker


def test_lead_form_saves(client):
    response = client.post(
        "/", {"kind": "venue", "name": "Sam", "email": "sam@example.com", "business": "Bar"}
    )
    assert response.status_code == 302
    assert Lead.objects.get().name == "Sam"


def test_lead_honeypot_discards(client):
    client.post("/", {"kind": "venue", "name": "Bot", "email": "b@example.com", "website": "x"})
    assert not Lead.objects.exists()


def test_lead_form_shows_errors(client):
    response = client.post("/", {"kind": "venue", "name": "", "email": "nope"})
    assert response.status_code == 200
    assert not Lead.objects.exists()


def test_seed_demo_is_gated_and_idempotent(monkeypatch):
    monkeypatch.delenv("ALLOW_DEMO_SEED", raising=False)
    call_command("seed_demo")
    assert not Venue.objects.exists()
    monkeypatch.setenv("ALLOW_DEMO_SEED", "1")
    call_command("seed_demo")
    call_command("seed_demo")
    assert Venue.objects.filter(slug="the-rusty-tap").count() == 1


@pytest.fixture
def both_hosts(settings):
    settings.ALLOWED_HOSTS = ["pisspooridea.com", "pisspooridea.lol", "www.pisspooridea.lol"]
    settings.FUN_HOSTS = ["pisspooridea.lol", "www.pisspooridea.lol"]
    settings.AGENCY_URL = "https://pisspooridea.com"


def test_lol_host_gets_the_fun_front_door(client, both_hosts):
    body = client.get("/", HTTP_HOST="www.pisspooridea.lol").content.decode()
    assert "You found a piss poor idea." in body
    assert 'href="https://pisspooridea.com/#contact"' in body
    assert "The Big Splash" not in body


def test_com_host_gets_the_agency_site(client, both_hosts):
    body = client.get("/", HTTP_HOST="pisspooridea.com").content.decode()
    assert "The Big Splash" in body
    assert "idea<span>.</span>com" in body


def test_short_codes_resolve_on_both_hosts(client, both_hosts, placement):
    for host in ("pisspooridea.com", "pisspooridea.lol"):
        assert client.get(f"/{placement.code}", HTTP_HOST=host).status_code == 200


def test_stickers_default_to_the_com_domain():
    from django.conf import settings

    assert settings.PUBLIC_BASE_URL == "https://pisspooridea.com"
