
from django.contrib import admin
from django.http import HttpResponse
from django.apps import apps
import csv

from .models import Member, MemberAsset, YearPricing, YearRule, YearSequence, YearInvestScale

def export_assets_csv(modeladmin, request, queryset):
    if not queryset.exists():
        queryset = modeladmin.get_queryset(request)
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="member_assets.csv"'
    w = csv.writer(response)
    w.writerow(['type','identifier','member_id','member_name','active'])
    for a in queryset.select_related('member'):
        name = f"{getattr(a.member,'first_name','')} {getattr(a.member,'last_name','')}".strip()
        w.writerow([a.asset_type, a.identifier or '', a.member_id, name, a.active])
    return response
export_assets_csv.short_description = "Exporteer selectie (of filter) naar CSV"

class MemberAssetInline(admin.TabularInline):
    model = MemberAsset
    extra = 0
    fields = ('asset_type','identifier','active','released_on')
    show_change_link = True

@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    inlines = [MemberAssetInline]
    list_display = ('id','first_name','last_name','household_role','course')
    search_fields = ('first_name','last_name','email')
    list_filter = ('household_role','course')

@admin.register(MemberAsset)
class MemberAssetAdmin(admin.ModelAdmin):
    list_display = ('id','asset_type','identifier','member','active','released_on')
    list_filter = ('asset_type','active')
    search_fields = ('identifier','member__first_name','member__last_name','member__email')
    actions = [export_assets_csv]

# Probeer extra Year-* modellen te registreren als ze bestaan (zonder harde imports)
for name in ['YearPricing', 'YearRule', 'YearSequence', 'YearInvestScale', 'YearOrder']:
    try:
        M = apps.get_model('core', name)
    except Exception:
        M = None
    if M:
        try:
            admin.site.register(M)
        except admin.sites.AlreadyRegistered:
            pass
