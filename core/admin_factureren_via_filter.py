from django.contrib import admin
from django.apps import apps

"""
Filter & sortering voor het FK-veld "factureren_via" in MemberAdmin
- toont enkel Gezinshoofden
- sorteert op achternaam, dan voornaam (met fallbacks als je veldnamen anders zijn)
"""

def apply():
    M = apps.get_model("core", "Member")
    ma = admin.site._registry.get(M)
    if not ma:
        return

    # Bepaal best mogelijke sorteer-velden op het Member-model
    field_names = {f.name for f in M._meta.get_fields() if hasattr(f, "attname")}
    if {"last_name", "first_name"}.issubset(field_names):
        order = ["last_name", "first_name"]
    elif {"surname", "given_name"}.issubset(field_names):
        order = ["surname", "given_name"]
    elif {"family_name", "given_names"}.issubset(field_names):
        order = ["family_name", "given_names"]
    elif "name" in field_names:
        order = ["name"]
    else:
        order = ["id"]  # ultieme fallback

    # Originele (gebonden) methode bewaren
    orig = ma.formfield_for_foreignkey

    # Wrapper met dezelfde signatuur als ModelAdmin: (db_field, request, **kwargs)
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "factureren_via":
            qs = M.objects.filter(household_role="Gezinshoofd").order_by(*order)
            kwargs["queryset"] = qs

        # BELANGRIJK: orig is doorgaans al gebonden → geen self meegeven.
        try:
            return orig(db_field, request, **kwargs)      # moderne Django
        except TypeError:
            # fallback voor randgevallen/andere mixins
            return orig(self, db_field, request, **kwargs)

    # Methode op de admin-klasse vervangen
    setattr(ma.__class__, "formfield_for_foreignkey", formfield_for_foreignkey)
