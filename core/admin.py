from decimal import Decimal
from django import forms
from django.contrib import admin
from django.urls import path
from django.http import JsonResponse, Http404
from .models import (
    Member, Household, InvoiceAccount, Invoice, InvoiceLine, Product,
    YearPlan, YearPlanItem, YearSequence, ImportMapping, PricingRule,
    MemberAsset, OrganizationProfile
)

# --- Admin form met server-side fallback voor prijs/btw/omschrijving ---
class InvoiceLineAdminForm(forms.ModelForm):
    class Meta:
        model = InvoiceLine
        fields = "__all__"

    def clean(self):
        data = super().clean()
        product = data.get("product")
        if product:
            # Omschrijving automatisch invullen als die leeg is
            if not data.get("description"):
                data["description"] = product.name

            # Prijs invullen als 0 of leeg
            price = data.get("unit_price_excl")
            if price in (None, Decimal("0"), 0):
                if product.default_price_excl is not None:
                    data["unit_price_excl"] = product.default_price_excl

            # Btw invullen als 0 of leeg
            vat = data.get("vat_rate")
            if vat in (None, Decimal("0"), 0):
                if product.default_vat_rate is not None:
                    data["vat_rate"] = product.default_vat_rate
        return data

# --- Inline voor factuurregels (laadt ons JS) ---
class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    form = InvoiceLineAdminForm
    extra = 1
    fields = ("product", "description", "quantity", "unit_price_excl", "vat_rate")
    # Belangrijk: een gewone <select>, GEEN autocomplete hier
    class Media:
        js = ("admin/invoice_line.js",)

# --- Facturen ---
@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    inlines = [InvoiceLineInline]
    list_display = ("id", "number", "status", "account", "issue_date")
    list_filter = ("status",)
    search_fields = ("number", "account__name")

# --- Producten + JSON-eindpunt voor JS autofill ---
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "default_price_excl", "default_vat_rate")
    search_fields = ("code", "name")

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path("<int:pk>/json/", self.admin_site.admin_view(self.product_json), name="core_product_json"),
        ]
        return custom + urls

    def product_json(self, request, pk: int):
        try:
            p = Product.objects.get(pk=pk)
        except Product.DoesNotExist:
            raise Http404("Product niet gevonden")
        return JsonResponse({
            "id": p.pk,
            "code": p.code,
            "name": p.name,
            "default_price_excl": str(p.default_price_excl) if p.default_price_excl is not None else "",
            "default_vat_rate": str(p.default_vat_rate) if p.default_vat_rate is not None else "",
        })

# --- De rest gewoon registreren ---
@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    search_fields = ("first_name", "last_name", "email")

@admin.register(Household)
class HouseholdAdmin(admin.ModelAdmin):
    search_fields = ("name",)

@admin.register(InvoiceAccount)
class InvoiceAccountAdmin(admin.ModelAdmin):
    search_fields = ("name", "email")

@admin.register(YearPlan)
class YearPlanAdmin(admin.ModelAdmin):
    list_display = ("year", "name")

@admin.register(YearPlanItem)
class YearPlanItemAdmin(admin.ModelAdmin):
    list_display = ("yearplan", "code", "description", "price_excl", "vat_rate")

@admin.register(YearSequence)
class YearSequenceAdmin(admin.ModelAdmin):
    list_display = ("year", "last_number")

@admin.register(ImportMapping)
class ImportMappingAdmin(admin.ModelAdmin):
    list_display = ("model", "name", "updated_at")

@admin.register(PricingRule)
class PricingRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "priority", "valid_from_year", "valid_to_year")

@admin.register(MemberAsset)
class MemberAssetAdmin(admin.ModelAdmin):
    list_display = ("member", "asset_type", "year", "price_excl", "vat_rate")

@admin.register(OrganizationProfile)
class OrganizationProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "vat_number")
