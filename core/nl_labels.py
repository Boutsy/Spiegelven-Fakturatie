from django.apps import apps

def _patch(model, singular, plural):
    m = apps.get_model('core', model)
    if m:
        m._meta.verbose_name = singular
        m._meta.verbose_name_plural = plural

_patch('Member', 'Lid', 'Leden')
_patch('Invoice', 'Factuur', 'Facturen')
_patch('InvoiceLine', 'Factuurlijn', 'Factuurlijnen')
_patch('InvoiceAccount', 'Facturatieaccount', 'Facturatieaccounts')
_patch('Product', 'Product', 'Producten')
_patch('YearPlan', 'Jaarplan', 'Jaarplannen')
_patch('YearPlanItem', 'Jaarplan-onderdeel', 'Jaarplan-onderdelen')
_patch('YearSequence', 'Jaarvolgnummer', 'Jaarvolgnummers')
_patch('MemberAsset', 'Ledenvoorziening', 'Ledenvoorzieningen')
_patch('OrganizationProfile', 'Organisatie', 'Organisaties')
_patch('ImportMapping', 'Importmapping', 'Importmappings')
