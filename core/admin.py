from django.contrib import admin
from django.apps import apps
from django.db.models import Count, Q, F, Value
from django.db.models.functions import Coalesce
from django.utils.translation import gettext_lazy as _
from datetime import date

Member = apps.get_model("core", "Member")

# Kandidaten voor externe ID (we testen dynamisch welke bestaan)
EXTERNAL_ID_CANDIDATES = [
    "external_id", "externalid", "external_member_id", "legacy_id",
    "old_id", "external", "ext_id", "member_external_id",
]

# ---------- Helpers ----------
def _age_on(born, ref_year=None):
    if not born:
        return None
    if ref_year is None:
        today = date.today()
    else:
        today = date(ref_year, 7, 1)  # midden van het jaar
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

def _first_existing_member_fields(model, candidates):
    """Geef lijst terug met candidate velden die écht bestaan op het model."""
    existing = []
    field_names = {f.name for f in model._meta.get_fields() if getattr(f, "concrete", False)}
    for c in candidates:
        if c in field_names:
            existing.append(c)
    return existing

# ---------- Member Admin (maatwerk) ----------
@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = (
        "last_name",
        "first_name",
        "external_id_display",
        "age_display",
        "status_display",
        "household_info",
    )
    list_display_links = ("last_name", "first_name")
    ordering = ("last_name", "first_name")  # alfabetisch
    list_per_page = 50

    # we overriden get_search_results zodat we flexibel extra velden kunnen meenemen
    search_fields = ()

    # cache per process-run
    _ext_fields = None

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        # Annotatie: aantal leden per billing_account (gezinssize)
        try:
            qs = qs.annotate(hh_size=Count("billing_account__member", distinct=True))
        except Exception:
            qs = qs.annotate(hh_size=Count("id"))

        # Zoek welke external-id velden echt bestaan
        if self._ext_fields is None:
            self._ext_fields = _first_existing_member_fields(Member, EXTERNAL_ID_CANDIDATES)

        # Annotatie: samengevoegde externe id (eerste niet-NULL)
        try:
            if self._ext_fields:
                coalesce_args = [F(self._ext_fields[0])]
                for fn in self._ext_fields[1:]:
                    coalesce_args.append(F(fn))
                coalesce_args.append(Value(""))
                qs = qs.annotate(ext_id_any=Coalesce(*coalesce_args))
        except Exception:
            pass

        return qs

    # --------- Weergavekolommen (sorteerbaar) ---------
    @admin.display(description=_("External ID"))
    def external_id_display(self, obj):
        # toon geannoteerde waarde als die bestaat, anders de eerste bestaande fieldwaarde
        val = getattr(obj, "ext_id_any", None)
        if val:
            return val
        if self._ext_fields:
            for fn in self._ext_fields:
                v = getattr(obj, fn, None)
                if v not in (None, ""):
                    return v
        return "—"

    @admin.display(description=_("Leeftijd"), ordering="birth_date")
    def age_display(self, obj):
        a = _age_on(getattr(obj, "birth_date", None))
        return a if a is not None else "—"

    @admin.display(description=_("Status"))
    def status_display(self, obj):
        """
        Logica:
        - Geen billing_account -> 'Individueel'
        - Met billing_account:
            - 'is_household_head' True -> 'Gezinshoofd'
            - anders -> 'Gezinslid'
        """
        ba = getattr(obj, "billing_account", None)
        if not ba:
            return "Individueel"
        if hasattr(obj, "is_household_head") and getattr(obj, "is_household_head"):
            return "Gezinshoofd"
        if hasattr(obj, "household_head") and getattr(obj, "household_head_id", None) == obj.id:
            return "Gezinshoofd"
        return "Gezinslid"

    @admin.display(description=_("Gezinshoofd / Omvang"), ordering="hh_size")
    def household_info(self, obj):
        """
        Voor gezinshoofd: 'N leden'
        Voor gezinslid: 'Hoofd: <naam>'
        Voor individueel: '—'
        """
        ba = getattr(obj, "billing_account", None)
        size = getattr(obj, "hh_size", None) or 0
        if not ba:
            return "—"

        status = self.status_display(obj)
        if status == "Gezinshoofd":
            return f"{max(1, size)} leden"

        if hasattr(obj, "household_head") and getattr(obj, "household_head", None):
            hh = obj.household_head
            return f"Hoofd: {getattr(hh, 'last_name', '')} {getattr(hh, 'first_name', '')}".strip()

        try:
            others = Member.objects.filter(billing_account=ba).order_by("id")
            if others.exists():
                hh = others.first()
                return f"Hoofd: {getattr(hh, 'last_name', '')} {getattr(hh, 'first_name', '')}".strip()
        except Exception:
            pass
        return "Hoofd: onbekend"

    # --------- Zoeken (flexibel) ---------
    def get_search_results(self, request, queryset, search_term):
        """
        Altijd op naam/voornaam; plus gemeente/plaats als veld bestaat;
        plus external-id (elk gevonden veld in EXTERNAL_ID_CANDIDATES).
        """
        if not search_term:
            return super().get_search_results(request, queryset, search_term)

        q = Q(last_name__icontains=search_term) | Q(first_name__icontains=search_term)

        # Gemeente/plaats
        candidate_city_fields = ["city", "gemeente", "municipality", "town", "plaats"]
        for field in candidate_city_fields:
            try:
                queryset.model._meta.get_field(field)
                q |= Q(**{f"{field}__icontains": search_term})
            except Exception:
                continue

        # External ID velden
        if self._ext_fields is None:
            self._ext_fields = _first_existing_member_fields(Member, EXTERNAL_ID_CANDIDATES)
        for fn in self._ext_fields:
            q |= Q(**{f"{fn}__icontains": search_term})

        return queryset.filter(q), False

# ---------- Overige core modellen: auto-registreren met standaard admin ----------
_core_app = apps.get_app_config("core")
for _model in _core_app.get_models():
    if _model is Member:
        continue  # al geregistreerd
    try:
        admin.site.register(_model)
    except admin.sites.AlreadyRegistered:
        pass
