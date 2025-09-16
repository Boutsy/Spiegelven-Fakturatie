import django
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.apps import apps

def apply():
    Member = apps.get_model("core", "Member")
    ma = admin.site._registry.get(Member)
    if not ma:
        return
    C = ma.__class__

    base_get_ro = getattr(C, "get_readonly_fields", admin.ModelAdmin.get_readonly_fields)
    def get_readonly_fields(self, request, obj=None):
        ro = list(base_get_ro(self, request, obj) or ())
        for n in ("household_role_display", "household_role"):
            if n in ro:
                ro.remove(n)
        return tuple(ro)
    setattr(C, "get_readonly_fields", get_readonly_fields)

    base_gfs = getattr(C, "get_fieldsets", admin.ModelAdmin.get_fieldsets)
    def get_fieldsets(self, request, obj=None):
        fs = list(base_gfs(self, request, obj))
        found = False
        for i, (title, cfg) in enumerate(fs):
            if str(title).strip().lower() == "facturatie":
                cfg = dict(cfg)
                fields = list(cfg.get("fields", ()))
                while "household_role_display" in fields:
                    fields.remove("household_role_display")
                if "household_role" not in fields:
                    try:
                        idx = fields.index("billing_account") + 1
                    except ValueError:
                        idx = len(fields)
                    fields.insert(idx, "household_role")
                cfg["fields"] = tuple(fields)
                fs[i] = (title, cfg)
                found = True
                break
        if not found:
            fs.append((_(Facturatie),
                       {"fields": ("billing_account", "household_role", "course", "active")}))
        return tuple(fs)
    setattr(C, "get_fieldsets", get_fieldsets)
