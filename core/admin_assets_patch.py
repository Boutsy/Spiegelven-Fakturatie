
from django.utils.translation import gettext_lazy as _
from django.contrib import admin
from django.apps import apps

# Probeer MemberAdmin op te halen uit de bestaande admin
try:
    from .admin import MemberAdmin  # type: ignore
except Exception:
    MemberAdmin = None

MemberAsset = apps.get_model("core", "MemberAsset")

class MemberAssetInline(admin.TabularInline):
    model = MemberAsset
    extra = 0
    can_delete = False
    verbose_name = _("Lid-actief")
    verbose_name_plural = _("Lid-activa")
    fields = ("asset_type_nl", "identifier", "active")
    readonly_fields = ("asset_type_nl", "identifier", "active")

    @admin.display(description=_("Type"))
    def asset_type_nl(self, obj):
        # gebruik choice label indien aanwezig
        try:
            if hasattr(obj, "get_asset_type_display"):
                disp = obj.get_asset_type_display()
                if disp:
                    return disp
        except Exception:
            pass
        code = getattr(obj, "asset_type", "") or ""
        mapping = {
            "VST_KAST": "Kast",
            "KAR_KLN": "Kar-kast",
            "KAR_ELEC": "E-kar-kast",
            "LOCKER": "Kast",
        }
        return mapping.get(code, code or "–")

def apply_assets_inline():
    if MemberAdmin is None:
        return
    current = list(getattr(MemberAdmin, "inlines", []) or [])
    if MemberAssetInline not in current:
        current.append(MemberAssetInline)
    MemberAdmin.inlines = current
