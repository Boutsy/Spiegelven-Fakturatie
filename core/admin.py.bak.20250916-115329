from datetime import date
from django.contrib import admin
from django.apps import apps
from django.db import models
from django.db.models import F, Value, IntegerField, Case, When, Q
from django.db.models.functions import Coalesce
from django.utils.translation import gettext_lazy as _

Member = apps.get_model("core", "Member")

EXTERNAL_ID_CANDIDATES = [
    "external_id","externalid","external_member_id","legacy_id","old_id","external","ext_id","member_external_id",
]

def _concrete_fields(model):
    return {f.name: f for f in model._meta.get_fields() if getattr(f, "concrete", False)}
def _exists(model, name): return name in _concrete_fields(model)

def _first_existing(model, names):
    for n in names:
        if _exists(model, n):
            return n
    return None

def _age_on(born, ref_year=None):
    if not born: return None
    today = date.today() if ref_year is None else date(ref_year, 7, 1)
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

def _birthdate_field(model):
    pref = ("birth_date","date_of_birth","dob","geboortedatum","birthdate")
    f = _first_existing(model, pref)
    if f: return f
    for n, f in _concrete_fields(model).items():
        if isinstance(f, models.DateField):
            return n
    return None

def _contact_fields(model):
    order = []
    # straat + nr
    street = _first_existing(model, ("street","address","address1","street1"))
    if street: order.append(street)
    street_no = _first_existing(model, ("street_number","house_number","nr","number"))
    if street_no: order.append(street_no)
    # postcode + gemeente
    postal = _first_existing(model, ("postal_code","postcode","zip","zip_code"))
    if postal: order.append(postal)
    city = _first_existing(model, ("city","gemeente","municipality","town","plaats"))
    if city: order.append(city)
    # land + email
    country = _first_existing(model, ("country","country_name","country_code"))
    if country: order.append(country)
    email = _first_existing(model, ("email","e_mail"))
    if email: order.append(email)

    # *** Telefoons (prefer specifieke modelvelden) ***
    # Vast: phone_private > phone_work > phone/telephone/tel
    phone_candidates = ("phone_private","phone_work","phone","telephone","tel","phone_number","landline")
    phone = _first_existing(model, phone_candidates)
    if phone: order.append(phone)
    # Mobiel: phone_mobile > mobile/gsm/…
    mobile_candidates = ("phone_mobile","mobile","gsm","cellphone","mobile_phone","mobile_number")
    mobile = _first_existing(model, mobile_candidates)
    if mobile: order.append(mobile)

    # extras
    for cand in ("address2","street2","state","region","province"):
        if _exists(model, cand) and cand not in order:
            order.append(cand)
    return tuple(order)

@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ("last_name","first_name","external_id_display","billing_account_display","age_display")
    list_display_links = ("last_name","first_name")
    ordering = ("last_name","first_name")
    list_per_page = 50

    search_fields = ("last_name","first_name")
    search_help_text = _("Zoekt o.a. in: naam, e-mail, telefoons, postcode, gemeente/plaats, external ID en (indien aanwezig) naam/label van facturatieprofiel.")

    readonly_fields = ("id",)

    _ext_fields = None

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if self._ext_fields is None:
            cf = _concrete_fields(Member)
            self._ext_fields = [n for n in EXTERNAL_ID_CANDIDATES if n in cf]
        try:
            if self._ext_fields:
                args = [F(self._ext_fields[0]), *[F(fn) for fn in self._ext_fields[1:]], Value("")]
                qs = qs.annotate(ext_id_any=Coalesce(*args))
        except Exception:
            pass
        if _exists(Member, "billing_account"):
            qs = qs.annotate(has_billing=Case(
                When(billing_account__isnull=False, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            ))
        return qs

    @admin.display(description=_("External ID"), ordering="ext_id_any")
    def external_id_display(self, obj):
        val = getattr(obj, "ext_id_any", None)
        if val: return val
        if self._ext_fields:
            for fn in self._ext_fields:
                v = getattr(obj, fn, None)
                if v not in (None,""): return v
        return "—"

    @admin.display(description=_("Facturatie via"))
    def billing_account_display(self, obj):
        if _exists(Member, "billing_account") and getattr(obj, "billing_account", None):
            try: return str(obj.billing_account)
            except Exception: return "Alternatief profiel"
        return "Persoonlijk"

    @admin.display(description=_("Leeftijd"))
    def age_display(self, obj):
        bd_name = _birthdate_field(Member)
        born = getattr(obj, bd_name, None) if bd_name else None
        a = _age_on(born)
        return a if a is not None else "—"

    def get_fieldsets(self, request, obj=None):
        sections = []
        sections.append((_('Interne info'), {"fields": ("id",), "description": _("Intern database-ID (alleen-lezen).")}))
        ident = []
        for f in ("last_name","first_name"):
            if _exists(Member, f): ident.append(f)
        bd = _birthdate_field(Member)
        if bd: ident.append(bd)
        if _exists(Member, "gender"): ident.append("gender")
        if ident:
            sections.append((_('Identiteit'), {"fields": tuple(ident)}))

        contact = _contact_fields(Member)
        if contact:
            sections.append((_('Contact'), {"fields": contact}))

        fact = tuple(f for f in ("billing_account","course","active") if _exists(Member, f))
        if fact:
            sections.append((_('Facturatie'), {"fields": fact,
                "description": _("Indien ingevuld, wordt dit facturatieprofiel gebruikt i.p.v. het standaard adres van het lid.")}))
        if _exists(Member, "notes"):
            sections.append((_('Overig'), {"fields": ("notes",)}))
        return tuple(sections)

    def get_search_results(self, request, queryset, search_term):
        if not search_term:
            return super().get_search_results(request, queryset, search_term)
        q = Q(last_name__icontains=search_term) | Q(first_name__icontains=search_term)
        for f in ("email","e_mail","postal_code","postcode","zip","zip_code",
                  "city","gemeente","municipality","town","plaats",
                  "phone_private","phone_work","phone","telephone","tel","phone_number","landline",
                  "phone_mobile","mobile","gsm","cellphone","mobile_phone","mobile_number"):
            if _exists(Member, f):
                q |= Q(**{f"{f}__icontains": search_term})
        if self._ext_fields is None:
            self._ext_fields = [n for n in EXTERNAL_ID_CANDIDATES if _exists(Member, n)]
        for fn in self._ext_fields:
            q |= Q(**{f"{fn}__icontains": search_term})
        # billing_account tekstvelden
        if _exists(Member, "billing_account"):
            try:
                rel_model = Member._meta.get_field("billing_account").remote_field.model
                rel_concrete = {f.name: f for f in rel_model._meta.get_fields() if getattr(f, "concrete", False)}
                for rf_name, rf in rel_concrete.items():
                    if isinstance(rf, (models.CharField, models.TextField)) and rf_name in {"name","label","title","company_name"}:
                        q |= Q(**{f"billing_account__{rf_name}__icontains": search_term})
            except Exception:
                pass
        return queryset.filter(q).distinct(), False

# Registreer alle andere core-modellen generiek
_core_app = apps.get_app_config("core")
for _model in _core_app.get_models():
    if _model is Member:
        continue
    try:
        admin.site.register(_model)
    except admin.sites.AlreadyRegistered:
        pass
