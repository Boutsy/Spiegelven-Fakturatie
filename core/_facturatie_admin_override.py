
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.apps import apps

Member = apps.get_model("core", "Member")

# Haal bestaande admin-registratie op
site = admin.site
original_admin = site._registry.get(Member)

def household_role_label(obj):
    try:
        if hasattr(obj, "get_household_role_display"):
            lbl = obj.get_household_role_display()
        else:
            lbl = str(getattr(obj, "household_role", "")) or "—"
    except Exception:
        lbl = "—"
    l = (lbl or "").strip().lower()
    if l in ("head","gezinshoofd","household head","hoofdlid"):
        return "👑 Gezinshoofd"
    if l in ("individual","individueel","solo"):
        return "👤 Individueel"
    if l in ("child","kind","kid"):
        return "🧒 Kind"
    if l in ("partner","partnerlid"):
        return "👥 Partner"
    return lbl or "—"

if original_admin:
    Base = original_admin.__class__
else:
    # fallback als er nog niets geregistreerd was
    from django.contrib.admin import ModelAdmin as Base

class PatchedMemberAdmin(Base):
    # behoud inlines/opties van de bestaande admin als die er waren
    pass

# readonly display-methode toevoegen
if not hasattr(PatchedMemberAdmin, "household_role_display"):
    def household_role_display(self, obj):
        return household_role_label(obj)
    household_role_display.short_description = _("Rol binnen huishouden")
    setattr(PatchedMemberAdmin, "household_role_display", household_role_display)

# get_fieldsets uitbreiden met "Facturatie"
_old_get_fieldsets = getattr(PatchedMemberAdmin, "get_fieldsets", None)

def _ensure_tuple(fs):
    if fs is None: return tuple()
    if isinstance(fs, tuple): return fs
    if isinstance(fs, list): return tuple(fs)
    return tuple(fs)

def _has_facturatie(fs):
    for title, cfg in fs:
        try:
            if str(title).strip().lower() in ("facturatie","billing","facturation"):
                return True
            fields = tuple(cfg.get("fields", ()))
            if "billing_account" in fields and "household_role_display" in fields:
                return True
        except Exception:
            continue
    return False

from django.contrib import admin as _admin_mod
def _base_get_fieldsets(self, request, obj=None):
    if _old_get_fieldsets and callable(_old_get_fieldsets):
        fs = _old_get_fieldsets(self, request, obj)
    else:
        fs = _admin_mod.ModelAdmin.get_fieldsets(self, request, obj)
    fs = list(_ensure_tuple(fs))
    if not _has_facturatie(fs):
        fs.append((_("Facturatie"), {"fields": ("billing_account", "household_role_display")}))
    return tuple(fs)

setattr(PatchedMemberAdmin, "get_fieldsets", _base_get_fieldsets)

# Inlines van de originele admin meenemen (als die er zijn)
if original_admin:
    try:
        current_inlines = list(getattr(original_admin, "inlines", []) or [])
        PatchedMemberAdmin.inlines = current_inlines
    except Exception:
        pass

# Unregister + register
try:
    site.unregister(Member)
except Exception:
    pass
site.register(Member, PatchedMemberAdmin)
