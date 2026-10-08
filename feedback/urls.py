from django.urls import path

from . import views

app_name = "feedback"

urlpatterns = [
    path("b/<str:token>", views.board, name="board"),
    path("b/<str:token>/requests/<int:pk>", views.update_request, name="update_request"),
    path("b/<str:token>/alerts", views.alerts, name="alerts"),
    path("b/<str:token>/leaderboard", views.toggle_leaderboard, name="toggle_leaderboard"),
    path("cleanest", views.cleanest, name="cleanest"),
    path("b/<str:token>/alerts/test", views.test_alert, name="test_alert"),
]
