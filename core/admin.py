from django.contrib import admin
from django.apps import apps
from django.db.models import Count, Q, F, Value, IntegerField
from django.db.models.functions import Coalesce
from django.db.models import Case, When
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
        today = date(ref_year, 7, 1)
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

def _first_existing_member_fields(model, candidates):
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
        "external_id_display",   # <- sorteerbaar
        "household_role_display",# <- sorteerbaar
        "age_display",
        "household_info",
    )
    list_display_links = ("last_name", "first_name")
    ordering = ("last_name", "first_name")
    list_per_page = 50
    search_fields = ()  # we overschrijven get_search_results voor flexibiliteit

    _ext_fields = None  # cache

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        # Annotatie: hh_size = aantal leden per billing_account
        try:
            qs = qs.annotate(hh_size=Count("billing_account__member", distinct=True))
        except Exception:
            qs = qs.annotate(hh_size=Count("id"))

        # External ID annotatie (ext_id_any) om op te tonen + sorteren
        if self._ext_fields is None:
            self._ext_fields = _first_existing_member_fields(Member, EXTERNAL_ID_CANDIDATES)
        try:
            if self._ext_fields:
                coalesce_args = [F(self._ext_fields[0])]
                for fn in self._ext_fields[1:]:
                    coalesce_args.append(F(fn))
                coalesce_args.append(Value(""))
                qs = qs.annotate(ext_id_any=Coalesce(*coalesce_args))
        except Exception:
            pass

        # Household role rank: 0 = Individueel (geen account), 2 = Gezinshoofd, 1 = Gezinslid
        role_whens = [When(billing_account__isnull=True, then=Value(0))]
        # Als veld bestaat: is_household_head = True => 2
        try:
            Member._meta.get_field("is_household_head")
            role_whens.append(When(is_household_head=True, then=Value(2)))
        except Exception:
            pass
        # Als relationeel veld bestaat: household_head == self => 2
        try:
            Member._meta.get_field("household_head")
            role_whens.append(When(household_head_id=F("id"), then=Value(2)))
        except Exception:
            pass

        qs = qs.annotate(
            role_rank=Case(
                *role_whens,
                default=Value(1),
                output_field=IntegerField(),
            )
        )
        return qs

    # --------- Kolommen ---------
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

    @admin.display(description=_("Household role"), ordering="role_rank")
    def household_role_display(self, obj):
        """
        0 = Individueel (geen account)
        2 = Gezinshoofd
        1 = Gezinslid
        """
        rank = getattr(obj, "role_rank", None)
        if rank == 0:
            return "Individueel"
        if rank == 2:
            return "Gezinshoofd"
        return "Gezinslid"

    @admin.display(description=_("Leeftijd"), ordering="birth_date")
    def age_display(self, obj):
        a = _age_on(getattr(obj, "birth_date", None))
        return a if a is not None else "—"

    @admin.display(description=_("Gezinshoofd / Omvang"), ordering="hh_size")
    def household_info(self, obj):
        ba = getattr(obj, "billing_account", None)
        size = getattr(obj, "hh_size", None) or 0
        if not ba:
            return "—"
        if getattr(obj, "role_rank", None) == 2:  # gezinshoofd
            return f"{max(1, size)} leden"
        # toon household_head naam indien bekend
        if hasattr(obj, "household_head") and getattr(obj, "household_head", None):
            hh = obj.household_head
            return f"Hoofd: {getattr(hh, 'last_name', '')} {getattr(hh, 'first_name', '')}".strip()
        # fallback: eerste lid binnen account
        try:
            others = Member.objects.filter(billing_account=ba).order_by("id")
            if others.exists():
                hh = others.first()
                return f"Hoofd: {getattr(hh, 'last_name', '')} {getattr(hh, 'first_name', '')}".strip()
        except Exception:
            pass
        return "Hoofd: onbekend"

    # --------- Zoeken ---------
    def get_search_results(self, request, queryset, search_term):
        if not search_term:
            return super().get_search_results(request, queryset, search_term)

        q = Q(last_name__icontains=search_term) | Q(first_name__icontains=search_term)

        # Gemeente/plaats (proberen; stil falen als veld niet bestaat)
        for field in ["city", "gemeente", "municipality", "town", "plaats"]:
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

# ---------- Overige core-modellen: auto-registreren ----------
_core_app = apps.get_app_config("core")
for _model in _core_app.get_models():
    if _model is Member:
        continue
    try:
        admin.site.register(_model)
    except admin.sites.AlreadyRegistered:
        pass
