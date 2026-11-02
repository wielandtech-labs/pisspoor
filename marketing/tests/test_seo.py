import pytest

from marketing.views import SITEMAP_PAGES

pytestmark = pytest.mark.django_db

PROD = "pisspooridea.lol"


@pytest.fixture(autouse=True)
def _hosts(settings):
    settings.ALLOWED_HOSTS = [PROD, "www.pisspooridea.lol", "pr-1-pisspoor.review.wielandtech.com"]
    settings.PUBLIC_BASE_URL = "https://pisspooridea.lol"


def test_robots_points_at_sitemap_on_prod(client):
    response = client.get("/robots.txt", HTTP_HOST=PROD, secure=True)
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/plain")
    body = response.content.decode()
    assert "Sitemap: https://pisspooridea.lol/sitemap.xml" in body
    assert "Disallow: /b/" in body


def test_sitemap_lists_every_public_page_and_each_one_works(client):
    response = client.get("/sitemap.xml", HTTP_HOST=PROD, secure=True)
    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/xml")
    body = response.content.decode()
    assert body.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    assert body.count("<loc>") == len(SITEMAP_PAGES)
    assert "<loc>https://pisspooridea.lol/</loc>" in body
    for loc in body.split("<loc>")[1:]:
        path = loc.split("</loc>")[0].removeprefix("https://pisspooridea.lol")
        assert client.get(path, HTTP_HOST=PROD, secure=True).status_code == 200, path


def test_www_sitemap_redirects_to_the_apex_one(client):
    response = client.get("/sitemap.xml", HTTP_HOST="www.pisspooridea.lol", secure=True)
    assert response.status_code == 308
    assert response["Location"] == "https://pisspooridea.lol/sitemap.xml"


def test_review_hosts_stay_out_of_search(client):
    host = "pr-1-pisspoor.review.wielandtech.com"
    robots = client.get("/robots.txt", HTTP_HOST=host, secure=True)
    assert robots.content.decode() == "User-agent: *\nDisallow: /\n"
    assert client.get("/sitemap.xml", HTTP_HOST=host, secure=True).status_code == 404
