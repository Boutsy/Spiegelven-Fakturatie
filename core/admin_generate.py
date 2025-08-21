from datetime import date, timedelta
import io

from django import forms
from django.contrib import admin, messages
from django.core.management import call_command
from django.shortcuts import redirect, render
from django.urls import path

from .models import Invoice

def _first_monday(year: int) -> date:
    d = date(year, 1, 1)
    # maandag = 0
    return d + timedelta(days=(7 - d.weekday()) % 7)

class _GenereerJaarForm(forms.Form):
    jaar = forms.IntegerField(label="Jaar", initial=date.today().year, min_value=2000, max_value=2100)
    factuurdatum = forms.DateField(
        label="Factuurdatum (optioneel)",
        required=False,
        help_text="Laat leeg om de standaard van de generator te gebruiken. "
                  "Gebruik normaal de eerste maandag van het jaar."
    )
    echt_aanmaken = forms.BooleanField(
        label="Echt aanmaken (commit)",
        required=False,
        initial=True,
        help_text="Vink aan om effectief facturen te bewaren."
    )

class _GenerateMixin:
    """Voegt een extra admin-view + knop op de changelist toe."""

    change_list_template = "admin/core/invoice/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        my_name = f"{self.model._meta.app_label}_{self.model._meta.model_name}_generate_yearly"
        extra = [
            path(
                "genereer-jaar/",
                self.admin_site.admin_view(self.generate_year_view),
                name=my_name,
            )
        ]
        return extra + urls

    def generate_year_view(self, request):
        # Voorvullen: eerste maandag van gekozen/actueel jaar
        initial = {}
        try:
            y = int(request.GET.get("jaar", date.today().year))
            initial["jaar"] = y
            initial["factuurdatum"] = _first_monday(y)
        except Exception:
            pass

        if request.method == "POST":
            form = _GenereerJaarForm(request.POST)
            if form.is_valid():
                jaar = form.cleaned_data["jaar"]
                factuurdatum = form.cleaned_data["factuurdatum"]
                commit = form.cleaned_data["echt_aanmaken"]

                buf = io.StringIO()
                # Bouw argumenten op voor de bestaande management command
                kwargs = {"year": str(jaar)}
                if commit:
                    kwargs["commit"] = True

                # Probeer (optioneel) de factuurdatum door te geven als de command dat ondersteunt
                try:
                    if factuurdatum:
                        kwargs["issue_date"] = factuurdatum.isoformat()
                    call_command("generate_yearly_invoices", stdout=buf, **kwargs)
                except TypeError:
                    # Oudere variant zonder issue_date-parameter
                    call_command("generate_yearly_invoices", stdout=buf, year=str(jaar), commit=commit)

                output = buf.getvalue().strip() or "Generator voltooid."
                messages.success(
                    request,
                    f"Jaarfacturen voor {jaar} uitgevoerd.<br><pre style='white-space:pre-wrap'>{output}</pre>",
                )
                return redirect("admin:core_invoice_changelist")
        else:
            form = _GenereerJaarForm(initial=initial)

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Genereer jaarfacturen",
            "form": form,
        }
        return render(request, "admin/generate_year_form.html", context)

# Huidige Invoice-admin pakken, subclassen met onze mixin, en opnieuw registreren
try:
    orig_admin = admin.site._registry[Invoice]
    admin.site.unregister(Invoice)

    @admin.register(Invoice)
    class PatchedInvoiceAdmin(_GenerateMixin, orig_admin.__class__):
        pass
except Exception:
    # Als nog niet geregistreerd (of iets gaat mis), registreren we minimaal met alleen onze mixin.
    @admin.register(Invoice)
    class PatchedInvoiceAdmin(_GenerateMixin, admin.ModelAdmin):
        pass