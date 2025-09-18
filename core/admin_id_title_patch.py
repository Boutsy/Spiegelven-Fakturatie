from django.utils.translation import gettext_lazy as _
from django.contrib import admin
from django.apps import apps

def apply_member_id_and_facturatie():
    """
    - Verwijdert de rubriek "Interne info"
    - Haalt het veld "id" uit de veldenlijst
    - Toont het ID rechts in de titelbalk van "Facturatie"
    - Zorgt dat "Gefactureerd via" (FK naar Member) in Facturatie staat als het veld bestaat
    """
    Member = apps.get_model("core", "Member")
    ma = admin.site._registry.get(Member)
    if not ma:
        return
    C = ma.__class__

    # Zoek hoe het FK-veld naar "gefactureerd via" heet (robust: controleer meerdere kandidaten)
    model_field_names = {f.name for f in Member._meta.get_fields() if getattr(f, "concrete", False)}
    billed_fk_candidates = ["billed_via", "invoice_via", "invoiced_via", "billed_through", "factureren_via"]
    billed_fk = next((n for n in billed_fk_candidates if n in model_field_names), None)

    def new_get_fieldsets(self, request, obj=None):
        original = admin.ModelAdmin.get_fieldsets(self, request, obj)
        fs_out = []

        def norm(s): 
            return (str(s) if s is not None else "").strip().lower()

        for title, cfg in (original or ()):
            t = norm(title)
            fields = list(cfg.get("fields", ()))

            # veld "id" nooit als formulier-veld tonen
            if "id" in fields:
                fields = [f for f in fields if f != "id"]

            # volledige rubriek "Interne info" verbergen
            if t in {"interne info", "interne-info", "internal", "internal info"}:
                continue

            # Facturatie-rubriek: titel verrijken met ID en "gefactureerd via" toevoegen
            if t in {"facturatie", "billing", "invoice"}:
                # Titel: rechts ID tonen wanneer obj bestaat
                title = _("Facturatie") if obj is None else f"{_('Facturatie')} — ID {obj.pk}"
                # Plaats vooraan "gefactureerd via" als dat veld bestaat en nog niet staat
                if billed_fk and billed_fk not in fields:
                    # Zet het direct na "billing_account" als die bestaat, anders vooraan
                    if "billing_account" in fields:
                        idx = fields.index("billing_account") + 1
                        fields.insert(idx, billed_fk)
                    else:
                        fields.insert(0, billed_fk)

            cfg = dict(cfg)
            cfg["fields"] = tuple(fields)
            fs_out.append((title, cfg))

        # Als er helemaal geen Facturatie-rubriek bestond, maak er één met ID in titel.
        if not any(norm(t) in {"facturatie", "billing", "invoice"} for t, _ in fs_out):
            new_fields = []
            if billed_fk:
                new_fields.append(billed_fk)
            if "billing_account" in model_field_names:
                new_fields.append("billing_account")
            if "course" in model_field_names:
                new_fields.append("course")
            if "active" in model_field_names:
                new_fields.append("active")
            title = _("Facturatie") if obj is None else f"{_('Facturatie')} — ID {obj.pk}"
            fs_out.append((title, {"fields": tuple(new_fields)}))

        return tuple(fs_out)

    setattr(C, "get_fieldsets", new_get_fieldsets)
