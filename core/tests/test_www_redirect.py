import pytest

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _hosts(settings):
    settings.ALLOWED_HOSTS = ["pisspooridea.lol", "www.pisspooridea.lol"]


def test_www_redirects_to_apex_keeping_path_and_query(client):
    response = client.get("/cleanest?x=1", HTTP_HOST="www.pisspooridea.lol", secure=True)
    assert response.status_code == 308
    assert response["Location"] == "https://pisspooridea.lol/cleanest?x=1"
    assert "ppv" not in response.cookies


def test_www_post_keeps_its_method(client):
    response = client.post("/", {"name": "x"}, HTTP_HOST="www.pisspooridea.lol", secure=True)
    assert response.status_code == 308


def test_apex_is_served(client):
    assert client.get("/", HTTP_HOST="pisspooridea.lol", secure=True).status_code == 200


def test_unknown_www_host_is_rejected_not_redirected(client):
    response = client.get("/", HTTP_HOST="www.evil.example", secure=True)
    assert response.status_code == 400


def test_health_probe_is_not_redirected(client):
    assert client.get("/healthz", HTTP_HOST="www.pisspooridea.lol").status_code == 200
