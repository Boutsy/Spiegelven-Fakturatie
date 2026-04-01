
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

# zoekvelden (naam, e-mail, postcode, telefoons) zoals in de NL admin
PatchedMemberAdmin.search_fields = (
    "last_name", "first_name", "email", "postal_code", "city",
    "phone_private", "phone_mobile", "phone_work",
)

# readonly display-methode toevoegen
if not hasattr(PatchedMemberAdmin, "household_role_display"):
    @admin.display(description=_("Rol binnen huishouden"))
    def household_role_display(self, obj):
        try:
            if hasattr(obj, "get_household_role_display"):
                lbl = obj.get_household_role_display() or ""
            else:
                lbl = getattr(obj, "household_role", "") or ""
        except Exception:
            lbl = ""
        l = (lbl or "").strip().lower()
        if l in {"head","gezinshoofd","household head","hoofdlid"}:
            return "Gezinshoofd"
        if l in {"individual","individueel","solo"}:
            return "Individueel"
        if l in {"child","kind","kid"}:
            return "Kind"
        if l in {"partner","partnerlid"}:
            return "Partner"
        return lbl or "—"
    setattr(PatchedMemberAdmin, "household_role_display", household_role_display)

# Zorg dat het veld read-only is zodat de ModelForm het accepteert
existing_readonly = getattr(PatchedMemberAdmin, "readonly_fields", ()) or ()
if "household_role_display" not in existing_readonly:
    PatchedMemberAdmin.readonly_fields = tuple(existing_readonly) + ("household_role_display",)

# get_fieldsets: behoud de bestaande van MemberAdmin zonder aanpassingen
_old_get_fieldsets = getattr(original_admin, "get_fieldsets", None)
if _old_get_fieldsets and callable(_old_get_fieldsets):
    setattr(PatchedMemberAdmin, "get_fieldsets", _old_get_fieldsets)

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
