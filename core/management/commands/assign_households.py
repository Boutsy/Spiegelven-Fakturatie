from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.apps import apps
import re

def _get_member_model():
    return apps.get_model("core", "Member")

def _parse_external_id(extid):
    # verwacht vorm PREFIX/SUFFIX (suffix = 1..9)
    if not extid or "/" not in str(extid):
        return None, None
    p, s = str(extid).split("/", 1)
    s = s.strip()
    if not p.strip():
        return None, None
    return p.strip(), s

def _birth_year(member):
    for name in ("birth_date","date_of_birth","dob","birthday"):
        if hasattr(member, name):
            val = getattr(member, name)
            if val:
                try:
                    return val.year
                except Exception:
                    pass
    return None

def _age_in_year(member, year):
    by = _birth_year(member)
    if by is None:
        return None
    # leeftijd op 31/12 van het gegeven jaar
    return year - by

def _role_key_for_label(field, label_nl):
    # zoek in choices de key die bij het NL label hoort
    lab = label_nl.lower()
    for key, lbl in getattr(field, "choices", []) or []:
        if str(lbl).lower() == lab:
            return key
    # fallback: probeer bekende keys
    fallback = {
        "Gezinshoofd": "head",
        "Partner": "partner",
        "Kind": "child",
        "Individueel": "individual",
        "Overig": "other",
    }.get(label_nl)
    return fallback

class Command(BaseCommand):
    help = "Zet Factureren via en household_role op basis van external_id en leeftijdsregels."

    def add_arguments(self, parser):
        parser.add_argument("--year", type=int, default=timezone.now().year, help="Factuurjaar voor leeftijdsberekening (default = huidig jaar).")
        parser.add_argument("--apply", action="store_true", help="Zonder deze vlag is het een dry-run (enkel tonen wat zou wijzigen).")

    @transaction.atomic
    def handle(self, *args, **opts):
        year = opts["year"]
        do_apply = opts["apply"]

        M = _get_member_model()
        # veldnamen ophalen
        try:
            fact_fk = M._meta.get_field("factureren_via")
        except Exception:
            self.stderr.write("factureren_via veld niet gevonden op Member.")
            return

        try:
            role_field = M._meta.get_field("household_role")
        except Exception:
            self.stderr.write("household_role veld niet gevonden op Member.")
            return

        # keys per label bepalen (veilig vs choices)
        key_head = _role_key_for_label(role_field, "Gezinshoofd") or "head"
        key_partner = _role_key_for_label(role_field, "Partner") or "partner"
        key_child = _role_key_for_label(role_field, "Kind") or "child"
        key_individual = _role_key_for_label(role_field, "Individueel") or _role_key_for_label(role_field, "Overig") or "other"
        key_other = _role_key_for_label(role_field, "Overig") or "other"

        # alle leden ophalen met external_id
        qs_all = M.objects.all().only("id","external_id")
        groups = {}
        for m in qs_all:
            pfx, sfx = _parse_external_id(getattr(m, "external_id", None))
            if pfx is None:
                continue
            groups.setdefault(pfx, []).append((sfx, m))

        changed_fk = 0
        changed_role = 0

        for pfx, items in groups.items():
            # map op suffix, en hoofd zoeken
            by_sfx = {}
            for sfx, m in items:
                by_sfx.setdefault(sfx, []).append(m)
            head = by_sfx.get("1", [None])[0]

            # single-case: slechts één item én geen andere met zelfde prefix
            if len(items) == 1:
                sfx, member = items[0]
                # geen gezin, dus individueel
                new_role = key_individual
                if getattr(member, "household_role", None) != new_role:
                    if do_apply:
                        setattr(member, "household_role", new_role)
                        member.save(update_fields=["household_role"])
                    changed_role += 1
                # factureren_via leegmaken indien gevuld
                if getattr(member, "factureren_via_id", None):
                    if do_apply:
                        setattr(member, "factureren_via", None)
                        member.save(update_fields=["factureren_via"])
                    changed_fk += 1
                continue

            # er zijn meerdere in het huishouden
            if head:
                # zet head rol
                if getattr(head, "household_role", None) != key_head:
                    if do_apply:
                        setattr(head, "household_role", key_head)
                        head.save(update_fields=["household_role"])
                    changed_role += 1

            for sfx, m in items:
                # sla head zelf over voor fk-koppeling
                if sfx in [str(i) for i in range(2, 10)] and head:
                    # factureren via head
                    if getattr(m, "factureren_via_id", None) != head.id:
                        if do_apply:
                            setattr(m, "factureren_via", head)
                            m.save(update_fields=["factureren_via"])
                        changed_fk += 1

                # rol bepalen
                new_role = None
                if sfx == "1":
                    new_role = key_head if head else key_other
                elif sfx == "2" and head:
                    # partner of kind op basis van leeftijd
                    age = _age_in_year(m, year)
                    if age is not None and age < 36:
                        new_role = key_child
                    else:
                        new_role = key_partner
                else:
                    # 3..9
                    age = _age_in_year(m, year)
                    if age is not None and age < 36:
                        new_role = key_child
                    else:
                        # ouder gezinslid dat geen partner is -> other
                        new_role = key_other

                if new_role and getattr(m, "household_role", None) != new_role:
                    if do_apply:
                        setattr(m, "household_role", new_role)
                        m.save(update_fields=["household_role"])
                    changed_role += 1

        self.stdout.write(f"Year={year} dry_run={not do_apply} updated_fk={changed_fk} updated_roles={changed_role}")
        if not do_apply:
            transaction.set_rollback(True)
