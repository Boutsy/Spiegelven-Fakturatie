from django.contrib import admin
from django.apps import apps
from django.db.models import Count, Q
from django.utils.translation import gettext_lazy as _
from datetime import date

Member = apps.get_model("core", "Member")

# ---------- Helpers ----------
def _age_on(born, ref_year=None):
    if not born:
        return None
    if ref_year is None:
        today = date.today()
    else:
        today = date(ref_year, 7, 1)  # midden van het jaar
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

# ---------- Member Admin (maatwerk) ----------
@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = (
        "last_name",
        "first_name",
        "age_display",
        "status_display",
        "household_info",
    )
    list_display_links = ("last_name", "first_name")
    ordering = ("last_name", "first_name")  # alfabetisch
    list_per_page = 50

    # Basale search op naam/voornaam; gemeente/plaats wordt dynamisch toegevoegd in get_search_results
    search_fields = ()  # we overriden get_search_results om flexibel te zijn

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        # Annotatie: aantal leden per billing_account (gezinssize)
        # Als je Member.billing_account een FK is naar bvb InvoiceAccount met related_name='member_set',
        # dan telt Count('billing_account__member') alle leden in dat account.
        try:
            qs = qs.annotate(hh_size=Count("billing_account__member", distinct=True))
        except Exception:
            # fallback als veld/relatie anders heet
            qs = qs.annotate(hh_size=Count("id"))  # degrade gracefully (altijd 1)
        return qs

    # --------- Weergavekolommen (sorteerbaar) ---------
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
            - Als er een boolean/attribuut 'is_household_head' op Member bestaat en True -> 'Gezinshoofd'
            - Anders -> 'Gezinslid'
        """
        ba = getattr(obj, "billing_account", None)
        if not ba:
            return "Individueel"
        # probeer expliciete vlag
        if hasattr(obj, "is_household_head") and getattr(obj, "is_household_head"):
            return "Gezinshoofd"
        # fallback: als er een attribuut 'household_head' bestaat en verwijst naar zichzelf
        if hasattr(obj, "household_head") and getattr(obj, "household_head_id", None) == obj.id:
            return "Gezinshoofd"
        return "Gezinslid"

    @admin.display(description=_("Gezinshoofd / Omvang"), ordering="hh_size")
    def household_info(self, obj):
        """
        Voor gezinshoofd: toon 'N leden'
        Voor gezinslid: toon 'Hoofd: <naam>' (als bekend)
        Voor individueel: '—'
        """
        ba = getattr(obj, "billing_account", None)
        size = getattr(obj, "hh_size", None) or 0
        if not ba:
            return "—"

        status = self.status_display(obj)
        if status == "Gezinshoofd":
            # minimaal 1; als annotatie faalde kan size 0 zijn -> maak het minstens 1
            return f"{max(1, size)} leden"

        # Probeer household_head te tonen als dat veld bestaat
        if hasattr(obj, "household_head") and getattr(obj, "household_head", None):
            hh = obj.household_head
            return f"Hoofd: {getattr(hh, 'last_name', '')} {getattr(hh, 'first_name', '')}".strip()

        # Fallback: probeer via de account het laagste id-lid als hoofd te nemen
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
        Zoek altijd op naam/voornaam; breidt automatisch uit met gemeente/plaats
        als het veld bestaat (zonder fouten als het niet bestaat).
        """
        if not search_term:
            return super().get_search_results(request, queryset, search_term)

        q = Q(last_name__icontains=search_term) | Q(first_name__icontains=search_term)

        # Probeer gangbare veldnamen voor gemeente
        candidate_city_fields = ["city", "gemeente", "municipality", "town", "plaats"]
        for field in candidate_city_fields:
            try:
                queryset.model._meta.get_field(field)  # veld bestaat?
                q |= Q(**{f"{field}__icontains": search_term})
            except Exception:
                continue

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
