from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.apps import apps

from .models import (
    Member,
    MemberAsset,
    Product,
    Invoice,
    InvoiceLine,
    InvoiceAccount,
    YearPlan,
    YearPlanItem,
    YearSequence,
    PricingRule,
    ImportMapping,
    OrganizationProfile,
)

# --- Factuurlijnen inline ---
class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 1
    fields = (
        "description",
        "quantity",
        "unit_price_excl",
        "vat_rate",
        "line_excl",
        "vat_amount",
        "line_incl",
    )
    readonly_fields = ("line_excl", "vat_amount", "line_incl")

    class Media:
        js = ("admin/invoice_line.js",)  # laat staan; bestaat al bij jou

# ---------- Helpers ----------

def _money(v):
    try:
        if v is None:
            return ""
        return f"€ {v:.2f}"
    except Exception:
        return str(v) if v is not None else ""

def _has_field(model, name: str) -> bool:
    try:
        return any(getattr(f, "name", None) == name for f in model._meta.get_fields())
    except Exception:
        return False

HAS_HH = _has_field(Member, "household_head")
HAS_BILLING = _has_field(Member, "billing_account")
HAS_MEMBERSHIP_MODE = _has_field(Member, "membership_mode")
HAS_ROLE = _has_field(Member, "household_role")
HAS_FED_VIA_CLUB = _has_field(Member, "federation_via_club")
HAS_MEMBER_ACTIVE = _has_field(Member, "is_active")

# ---------- Inlines ----------

if HAS_HH:
    class FamilyMemberInline(admin.TabularInline):
        # NL titels → voorkomt “Members”/“Leden” dubbelzinnigheid
        verbose_name = "Gezinslid"
        verbose_name_plural = "Gezinsleden"

        model = Member
        fk_name = "household_head"
        extra = 0

        _fields = ["first_name", "last_name", "email"]
        if _has_field(Member, "date_of_birth"):
            _fields.append("date_of_birth")
        if HAS_MEMBERSHIP_MODE:
            _fields.append("membership_mode")
        if HAS_FED_VIA_CLUB:
            _fields.append("federation_via_club")
        if HAS_ROLE:
            _fields.append("household_role")
        if HAS_MEMBER_ACTIVE:
            _fields.append("is_active")
        fields = tuple(_fields)

        if HAS_BILLING:
            autocomplete_fields = ("billing_account",)
        else:
            autocomplete_fields = ()

        show_change_link = True
else:
    FamilyMemberInline = None


class MemberAssetInline(admin.TabularInline):
    # NL titels → voorkomt dat deze inline “Leden” lijkt te heten
    verbose_name = "Ledenvoorziening"
    verbose_name_plural = "Ledenvoorzieningen"

    model = MemberAsset
    extra = 0
    fields = ("asset_type", "identifier", "active", "price_excl", "vat_rate")
    autocomplete_fields = ()

# ---------- Member ----------

@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    ordering = ("last_name", "first_name")

    # Gebruik NL methoden i.p.v. veldnamen om NL-kolomtitels te tonen
    _cols = ["achternaam", "voornaam", "e_mail", "is_household_head_display"]
    if HAS_HH:
        _cols.append("household_head")  # label blijft model-gedreven
    if HAS_BILLING:
        _cols.append("billing_account")
    if HAS_MEMBER_ACTIVE:
        _cols.append("is_active")
    list_display = tuple(_cols)

    # filters
    _filters = []
    if HAS_MEMBER_ACTIVE:
        _filters.append("is_active")
    if HAS_MEMBERSHIP_MODE:
        _filters.append("membership_mode")
    if HAS_ROLE:
        _filters.append("household_role")
    if HAS_FED_VIA_CLUB:
        _filters.append("federation_via_club")
    list_filter = tuple(_filters)

    # zoeken
    search_fields = ("first_name", "last_name", "email")

    # autocompletes
    _ac = []
    if HAS_HH:
        _ac.append("household_head")
    if HAS_BILLING:
        _ac.append("billing_account")
    autocomplete_fields = tuple(_ac)

    # fieldsets
    _general = ["first_name", "last_name", "email"]
    if _has_field(Member, "date_of_birth"):
        _general.append("date_of_birth")
    if HAS_MEMBER_ACTIVE:
        _general.append("is_active")

    fieldsets = []
    fieldsets.append((None, {"fields": tuple(_general)}))

    gezin_fields = []
    if HAS_HH:
        gezin_fields.append("household_head")
    if HAS_ROLE:
        gezin_fields.append("household_role")
    if HAS_FED_VIA_CLUB:
        gezin_fields.append("federation_via_club")
    if gezin_fields:
        fieldsets.append((_("Gezin"), {"fields": tuple(gezin_fields)}))

    lid_fields = []
    if HAS_MEMBERSHIP_MODE:
        lid_fields.append("membership_mode")
    if HAS_BILLING:
        lid_fields.append("billing_account")
    if lid_fields:
        fieldsets.append((_("Lidmaatschap & facturatie"), {"fields": tuple(lid_fields)}))

    # inlines → precies één gezinsleden-inline + ledenvoorzieningen
    inlines = [MemberAssetInline] if FamilyMemberInline is None else [FamilyMemberInline, MemberAssetInline]

    # acties
    actions = ["make_invoice_account"]

    # NL kolomtitels
    @admin.display(description="Achternaam", ordering="last_name")
    def achternaam(self, obj):
        return obj.last_name

    @admin.display(description="Voornaam", ordering="first_name")
    def voornaam(self, obj):
        return obj.first_name

    @admin.display(description="E-mail", ordering="email")
    def e_mail(self, obj):
        return obj.email

    @admin.display(boolean=True, description=_("Gezinshoofd?"))
    def is_household_head_display(self, obj):
        return obj.household_head_id is None if HAS_HH else True

    @admin.action(description=_("Maak factuuraccount van geselecteerde leden"))
    def make_invoice_account(self, request, queryset):
        made = 0
        reused = 0
        for m in queryset:
            first = (getattr(m, "first_name", "") or "").strip()
            last = (getattr(m, "last_name", "") or "").strip()
            name = (first + " " + last).strip() or str(m)
            email = (getattr(m, "email", "") or "").strip()
            if email:
                acc, created = InvoiceAccount.objects.get_or_create(
                    email=email, defaults={"name": name, "email": email}
                )
            else:
                acc, created = InvoiceAccount.objects.get_or_create(
                    name=name, defaults={"name": name}
                )
            if created:
                made += 1
            else:
                reused += 1
        self.message_user(request, f"Factuuraccount(s): nieuw={made}, hergebruikt={reused}")

# ---------- MemberAsset ----------

@admin.register(MemberAsset)
class MemberAssetAdmin(admin.ModelAdmin):
    list_display = ("member", "asset_type", "identifier", "active", "price_excl_display", "vat_rate")
    list_filter = ("asset_type", "active")
    search_fields = ("member__first_name", "member__last_name", "identifier")
    autocomplete_fields = ("member",)

    @admin.display(description=_("Prijs (excl.)"))
    def price_excl_display(self, obj):
        v = getattr(obj, "price_excl", None)
        return _money(v)

# ---------- Product ----------

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    _cols = []
    if _has_field(Product, "code"):
        _cols.append("code")
    if _has_field(Product, "name"):
        _cols.append("name")
    _cols += ["price_display", "vat_display"]
    list_display = tuple(_cols)

    _search = []
    if _has_field(Product, "code"):
        _search.append("code")
    if _has_field(Product, "name"):
        _search.append("name")
    search_fields = tuple(_search) if _search else ()

    @admin.display(description=_("Prijs (excl.)"))
    def price_display(self, obj):
        for attr in ("unit_price_excl", "price_excl", "unit_price", "price"):
            if hasattr(obj, attr):
                return _money(getattr(obj, attr))
        return ""

    @admin.display(description=_("BTW"))
    def vat_display(self, obj):
        for attr in ("vat_rate", "vat", "vat_percent"):
            if hasattr(obj, attr):
                return getattr(obj, attr)
        return ""

# ---------- Invoice ----------

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    date_hierarchy = "issue_date"
    list_display = ("number", "issue_date", "doc_type", "status", "account", "total_excl_display", "total_vat_display", "total_incl_display")
    list_filter = ("status", "doc_type")
    search_fields = ("number", "account__name", "account__email")
    autocomplete_fields = ("account",)

    @admin.display(description=_("Totaal excl."))
    def total_excl_display(self, obj):
        return _money(getattr(obj, "total_excl", None))
    
    @admin.display(description=_("BTW"))
    def total_vat_display(self, obj):
        return _money(getattr(obj, "total_vat", None))

    @admin.display(description=_("Totaal incl."))
    def total_incl_display(self, obj):
        return _money(getattr(obj, "total_incl", None))

# ---------- InvoiceLine ----------

@admin.register(InvoiceLine)
class InvoiceLineAdmin(admin.ModelAdmin):
    _cols = ["invoice", "description", "quantity", "unit_price_display", "vat_rate_display"]
    if _has_field(InvoiceLine, "product"):
        _cols.append("product")
    list_display = tuple(_cols)

    _ac = ["invoice"]
    if _has_field(InvoiceLine, "product"):
        _ac.append("product")
    autocomplete_fields = tuple(_ac)

    search_fields = ("description", "invoice__number", "invoice__account__name")

    @admin.display(description=_("Prijs/eenheid (excl.)"))
    def unit_price_display(self, obj):
        for attr in ("unit_price_excl", "price_excl", "unit_price", "price"):
            if hasattr(obj, attr):
                return _money(getattr(obj, attr))
        return ""

    @admin.display(description=_("BTW"))
    def vat_rate_display(self, obj):
        for attr in ("vat_rate", "vat", "vat_percent"):
            if hasattr(obj, attr):
                return getattr(obj, attr)
        return ""

# ---------- InvoiceAccount ----------

@admin.register(InvoiceAccount)
class InvoiceAccountAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "vat_number", "street", "postal_code", "city")
    search_fields = ("name", "email", "vat_number", "street", "postal_code", "city")

# ---------- YearPlan ----------

@admin.register(YearPlan)
class YearPlanAdmin(admin.ModelAdmin):
    _yd = []
    for f in ("year", "name", "membership_vat", "federation_vat"):
        if _has_field(YearPlan, f):
            _yd.append(f)
    list_display = tuple(_yd) if _yd else ("id",)
    search_fields = tuple([f for f in ("year", "name") if _has_field(YearPlan, f)])
    _lf = [f for f in ("year",) if _has_field(YearPlan, f)]
    list_filter = tuple(_lf)

# ---------- YearPlanItem ----------

@admin.register(YearPlanItem)
class YearPlanItemAdmin(admin.ModelAdmin):
    _cols = []
    for f in ("yearplan", "code", "description"):
        if _has_field(YearPlanItem, f):
            _cols.append(f)
    _cols.append("price_excl_display")
    if _has_field(YearPlanItem, "vat_rate"):
        _cols.append("vat_rate")
    if _has_field(YearPlanItem, "product"):
        _cols.append("product")
    list_display = tuple(_cols)

    _lf = []
    for f in ("yearplan", "code"):
        if _has_field(YearPlanItem, f):
            _lf.append(f)
    if _has_field(YearPlanItem, "product"):
        _lf.append("product")
    list_filter = tuple(_lf)

    search_fields = tuple([f for f in ("code", "description") if _has_field(YearPlanItem, f)])

    _ac = []
    if _has_field(YearPlanItem, "yearplan"):
        _ac.append("yearplan")
    if _has_field(YearPlanItem, "product"):
        _ac.append("product")
    autocomplete_fields = tuple(_ac)

    @admin.display(description=_("Prijs (excl.)"))
    def price_excl_display(self, obj):
        for attr in ("price_excl", "unit_price_excl", "unit_price", "price"):
            if hasattr(obj, attr):
                return _money(getattr(obj, attr))
        return ""

# ---------- YearSequence ----------

@admin.register(YearSequence)
class YearSequenceAdmin(admin.ModelAdmin):
    _cols = []
    if _has_field(YearSequence, "year"):
        _cols.append("year")
    if _has_field(YearSequence, "next_invoice_number"):
        _cols.append("next_invoice_number")
    else:
        _cols.append("next_display")
    list_display = tuple(_cols)

    _lf = tuple([f for f in ("year",) if _has_field(YearSequence, f)])
    list_filter = _lf
    search_fields = _lf

    @admin.display(description=_("Volgend nummer"))
    def next_display(self, obj):
        for attr in ("next_invoice_number", "next_number", "seed", "current"):
            if hasattr(obj, attr):
                return getattr(obj, attr)
        return ""

# ---------- PricingRule ----------

@admin.register(PricingRule)
class PricingRuleAdmin(admin.ModelAdmin):
    _cols = ["name"]
    if _has_field(PricingRule, "active"):
        _cols.append("active")
    list_display = tuple(_cols)
    list_filter = tuple([f for f in ("active",) if _has_field(PricingRule, f)])
    search_fields = ("name",)

# ---------- ImportMapping ----------

@admin.register(ImportMapping)
class ImportMappingAdmin(admin.ModelAdmin):
    _cols = []
    for f in ("name", "created_at"):
        if _has_field(ImportMapping, f):
            _cols.append(f)
    list_display = tuple(_cols) if _cols else ("id",)
    search_fields = tuple([f for f in ("name",) if _has_field(ImportMapping, f)])

# ---------- OrganizationProfile ----------

@admin.register(OrganizationProfile)
class OrganizationProfileAdmin(admin.ModelAdmin):
    _cols = []
    for f in ("name", "vat_number"):
        if _has_field(OrganizationProfile, f):
            _cols.append(f)
    list_display = tuple(_cols) if _cols else ("id",)
    search_fields = tuple([f for f in ("name", "vat_number") if _has_field(OrganizationProfile, f)])

# ---------- Admin branding ----------

admin.site.site_header = "Spiegelven Facturatie"
admin.site.site_title = "Spiegelven Facturatie"
admin.site.index_title = "Beheer"

# ---------- Verberg 'Gezinnen' uit admin ----------

try:
    Household = apps.get_model("core", "Household")
except Exception:
    Household = None

if Household is not None:
    from django.contrib.admin.sites import NotRegistered
    try:
        admin.site.unregister(Household)
    except NotRegistered:
        pass