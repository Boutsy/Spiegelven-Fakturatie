from django.apps import AppConfig, apps

class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "Fakturatie"

    def ready(self):
        from . import numbering  # activeer nummering

        # Zet NL modelnamen in de admin
        def set_names(model_label, enkelvoud, meervoud):
            try:
                m = apps.get_model("core", model_label)
                m._meta.verbose_name = enkelvoud
                m._meta.verbose_name_plural = meervoud
            except LookupError:
                pass

        set_names("Member", "Lid", "Leden")
        set_names("Household", "Gezin", "Gezinnen")
        set_names("InvoiceAccount", "Facturatieaccount", "Facturatieaccounts")
        set_names("Invoice", "Factuur", "Facturen")
        set_names("InvoiceLine", "Factuurregel", "Factuurregels")
        set_names("Product", "Product", "Producten")
        set_names("YearPlan", "Jaarplan", "Jaarplannen")
        set_names("YearPlanItem", "Jaarplan-onderdeel", "Jaarplan-onderdelen")
        set_names("YearSequence", "Nummerreeks", "Nummerreeksen")
        set_names("ImportMapping", "Importkoppeling", "Importkoppelingen")
        set_names("PricingRule", "Prijsregel", "Prijsregels")
        set_names("MemberAsset", "Ledenvoorziening", "Ledenvoorzieningen")
        set_names("OrganizationProfile", "Organisatieprofiel", "Organisatieprofielen")