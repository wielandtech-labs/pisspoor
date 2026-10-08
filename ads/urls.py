from django.urls import path

from . import views

app_name = "ads"

urlpatterns = [
    path("advertising-policy", views.policy, name="policy"),
    path("political-ads", views.political_archive, name="political_archive"),
    path("advertising-terms", views.advertiser_terms, name="advertiser_terms"),
]
