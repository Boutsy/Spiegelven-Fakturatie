from django.contrib import admin
from django.apps import apps
from django.utils.html import format_html_join

def _order_fields(Model):
    names = {f.name for f in Model._meta.get_fields() if hasattr(f, "attname")}
    if {"last_name", "first_name"}.issubset(names):
        return ["last_name", "first_name"]
    if {"surname", "given_name"}.issubset(names):
        return ["surname", "given_name"]
    if {"family_name", "given_names"}.issubset(names):
        return ["family_name", "given_names"]
    if "name" in names:
        return ["name"]
    return ["id"]

def apply():
    M = apps.get_model("core", "Member")
    ma = admin.site._registry.get(M)
    if not ma:
        return

    order = _order_fields(M)

    def gezinsleden(self, obj):
        if obj is None:
            return ""
        qs = M.objects.filter(factureren_via=obj).order_by(*order).only("id")
        if not qs.exists():
            return "—"
        rows = []
        for m in qs:
            last = getattr(m, "last_name", None) or getattr(m, "surname", None) or getattr(m, "family_name", None)
            first = getattr(m, "first_name", None) or getattr(m, "given_name", None) or getattr(m, "given_names", None)
            if last and first:
                label = f"{last} {first}"
            elif hasattr(m, "name") and getattr(m, "name"):
                label = getattr(m, "name")
            else:
                label = str(m)
            rows.append((f"{label} — ID {m.pk}",))
        return format_html_join("<br>", "{}", rows)

    setattr(ma.__class__, "gezinsleden", gezinsleden)

    orig_ro = getattr(ma.__class__, "get_readonly_fields", None)
    def get_readonly_fields(self, request, obj=None):
        base = []
        if orig_ro:
            base = list(orig_ro(self, request, obj))
        if "gezinsleden" not in base:
            base.append("gezinsleden")
        return tuple(base)
    setattr(ma.__class__, "get_readonly_fields", get_readonly_fields)

    orig_fs = ma.__class__.get_fieldsets
    def get_fieldsets(self, request, obj=None):
        fs = list(orig_fs(self, request, obj))
        fs.append(("Gezinsleden", {"fields": ("gezinsleden",)}))
        return tuple(fs)
    setattr(ma.__class__, "get_fieldsets", get_fieldsets)
