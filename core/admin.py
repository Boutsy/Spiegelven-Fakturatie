from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import (
    Product, Invoice, InvoiceLine, InvoiceAccount,
    Member, Household, YearPlan, YearPlanItem, YearSequence,
    OrganizationProfile, ImportMapping, PricingRule, MemberAsset
)

# Inline voor factuurregels + koppel admin JS dat product-prijs/btw invult
class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 1
    fields = ("product", "description", "quantity", "unit_price_excl", "vat_rate")
    autocomplete_fields = ("product",)

    class Media:
        js = ("admin/invoice_line.js",)  # gebruikt URL 'product-defaults'

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("number", "account", "issue_date", "status", "preview_link")
    autocomplete_fields = ("account",)
    inlines = [InvoiceLineInline]

    def preview_link(self, obj):
        url = reverse("invoice_preview", args=[obj.pk])
        return format_html('<a class="button" target="_blank" href="{}">Voorbeeld</a>', url)
    preview_link.short_description = "Voorbeeld"

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "default_price_excl", "default_vat_rate", "active")
    list_filter = ("active",)
    search_fields = ("code", "name")

@admin.register(InvoiceAccount)
class InvoiceAccountAdmin(admin.ModelAdmin):
    search_fields = ("name", "email", "vat_number", "city")

@admin.register(Household)
class HouseholdAdmin(admin.ModelAdmin):
    search_fields = ("name",)

# De rest gewoon registreren met standaard admin
admin.site.register(Member)
admin.site.register(YearPlan)
admin.site.register(YearPlanItem)
admin.site.register(YearSequence)
admin.site.register(OrganizationProfile)
admin.site.register(ImportMapping)
admin.site.register(PricingRule)
admin.site.register(MemberAsset)