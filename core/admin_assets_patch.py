
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
    fields = ("asset_type", "identifier", "active")
    readonly_fields = ()

def apply_assets_inline():
    if MemberAdmin is None:
        return
    current = list(getattr(MemberAdmin, "inlines", []) or [])
    if MemberAssetInline not in current:
        current.append(MemberAssetInline)
    MemberAdmin.inlines = current
