from django.contrib import admin
from django.apps import apps
from django.db.models import Q, F, Value, IntegerField, Case, When, Count
from django.db.models.functions import Coalesce
from django.utils.translation import gettext_lazy as _
from datetime import date

Member = apps.get_model("core", "Member")

# Kandidaten voor externe ID
EXTERNAL_ID_CANDIDATES = [
    "external_id", "externalid", "external_member_id", "legacy_id",
    "old_id", "external", "ext_id", "member_external_id",
]

# ---- helpers ----
def _age_on(born, ref_year=None):
    if not born:
        return None
    today = date.today() if ref_year is None else date(ref_year, 7, 1)
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

def _existing_fields(model, names):
    concrete = {f.name for f in model._meta.get_fields() if getattr(f, "concrete", False)}
    return tuple(n for n in names if n in concrete)

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
    search_fields = ()  # flexibel in get_search_results

    # ===== FORM =====
    readonly_fields = ("id",)  # intern DB-id (alleen-lezen)

    def get_fieldsets(self, request, obj=None):
        sections = []
        sections.append( (_("Interne info"), {"fields": ("id",), "description": _("Intern database-ID (alleen-lezen).")}) )
        ident = _existing_fields(Member, ("last_name","first_name","birth_date","gender"))
        if ident: sections.append( (_("Identiteit"), {"fields": ident}) )
        contact = _existing_fields(Member, ("email","mobile","phone","address","postal_code","city"))
        if contact: sections.append( (_("Contact"), {"fields": contact}) )
        # Facturatie: enkel het veld 'billing_account' indien aanwezig
        fact = _existing_fields(Member, ("billing_account","course","active"))
        if fact: sections.append( (_("Facturatie"), {"fields": fact, "description": _("Indien ingevuld, wordt dit facturatieprofiel gebruikt i.p.v. het standaard adres van het lid.")}) )
        overig = _existing_fields(Member, ("notes",))
        if overig: sections.append( (_("Overig"), {"fields": overig}) )
        return tuple(sections)

    _ext_fields = None  # cache

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        # External ID coalesce (voor tonen/sorteren)
        if self._ext_fields is None:
            concrete = {f.name for f in Member._meta.get_fields() if getattr(f, "concrete", False)}
            self._ext_fields = [n for n in EXTERNAL_ID_CANDIDATES if n in concrete]
        try:
            if self._ext_fields:
                args = [F(self._ext_fields[0]), *[F(fn) for fn in self._ext_fields[1:]], Value("")]
                qs = qs.annotate(ext_id_any=Coalesce(*args))
        except Exception:
            pass

        # Annotatie of er een billing account is (voor nette display/sort-optie indien gewenst)
        concrete = {f.name for f in Member._meta.get_fields() if getattr(f, "concrete", False)}
        if "billing_account" in concrete:
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
        # Toon 'Persoonlijk' of string van billing account als die bestaat
        if hasattr(obj, "billing_account") and getattr(obj, "billing_account", None):
            try:
                return str(obj.billing_account)
            except Exception:
                return "Alternatief profiel"
        return "Persoonlijk"

    @admin.display(description=_("Leeftijd"), ordering="birth_date")
    def age_display(self, obj):
        a = _age_on(getattr(obj, "birth_date", None))
        return a if a is not None else "—"

    # ===== zoeken =====
    def get_search_results(self, request, queryset, search_term):
        if not search_term:
            return super().get_search_results(request, queryset, search_term)

        result = queryset.filter(
            Q(last_name__icontains=search_term) |
            Q(first_name__icontains=search_term)
        )

        # gemeente/plaats indien beschikbaar
        for field in ["city", "gemeente", "municipality", "town", "plaats"]:
            try:
                queryset.model._meta.get_field(field)
                result = result | queryset.filter(**{f"{field}__icontains": search_term})
            except Exception:
                continue

        # external id velden
        if self._ext_fields is None:
            concrete = {f.name for f in Member._meta.get_fields() if getattr(f, "concrete", False)}
            self._ext_fields = [n for n in EXTERNAL_ID_CANDIDATES if n in concrete]
        for fn in self._ext_fields:
            result = result | queryset.filter(**{f"{fn}__icontains": search_term})

        # proberen op billing account te zoeken (indien relationele velden bestaan)
        if any(f.name == "billing_account" for f in Member._meta.get_fields()):
            for path in [
                "billing_account__name__icontains",
                "billing_account__company__icontains",
                "billing_account__company_name__icontains",
                "billing_account__label__icontains",
                "billing_account__title__icontains",
            *()  # extensie mogelijk
            ]:
                try:
                    result = result | queryset.filter(**{path: search_term})
                except Exception:
                    continue

        return result.distinct(), False

# Overige core-modellen automatisch registreren (zodat je alles ziet)
_core_app = apps.get_app_config("core")
for _model in _core_app.get_models():
    if _model is Member:
        continue
    try:
        admin.site.register(_model)
    except admin.sites.AlreadyRegistered:
        pass
