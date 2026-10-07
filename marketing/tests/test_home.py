def test_homepage_renders(client, settings):
    settings.ALLOWED_HOSTS = ["testserver"]
    response = client.get("/")
    assert response.status_code == 200
