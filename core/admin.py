from django.contrib import admin
from django import forms
from .models import (
    Member, Household, InvoiceAccount, Invoice, InvoiceLine,
    Product, YearPlan, YearPlanItem, YearSequence,
    ImportMapping, PricingRule, MemberAsset, OrganizationProfile
)

# --- Inlines -------------------------------------------------
class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 0
    autocomplete_fields = ['product']
    fields = ('product', 'description', 'quantity', 'unit_price_excl', 'vat_rate')
    can_delete = True  # toon "verwijderen"-kolom

    def has_delete_permission(self, request, obj=None):
        # Mag verwijderen zolang de factuur in "concept" staat
        if obj is None:
            return True
        return getattr(obj, 'status', 'concept') == 'concept'


# --- Admins --------------------------------------------------
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'default_price_excl', 'default_vat_rate', 'active')
    list_filter = ('active',)
    search_fields = ('code', 'name')
    ordering = ('code',)


@admin.register(Household)
class HouseholdAdmin(admin.ModelAdmin):
    list_display = ('name', 'account', 'prefer_billing')
    search_fields = ('name', 'account__name')


@admin.register(InvoiceAccount)
class InvoiceAccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'email', 'vat_number', 'city')
    search_fields = ('name', 'email', 'vat_number')
    list_filter = ('type',)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('number', 'account', 'status', 'issue_date')
    list_filter = ('status',)
    search_fields = ('number', 'account__name')
    autocomplete_fields = ('account',)
    inlines = [InvoiceLineInline]

    class Media:
        # Laad onze JS die prijzen/btw/omschrijving invult bij productkeuze
        js = ('admin/invoice_line.js',)

    # Server-side vangnet: als JS niet liep, zet default waarden toch correct
    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for obj in instances:
            if isinstance(obj, InvoiceLine):
                if obj.product:
                    if not obj.description:
                        obj.description = obj.product.name
                    if not obj.unit_price_excl or float(obj.unit_price_excl) == 0.0:
                        obj.unit_price_excl = obj.product.default_price_excl or 0
                    if obj.vat_rate is None:
                        obj.vat_rate = obj.product.default_vat_rate or 0
                if not obj.quantity or float(obj.quantity) == 0.0:
                    obj.quantity = 1
                obj.save()
        for obj in formset.deleted_objects:
            obj.delete()
        formset.save_m2m()


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ('last_name', 'first_name', 'email', 'membership_mode', 'active')
    search_fields = ('last_name', 'first_name', 'email')
    list_filter = ('membership_mode', 'active')


@admin.register(YearPlan)
class YearPlanAdmin(admin.ModelAdmin):
    list_display = ('year', 'name', 'membership_vat', 'federation_vat')
    search_fields = ('name',)
    ordering = ('-year',)


@admin.register(YearPlanItem)
class YearPlanItemAdmin(admin.ModelAdmin):
    list_display = ('yearplan', 'code', 'description', 'price_excl', 'vat_rate')
    list_filter = ('yearplan',)
    search_fields = ('code', 'description')


@admin.register(YearSequence)
class YearSequenceAdmin(admin.ModelAdmin):
    list_display = ('year', 'last_number')
    ordering = ('-year',)


@admin.register(ImportMapping)
class ImportMappingAdmin(admin.ModelAdmin):
    list_display = ('name', 'model', 'updated_at')
    search_fields = ('name', 'model')


@admin.register(PricingRule)
class PricingRuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'priority', 'action', 'valid_from_year', 'valid_to_year')
    search_fields = ('name', 'action')


@admin.register(MemberAsset)
class MemberAssetAdmin(admin.ModelAdmin):
    list_display = ('member', 'asset_type', 'identifier', 'price_excl', 'vat_rate', 'year')
    list_filter = ('asset_type', 'year')
    search_fields = ('member__last_name', 'member__first_name', 'identifier')


@admin.register(OrganizationProfile)
class OrganizationProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'enterprise_number', 'iban', 'bic', 'city')
    search_fields = ('name', 'enterprise_number')
