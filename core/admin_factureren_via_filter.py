from django.contrib import admin
from django.apps import apps

def apply():
    M = apps.get_model("core", "Member")
    ma = admin.site._registry.get(M)
    if not ma:
        return

    field_names = {f.name for f in M._meta.get_fields() if hasattr(f, "attname")}
    if {"last_name", "first_name"}.issubset(field_names):
        order = ["last_name", "first_name"]; name_fields = ("last_name", "first_name")
    elif {"surname", "given_name"}.issubset(field_names):
        order = ["surname", "given_name"]; name_fields = ("surname", "given_name")
    elif {"family_name", "given_names"}.issubset(field_names):
        order = ["family_name", "given_names"]; name_fields = ("family_name", "given_names")
    elif "name" in field_names:
        order = ["name"]; name_fields = ("name", None)
    else:
        order = ["id"]; name_fields = (None, None)

    def heads_qs():
        try:
            qs = M.objects.filter(household_role="Gezinshoofd")
            if qs.exists():
                return qs
        except Exception:
            pass
        try:
            fld = M._meta.get_field("household_role")
            choices = list(getattr(fld, "choices", []) or [])
            keys = [k for (k, lbl) in choices if str(lbl).lower().strip().startswith("gezinshoofd") or "head" in str(lbl).lower()]
            if keys:
                qs = M.objects.filter(household_role__in=keys)
                if qs.exists():
                    return qs
        except Exception:
            pass
        return M.objects.all()

    orig_formfk = ma.formfield_for_foreignkey

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "factureren_via":
            kwargs["queryset"] = heads_qs().order_by(*order)
            formfield = orig_formfk(db_field, request, **kwargs)
            def label_from_instance(obj):
                ln_field, fn_field = name_fields
                ln = getattr(obj, ln_field, "") if ln_field else ""
                fn = getattr(obj, fn_field, "") if fn_field else ""
                ln, fn = (ln or "").strip(), (fn or "").strip()
                if ln and fn: return f"{ln}, {fn}"
                if ln: return ln
                if fn: return fn
                name = (getattr(obj, "name", "") or "").strip()
                return name or f"#{obj.pk}"
            try:
                formfield.label_from_instance = label_from_instance
            except Exception:
                pass
            return formfield
        return orig_formfk(db_field, request, **kwargs)

    setattr(ma.__class__, "formfield_for_foreignkey", formfield_for_foreignkey)

    orig_get_wrapper = getattr(ma.__class__, "get_related_field_wrapper", None)
    if orig_get_wrapper:
        def get_related_field_wrapper(self, db_field, request, *args, **kwargs):
            wrapper = orig_get_wrapper(self, db_field, request, *args, **kwargs)
            if db_field.name == "factureren_via":
                for attr in ("can_add_related","can_change_related","can_delete_related","can_view_related"):
                    if hasattr(wrapper, attr):
                        setattr(wrapper, attr, False)
            return wrapper
        setattr(ma.__class__, "get_related_field_wrapper", get_related_field_wrapper)
