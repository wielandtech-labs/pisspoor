from django.urls import path

from . import views

app_name = "feedback"

urlpatterns = [
    path("b/<str:token>", views.board, name="board"),
    path("b/<str:token>/requests/<int:pk>", views.update_request, name="update_request"),
]
