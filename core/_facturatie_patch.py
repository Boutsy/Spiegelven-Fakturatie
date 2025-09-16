
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.apps import apps

# Probeer MemberAdmin uit de bestaande admin te halen
try:
    from .admin import MemberAdmin  # type: ignore
except Exception:
    MemberAdmin = None

Member = apps.get_model("core", "Member")

def household_role_label(obj):
    # gebruik choices-label als beschikbaar
    try:
        if hasattr(obj, "get_household_role_display"):
            lbl = obj.get_household_role_display()
        else:
            lbl = str(getattr(obj, "household_role", "")) or "—"
    except Exception:
        lbl = "—"
    l = (lbl or "").strip().lower()
    if l in ("head", "gezinshoofd", "household head", "hoofdlid"):
        return "👑 Gezinshoofd"
    if l in ("individual", "individueel", "solo"):
        return "👤 Individueel"
    if l in ("child", "kind", "kid"):
        return "🧒 Kind"
    if l in ("partner", "partnerlid"):
        return "👥 Partner"
    return lbl or "—"

def apply_facturatie():
    if MemberAdmin is None:
        return

    # Voeg readonly display-methode toe als die niet bestaat
    if not hasattr(MemberAdmin, "household_role_display"):
        def household_role_display(self, obj):
            return household_role_label(obj)
        household_role_display.short_description = _("Rol binnen huishouden")
        setattr(MemberAdmin, "household_role_display", household_role_display)

    # Injecteer een extra fieldset "Facturatie" (billing_account + rol-display)
    old_get_fieldsets = getattr(MemberAdmin, "get_fieldsets", None)

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

    if callable(old_get_fieldsets):
        def get_fieldsets_with_facturatie(self, request, obj=None):
            fs = list(_ensure_tuple(old_get_fieldsets(self, request, obj)))
            if not _has_facturatie(fs):
                fs.append( (_("Facturatie"), {"fields": ("billing_account", "household_role_display")}) )
            return tuple(fs)
        setattr(MemberAdmin, "get_fieldsets", get_fieldsets_with_facturatie)
    else:
        from django.contrib import admin as _admin_mod
        def get_fieldsets_with_facturatie(self, request, obj=None):
            fs = list(_ensure_tuple(_admin_mod.ModelAdmin.get_fieldsets(self, request, obj)))
            if not _has_facturatie(fs):
                fs.append( (_("Facturatie"), {"fields": ("billing_account", "household_role_display")}) )
            return tuple(fs)
        setattr(MemberAdmin, "get_fieldsets", get_fieldsets_with_facturatie)
