from django.http import HttpResponse
from django.template.response import TemplateResponse
import csv

from .models import MemberAsset

def export_assets_csv(modeladmin, request, queryset):
    if not queryset.exists():
        queryset = modeladmin.get_queryset(request)
    resp = HttpResponse(content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = 'attachment; filename="member_assets.csv"'
    w = csv.writer(resp)
    w.writerow(['type','identifier','member_id','member_name','active'])
    for a in queryset.select_related('member'):
        name = f"{getattr(a.member,'first_name','')} {getattr(a.member,'last_name','')}".strip() or str(a.member)
        w.writerow([a.asset_type, a.identifier or '', a.member_id, name, a.active])
    return resp
export_assets_csv.short_description = "Exporteer selectie (of filter) naar CSV"

def print_assets_html(modeladmin, request, queryset):
    if not queryset.exists():
        queryset = modeladmin.get_queryset(request)
    queryset = queryset.select_related('member').order_by('asset_type','identifier')

    titles = {
        'locker': 'Vestiaire kasten',
        'trolley_locker': 'Karrengarage klein',
        'e_trolley_locker': 'Karrengarage elektrisch',
    }
    order = ['locker','trolley_locker','e_trolley_locker']

    groups, by_type = [], {k: [] for k in order}
    for a in queryset:
        by_type.get(a.asset_type, []).append(a)
    for key in order:
        items = by_type[key]
        if items:
            groups.append({'key': key, 'title': titles[key], 'items': items, 'count': len(items)})
    ctx = {'groups': groups, 'total': sum(g['count'] for g in groups)}
    return TemplateResponse(request, 'admin/memberasset_print.html', ctx)
print_assets_html.short_description = "Print overzicht per type (HTML)"
