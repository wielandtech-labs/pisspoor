from django import forms
from django.conf import settings
from django.shortcuts import redirect, render

from .models import Lead
from .scenes import homepage_scenes
from .sites import is_fun_site


class LeadForm(forms.ModelForm):
    # Honeypot: hidden from people, irresistible to form-filling bots.
    website = forms.CharField(
        required=False, widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"})
    )

    class Meta:
        model = Lead
        fields = ["kind", "name", "business", "email", "phone", "message"]
        widgets = {"message": forms.Textarea(attrs={"rows": 4})}


def home(request):
    if is_fun_site(request):
        return render(request, "marketing/fun.html", homepage_scenes(settings.PUBLIC_BASE_URL))
    form = LeadForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if not form.cleaned_data["website"]:
            form.save()
        return redirect("/?thanks=1#contact")
    return render(
        request,
        "marketing/home.html",
        {
            "form": form,
            "thanks": request.GET.get("thanks") == "1",
            **homepage_scenes(settings.PUBLIC_BASE_URL),
        },
    )


def privacy(request):
    return render(request, "marketing/privacy.html")
