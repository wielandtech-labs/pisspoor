import pytest


def test_healthz_never_touches_the_database(client):
    # No django_db mark: pytest-django raises if the view touches the database.
    response = client.get("/healthz", HTTP_HOST="10.42.0.7:8080")
    assert response.status_code == 200


@pytest.mark.django_db
def test_readyz_checks_the_database(client):
    response = client.get("/readyz", HTTP_HOST="10.42.0.7:8080")
    assert response.status_code == 200
    assert response.json()["database"] == "ok"
