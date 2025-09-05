
from django.core.management.base import BaseCommand
from django.apps import apps
from django.db import transaction
import csv, re
from datetime import datetime, date

Member = apps.get_model('core','Member')

def pick(row, *names):
    for n in names:
        if n in row and (row[n] or "").strip():
            return row[n].strip()
    return ""

def normalize_course(val):
    s = (val or "").strip()
    if not s:
        return None  # geen wijziging
    s_low  = s.lower()
    if s_low in {"null","none","-", "geen"}:
        return ""  # leegmaken
    s_flat = re.sub(r"[.\s]", "", s).upper()  # bv. "P 3" -> "P3"
    if s_flat in {"CC","P3"}:
        return s_flat
    return None  # onbekende waarde => geen wijziging

class Command(BaseCommand):
    help = "Update Member.course vanuit CSV. Verwacht kolommen: external_id, course"

    def add_arguments(self, parser):
        parser.add_argument("csv_path")
        parser.add_argument("--dry-run", action="store_true")

    @transaction.atomic
    def handle(self, csv_path, dry_run=False, **opts):
        # CSV lezen met delimiter-detectie
        with open(csv_path, "r", encoding="utf-8-sig", newline="") as fh:
            sample = fh.read(4096); fh.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=";,")
                delim = dialect.delimiter
            except Exception:
                delim = ","
            reader = csv.DictReader(fh, delimiter=delim)
            rows = list(reader)
        self.stdout.write(f"CSV delimiter: {repr(delim)}")

        updated = skipped = missing = badval = 0

        for idx, row in enumerate(rows, start=2):
            eid = pick(row, "external_id", "member_external_id")
            if not eid:
                missing += 1
                self.stderr.write(f"Rij {idx}: geen external_id.")
                continue

            try:
                m = Member.objects.get(external_id=eid)
            except Member.DoesNotExist:
                missing += 1
                self.stderr.write(f"Rij {idx}: geen member voor external_id={eid}.")
                continue
            except Member.MultipleObjectsReturned:
                missing += 1
                self.stderr.write(f"Rij {idx}: meerdere members voor external_id={eid}.")
                continue

            new_course = normalize_course(pick(row, "course"))
            if new_course is None:
                badval += 1
                self.stderr.write(f"Rij {idx}: onbekende/lege course-waarde {row.get('course')!r}, overslaan.")
                continue

            cur = (m.course or "")
            if new_course != cur:
                if dry_run:
                    updated += 1
                else:
                    m.course = new_course
                    # leeg veld consistent als None i.p.v. lege string?
                    if m.course == "":
                        m.course = None
                    m.save(update_fields=["course"])
                    updated += 1
            else:
                skipped += 1

        self.stdout.write(
            f"Courses import: updated={updated}, skipped={skipped}, missing_member={missing}, bad_value={badval}"
        )
