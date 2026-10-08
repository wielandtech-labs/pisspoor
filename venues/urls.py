from django.urls import path

from . import views

app_name = "venues"

urlpatterns = [
    path("venues/join", views.join, name="join"),
    path("venues/join/done/<str:token>", views.join_done, name="join_done"),
    path("venues/agreement", views.agreement, name="agreement"),
    path("print/sheet", views.print_sheet, name="print_sheet"),
    path("print/<str:code>.svg", views.sticker_svg, name="sticker_svg"),
]
