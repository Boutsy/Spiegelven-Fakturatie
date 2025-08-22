from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.db.models import Q

from core.models import (
    Household, Member, Invoice, InvoiceLine, YearPlan, YearPlanItem, MemberAsset
)

# Helpers
def first_monday(year: int) -> date:
    d = date(year, 1, 1)
    # weekday(): Monday=0 ... Sunday=6
    delta = (7 - d.weekday()) % 7
    return d + timedelta(days=delta)

def age_on(dob, ref: date) -> int:
    if not dob:
        return 0
    return ref.year - dob.year - ((ref.month, ref.day) < (dob.month, dob.day))

def q2(x) -> Decimal:
    return (Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

class Command(BaseCommand):
    help = "Genereer jaarfacturen voor alle leden (per gezinshoofd) voor het gegeven jaar."

    def add_arguments(self, parser):
        parser.add_argument(
            "--year",
            type=int,
            default=timezone.now().year,
            help="Jaar waarvoor te factureren (default: huidig jaar).",
        )
        parser.add_argument(
            "--commit",
            action="store_true",
            help="Pas effectief toe (zonder deze vlag is het een dry-run log).",
        )

    def handle(self, *args, **opts):
        year = opts["year"]
        do_commit = opts["commit"]

        try:
            plan = YearPlan.objects.get(year=year)
        except YearPlan.DoesNotExist:
            raise CommandError(f"Geen YearPlan gevonden voor jaar {year}. Maak die eerst aan.")

        # Sla YearPlanItems op in dict per code
        items = {i.code: i for i in YearPlanItem.objects.filter(yearplan=plan)}
        ref_date = date(year, 1, 1)
        issue_dt = first_monday(year)

        created = 0
        skipped = 0

        # We factureren per gezin (Household). Voor elk gezin: één factuur naar het facturatieaccount.
        heads = Member.objects.filter(household_head__isnull=True).order_by("last_name", "first_name")
        self.stdout.write(f"Gevonden gezinshoofden/individuelen: {heads.count()}")

        for head in heads:
            # Actieve leden in dit gezin
            leden = Member.objects.filter(Q(pk=head.pk) | Q(household_head=head)).order_by("last_name", "first_name")
            if not leden:
                skipped += 1
                continue

            # Gezinshoofd + partner (volwassenen)
            volwassenen = [m for m in leden if m.household_role in ("GEZINSHOOFD", "PARTNER")]
            kinderen = [m for m in leden if m not in volwassenen]

            account = getattr(head, 'billing_account', None) or getattr(head, 'account', None)
        if not account:
                self.stdout.write(f"- SKIP {head}: geen facturatieaccount")
                skipped += 1
                continue

            # Start conceptfactuur
        inv = Invoice(account=account, issue_date=issue_dt, doc_type="FACTUUR", status="CONCEPT")
        lines_to_add = []

            def add_by_code(code: str, fallback_desc: str, qty=1, override_price=None):
                try:
                    ypi = YearPlanItem.objects.get(yearplan=yp, code=code)
                    price = override_price if override_price is not None else ypi.unit_price
                    vat = getattr(ypi, 'vat_rate', Decimal('0.21'))
                    lines_to_add.append(dict(
                        description=(ypi.description or fallback_desc),
                        unit_price=price,
                        quantity=qty,
                        vat_rate=vat,
                        product_id=getattr(ypi, 'product_id', None),
                    ))
                except YearPlanItem.DoesNotExist:
                    self.stdout.write(f"  ! ontbrekend YearPlanItem code={code} → lijn overgeslagen")
            # 1) Lidgeld volwassenen (Normaal/Flex + individueel/koppel)
            # Regels:
            # - "Normaal lid" is wat vroeger "INVEST" heette (we kijken naar membership_mode op leden).
            # - Als er ≥2 volwassenen zijn, factureren we als koppel; anders individueel.
            # - Als één van de volwassenen FLEX is → koppel = FLEX.
            # Let op: 60+/70+ intredegeld is beleidsmatig; dat vangen we met aparte lijnen, niet hier.
            if volwassenen:
                if len(volwassenen) >= 2:
                    is_flex = any(v.membership_mode == "FLEX" for v in volwassenen)
                    code = "MEMB_FLEX_COUPLE" if is_flex else "MEMB_NORMAL_COUPLE"
                    add_by_code(code, "Lidgeld koppel")
                else:
                    volw = volwassenen[0]
                    code = "MEMB_FLEX_INDIV" if volw.membership_mode == "FLEX" else "MEMB_NORMAL_INDIV"
                    add_by_code(code, "Lidgeld individueel")

            # 2) Kinderen/YA-categorieën (leeftijd op 1 januari)
            for k in kinderen:
                a = age_on(k.date_of_birth, ref_date)
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
                # >35 vallen in volwassenen, die verrekenden we hierboven

            # 3) Federatiebijdrage (via club)
            for m in leden:
                if m.federation_via_club:
                    a = age_on(m.date_of_birth, ref_date)
                    if a <= 21:
                        add_by_code("FED_14", f"Federatiebijdrage (GV) {m.first_name} {m.last_name}")
                    else:
                        add_by_code("FED_67", f"Federatiebijdrage (GV) {m.first_name} {m.last_name}")

            # 4) Ledenvoorzieningen (kasts, kar, e-kar) voor dit jaar
            assets = MemberAsset.objects.filter(member__in=leden, active=True)
            for asset in assets:
                desc = f"{asset.get_asset_type_display()} — {asset.identifier or ''}".strip()
                lines_to_add.append(dict(
                    description=desc,
                    quantity=1,
                    unit_price_excl=q2(asset.price_excl),
                    vat_rate=asset.vat_rate,
                ))

            # 5) Intredegeld (optioneel): we verwachten YearPlanItem code 'ENTRY_TRANCHE' of 'ENTRY_FULL' met juiste BTW.
            #    Hoeveelheid & bedrag bepaal je zelf: zet voor elk gezinshoofd desgewenst een apart YearPlanItem met correcte prijs,
            #    of maak (voor dit jaar) een losse "tranche" als YearPlanItem en gebruik die code hieronder.
            #    Als je liever automatische verdeling in X schijven wil: zeg het, dan voegen we velden + logica toe via migratie.
            # Voor nu: als code aanwezig is, voegen we één schijf toe.
            if items.get("ENTRY_TRANCHE"):
                add_by_code("ENTRY_TRANCHE", "Intredegeld (jaarlijkse schijf)")

            # Skip lege facturen
            if not lines_to_add:
                skipped += 1
                continue

            if do_commit:
                with transaction.atomic():
                    inv.save()
                    for l in lines_to_add:
                        InvoiceLine.objects.create(invoice=inv, **l)
                created += 1
                self.stdout.write(f"+ Factuur aangemaakt voor {head.name or str(account)}")
            else:
                self.stdout.write(f"[DRY-RUN] zou factuur maken voor {head.name or str(account)} met {len(lines_to_add)} lijnen.")

        self.stdout.write(self.style.SUCCESS(
            f"Klaar: aangemaakt={created}, overgeslagen={skipped}, jaar={year}, datum={issue_dt}"
        ))