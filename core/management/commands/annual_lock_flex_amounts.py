from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.models import Member, YearInvestScale, YearPricing

DEC = lambda s: Decimal(s)

def age_on_1_jan(year, dob):
    if not dob:
        return None
    return year - dob.year  # voor jouw jaarlogica volstaat dit

def base_invest_amount(start_year: int, age: int, role_code: str) -> Decimal:
    """
    role_code: 'IND' of 'PRT'
    """
    if age is None:
        return None
    if age >= 70:
        return DEC("0.00")
    if 60 <= age <= 69:
        try:
            rec = YearInvestScale.objects.get(age=age, role=role_code)
            return rec.amount_normal
        except YearInvestScale.DoesNotExist:
            return None
    # < 60: pak basis uit YearPricing (vast bedrag; jij gaf aan: investeringsbedragen zelf veranderen niet per jaar)
    code = "INV_PRT" if role_code == "PRT" else "INV_IND"
    try:
        yp = YearPricing.objects.get(year=start_year, code=code, active=True)
    except YearPricing.DoesNotExist:
        # probeer fallback op recent jaar (bv. 2026)
        try:
            yp = YearPricing.objects.filter(code=code, active=True).order_by("-year").first()
        except Exception:
            yp = None
    return yp.amount if yp else None

class Command(BaseCommand):
    help = "Zet voor FLEX-leden het vaste jaarlijkse investeringsbedrag op basis van het startjaar (aantreden)."

    def add_arguments(self, parser):
        parser.add_argument("--year", type=int, help="Startjaar om te gebruiken indien nog niet gezet", required=True)
        parser.add_argument("--commit", action="store_true", help="Effectief opslaan (anders: dry-run)")

    def handle(self, *args, **opts):
        start_default_year = opts["year"]
        do_commit = opts["commit"]
        qs = Member.objects.filter(membership_mode=Member.MODE_FLEX, active=True)

        updated = 0
        examined = 0
        skipped = 0
        now_year = timezone.now().year

        for m in qs.iterator():
            examined += 1
            # rol bepalen
            role_code = "PRT" if m.household_role == Member.ROLE_PARTNER else "IND"
            # startjaar bepalen/zetten
            start_year = m.invest_flex_start_year or start_default_year
            # leeftijd op 1 jan startjaar
            age = age_on_1_jan(start_year, m.date_of_birth)

            base = base_invest_amount(start_year, age, role_code)
            if base is None:
                self.stdout.write(f"- SKIP {m.pk}: geen basisbedrag (age={age}, role={role_code})")
                skipped += 1
                continue

            locked_yearly = (base * DEC("1.17") / DEC("7")).quantize(DEC('1'))

            need_save = False
            changes = []
            if m.invest_flex_locked_amount is None:
                m.invest_flex_locked_amount = locked_yearly
                need_save = True
                changes.append(f"locked={locked_yearly}")
            if m.invest_flex_start_year is None:
                m.invest_flex_start_year = start_year
                need_save = True
                changes.append(f"start_year={start_year}")

            if need_save:
                updated += 1
                if do_commit:
                    m.save(update_fields=["invest_flex_locked_amount", "invest_flex_start_year"])
                self.stdout.write(f"+ {('SAVED' if do_commit else 'WOULD SAVE')} member {m.pk}: " + ", ".join(changes))
            else:
                self.stdout.write(f"= OK member {m.pk}: locked={m.invest_flex_locked_amount}, start_year={m.invest_flex_start_year}")

        self.stdout.write(self.style.SUCCESS(f"Done. examined={examined}, updated={updated}, skipped={skipped}."))
