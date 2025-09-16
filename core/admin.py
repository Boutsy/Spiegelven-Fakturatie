from django.contrib import admin
from django.apps import apps
from django.db.models import Q, F, Value, IntegerField, Case, When
from django.db.models.functions import Coalesce
from django.utils.translation import gettext_lazy as _
from datetime import date
from django.db import models

Member = apps.get_model("core", "Member")

EXTERNAL_ID_CANDIDATES = [
    "external_id", "externalid", "external_member_id", "legacy_id",
    "old_id", "external", "ext_id", "member_external_id",
]

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

    # toon zoekvak
    search_fields = ("last_name", "first_name")
    search_help_text = _(
        "Zoekt in: achternaam, voornaam, e-mail, gsm, postcode, gemeente/plaats, external ID en (indien aanwezig) naam/label van facturatieprofiel."
    )

    # ===== FORM =====
    readonly_fields = ("id",)

    def get_fieldsets(self, request, obj=None):
        sections = []
        sections.append( (_("Interne info"), {"fields": ("id",), "description": _("Intern database-ID (alleen-lezen).")}) )
        ident = _existing_fields(Member, ("last_name","first_name","birth_date","gender"))
        if ident: sections.append( (_("Identiteit"), {"fields": ident}) )
        contact = _existing_fields(Member, ("email","mobile","phone","address","postal_code","city"))
        if contact: sections.append( (_("Contact"), {"fields": contact}) )
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

        # Heeft een billing account? (voor eventuele sort/filters in toekomst)
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

        q = Q(last_name__icontains=search_term) | Q(first_name__icontains=search_term)

        # Extra: e-mail, gsm/mobiel, postcode
        for field in ["email", "mobile", "phone", "postal_code"]:
            try:
                queryset.model._meta.get_field(field)
                q |= Q(**{f"{field}__icontains": search_term})
            except Exception:
                continue

        # Gemeente/plaats
        for field in ["city", "gemeente", "municipality", "town", "plaats"]:
            try:
                queryset.model._meta.get_field(field)
                q |= Q(**{f"{field}__icontains": search_term})
            except Exception:
                continue

        # External ID velden
        if self._ext_fields is None:
            concrete = {f.name for f in Member._meta.get_fields() if getattr(f, "concrete", False)}
            self._ext_fields = [n for n in EXTERNAL_ID_CANDIDATES if n in concrete]
        for fn in self._ext_fields:
            q |= Q(**{f"{fn}__icontains": search_term})

        # Veilig zoeken op billing_account subvelden:
        # - Check of 'billing_account' een ForeignKey is
        try:
            bf = Member._meta.get_field("billing_account")
            rel_model = getattr(bf.remote_field, "model", None)
        except Exception:
            rel_model = None

        if rel_model is not None:
            # kandidaat tekstvelden waarop we *mogen* zoeken
            candidate_rel_fields = ["name", "label", "title", "company_name"]
            rel_concrete = {f.name: f for f in rel_model._meta.get_fields() if getattr(f, "concrete", False)}

            for rf_name in candidate_rel_fields:
                f = rel_concrete.get(rf_name)
                if isinstance(f, (models.CharField, models.TextField)):
                    q |= Q(**{f"billing_account__{rf_name}__icontains": search_term})
                # anders: niet toevoegen (voorkomt FieldError)

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
