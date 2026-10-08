import pytest

from ads.legal import ADVERTISER_TERMS_VERSION, advertiser_terms_sha256

# Pinned like the venue agreement: edit the text -> new version + new hash.
ADVERTISER_TERMS = {
    "2026-10-v1": "cdb13c1c9afae2a13eec7a1c8a59d5049d1b60c9c92900a4ae0cda794527e008",
}


def test_advertiser_terms_text_matches_its_version():
    assert ADVERTISER_TERMS[ADVERTISER_TERMS_VERSION] == advertiser_terms_sha256()


@pytest.mark.parametrize(
    ("path", "marker"),
    [
        ("/terms", "Not for emergencies"),
        ("/terms", "Put our stickers on property without the owner"),
        ("/advertising-terms", "Political ads"),
        ("/advertising-policy", "Advertiser Terms"),
    ],
)
def test_legal_pages_render(client, db, path, marker):
    response = client.get(path)
    assert response.status_code == 200
    assert marker in response.content.decode()


def test_legal_pages_name_the_operator_and_notice_address(client, db, settings):
    settings.OPERATOR_LEGAL_NAME = "PPI Media LLC, d/b/a Piss Poor Idea"
    settings.LEGAL_EMAIL = "legal@example.com"
    for path in ("/terms", "/advertising-terms"):
        body = client.get(path).content.decode()
        assert "PPI Media LLC, d/b/a Piss Poor Idea" in body
        assert "legal@example.com" in body
