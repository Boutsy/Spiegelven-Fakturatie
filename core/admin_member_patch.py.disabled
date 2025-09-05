from django.contrib import admin
from .models import Member

def _has_field(model, name):
    try:
        model._meta.get_field(name)
        return True
    except Exception:
        return False

class FamilyMemberInline(admin.TabularInline):
    model = Member
    fk_name = "household_head"
    extra = 0
    can_delete = True
    fields = ("first_name","last_name","date_of_birth","household_role","membership_mode","federation_via_club","active","email","phone")
    show_change_link = True

admin.site.site_header = "Spiegelven Facturatie"
admin.site.site_title = "Spiegelven Facturatie"
admin.site.index_title = "Beheer"

ma = admin.site._registry.get(Member)
if ma:
    cur_inlines = list(getattr(ma, "inlines", []))
    if FamilyMemberInline not in [type(x) for x in cur_inlines]:
        ma.inlines = cur_inlines + [FamilyMemberInline]

    fs = getattr(ma, "fieldsets", None)
    used = set()
    if fs:
        for _title, opts in fs:
            for f in opts.get("fields", []):
                if isinstance(f, (list, tuple)):
                    for sub in f:
                        used.add(sub)
                else:
                    used.add(f)

    add_blocks = []

    contact_rows = []
    row1 = tuple([f for f in ("email","phone") if _has_field(Member, f) and f not in used])
    if row1:
        contact_rows.append(row1)
    row2 = tuple([f for f in ("street","postal_code","city") if _has_field(Member, f) and f not in used])
    if row2:
        contact_rows.append(row2)
    row3 = tuple([f for f in ("country",) if _has_field(Member, f) and f not in used])
    if row3:
        contact_rows.append(row3)
    if contact_rows:
        add_blocks.append(("Contact & adres", {"fields": tuple(contact_rows)}))

    fam_fields = tuple([f for f in ("household_head","household_role") if _has_field(Member, f) and f not in used])
    if fam_fields:
        add_blocks.append(("Gezin", {"fields": fam_fields}))

    bill_fields = tuple([f for f in ("billing_account",) if _has_field(Member, "billing_account") and "billing_account" not in used])
    if bill_fields:
        add_blocks.append(("Facturatie", {"fields": bill_fields}))

    if add_blocks:
        if fs:
            ma.fieldsets = tuple(fs) + tuple(add_blocks)
        else:
            ma.fieldsets = tuple(add_blocks)
