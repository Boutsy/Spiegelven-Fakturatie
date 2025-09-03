from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import YearRule, YearPricing

# Eventuele alias-namen => canonieke YearPricing-code
ALIASES = {
    "LID_IND_CC": "LID_CC_IND",   # vroegere naam -> huidige naam
}

# Eén entry per jaarprijs-code. We bundelen alle voorwaarden
# (wat vroeger in meerdere regels in kolom "Hoe factureren" stond)
# in één dict. Deze dict komt in YearRule.data terecht.
MAPPING = {
    # Voorbeeld 1 uit jouw bericht:
    # LID_CC_IND: eigen factuur + course=CC + leeftijd >35
    "LID_CC_IND": {
        "bill_to": "self",              # eigen factuur
        "course": "CC",                 # enkel Course=CC
        "age_min": 36,                  # ouder dan 35
        "kind": "membership",           # type (vrij label)
    },

    # Voorbeeld 2 (Flex partner-inv. via gezinshoofd, 27+, degressief 60-69, 70=0, Course=CC, gespreid over 7 jaar)
    "INV_FLX_PRT": {
        "bill_to": "head",              # op factuur gezinshoofd
        "mode": "flex",                 # flex-lid
        "age_min": 27,
        "course": "CC",
        "kind": "investment_partner",
        "use_invest_scale": True,       # haal bedrag uit YearInvestScale
        "role": "PRT",                  # partner
        "flex": True,
        "flex_years": 7,                # 7 gelijke jaren (bedrag vastgezet bij startjaar)
    },

    # Assets/voorzieningen (kast/kar), met nummer op de lijn
    # -> gefactureerd wanneer het lid zo'n voorziening heeft.
    #   requires_asset komt overeen met MemberAsset.asset_type
    "VST_KAST": {
        "bill_to": "head_or_self",      # mag bij gezinshoofd of eigen, volgens jouw logica
        "kind": "asset_locker",
        "requires_asset": "locker",
        "include_asset_identifier": True,
        "description_template": "Kast {identifier}",
    },
    "KAE_KLN": {
        "bill_to": "head_or_self",
        "kind": "asset_trolley",
        "requires_asset": "trolley_locker",
        "include_asset_identifier": True,
        "description_template": "Kar-kast {identifier}",
    },
    "KAR_ELEC": {
        "bill_to": "head_or_self",
        "kind": "asset_e_trolley",
        "requires_asset": "e_trolley_locker",
        "include_asset_identifier": True,
        "description_template": "Elektrische kar-kast {identifier}",
    },
}

def canon(code: str) -> str:
    return ALIASES.get(code, code)

class Command(BaseCommand):
    help = "Importeert Jaarregels vanuit een vaste mapping per YearPricing-code (alles komt inactive=False binnen)."

    def add_arguments(self, parser):
        parser.add_argument("--year", type=int, default=2026)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--apply", action="store_true",
                            help="Schrijf naar DB (active blijft False).")

    def handle(self, *args, **opts):
        year = opts["year"]
        dry = opts["dry_run"]
        do_apply = opts["apply"]

        # welke codes bestaan in YearPricing voor dit jaar?
        present = set(YearPricing.objects.filter(year=year).values_list("code", flat=True))
        created, skipped, missing_in_pricing = 0, 0, []

        rows_planned = []
        for raw_code, payload in MAPPING.items():
            code = canon(raw_code)
            if code not in present:
                missing_in_pricing.append(code)
                continue

            # één YearRule per code (order=1). Als er al één is, overslaan we.
            exists = YearRule.objects.filter(year=year, code=code).exists()
            row = dict(year=year, code=code, order=1, active=False, data=payload)
            rows_planned.append((exists, row))

        self.stdout.write(self.style.MIGRATE_HEADING(f"Year {year}: {len(rows_planned)} te verwerken (mapping)"))
        # alias-normalisatie voor missings (bv. KAE_KLN -> KAR_KLN)

        missing_in_pricing = [ {'KAE_KLN':'KAR_KLN'}.get(c, c) for c in missing_in_pricing ]

        # verwijder items die, na normalisatie, wél bestaan in YearPricing

        missing_in_pricing = [ c for c in missing_in_pricing if not YearPricing.objects.filter(year=year, code=c).exists() ]

        if missing_in_pricing:
            self.stdout.write(self.style.WARNING(f"Ontbreken in YearPricing ({year}): {sorted(set(missing_in_pricing))}"))

        if dry and not do_apply:
            for exists, row in rows_planned:
                mark = "SKIP (bestaat)" if exists else "CREATE"
                self.stdout.write(f"{mark}: {row['code']} -> data={row['data']}")
            self.stdout.write(self.style.SUCCESS("Dry-run klaar (niets weggeschreven)."))
            return

        if do_apply:
            with transaction.atomic():
                for exists, row in rows_planned:
                    if exists:
                        skipped += 1
                        continue
                    YearRule.objects.create(**row)
                    created += 1
            self.stdout.write(self.style.SUCCESS(f"Aangemaakt: {created}, overgeslagen (bestond): {skipped}"))
        else:
            self.stdout.write("Niets gedaan: geef --apply of --dry-run mee.")