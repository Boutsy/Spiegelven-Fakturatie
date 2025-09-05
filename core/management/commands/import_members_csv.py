from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.apps import apps
import csv, re
from datetime import datetime, date

Member = apps.get_model('core','Member')

def has_field(model,name):
    try:
        model._meta.get_field(name); return True
    except Exception:
        return False

def parse_bool(val):
    s = (val or '').strip().lower()
    return s in ('1','true','t','yes','y','ja','waar','active','actief')

def parse_date(s):
    s = (s or '').strip()
    if not s:
        return None
    for fmt in ('%Y-%m-%d','%d-%m-%Y','%d/%m/%Y','%Y/%m/%d','%d.%m.%Y'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    m = re.match(r'^(\d{1,2})[./-](\d{1,2})[./-](\d{4})$', s)
    if m:
        d,mn,y = m.groups()
        return date(int(y), int(mn), int(d))
    raise ValueError(f"Onbekende datum '{s}'")

def split_external(eid):
    m = re.match(r'^\s*(\d+)\s*/\s*(\d+)\s*$', str(eid or ''))
    if not m:
        return None, None
    return m.group(1), int(m.group(2))

class Command(BaseCommand):
    help = "Importeer leden uit CSV en link gezinnen via external_id 'HHHH/seq'."

    def add_arguments(self, parser):
        parser.add_argument('csv_path')
        parser.add_argument('--update', action='store_true', help='Update bestaande leden (matching external_id)')
        parser.add_argument('--dry-run', action='store_true')

    @transaction.atomic
    def handle(self, csv_path, update=False, dry_run=False, **opts):
        # --- delimiter auto-detect (comma of semicolon) ---
        with open(csv_path, newline='', encoding='utf-8-sig') as fh:
            sample = fh.read(4096)
            fh.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=';,')
                delim = dialect.delimiter
            except Exception:
                delim = ','
            reader = csv.DictReader(fh, delimiter=delim)

            required = ['external_id','couple_status','first_name','last_name',
                        'street','postal_code','city','country','birth_date',
                        'course','active','email','phone_mobile','phone_private','phone_work']
            missing = [c for c in required if c not in (reader.fieldnames or [])]
            if missing:
                raise CommandError(f'CSV mist kolommen: {missing}')
            rows = list(reader)
        self.stdout.write(f'CSV delimiter gedetecteerd: {repr(delim)}')

        created = updated = skipped = errors = 0
        objs = []
        head_map = {}

        for idx, row in enumerate(rows, start=2):
            eid = (row.get('external_id') or '').strip()
            hh, seq = split_external(eid)
            if not hh or not seq:
                self.stderr.write(f'Rij {idx}: ongeldige external_id "{eid}", overslaan.')
                errors += 1
                continue

            exists = False
            if has_field(Member, 'external_id'):
                try:
                    m = Member.objects.get(external_id=eid)
                    exists = True
                except Member.DoesNotExist:
                    m = Member()
            else:
                m = Member()

            # Basisgegevens
            if has_field(Member, 'external_id'):
                m.external_id = eid
            m.first_name = (row.get('first_name') or '').strip()
            m.last_name  = (row.get('last_name')  or '').strip()
            m.street     = (row.get('street')     or '').strip()
            m.postal_code= (row.get('postal_code')or '').strip()
            m.city       = (row.get('city')       or '').strip()
            m.country    = (row.get('country')    or '').strip() or 'BE'
            try:
                bd = parse_date(row.get('birth_date'))
            except Exception as e:
                bd = None
                self.stderr.write(f'Rij {idx}: birth_date fout "{row.get("birth_date")}": {e}')
            if bd is not None and has_field(Member,'birth_date'):
                m.birth_date = bd

            if has_field(Member,'email'):
                m.email = (row.get('email') or '').strip()
            if has_field(Member,'phone_mobile'):
                m.phone_mobile = (row.get('phone_mobile') or '').strip()
            if has_field(Member,'phone_private'):
                m.phone_private = (row.get('phone_private') or '').strip()
            if has_field(Member,'phone_work'):
                m.phone_work = (row.get('phone_work') or '').strip()

            course = (row.get('course') or '').strip().upper()
            if course in ('CC','P3') and has_field(Member,'course'):
                m.course = course

            if has_field(Member,'active'):
                m.active = parse_bool(row.get('active'))

            couple = ((row.get('couple_status') or '').strip().lower() == 'koppel')
            role = 'head' if seq == 1 else ('partner' if (seq == 2 and couple) else 'member')
            if has_field(Member,'household_role'):
                m.household_role = role

            if dry_run:
                skipped += 1
                continue

            m.save()
            objs.append((hh, seq, m))
            if seq == 1:
                head_map[hh] = m
            if exists:
                updated += 1
            else:
                created += 1

        # Tweede fase: household_head koppelen
        if has_field(Member,'household_head'):
            for hh, seq, m in objs:
                if seq != 1:
                    head = head_map.get(hh)
                    if head and getattr(m, 'household_head_id', None) != head.id:
                        m.household_head = head
                        m.save(update_fields=['household_head'])

        self.stdout.write(self.style.SUCCESS(
            f'Import klaar. Aangemaakt: {created}, Bijgewerkt: {updated}, Dry-run overslagen: {skipped}, Fouten: {errors}, Huishoudens: {len(head_map)}'
        ))
