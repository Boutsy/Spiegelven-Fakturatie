
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.apps import apps

Member = apps.get_model("core","Member")
site = admin.site
ma = site._registry.get(Member)
if not ma:
    raise SystemExit("MemberAdmin niet gevonden.")

Cls = ma.__class__

def _ensure_tuple(fs):
    if fs is None: return tuple()
    if isinstance(fs, tuple): return fs
    if isinstance(fs, list): return tuple(fs)
    return tuple(fs)

def _norm(x): return (str(x or "")).strip().lower()

_old_get_fieldsets = getattr(Cls, "get_fieldsets", None)

def get_fieldsets_with_role(self, request, obj=None):
    # haal bestaande fieldsets op (van huidige admin)
    if callable(_old_get_fieldsets):
        fs = _old_get_fieldsets(self, request, obj)
    else:
        fs = admin.ModelAdmin.get_fieldsets(self, request, obj)
    fs = list(_ensure_tuple(fs))

    # loop over secties, zoek "Facturatie"; voeg household_role_display in
    updated = False
    for i, (title, cfg) in enumerate(fs):
        title_norm = _norm(title)
        if title_norm == "facturatie":
            fields = list(cfg.get("fields", ()))
            if "household_role_display" not in fields:
                # insert na billing_account indien aanwezig, anders op het einde
                try:
                    idx = fields.index("billing_account") + 1
                except ValueError:
                    idx = len(fields)
                fields.insert(idx, "household_role_display")
                cfg = dict(cfg)
                cfg["fields"] = tuple(fields)
                fs[i] = (title, cfg)
                updated = True
            break

    # Als nog geen Facturatie-sectie gevonden werd, voeg nieuwe toe
    if not updated:
        fs.append( (_("Facturatie"), {"fields": ("billing_account", "household_role_display")}) )

    return tuple(fs)

setattr(Cls, "get_fieldsets", get_fieldsets_with_role)
print("✓ get_fieldsets gepatcht: household_role_display wordt in Facturatie geplaatst.")
