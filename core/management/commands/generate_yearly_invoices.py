from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction
from django.db.models import Prefetch

from core.models import (
    Household,
    Invoice,
    InvoiceAccount,
    InvoiceLine,
    Member,
    MemberAsset,
    Product,
    YearPlan,
    YearPlanItem,
)

class Command(BaseCommand):
    help = "Genereer jaarfacturen op basis van het Jaarplan. Alle prijzen komen UITSLUITEND uit Jaarplan-onderdelen."

    def add_arguments(self, parser):
        parser.add_argument("--year", type=int, help="Jaar voor het Jaarplan (bv. 2025). Standaard: huidig jaar.")
        parser.add_argument("--commit", action="store_true", help="Zonder deze vlag is het een proefrun (niets wordt opgeslagen).")

    def handle(self, *args, **options):
        year = options.get("year") or timezone.now().year
        commit = options.get("commit", False)

        try:
            yp = YearPlan.objects.get(year=year)
        except YearPlan.DoesNotExist:
            raise CommandError(f"Geen Jaarplan gevonden voor {year}.")

        def yp_item_for(code: str):
            try:
                return YearPlanItem.objects.get(yearplan=yp, code=code)
            except YearPlanItem.DoesNotExist:
                return None

        # Prefetch leden + hun voorzieningen
        households = (
            Household.objects.all()
            .select_related("account")
            .prefetch_related(
                Prefetch("member_set", queryset=Member.objects.filter(active=True).prefetch_related("memberasset_set"))
            )
        )

        created_invoices = 0
        preview_invoices = 0
        total_lines = 0

        for hh in households:
            members = list(hh.member_set.all())
            if not members:
                continue

            if not hh.account:
                self.stdout.write(self.style.WARNING(f"[{hh.name}] Geen facturatieaccount gekoppeld — overgeslagen."))
                continue

            # Stel de lijnen samen (alleen Jaarplan-prijzen)
            lines = []

            # 1) Ledenvoorzieningen (Soort = code, Nummer = identifier)
            for m in members:
                for ass in m.memberasset_set.all():
                    code = (ass.asset_type or "").strip()
                    if not code:
                        self.stdout.write(self.style.WARNING(f"[{hh.name}] Voorziening zonder code — overgeslagen."))
                        continue

                    ypi = yp_item_for(code)
                    if not ypi:
                        self.stdout.write(self.style.WARNING(f"[{hh.name}] Geen Jaarplan-onderdeel met code '{code}' ({year})."))
                        continue

                    desc = ypi.description or code
                    if ass.identifier:
                        desc = f"{desc} – nr. {ass.identifier}"

                    product = Product.objects.filter(code=code).first()

                    lines.append(
                        InvoiceLine(
                            product=product,
                            description=desc,
                            quantity=1,
                            unit_price_excl=ypi.price_excl,
                            vat_rate=ypi.vat_rate,
                        )
                    )

            # 2) (Optioneel) Lidgelden, federatie, intredegeld
            # Wil je ook deze uitsluitend via Jaarplan laten lopen, definieer dan in Jaarplan-onderdelen de juiste codes
            # en plaats hieronder jouw logica die per lid/huishouden de juiste code(s) kiest en steeds ypi.price_excl / ypi.vat_rate gebruikt.
            # Voor nu: we laten bestaande lidgeldlogica met rust als die elders draait; deze command voegt zeker de voorzieningen toe met Jaarplan-prijzen.

            if not lines:
                continue

            if commit:
                with transaction.atomic():
                    inv = Invoice.objects.create(
                        account=hh.account,
                        issue_date=timezone.now().date(),
                        # laat status/doc_type op default (concept)
                    )
                    for ln in lines:
                        ln.invoice = inv
                    InvoiceLine.objects.bulk_create(lines)
                created_invoices += 1
                total_lines += len(lines)
                self.stdout.write(self.style.SUCCESS(f"Factuur aangemaakt voor '{hh.name}' met {len(lines)} lijnen."))
            else:
                preview_invoices += 1
                total_lines += len(lines)
                self.stdout.write(f"[PROEFRUN] '{hh.name}': {len(lines)} lijnen (Jaarplan: {year}).")

        msg = f"Klaar. {'Aangemaakt: ' + str(created_invoices) if commit else 'Proef: ' + str(preview_invoices)} facturen, totaal {total_lines} lijnen."
        self.stdout.write(self.style.SUCCESS(msg))