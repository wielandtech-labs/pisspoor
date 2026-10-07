from django.urls import path, register_converter

from venues.models import CODE_ALPHABET, CODE_LENGTH

from . import views


class ShortCodeConverter:
    # Case-insensitive so a hand-typed code in caps still works.
    regex = f"[{CODE_ALPHABET}{CODE_ALPHABET.upper()}]{{{CODE_LENGTH}}}"

    def to_python(self, value: str) -> str:
        return value.lower()

    def to_url(self, value: str) -> str:
        return value


register_converter(ShortCodeConverter, "code")

app_name = "scans"

urlpatterns = [
    path("<code:code>", views.landing, name="landing"),
    path("<code:code>/rate", views.rate, name="rate"),
    path("<code:code>/report", views.report, name="report"),
    path("<code:code>/ad/<int:campaign_id>", views.ad_click, name="ad_click"),
]
