from decimal import Decimal, ROUND_HALF_UP
from django.core.management.base import BaseCommand
from core.models import YearInvestScale

# helper: afronden op 2 decimaal (handelsafronding)
def q2(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

class Command(BaseCommand):
    help = "Vult/actualiseert de degressieve investeringsbedragen 60-69 (en 70=0) incl. FLEX-jaarbedragen (+17% / 7)."

    def add_arguments(self, parser):
        parser.add_argument("--vat", type=str, default="0.00",
                            help="BTW-percentage voor investeringsbijdrage (default 0.00).")
        parser.add_argument("--activate", action="store_true", help="Zet 'active' op True voor alle ingevoerde rijen.")

    def handle(self, *args, **opts):
        vat = Decimal(opts["vat"])
        IND = {
            60: Decimal("2595"), 61: Decimal("2495"), 62: Decimal("2395"),
            63: Decimal("2295"), 64: Decimal("2195"), 65: Decimal("2000"),
            66: Decimal("1700"), 67: Decimal("1350"), 68: Decimal("900"),
            69: Decimal("450"),
        }
        PRT = {
            60: Decimal("1255"), 61: Decimal("1155"), 62: Decimal("1055"),
            63: Decimal("955"),  64: Decimal("855"),  65: Decimal("600"),
            66: Decimal("500"),  67: Decimal("425"),  68: Decimal("300"),
            69: Decimal("150"),
        }

        created = 0
        updated = 0

        def upsert(age: int, role: str, base: Decimal):
            flex_year = q2(q2(base * Decimal("1.17")) / Decimal("7")) if base > 0 else Decimal("0.00")
            obj, was_created = YearInvestScale.objects.update_or_create(
                age=age, role=role,
                defaults=dict(
                    amount_normal=base,
                    amount_flex_yearly=flex_year,
                    vat_rate=vat,
                    active=True if opts["activate"] else False,
                )
            )
            return was_created

        # 60..69
        for age, base in IND.items():
            if upsert(age, "IND", base): created += 1
            else: updated += 1
        for age, base in PRT.items():
            if upsert(age, "PRT", base): created += 1
            else: updated += 1

        # 70: 0, voor IND en PRT
        for role in ("IND", "PRT"):
            if upsert(70, role, Decimal("0.00")): created += 1
            else: updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Degressieve investering ingevoerd/gewijzigd. created={created}, updated={updated}, vat={vat}"
        ))
