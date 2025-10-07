from datetime import date
from decimal import Decimal
from django import forms
from django.contrib import admin
from django.apps import apps
from django.db import models
from django.contrib import admin as _admin
from django.db.models import F, Value, IntegerField, Case, When, Q
from django.db.models.functions import Coalesce
from django.utils.translation import gettext_lazy as _
from .phonefmt import normalize_phone_be_store, format_phone_be_display
from django.core.exceptions import ValidationError


# -- helpers -------------------------------------------------

def _concrete_fields(model):
    return {f.name: f for f in model._meta.get_fields() if getattr(f, "concrete", False)}

def _exists(model, name: str) -> bool:
    return name in _concrete_fields(model)

def _first_existing(model, names):
    for n in names:
        if _exists(model, n):
            return n
    return None

def _age_on(born, ref_year=None):
    if not born:
        return None
    today = date.today() if ref_year is None else date(ref_year, 7, 1)
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

def _birthdate_field(model):
    pref = ("birth_date", "date_of_birth", "dob", "geboortedatum", "birthdate")
    f = _first_existing(model, pref)
    if f:
        return f
    # fallback: eerste DateField
    for n, f in _concrete_fields(model).items():
        if isinstance(f, models.DateField):
            return n
    return None

def _contact_fields(model):
    order = []
    # adres
    street = _first_existing(model, ("street","address","address1","street1"))
    if street: order.append(street)
    street_no = _first_existing(model, ("street_number","house_number","nr","number"))
    if street_no: order.append(street_no)
    postal = _first_existing(model, ("postal_code","postcode","zip","zip_code"))
    if postal: order.append(postal)
    city = _first_existing(model, ("city","gemeente","municipality","town","plaats"))
    if city: order.append(city)
    country = _first_existing(model, ("country","country_name","country_code"))
    if country: order.append(country)
    email = _first_existing(model, ("email","e_mail"))
    if email: order.append(email)
    # telefoons (echte modelvelden)
    if _exists(model, "phone_private"): order.append("phone_private")
    if _exists(model, "phone_mobile"):  order.append("phone_mobile")
    if _exists(model, "phone_work"):    order.append("phone_work")
    return tuple(order)

EXTERNAL_ID_CANDIDATES = [
    "external_id","externalid","external_member_id","legacy_id","old_id","ext_id","member_external_id",
]

Member = apps.get_model("core", "Member")

# -- Form die bij openen nationale BE-weergave toont, en bij opslaan normaliseert naar +32... --

class MemberAdminForm(forms.ModelForm):
    class Meta:
        model = Member
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        inst = getattr(self, "instance", None)
        if inst and getattr(inst, "pk", None):
            for fn in ("phone_private","phone_mobile","phone_work"):
                if fn in self.fields and hasattr(inst, fn):
                    raw = getattr(inst, fn) or ""
                    self.initial[fn] = format_phone_be_display(raw)

    def clean(self):
        data = super().clean()
        for fn in ("phone_private","phone_mobile","phone_work"):
            if fn in self.fields and data.get(fn) is not None:
                try:
                    data[fn] = normalize_phone_be_store(data.get(fn))
                except Exception:
                    pass
        return data

# -- Admin ---------------------------------------------------

@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    form = MemberAdminForm

    # lijst: toon naam, leeftijd, external id, facturatie, + MOOI geformatteerde telefoons
    list_display = (
        "last_name","first_name",
        "age_display",
        "external_id_display",
        "billing_account_display",
        "phone_private_fmt","phone_mobile_fmt",
    )
    list_display_links = ("last_name","first_name")
    ordering = ("last_name","first_name")
    list_per_page = 50

    # zoeken op naam, e-mail, postcode/gemeente, en telefoons
    search_fields = ("last_name","first_name","email","postal_code","city",
                     "phone_private","phone_mobile","phone_work")
    search_help_text = _("Zoekt in naam, e-mail, postcode/gemeente, telefoons en external ID.")

    # readonly intern ID
    readonly_fields = ("id",)

    _ext_fields = None

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # annotate external id (beste beschikbare kolom)
        if self._ext_fields is None:
            cf = _concrete_fields(Member)
            self._ext_fields = [n for n in EXTERNAL_ID_CANDIDATES if n in cf]
        try:
            if self._ext_fields:
                args = [F(self._ext_fields[0]), *[F(fn) for fn in self._ext_fields[1:]], Value("")]
                qs = qs.annotate(ext_id_any=Coalesce(*args))
        except Exception:
            pass
        # simpele indicator billing
        if _exists(Member, "billing_account"):
            qs = qs.annotate(has_billing=Case(
                When(billing_account__isnull=False, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            ))
        return qs

    # kolommen
    @admin.display(description=_("Leeftijd"))
    def age_display(self, obj):
        bd_name = _birthdate_field(Member)
        born = getattr(obj, bd_name, None) if bd_name else None
        a = _age_on(born)
        return a if a is not None else "—"

    @admin.display(description=_("External ID"), ordering="ext_id_any")
    def external_id_display(self, obj):
        val = getattr(obj, "ext_id_any", None)
        if val not in (None, ""):
            return val
        if self._ext_fields:
            for fn in self._ext_fields:
                v = getattr(obj, fn, None)
                if v not in (None, ""):
                    return v
        return "—"

    @admin.display(description=_("Facturatie via"))
    def billing_account_display(self, obj):
        if _exists(Member, "billing_account") and getattr(obj, "billing_account", None):
            try:
                return str(obj.billing_account)
            except Exception:
                return "Alternatief"
        return "Persoonlijk"

    @admin.display(description=_("Telefoon (privé)"))
    def phone_private_fmt(self, obj):
        return format_phone_be_display(getattr(obj, "phone_private", "") or "")

    @admin.display(description=_("GSM / Mobile"))
    def phone_mobile_fmt(self, obj):
        return format_phone_be_display(getattr(obj, "phone_mobile", "") or "")

    # fieldsets
    def get_fieldsets(self, request, obj=None):
        sections = []
        # Interne info
        sections.append((_('Interne info'), {"fields": ("id",)}))

        # Identiteit
        ident = []
        for f in ("last_name","first_name"):
            if _exists(Member, f): ident.append(f)
        bd = _birthdate_field(Member)
        if bd: ident.append(bd)
        if _exists(Member, "gender"): ident.append("gender")
        if ident:
            sections.append((_('Identiteit'), {"fields": tuple(ident)}))

        # Contact
        contact = _contact_fields(Member)
        if contact:
            sections.append((_('Contact'), {"fields": contact}))

        # Facturatie
        fact = tuple(f for f in ("billing_account","course","active") if _exists(Member, f))
        if fact:
            sections.append((_('Facturatie'), {"fields": fact,
                "description": _("Indien ingevuld, wordt dit facturatieprofiel gebruikt i.p.v. het standaard adres van het lid.")}))
        # Overig
        if _exists(Member, "notes"):
            sections.append((_('Overig'), {"fields": ("notes",)}))
        return tuple(sections)

    # zoeken uitbreiden met external id
    def get_search_results(self, request, queryset, search_term):
        qs, may_have_duplicates = super().get_search_results(request, queryset, search_term)
        if search_term:
            q = Q()
            if self._ext_fields is None:
                self._ext_fields = [n for n in EXTERNAL_ID_CANDIDATES if _exists(Member, n)]
            for fn in self._ext_fields:
                q |= Q(**{f"{fn}__icontains": search_term})
            qs = qs.filter(q) if q else qs
        return qs, may_have_duplicates

# Registreer de rest van core-modellen generiek
_core_app = apps.get_app_config("core")
# voorkom dubbele registratie: sla Member, Product, Invoice, InvoiceLine over
_Skip = {
    apps.get_model("core", "Member"),
    apps.get_model("core", "Product"),
    apps.get_model("core", "Invoice"),
    apps.get_model("core", "InvoiceLine"),
}
for _model in _core_app.get_models():
    if _model in _Skip:
        continue
    try:
        admin.site.register(_model)
    except admin.sites.AlreadyRegistered:
        pass
# --- SAFE SEARCH PATCH (append) ---
try:
    from django.contrib import admin as _admin_mod
    from core.models import Member as _MemberModel
    # Neem de bestaande MemberAdmin-klasse over als die al gedefinieerd is
    MemberAdmin  # noqa: F401  # type: ignore[name-defined]
except NameError:
    MemberAdmin = None  # fallback

if MemberAdmin:
    def _safe_get_search_results(self, request, queryset, search_term):
        # Gebruik de standaard Django-zoeklogica op basis van search_fields
        return super(MemberAdmin, self).get_search_results(request, queryset, search_term)

    # Beperk naar velden die zeker bestaan op Member:
    _safe_fields = (
        "last_name", "first_name", "city",
        "external_id", "email",
        "phone_private", "phone_mobile",
    )

    try:
        MemberAdmin.get_search_results = _safe_get_search_results
        MemberAdmin.search_fields = _safe_fields
    except Exception:
        pass
# --- END SAFE SEARCH PATCH ---

try:
    from core import admin_assets_patch as _ap
    _ap.apply_assets_inline()
except Exception:
    pass

# FACTURATIE_PATCH_HOOK
try:
    from core import _facturatie_patch as _fp
    _fp.apply_facturatie()
except Exception:
    pass

# forceer facturatie fieldset
from core import _facturatie_admin_override  # noqa

# forceer toevoegen van household_role_display in Facturatie
from core import _facturatie_force_insert  # noqa

# -- facturatie fieldsets hotfix --
try:
    from core import admin_facturatie_fix as _af
    _af.apply()
except Exception:
    pass


# --- layout patch: Facturatie met ID + Interne info weg + gefactureerd-via ---
try:
    from core import admin_id_title_patch as _ltp
    _ltp.apply_member_id_and_facturatie()
except Exception:
    pass


# --- hook: filter/sort voor veld "Factureren via" ---
try:
    from core import admin_factureren_via_filter as _fv
    _fv.apply()
except Exception:
    pass


try:
    from core import admin_hide_factureren_icons as _hfi
    _hfi.apply()
except Exception:
    pass


try:
    from core import admin_household_role_choices as _hr
    _hr.apply()
except Exception:
    pass


# hook: gezinsleden-rubriek in MemberAdmin
try:
    from core import admin_gezinsleden as _gz
    _gz.apply()
except Exception:
    pass


# hook: gezinsleden-tabel
try:
    from core import admin_gezinsleden_patch as _g
    _g.apply()
except Exception:
    pass

# === DAGFACTUUR ADMIN (één set: Form -> Inline -> Admin) ===
from django import forms
from django.contrib import admin as _admin
from decimal import Decimal
from django.core.exceptions import ValidationError
from .models import Invoice as _Inv, InvoiceLine as _InvLine, Product as _Prod

class _InvLineForm(forms.ModelForm):
    VAT_CHOICES = [(0, "0"), (6, "6"), (12, "12"), (21, "21")]

    # twee display-velden (geen modelvelden)
    total_excl_display = forms.CharField(required=False, disabled=True, label="Tot. EX.")
    total_incl_display = forms.CharField(required=False, disabled=True, label="Tot. INC.")

    class Meta:
        model = _InvLine
        fields = "__all__"
        localized_fields = ("quantity", "unit_price_excl")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Kortere labels
        if "product" in self.fields:
            # Geen visueel label (we tonen de select + iconen op één lijn)
            self.fields["product"].label = "Produkt"
            # (optioneel) ook geen helptekst
            self.fields["product"].help_text = "Produkt"
        if "description" in self.fields:
            self.fields["description"].label = "Omschrijving"
        if "quantity" in self.fields:
            self.fields["quantity"].label = "Aantal"
        if "unit_price_excl" in self.fields:
            self.fields["unit_price_excl"].label = "Prijs EX."

        # BTW als dropdown (int-coerce)
        if "vat_rate" in self.fields:
            self.fields["vat_rate"] = forms.TypedChoiceField(
                label="BTW",
                choices=self.VAT_CHOICES,
                coerce=int,
                required=True,
                widget=forms.Select(attrs={"style": "min-width:4em; width:4em;"})
            )

        # Specifieke widgets
        if "quantity" in self.fields:
            f = self.fields["quantity"]
            f.localize = True
            f.widget = forms.NumberInput(
                attrs={
                    "style": "text-align:right; width:6em;",
                    "step": "1",        # altijd in eenheden
                    "min": "0",         # geen negatieve aantallen
                }
            )

        if "unit_price_excl" in self.fields:
            f = self.fields["unit_price_excl"]
            f.localize = True
            f.widget.is_localized = True
            f.widget = forms.TextInput(
                attrs={"inputmode": "decimal", "style": "text-align:right; width:8em;"}
            )

        # description & unit_price_excl mogen leeg binnenkomen; vullen/valideren in clean()
        if "description" in self.fields:
            self.fields["description"].required = False
        if "unit_price_excl" in self.fields:
            self.fields["unit_price_excl"].required = False

        # Indien bestaande instantie: initiale totalen vullen (cosmetisch)
        inst = getattr(self, "instance", None)
        if inst and getattr(inst, "pk", None):
            try:
                q   = Decimal(str(getattr(inst, "quantity", 0) or 0))
                upx = Decimal(str(getattr(inst, "unit_price_excl", 0) or 0))
                vr  = Decimal(str(getattr(inst, "vat_rate", 21) or 21))
                ex  = (q * upx).quantize(Decimal("0.01"))
                inc = (ex * (Decimal("1.00") + vr/Decimal("100"))).quantize(Decimal("0.01"))
                self.initial["total_excl_display"] = f"{ex:.2f}"
                self.initial["total_incl_display"] = f"{inc:.2f}"
            except Exception:
                pass

    def clean(self):
        data = super().clean()

        p   = data.get("product")
        dsc = data.get("description")
        up  = data.get("unit_price_excl")
        qty = data.get("quantity")

        def _is_zero_or_empty(val):
            if val in (None, ""):
                return True
            if isinstance(val, Decimal):
                return val == Decimal("0")
            try:
                return Decimal(str(val)) == Decimal("0")
            except Exception:
                return False

        # Prefill server-side (UI doet dit client-side ook)
        if p:
            if not dsc:
                data["description"] = getattr(p, "name", str(p))

            prod_price = getattr(p, "unit_price_excl", None)
            if prod_price in (None, ""):
                prod_price = getattr(p, "default_price_excl", None)
            if _is_zero_or_empty(up) and prod_price not in (None, ""):
                data["unit_price_excl"] = prod_price

            prod_vat = getattr(p, "vat_rate", None)
            if prod_vat in (None, ""):
                prod_vat = getattr(p, "default_vat_rate", None)
            try:
                pv = None if prod_vat in (None, "") else int(prod_vat)
            except Exception:
                pv = None
            if pv in (0, 6, 12, 21):
                data["vat_rate"] = pv

        if not qty:
            data["quantity"] = 1

        if data.get("vat_rate") not in (0, 6, 12, 21):
            raise ValidationError("BTW moet 0, 6, 12 of 21 zijn.")

        if not p:
            if not data.get("description") or data.get("unit_price_excl") in (None, ""):
                raise ValidationError("Geef een omschrijving én prijs, of kies een product.")

        if p and data.get("unit_price_excl") in (None, ""):
            raise ValidationError("Gekozen product heeft geen prijs. Vul de prijs in.")

        # display-velden updaten in formdata (optioneel, JS doet live updates)
        try:
            q   = Decimal(str(data.get("quantity", 0) or 0))
            upx = Decimal(str(data.get("unit_price_excl", 0) or 0))
            vr  = Decimal(str(data.get("vat_rate", 0) or 0))
            ex  = (q * upx).quantize(Decimal("0.01"))
            inc = (ex * (Decimal("1.00") + vr/Decimal("100"))).quantize(Decimal("0.01"))
            self.data = self.data.copy()
            self.data[self.add_prefix("total_excl_display")] = f"{ex:.2f}"
            self.data[self.add_prefix("total_incl_display")] = f"{inc:.2f}"
        except Exception:
            pass

        return data


class _InvLineInline(_admin.TabularInline):
    model = _InvLine
    form = _InvLineForm
    fk_name = "invoice"
    fields = (
        "product", "description", "quantity", "unit_price_excl", "vat_rate",
        "total_excl_display", "total_incl_display"
    )
    autocomplete_fields = ()
    extra = 0

    class Media:
        js = ("core/invoice.inline.v3.js",)
        css = {"all": ("core/admin.invoice.inline.css",)}

class _InvAdmin(_admin.ModelAdmin):
    # BELANGRIJK: dit zet jouw custom template met de print/preview knoppen terug
    change_form_template = "admin/core/invoice/change_form.html"

    list_display = ("id", "number", "member", "issue_date")
    list_filter = ("issue_date",)
    date_hierarchy = "issue_date"
    inlines = [_InvLineInline]


# Herregisteren met onze enige, juiste admin
try:
    _admin.site.unregister(_Inv)
except Exception:
    pass
_admin.site.register(_Inv, _InvAdmin)


class _ProdAdmin(_admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)

try:
    _admin.site.unregister(_Prod)
except Exception:
    pass
_admin.site.register(_Prod, _ProdAdmin)

# === EINDE DAGFACTUUR ADMIN ===