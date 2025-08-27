from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.db.models import Q
from core.models import Member, Invoice, InvoiceLine, YearPlan, YearPlanItem, MemberAsset, InvoiceAccount

def first_monday(year: int) -> date:
    d = date(year, 1, 1)
    delta = (7 - d.weekday()) % 7
    return d + timedelta(days=delta)

def age_on(dob, ref: date) -> int:
    if not dob:
        return 0
    return ref.year - dob.year - ((ref.month, ref.day) < (dob.month, dob.day))

def q2(x) -> Decimal:
    return Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

class Command(BaseCommand):
    help = "Genereer jaarfacturen per gezinshoofd/individueel voor het opgegeven jaar."

    def add_arguments(self, parser):
        parser.add_argument("--year", type=int, default=timezone.now().year)
        parser.add_argument("--commit", action="store_true")

    def handle(self, *args, **opts):
        year = opts["year"]
        do_commit = opts["commit"]

        try:
            plan = YearPlan.objects.get(year=year)
        except YearPlan.DoesNotExist:
            raise CommandError(f"Geen YearPlan voor {year}.")

        items = {i.code: i for i in YearPlanItem.objects.filter(yearplan=plan)}
        ref_date = date(year, 1, 1)
        issue_dt = first_monday(year)

        heads = Member.objects.filter(household_head__isnull=True).order_by("last_name", "first_name")
        self.stdout.write(f"Gevonden gezinshoofden/individuelen: {heads.count()}")

        created = 0
        skipped = 0

        def resolve_account(head: Member) -> InvoiceAccount:
            if getattr(head, "billing_account_id", None):
                return head.billing_account
            first = getattr(head, "first_name", "") or ""
            last = getattr(head, "last_name", "") or ""
            name = (first + " " + last).strip() or str(head)
            email = (getattr(head, "email", "") or "").strip()
            if email:
                acc, _ = InvoiceAccount.objects.get_or_create(email=email, defaults={"name": name, "email": email})
            else:
                acc, _ = InvoiceAccount.objects.get_or_create(name=name, defaults={"name": name})
            return acc

        for head in heads:
            leden = Member.objects.filter(Q(pk=head.pk) | Q(household_head=head)).order_by("last_name", "first_name")
            if not leden.exists():
                skipped += 1
                continue

            volwassenen = [m for m in leden if getattr(m, "household_role", "") in ("GEZINSHOOFD", "PARTNER")]
            kinderen = [m for m in leden if m not in volwassenen]

            account = resolve_account(head)
            inv = Invoice(account=account, issue_date=issue_dt, doc_type="FACTUUR", status="CONCEPT")
            lines_to_add = []

            def add_by_code(code: str, fallback_desc: str, qty=1, override_price=None):
                ypi = items.get(code)
                if not ypi:
                    self.stdout.write(f"  ! ontbrekend YearPlanItem code={code} → lijn overgeslagen")
                    return
                price = None
                for attr in ("unit_price_excl", "price_excl", "unit_price", "price"):
                    if hasattr(ypi, attr):
                        price = getattr(ypi, attr)
                        break
                if price is None:
                    self.stdout.write(f"  ! YearPlanItem code={code} mist prijs → lijn overgeslagen")
                    return
                vat = getattr(ypi, "vat_rate", Decimal("0.21"))
                desc = ypi.description or fallback_desc
                lines_to_add.append(dict(description=desc, unit_price_excl=q2(price), quantity=qty, vat_rate=vat))

            if volwassenen:
                if len(volwassenen) >= 2:
                    is_flex = any(getattr(v, "membership_mode", "") == "FLEX" for v in volwassenen)
                    add_by_code("MEMB_FLEX_COUPLE" if is_flex else "MEMB_NORMAL_COUPLE", "Lidgeld koppel")
                else:
                    volw = volwassenen[0]
                    is_flex = getattr(volw, "membership_mode", "") == "FLEX"
                    add_by_code("MEMB_FLEX_INDIV" if is_flex else "MEMB_NORMAL_INDIV", "Lidgeld individueel")

            for k in kinderen:
                a = age_on(getattr(k, "date_of_birth", None), ref_date)
                if a <= 15:
                    add_by_code("KID_0_15", f"Lidgeld kind t.e.m. 15 jaar: {k.first_name} {k.last_name}")
                elif a <= 21:
                    add_by_code("KID_16_21", f"Lidgeld kind t.e.m. 21 jaar: {k.first_name} {k.last_name}")
                elif a <= 26:
                    add_by_code("YA_22_26", f"Young Adult 22–26: {k.first_name} {k.last_name}")
                elif a <= 29:
                    add_by_code("YA_27_29", f"Young Adult 27–29: {k.first_name} {k.last_name}")
                elif a <= 35:
                    add_by_code("YA_30_35", f"Young Adult 30–35: {k.first_name} {k.last_name}")

            for m in leden:
                if getattr(m, "federation_via_club", False):
                    a = age_on(getattr(m, "date_of_birth", None), ref_date)
                    add_by_code("FED_14" if a <= 21 else "FED_67", f"Federatiebijdrage (GV) {m.first_name} {m.last_name}")

            assets = MemberAsset.objects.filter(member__in=leden, active=True)
            for asset in assets:
                desc = f"{asset.get_asset_type_display()} — {(asset.identifier or '').strip()}".strip(" —")
                price_attr = "price_excl" if hasattr(asset, "price_excl") else "unit_price_excl"
                price_val = getattr(asset, price_attr, Decimal("0.00")) or Decimal("0.00")
                vat_val = getattr(asset, "vat_rate", Decimal("0.21"))
                lines_to_add.append(dict(description=desc, quantity=1, unit_price_excl=q2(price_val), vat_rate=vat_val))

            if items.get("ENTRY_TRANCHE"):
                add_by_code("ENTRY_TRANCHE", "Intredegeld (jaarlijkse schijf)")

            if not lines_to_add:
                skipped += 1
                continue

            if do_commit:
                with transaction.atomic():
                    inv.save()
                    for l in lines_to_add:
                        InvoiceLine.objects.create(invoice=inv, **l)
                created += 1
                naam = (getattr(head, "first_name", "") + " " + getattr(head, "last_name", "")).strip() or str(account)
                self.stdout.write(f"+ Factuur aangemaakt voor {naam} ({len(lines_to_add)} lijnen)")
            else:
                naam = (getattr(head, "first_name", "") + " " + getattr(head, "last_name", "")).strip() or str(account)
                self.stdout.write(f"[DRY-RUN] zou factuur maken voor {naam} met {len(lines_to_add)} lijnen.")

        self.stdout.write(self.style.SUCCESS(f"Klaar: aangemaakt={created}, overgeslagen={skipped}, jaar={year}, datum={issue_dt}"))
