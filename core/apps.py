from django.apps import AppConfig, apps

class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "Fakturatie"  # zo heet het app-blok in de admin

    def ready(self):
        # Nummeringssignalen activeren (als bestand bestaat)
        try:
            from . import numbering  # noqa: F401
        except Exception:
            pass

        # Admin-branding: kopteksten
        try:
            from django.contrib import admin
            admin.site.site_header = "Spiegelven Fakturatie"
            admin.site.site_title = "Spiegelven Fakturatie"
            admin.site.index_title = "Beheer"
        except Exception:
            pass

        # Modellabels in de admin vernederlandsen (zonder migrations)
        def set_names(model_label, enkelvoud, meervoud):
            try:
                m = apps.get_model("core", model_label)
                m._meta.verbose_name = enkelvoud
                m._meta.verbose_name_plural = meervoud
            except LookupError:
                pass  # model bestaat (nog) niet? sla over

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
