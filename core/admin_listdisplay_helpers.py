from datetime import date
from django.contrib import admin
from django.apps import apps

Member = apps.get_model("core", "Member")


def _fmt_be(n: str | None) -> str:
    if not n:
        return "—"
    s = str(n).replace(" ", "").replace("-", "")
    if s.startswith("+32"):
        s = "0" + s[3:]
    return s or "—"


def apply_listdisplay_helpers():
    ma = admin.site._registry.get(Member)
    if not ma:
        return
    C = ma.__class__
    # age_display
    if not hasattr(C, "age_display"):
        def age_display(self, obj):
            dob = getattr(obj, "date_of_birth", None)
            if not dob:
                return "—"
            t = date.today()
            return t.year - dob.year - ((t.month, t.day) < (dob.month, dob.day))
        age_display.short_description = "Leeftijd"
        setattr(C, "age_display", age_display)
    # external_id_display
    if not hasattr(C, "external_id_display"):
        def external_id_display(self, obj):
            return getattr(obj, "external_id", "") or "—"
        external_id_display.short_description = "External id"
        setattr(C, "external_id_display", external_id_display)
    # billing_account_display
    if not hasattr(C, "billing_account_display"):
        def billing_account_display(self, obj):
            ba = getattr(obj, "billing_account", None)
            if not ba:
                return "—"
            company = getattr(ba, "company", None)
            if company:
                return company
            ln = getattr(ba, "last_name", "")
            fn = getattr(ba, "first_name", "")
            return (ln + ", " + fn).strip(", ") or "—"
        billing_account_display.short_description = "Facturatie-account"
        setattr(C, "billing_account_display", billing_account_display)
    # phone_private_fmt
    if not hasattr(C, "phone_private_fmt"):
        def phone_private_fmt(self, obj):
            return _fmt_be(getattr(obj, "phone_private", ""))
        phone_private_fmt.short_description = "Telefoon privaat"
        setattr(C, "phone_private_fmt", phone_private_fmt)
    # phone_mobile_fmt
    if not hasattr(C, "phone_mobile_fmt"):
        def phone_mobile_fmt(self, obj):
            return _fmt_be(getattr(obj, "phone_mobile", ""))
        phone_mobile_fmt.short_description = "GSM"
        setattr(C, "phone_mobile_fmt", phone_mobile_fmt)
