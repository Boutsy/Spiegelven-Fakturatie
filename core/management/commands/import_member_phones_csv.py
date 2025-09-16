import csv
from typing import Optional, List
from django.core.management.base import BaseCommand, CommandError
from django.apps import apps
from django.db import transaction

EXTERNAL_ID_FIELDS_CANDIDATES = [
    "external_id","externalid","external_member_id","legacy_id","old_id","ext_id","member_external_id",
]

PHONE_HEADER_CANDIDATES  = ["telefoon privaat","telefoon_prive","telefoon prive","phone","telephone","tel","vast","telefoon"]
MOBILE_HEADER_CANDIDATES = ["telefoon auto","gsm","mobile","mobile phone","cellphone","mobile_number","mobile telefoon","mobiel"]

class Command(BaseCommand):
    help = "Importeer phone/mobile van CSV via external id. Voorbeeld: manage.py import_member_phones_csv /app/import/leden.csv [--dry-run]"

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str, help="Pad naar CSV (bv. /app/import/leden.csv)")
        parser.add_argument("--dry-run", action="store_true", help="Toon wat er zou gebeuren, zonder te schrijven.")

    def handle(self, *args, **opts):
        csv_path = opts["csv_path"]
        dry = opts["dry_run"]
        Member = apps.get_model("core","Member")

        # bepaal welk Member-veld je external id is
        member_fields = {f.name for f in Member._meta.get_fields() if getattr(f, "concrete", False)}
        ext_field = next((f for f in EXTERNAL_ID_FIELDS_CANDIDATES if f in member_fields), None)
        if not ext_field:
            raise CommandError(f"Geen external-id veld gevonden op Member. Geprobeerd: {EXTERNAL_ID_FIELDS_CANDIDATES}")

        self.stdout.write(self.style.NOTICE(f"Zoek Member via external-id veld: {ext_field}"))

        # CSV lezen
        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            # normaliseer headers
            headers = [h.strip() for h in reader.fieldnames or []]
            lowmap = {h.lower(): h for h in headers}

            def pick_header(cands: List[str]) -> Optional[str]:
                for c in cands:
                    if c in lowmap:
                        return lowmap[c]
                # probeer ook cands zonder accenten e.d.
                normalized = {h.lower().replace("é","e").replace("ï","i").replace("  "," ").strip(): h for h in headers}
                for c in cands:
                    cc = c.replace("é","e").replace("ï","i").strip()
                    if cc in normalized:
                        return normalized[cc]
                return None

            # external id kolom bepalen (probeer direct en met varianten)
            ext_header = pick_header([ext_field] + EXTERNAL_ID_FIELDS_CANDIDATES + ["external id","extern id","member id"])
            if not ext_header:
                raise CommandError(f"Kon geen external-id kolom vinden in CSV. Headers: {headers}")

            phone_header  = pick_header(PHONE_HEADER_CANDIDATES)
            mobile_header = pick_header(MOBILE_HEADER_CANDIDATES)

            if not phone_header and not mobile_header:
                raise CommandError(
                    f"Geen phone/mobile kolommen gevonden. Geprobeerd:\n"
                    f"  phone-kandidaten: {PHONE_HEADER_CANDIDATES}\n"
                    f"  mobile-kandidaten: {MOBILE_HEADER_CANDIDATES}\n"
                    f"CSV headers: {headers}"
                )

            self.stdout.write(self.style.NOTICE(f"CSV mapping: external-id='{ext_header}', "
                                                f"phone='{phone_header}', mobile='{mobile_header}'"))

            updated = 0
            missing = 0
            notfound = 0
            total = 0

            @transaction.atomic
            def do_row(row):
                nonlocal updated, missing, notfound, total
                total += 1
                ext_val = (row.get(ext_header) or "").strip()
                if not ext_val:
                    missing += 1
                    return

                try:
                    m = Member.objects.get(**{ext_field: ext_val})
                except Member.DoesNotExist:
                    notfound += 1
                    return
                except Member.MultipleObjectsReturned:
                    self.stderr.write(self.style.WARNING(f"Meerdere Members met {ext_field}={ext_val} – skip."))
                    return

                phone_val  = (row.get(phone_header) or "").strip() if phone_header else ""
                mobile_val = (row.get(mobile_header) or "").strip() if mobile_header else ""

                changed = False
                if phone_val and (getattr(m, "phone", None) or "") != phone_val:
                    m.phone = phone_val
                    changed = True
                if mobile_val and (getattr(m, "mobile", None) or "") != mobile_val:
                    m.mobile = mobile_val
                    changed = True

                if changed and not dry:
                    m.save(update_fields=[f for f,v in [("phone",phone_val),("mobile",mobile_val)] if v])
                    updated += 1
                elif changed and dry:
                    updated += 1  # tellen als “zou bijwerken”

            # Loop over alle rijen
            for row in reader:
                do_row(row)

            mode = "(DRY-RUN)" if dry else ""
            self.stdout.write(self.style.SUCCESS(
                f"Import klaar {mode}: totaal={total}, zonder ext-id={missing}, member niet gevonden={notfound}, bijgewerkt={updated}"
            ))
