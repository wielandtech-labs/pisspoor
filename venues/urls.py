from django.urls import path

from . import views

app_name = "venues"

urlpatterns = [
    path("print/sheet", views.print_sheet, name="print_sheet"),
    path("print/<str:code>.svg", views.sticker_svg, name="sticker_svg"),
]
