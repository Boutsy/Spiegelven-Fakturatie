from django.contrib import admin
from django.apps import apps
from django.db import models
from django.db.models import Q, F, Value, IntegerField, Case, When
from django.db.models.functions import Coalesce
from django.utils.translation import gettext_lazy as _
from datetime import date

Member = apps.get_model("core", "Member")

EXTERNAL_ID_CANDIDATES = [
    "external_id", "externalid", "external_member_id", "legacy_id",
    "old_id", "external", "ext_id", "member_external_id",
]

# -------- helpers --------
def _age_on(born, ref_year=None):
    if not born:
        return None
    today = date.today() if ref_year is None else date(ref_year, 7, 1)
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

def _concrete_fields(model):
    return {f.name: f for f in model._meta.get_fields() if getattr(f, "concrete", False)}

def _existing(model, names):
    cf = _concrete_fields(model)
    return tuple(n for n in names if n in cf)

def _first_existing(model, names):
    for n in names:
        if n in _concrete_fields(model):
            return n
    return None

def _birthdate_field(model):
    # neem expliciet bekende namen, anders het eerste DateField
    candidates = ("birth_date","date_of_birth","dob","geboortedatum","birthdate")
    name = _first_existing(model, candidates)
    if name:
        return name
    for n, f in _concrete_fields(model).items():
        if isinstance(f, models.DateField):
            return n
    return None

def _address_fields(model):
    # alles wat nuttig kan zijn voor adres; we filteren op wat echt bestaat
    candidates = (
        "address","address1","address2","street","street1","street2","street_number","house_number",
        "postal_code","postcode","zip","zip_code",
        "city","gemeente","municipality","town","plaats",
        "country","country_code","country_name",
        "email","mobile","phone",
    )
    return _existing(model, candidates)

@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    # ===== LIST =====
    list_display = (
        "last_name",
        "first_name",
        "external_id_display",   # sorteerbaar
        "billing_account_display",
        "age_display",
    )
    list_display_links = ("last_name", "first_name")
    ordering = ("last_name", "first_name")
    list_per_page = 50

    # zoekvak tonen
    search_fields = ("last_name", "first_name")
    search_help_text = _(
        "Zoekt in: achternaam, voornaam, e-mail, gsm, postcode, gemeente/plaats, external ID en (indien aanwezig) naam/label van facturatieprofiel."
    )

    # ===== FORM =====
    readonly_fields = ("id",)

    def get_fieldsets(self, request, obj=None):
        sections = []

        # Interne info
        sections.append((_('Interne info'), {
            "fields": ("id",),
            "description": _("Intern database-ID (alleen-lezen)."),
        }))

        # Identiteit: last/first + dynamische geboortedatum + optioneel gender
        ident = ["last_name","first_name"]
        ident = [f for f in ident if f in _concrete_fields(Member)]
        bd = _birthdate_field(Member)
        if bd:
            ident.append(bd)
        if "gender" in _concrete_fields(Member):
            ident.append("gender")
        if ident:
            sections.append((_('Identiteit'), {"fields": tuple(ident)}))

        # Contact: dynamische adresvelden (straat, nr, land, …) + email/telefoon
        contact = _address_fields(Member)
        if contact:
            sections.append((_('Contact'), {"fields": contact}))

        # Facturatie: alternatief profiel + evt. course/active
        fact = _existing(Member, ("billing_account","course","active"))
        if fact:
            sections.append((_('Facturatie'), {
                "fields": fact,
                "description": _("Indien ingevuld, wordt dit facturatieprofiel gebruikt i.p.v. het standaard adres van het lid."),
            }))

        # Overig
        overig = _existing(Member, ("notes",))
        if overig:
            sections.append((_('Overig'), {"fields": overig}))

        return tuple(sections)

    _ext_fields = None  # cache

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        # External ID coalesce (voor tonen/sorteren)
        if self._ext_fields is None:
            cf = _concrete_fields(Member)
            self._ext_fields = [n for n in EXTERNAL_ID_CANDIDATES if n in cf]
        try:
            if self._ext_fields:
                args = [F(self._ext_fields[0]), *[F(fn) for fn in self._ext_fields[1:]], Value("")]
                qs = qs.annotate(ext_id_any=Coalesce(*args))
        except Exception:
            pass

        # Annotatie voor has_billing (optioneel nuttig later)
        if "billing_account" in _concrete_fields(Member):
            qs = qs.annotate(has_billing=Case(
                When(billing_account__isnull=False, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            ))
        return qs

    # ===== kolommen =====
    @admin.display(description=_("External ID"), ordering="ext_id_any")
    def external_id_display(self, obj):
        val = getattr(obj, "ext_id_any", None)
        if val:
            return val
        if self._ext_fields:
            for fn in self._ext_fields:
                v = getattr(obj, fn, None)
                if v not in (None, ""):
                    return v
        return "—"

    @admin.display(description=_("Facturatie via"))
    def billing_account_display(self, obj):
        if hasattr(obj, "billing_account") and getattr(obj, "billing_account", None):
            try:
                return str(obj.billing_account)
            except Exception:
                return "Alternatief profiel"
        return "Persoonlijk"

    @admin.display(description=_("Leeftijd"))
    def age_display(self, obj):
        bd_name = _birthdate_field(Member)
        born = getattr(obj, bd_name, None) if bd_name else None
        a = _age_on(born)
        return a if a is not None else "—"

    # ===== zoeken =====
    def get_search_results(self, request, queryset, search_term):
        if not search_term:
            return super().get_search_results(request, queryset, search_term)

        q = Q(last_name__icontains=search_term) | Q(first_name__icontains=search_term)

        for field in ["email", "mobile", "phone", "postal_code", "postcode", "zip", "zip_code"]:
            if field in _concrete_fields(Member):
                q |= Q(**{f"{field}__icontains": search_term})

        for field in ["city", "gemeente", "municipality", "town", "plaats"]:
            if field in _concrete_fields(Member):
                q |= Q(**{f"{field}__icontains": search_term})

        if self._ext_fields is None:
            self._ext_fields = [n for n in EXTERNAL_ID_CANDIDATES if n in _concrete_fields(Member)]
        for fn in self._ext_fields:
            q |= Q(**{f"{fn}__icontains": search_term})

        # Veilig zoeken op billing_account subvelden (alleen tekstvelden die bestaan)
        try:
            bf = Member._meta.get_field("billing_account")
            rel_model = getattr(bf.remote_field, "model", None)
        except Exception:
            rel_model = None
        if rel_model is not None:
            rel_concrete = {f.name: f for f in rel_model._meta.get_fields() if getattr(f, "concrete", False)}
            for rf_name, rf in rel_concrete.items():
                if isinstance(rf, (models.CharField, models.TextField)) and rf_name in {"name","label","title","company_name"}:
                    q |= Q(**{f"billing_account__{rf_name}__icontains": search_term})

        return queryset.filter(q).distinct(), False

# Overige core-modellen automatisch registreren (zodat je alles ziet)
_core_app = apps.get_app_config("core")
for _model in _core_app.get_models():
    if _model is Member:
        continue
    try:
        admin.site.register(_model)
    except admin.sites.AlreadyRegistered:
        pass
