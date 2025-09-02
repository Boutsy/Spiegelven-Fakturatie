from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
import json, csv, os

try:
    # models import
    from core.models import YearPricing
except Exception as e:
    YearPricing = None

DEFAULT_ITEMS = [
    # Lidgelden — Championship Course (CC)
    dict(code="LID_CC_IND",  description="Lidgeld CC — Individueel",           vat_rate=21, unit_price="0.00",  billing_strategy="FIXED_SELF",      rule_params={}),
    dict(code="LID_CC_HEAD", description="Lidgeld CC — Gezinshoofd",           vat_rate=21, unit_price="0.00",  billing_strategy="FIXED_SELF",      rule_params={}),
    dict(code="LID_CC_PRT",  description="Lidgeld CC — Partner (op factuur GH)",vat_rate=21, unit_price="0.00",  billing_strategy="BILL_TO_HEAD_FOR_PARTNER", rule_params={}),
    # Jeugdcategorieën (op basis van leeftijd)
    dict(code="LID_CC_KID_0_15",  description="Lidgeld CC — Kid t/m 15",       vat_rate=21, unit_price="0.00",  billing_strategy="FIXED_IF",        rule_params={"age_band":"KID_0_15"}),
    dict(code="LID_CC_KID_16_21", description="Lidgeld CC — Kid 16–21",        vat_rate=21, unit_price="0.00",  billing_strategy="FIXED_IF",        rule_params={"age_band":"KID_16_21"}),
    dict(code="LID_CC_YA_22_26",  description="Lidgeld CC — YA 22–26",         vat_rate=21, unit_price="0.00",  billing_strategy="FIXED_IF",        rule_params={"age_band":"YA_22_26"}),
    dict(code="LID_CC_YA_27_29",  description="Lidgeld CC — YA 27–29",         vat_rate=21, unit_price="0.00",  billing_strategy="FIXED_IF",        rule_params={"age_band":"YA_27_29"}),
    dict(code="LID_CC_YA_30_35",  description="Lidgeld CC — YA 30–35",         vat_rate=21, unit_price="0.00",  billing_strategy="FIXED_IF",        rule_params={"age_band":"YA_30_35"}),
    dict(code="LID_CC_60_PLUS",   description="Lidgeld CC — 60 Plus",          vat_rate=21, unit_price="0.00",  billing_strategy="FIXED_IF",        rule_params={"age_band":"60_PLUS"}),
    dict(code="LID_CC_70_PLUS",   description="Lidgeld CC — 70 Plus",          vat_rate=21, unit_price="0.00",  billing_strategy="FIXED_IF",        rule_params={"age_band":"70_PLUS"}),

    # Lidgelden — Par-3 (P3) (zelfde structuur, pas desnoods later aan)
    dict(code="LID_P3_IND",  description="Lidgeld P3 — Individueel",           vat_rate=21, unit_price="0.00",  billing_strategy="FIXED_SELF",      rule_params={}),
    dict(code="LID_P3_HEAD", description="Lidgeld P3 — Gezinshoofd",           vat_rate=21, unit_price="0.00",  billing_strategy="FIXED_SELF",      rule_params={}),
    dict(code="LID_P3_PRT",  description="Lidgeld P3 — Partner (op factuur GH)",vat_rate=21, unit_price="0.00",  billing_strategy="BILL_TO_HEAD_FOR_PARTNER", rule_params={}),
    dict(code="LID_P3_KID_0_15",  description="Lidgeld P3 — Kid t/m 15",       vat_rate=21, unit_price="0.00",  billing_strategy="FIXED_IF",        rule_params={"age_band":"KID_0_15"}),

    # Federatie — enkel bij Course == CC én federatie == Ja
    dict(code="FED_CC_ADULT", description="Federatiebijdrage CC — Volwassene", vat_rate=21, unit_price="0.00",  billing_strategy="FIXED_IF",        rule_params={"requires_federation": True, "course":"CC", "age_band":"ADULT"}),
    dict(code="FED_CC_JUNIOR",description="Federatiebijdrage CC — Junior",    vat_rate=21, unit_price="0.00",  billing_strategy="FIXED_IF",        rule_params={"requires_federation": True, "course":"CC", "age_band":"JUNIOR"}),

    # Investering — eenmalig (Norm) of flexibel (7 jaar, zonder ‘nth’ in seed)
    dict(code="INV_NORM_IND", description="Investering CC — IND (éénmalig)",   vat_rate=21, unit_price="0.00",  billing_strategy="INVEST_ONE_OFF",  rule_params={"role":"IND"}),
    dict(code="INV_NORM_PRT", description="Investering CC — PRT (éénmalig)",   vat_rate=21, unit_price="0.00",  billing_strategy="INVEST_ONE_OFF",  rule_params={"role":"PRT"}),
    dict(code="INV_FLEX_IND", description="Investering CC — IND (flex 7 jaar)",vat_rate=21, unit_price="0.00",  billing_strategy="FLEX_INSTALLMENT",rule_params={"years":7,"role":"IND"}),
    dict(code="INV_FLEX_PRT", description="Investering CC — PRT (flex 7 jaar)",vat_rate=21, unit_price="0.00",  billing_strategy="FLEX_INSTALLMENT",rule_params={"years":7,"role":"PRT"}),

    # Overige vaste codes uit je prijsblad kan je later toevoegen
]

class Command(BaseCommand):
    help = "Seed vaste jaarcodes/prijzen voor een bepaald jaar (met CSV-optie en force-overwrite)."

    def add_arguments(self, parser):
        parser.add_argument("year", type=int, help="Jaar (bv. 2026)")
        parser.add_argument("--csv", dest="csv_path", help="Pad naar CSV met kolommen: code,description,vat_rate,unit_price,billing_strategy,rule_params(JSON)")
        parser.add_argument("--force", action="store_true", help="Overschrijf bestaande regels voor dit jaar")

    def handle(self, *args, **opts):
        if YearPricing is None:
            raise CommandError("YearPricing model niet beschikbaar. Heb je de migraties gedraaid?")

        year = int(opts["year"])
        csv_path = opts.get("csv_path")
        force = bool(opts.get("force"))

        if csv_path:
            if not os.path.exists(csv_path):
                raise CommandError(f"CSV niet gevonden: {csv_path}")
            items = self._load_csv(csv_path)
            self.stdout.write(self.style.WARNING(f"CSV geladen ({len(items)}) uit {csv_path}"))
        else:
            items = DEFAULT_ITEMS
            self.stdout.write(self.style.WARNING(f"Gebruik ingebouwde defaults ({len(items)} items)."))

        created, updated, skipped = 0, 0, 0

        with transaction.atomic():
            for raw in items:
                code = raw["code"].strip()
                defaults = dict(
                    description=raw.get("description","").strip(),
                    vat_rate=int(raw.get("vat_rate",21)),
                    unit_price=Decimal(str(raw.get("unit_price","0.00"))),
                    active=True,
                    billing_strategy=raw.get("billing_strategy","FIXED_SELF"),
                    rule_params=raw.get("rule_params",{}) or {},
                )
                obj, exists = YearPricing.objects.get_or_create(year=year, code=code, defaults=defaults)
                if exists:
                    created += 1
                else:
                    if force:
                        for k,v in defaults.items():
                            setattr(obj, k, v)
                        obj.save(update_fields=list(defaults.keys()))
                        updated += 1
                    else:
                        skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f"Done for {year}: created={created}, updated={updated}, skipped={skipped}"
        ))

    def _load_csv(self, path):
        items = []
        with open(path, newline='', encoding="utf-8") as f:
            rd = csv.DictReader(f)
            for r in rd:
                rule = r.get("rule_params","").strip()
                try:
                    rule_params = json.loads(rule) if rule else {}
                except json.JSONDecodeError:
                    raise CommandError(f"rule_params is geen geldige JSON voor code {r.get('code')}: {rule}")
                items.append(dict(
                    code=(r.get("code") or "").strip(),
                    description=(r.get("description") or "").strip(),
                    vat_rate=int(r.get("vat_rate") or 21),
                    unit_price=str(r.get("unit_price") or "0.00"),
                    billing_strategy=(r.get("billing_strategy") or "FIXED_SELF").strip(),
                    rule_params=rule_params,
                ))
        return items
