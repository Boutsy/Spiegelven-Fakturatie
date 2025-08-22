from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    Household,
    Invoice,
    InvoiceAccount,
    InvoiceLine,
    Product,
    YearPlan,
    YearPlanItem,
    YearSequence,
    ImportMapping,
    PricingRule,
    Member,
    MemberAsset,
    OrganizationProfile,
)

class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 1
    autocomplete_fields = ('product',)
    fields = ('product', 'description', 'quantity', 'unit_price_excl', 'vat_rate')

    class Media:
        js = ('admin/invoice_line.js',)

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('id', 'account', 'issue_date', 'doc_type', 'status', 'number', 'preview_link')
    list_filter = ('status', 'doc_type',)
    search_fields = ('number', 'account__name', 'account__email',)
    autocomplete_fields = ('account',)
    inlines = [InvoiceLineInline]
    ordering = ('-issue_date', 'id')

    def preview_link(self, obj):
        url = reverse('invoice_preview', args=[obj.pk])
        return format_html('<a href={} target=_blank>Voorbeeld</a>', url)
    preview_link.short_description = 'Voorbeeld'

@admin.register(InvoiceLine)
class InvoiceLineAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'product', 'description', 'quantity', 'unit_price_excl', 'vat_rate')
    search_fields = ('description', 'product__code', 'product__name', 'invoice__number', 'invoice__account__name')
    autocomplete_fields = ('invoice', 'product')

@admin.register(InvoiceAccount)
class InvoiceAccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'vat_number', 'city')
    search_fields = ('name', 'email', 'vat_number', 'city', 'postal_code', 'street')
    ordering = ('name',)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'default_price_excl', 'default_vat_rate')
    search_fields = ('code', 'name')
    ordering = ('code',)

@admin.register(Household)
class HouseholdAdmin(admin.ModelAdmin):
    list_display = ('name', 'account', 'prefer_billing')
    search_fields = ('name', 'account__name')
    autocomplete_fields = ('account',)
    ordering = ('name',)

@admin.register(YearPlan)
class YearPlanAdmin(admin.ModelAdmin):
    list_display = ('year', 'name', 'membership_vat', 'federation_vat')
    list_filter = ('year',)
    search_fields = ('name',)
    ordering = ('-year', 'name')

@admin.register(YearPlanItem)
class YearPlanItemAdmin(admin.ModelAdmin):
    list_display = ('code', 'description', 'yearplan', 'price_excl', 'vat_rate')
    list_filter = ('yearplan',)
    search_fields = ('code', 'description', 'yearplan__year', 'yearplan__name')
    autocomplete_fields = ('yearplan',)
    ordering = ('-yearplan__year', 'code')

@admin.register(YearSequence)
class YearSequenceAdmin(admin.ModelAdmin):
    list_display = ('year', 'last_number')
    ordering = ('-year',)

@admin.register(PricingRule)
class PricingRuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'priority', 'valid_from_year', 'valid_to_year', 'action', 'value')
    list_filter = ('valid_from_year', 'valid_to_year', 'action')
    search_fields = ('name',)
    ordering = ('-valid_from_year', 'priority')

@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ('last_name', 'first_name', 'email', 'household_role', 'active')
    search_fields = ('last_name', 'first_name', 'email')
    list_filter = ('active', 'household_role')
    ordering = ('last_name', 'first_name')

@admin.register(MemberAsset)
class MemberAssetAdmin(admin.ModelAdmin):
    list_display = ('member', 'asset_type', 'identifier', 'year', 'price_excl', 'vat_rate')
    list_filter = ('asset_type', 'year')
    search_fields = ('member__last_name', 'member__first_name', 'identifier')
    autocomplete_fields = ('member',)
    ordering = ('-year', 'member')

@admin.register(ImportMapping)
class ImportMappingAdmin(admin.ModelAdmin):
    list_display = ('name', 'model', 'created_at', 'updated_at')
    search_fields = ('name', 'model')
    ordering = ('-updated_at',)

@admin.register(OrganizationProfile)
class OrganizationProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'vat_number', 'iban')
    search_fields = ('name', 'vat_number', 'iban', 'city')
    ordering = ('name',)

admin.site.site_header = 'Spiegelven Fakturatie'
admin.site.site_title = 'Spiegelven Fakturatie'
admin.site.index_title = 'Beheer'


# --- Ledenvoorzieningen inline toevoegen zonder bestaande MemberAdmin te overschrijven ---
try:
    from django.contrib import admin
    from .models import Member, MemberAsset

    class _MemberAssetInline(admin.TabularInline):
        model = MemberAsset
        fk_name = "member"
        extra = 0
        fields = ("asset_type", "identifier", "year")
        verbose_name = "Ledenvoorziening"
        verbose_name_plural = "Ledenvoorzieningen"

    # Als Member al geregistreerd is in admin, voeg inline toe
    _reg = getattr(admin.site, "_registry", {})
    if Member in _reg:
        _admin = _reg[Member]
        inlines = list(getattr(_admin, "inlines", []))
        if _MemberAssetInline not in inlines:
            _admin.inlines = ([_MemberAssetInline] + inlines)
except Exception as e:
    # Stil falen in importfase, toont zich als er echt iets mis is bij admin load
    pass
# --- einde inline toevoeging ---
