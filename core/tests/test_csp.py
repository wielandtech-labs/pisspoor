import pytest
from django.http import HttpResponse

from core.middleware import ContentSecurityPolicyMiddleware

HEADER = "Content-Security-Policy-Report-Only"


@pytest.mark.django_db
def test_pages_carry_the_report_only_policy(client, settings):
    response = client.get("/")
    assert response[HEADER] == settings.CONTENT_SECURITY_POLICY_REPORT_ONLY
    assert "Content-Security-Policy" not in response


def test_policy_keeps_the_hardening_directives(settings):
    policy = settings.CONTENT_SECURITY_POLICY_REPORT_ONLY
    for directive in ("object-src 'none'", "base-uri 'self'", "frame-ancestors 'none'"):
        assert directive in policy


def test_a_view_header_wins(rf, settings):
    def view(request):
        response = HttpResponse()
        response[HEADER] = "default-src 'none'"
        return response

    response = ContentSecurityPolicyMiddleware(view)(rf.get("/"))
    assert response[HEADER] == "default-src 'none'"


def test_empty_setting_sends_nothing(rf, settings):
    settings.CONTENT_SECURITY_POLICY_REPORT_ONLY = ""
    response = ContentSecurityPolicyMiddleware(lambda r: HttpResponse())(rf.get("/"))
    assert HEADER not in response
