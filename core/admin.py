from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import Household, Member, Invoice, InvoiceLine, Product, YearPlan, YearPlanItem, InvoiceAccount, MemberAsset, PricingRule, OrganizationProfile, YearSequence, ImportMapping

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("id", "account", "issue_date", "status", "preview_link")
    autocomplete_fields = ("account",)
    inlines = []

    def preview_link(self, obj):
        url = reverse("invoice_preview", args=[obj.pk])
        return format_html('<a class="button" href="{}" target="_blank">Voorbeeld</a>', url)
    preview_link.short_description = "Voorbeeld"

@admin.register(Household)
class HouseholdAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "account", "prefer_billing", "gen_link")
    search_fields = ("name",)
    autocomplete_fields = ("account",)

    def gen_link(self, obj):
        url = reverse("household_generate_invoice", args=[obj.pk])
        return format_html('<a class="button" href="{}">Genereer jaarfactuur (concept)</a>', url)
    gen_link.short_description = "Jaarfactuur"

# Standaard registraties (pas aan naar wens)
@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ("id", "first_name", "last_name", "household", "active")

@admin.register(InvoiceLine)
class InvoiceLineAdmin(admin.ModelAdmin):
    list_display = ("id", "invoice", "description", "quantity", "unit_price_excl", "vat_rate", "product")
    autocomplete_fields = ("invoice", "product")

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "name", "default_price_excl", "default_vat_rate")
    search_fields = ("code", "name")

@admin.register(YearPlan)
class YearPlanAdmin(admin.ModelAdmin):
    list_display = ("year", "name", "membership_vat", "federation_vat", "forecast_link")
    def forecast_link(self, obj):
        url = reverse("yearplan_forecast", args=[obj.year])
        return format_html('<a class="button" href="{}" target="_blank">Prognose inkomsten</a>', url)
    forecast_link.short_description = "Prognose"

@admin.register(YearPlanItem)
class YearPlanItemAdmin(admin.ModelAdmin):
    list_display = ("id", "year", "code", "description", "price_excl", "vat_rate")
    list_filter = ("year",)
    search_fields = ("code", "description")

@admin.register(InvoiceAccount)
class InvoiceAccountAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "type", "email", "street", "postal_code", "city", "country")

@admin.register(MemberAsset)
class MemberAssetAdmin(admin.ModelAdmin):
    list_display = ("id", "member", "asset_type", "identifier", "year", "active", "price_excl", "vat_rate")
    list_filter = ("year", "asset_type", "active")
    search_fields = ("member__first_name", "member__last_name", "identifier")

@admin.register(PricingRule)
class PricingRuleAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "valid_from_year", "valid_to_year", "priority", "action", "value", "code")

@admin.register(OrganizationProfile)
class OrganizationProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "vat_number", "iban", "bic")

@admin.register(YearSequence)
class YearSequenceAdmin(admin.ModelAdmin):
    list_display = ("year", "last_number")

@admin.register(ImportMapping)
class ImportMappingAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "model", "created_at")