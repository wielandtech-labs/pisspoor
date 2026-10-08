from pathlib import Path

from django.conf import settings

# `<meta name="referrer" content="no-referrer">` makes browsers send
# `Origin: null` on the page's own form posts, and Django's CSRF check
# rejects that with 403. It silently broke every button on the venue board
# in real browsers (the test client sends no Origin, so tests passed).
# Use "same-origin": secret links still never leak to other sites.


def test_no_template_uses_no_referrer():
    offenders = [
        str(path.relative_to(settings.BASE_DIR))
        for path in Path(settings.BASE_DIR).rglob("*.html")
        if ".venv" not in path.parts and 'content="no-referrer"' in path.read_text("utf-8")
    ]
    assert offenders == []


def test_board_form_posts_pass_csrf_with_a_real_origin(venue, client):
    from django.test import Client

    from feedback.models import MaintenanceRequest
    from venues.models import Placement

    placement = Placement.objects.create(venue=venue, label="Stall")
    item = MaintenanceRequest.objects.create(placement=placement, issue="no_tp", visitor_hash="v")
    browser = Client(enforce_csrf_checks=True)
    page = browser.get(f"/b/{venue.board_token}")
    token = page.cookies["csrftoken"].value
    response = browser.post(
        f"/b/{venue.board_token}/requests/{item.pk}",
        {"action": "resolve", "csrfmiddlewaretoken": token},
        HTTP_ORIGIN="http://testserver",
    )
    assert response.status_code == 302
