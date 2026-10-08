from django.urls import path

from . import views

app_name = "feedback"

urlpatterns = [
    path("b/<str:token>", views.board, name="board"),
    path("b/<str:token>/requests/<int:pk>", views.update_request, name="update_request"),
    path("b/<str:token>/alerts", views.alerts, name="alerts"),
    path("b/<str:token>/alerts/test", views.test_alert, name="test_alert"),
]
