
from django.utils.translation import gettext_lazy as _
from django.contrib import admin
from django.apps import apps

def _detect_factureervia_field(Member):
    """
    Zoek een ForeignKey van Member -> Member die waarschijnlijk 'gefactureerd via' betekent.
    Heuristiek:
      1) naam in een bekende lijst
      2) verbose_name bevat 'factur' of 'gefacture' of 'invoice' of 'bill'
    """
    preferred = {
        "gefactureerd_via", "factureren_via", "factureervia",
        "billed_via", "invoiced_via", "billed_via_member", "invoiced_via_member"
    }
    # 1) directe naam-match
    for f in Member._meta.get_fields():
        if getattr(f, "name", None) in preferred:
            return f.name
    # 2) heuristisch op basis van verbose_name + type
    for f in Member._meta.get_fields():
        if getattr(f, "is_relation", False) and getattr(f, "many_to_one", False):
            rel = getattr(f, "remote_field", None)
            if rel and getattr(rel, "model", None) is Member:
                vn = (getattr(f, "verbose_name", "") or "").lower()
                if any(k in vn for k in ("factur", "gefacture", "invoice", "bill")):
                    return f.name
    return None

def apply_member_id_and_facturatie():
    M = apps.get_model("core","Member")
    ma = admin.site._registry.get(M)
    if not ma:
        return

    factureervia = _detect_factureervia_field(M)

    get_fieldsets_orig = ma.__class__.get_fieldsets

    def new_get_fieldsets(self, request, obj=None, *args, **kwargs):
        fs = list(get_fieldsets_orig(self, request, obj))
        out = []

        for title, cfg in fs:
            t = str(title or "").strip()
            tl = t.lower()

            # id-veld niet apart tonen in een fieldset
            fields = list(cfg.get("fields", ()))
            fields = [f for f in fields if f != "id"]
            cfg = dict(cfg)
            cfg["fields"] = tuple(fields)

            # "Interne info" wég
            if tl in {"interne info", "interne-info", "internal", "internal info"}:
                continue

            # Titelbalk: toon ID bij "Facturatie"
            if tl in {"facturatie", "facturering", "billing"}:
                # Voeg factureervia-veld toe indien gevonden en nog niet aanwezig
                if factureervia and factureervia not in fields:
                    try:
                        idx = fields.index("billing_account") + 1
                    except ValueError:
                        idx = len(fields)
                    fields.insert(idx, factureervia)
                    cfg["fields"] = tuple(fields)

                title = _("Facturatie") if obj is None else f"{_('Facturatie')} — ID {obj.pk}"
            else:
                title = _("Identiteit") if (tl in {"identiteit","identity"}) else t

            out.append((title, cfg))

        return tuple(out)

    setattr(ma.__class__, "get_fieldsets", new_get_fieldsets)
