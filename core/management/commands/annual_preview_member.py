from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from core.models import Member, MemberAsset, YearRule
from datetime import date

def age_on_year(dob, year):
    if not dob:
        return None
    # Leeftijd op 1 januari van het jaar
    ref = date(year, 1, 1)
    a = ref.year - dob.year - ((ref.month, ref.day) < (dob.month, dob.day))
    return a

def resolve_bill_to(member, bill_to):
    if bill_to in (None, "", "self"):
        return ("self", member)
    # household_head: FK naar hoofd; als None => dit lid is het hoofd
    head = member if member.household_head_id is None else member.household_head
    if bill_to in ("head", "head_or_self"):
        return ("head" if head and head.id != member.id else "self", head or member)
    return ("self", member)

def rule_match(member, data, year):
    """Zachte evaluatie van voorwaarden → (match_bool, notes[])."""
    notes = []
    match = True

    # leeftijdsvoorwaarden
    a = age_on_year(getattr(member, "date_of_birth", None), year)
    if "age_min" in data and a is not None and a < int(data["age_min"]):
        match = False; notes.append(f"leeftijd {a} < min {data[age_min]}")
    if "age_max" in data and a is not None and a > int(data["age_max"]):
        match = False; notes.append(f"leeftijd {a} > max {data[age_max]}")
    if a is None and any(k in data for k in ("age_min","age_max")):
        notes.append("leeftijd onbekend (kan invloed hebben)")

    # membership_mode (flex/invest)
    mode_req = data.get("mode")
    if mode_req:
        actual = getattr(member, "membership_mode", None)
        if actual and actual != mode_req:
            match = False; notes.append(f"mode={actual} <> vereist={mode_req}")
        elif not actual:
            notes.append("membership_mode onbekend")

    # rol (algemeen)
    role_req = data.get("role")
    if role_req:
        actual = getattr(member, "household_role", None)
        if actual != role_req:
            match = False; notes.append(f"role={actual} <> vereist={role_req}")

    # course (let op: veld bestaat (nog) niet in model)
 (let op: veld bestaat (nog) niet in model)
    course_req = data.get("course")
    if course_req:
        actual = getattr(member, "course", None)  # bestaat mogelijk niet
        if actual and actual != course_req:
            match = False; notes.append(f"course={actual} <> vereist={course_req}")
        elif actual is None:
            notes.append("course ontbreekt in ledenmodel (kan invloed hebben)")

    # assets
    req_asset = data.get("requires_asset")
    if req_asset:
        has = MemberAsset.objects.filter(member=member, asset_type=req_asset, active=True, released_on__isnull=True).exists()
        if not has:
            match = False; notes.append(f"benodigde asset ontbreekt: {req_asset}")

    return match, notes

class Command(BaseCommand):
    help = "Toon (dry-run) welke regels voor een lid zouden gelden en op wiens factuur (self/head)."

    def add_arguments(self, parser):
        parser.add_argument("--member-id", type=int, help="ID van het lid")
        parser.add_argument("--email", help="E-mail van het lid (alternatief)")
        parser.add_argument("--year", type=int, default=timezone.now().year, help="Jaar (default: huidig)")

    def handle(self, *args, **opts):
        year = int(opts["year"])
        mid  = opts.get("member_id")
        email= opts.get("email")

        if not mid and not email:
            raise CommandError("Geef --member-id of --email.")

        try:
            if mid:
                member = Member.objects.get(id=mid)
            else:
                member = Member.objects.get(email=email)
        except Member.DoesNotExist:
            raise CommandError("Lid niet gevonden.")

        # Basisinfo
        self.stdout.write(self.style.MIGRATE_HEADING(f"Preview {year} voor lid #{member.id}: {member}"))
        self.stdout.write(f" - household_role: {getattr(member, 'household_role', '')}")
        self.stdout.write(f" - membership_mode: {getattr(member, 'membership_mode', '')}")
        self.stdout.write(f" - geboortedatum: {getattr(member, 'date_of_birth', None)}  (leeftijd@{year}: {age_on_year(getattr(member, 'date_of_birth', None), year)})")

        # Assets overzicht
        assets = list(MemberAsset.objects.filter(member=member, active=True, released_on__isnull=True)
                      .values_list("asset_type","identifier"))
        if assets:
            self.stdout.write(" - actieve assets: " + ", ".join(f"{t}:{(i or '-')}" for t,i in assets))
        else:
            self.stdout.write(" - actieve assets: (geen)")

        # Regels
        self.stdout.write(self.style.MIGRATE_LABEL("Regels (op volgorde):"))
        for r in YearRule.objects.filter(year=year).order_by("order","code"):
            data = r.data or {}
            bill_to_key = data.get("bill_to") or "self"
            bill_as, billed_person = resolve_bill_to(member, bill_to_key)
            m, notes = rule_match(member, data, year)
            status = "MATCH" if (m and r.active) else ("—" if r.active else "INACTIEF")
            self.stdout.write(f"  [{status:8}] order={r.order:02d} code={r.code} bill_to={bill_as}({billed_person.id}) data={data}")
            if notes:
                self.stdout.write("           notes: " + "; ".join(notes))
