from django.urls import path

from . import views

app_name = "marketing"

urlpatterns = [
    path("", views.home, name="home"),
    path("privacy", views.privacy, name="privacy"),
    path("terms", views.terms, name="terms"),
    path("robots.txt", views.robots_txt, name="robots"),
    path("sitemap.xml", views.sitemap_xml, name="sitemap"),
]
