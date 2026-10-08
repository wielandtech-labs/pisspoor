import pytest

TAILNET = "pisspoor-admin.example.ts.net"


@pytest.fixture
def gated(settings):
    settings.ALLOWED_HOSTS = ["pisspooridea.lol", TAILNET]
    settings.ADMIN_HOSTS = [TAILNET]


@pytest.mark.django_db
@pytest.mark.parametrize("path", ["/admin/", "/admin/login/", "/admin", "/print/sheet?codes=x"])
def test_back_office_is_404_on_public_host(client, gated, path):
    assert client.get(path, HTTP_HOST="pisspooridea.lol").status_code == 404


@pytest.mark.django_db
def test_back_office_works_on_tailnet_host(client, gated):
    response = client.get("/admin/login/", HTTP_HOST=TAILNET)
    assert response.status_code == 200


@pytest.mark.django_db
def test_admin_host_match_ignores_port_and_case(client, gated):
    response = client.get("/admin/login/", HTTP_HOST=f"{TAILNET.upper()}:443")
    assert response.status_code == 200


@pytest.mark.django_db
def test_public_pages_unaffected(client, gated, venue):
    assert client.get("/", HTTP_HOST="pisspooridea.lol").status_code == 200
    assert client.get(f"/b/{venue.board_token}", HTTP_HOST="pisspooridea.lol").status_code == 200


@pytest.mark.django_db
def test_unset_means_unrestricted(client, settings):
    settings.ADMIN_HOSTS = []
    assert client.get("/admin/login/").status_code == 200
