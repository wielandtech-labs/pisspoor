from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Piss Poor Idea HQ"
admin.site.site_title = "Piss Poor Idea"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    path("", include("marketing.urls")),
    path("", include("venues.urls")),
    path("", include("feedback.urls")),
    # Last: short codes live at the URL root and must never shadow a real page.
    path("", include("scans.urls")),
]
