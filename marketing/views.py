from django.shortcuts import render


def home(request):
    return render(request, "marketing/home.html")
