from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, List

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import YearPricing, YearRule


@dataclass
class RuleTemplate:
    order: int
    condition: Dict
    action: str
    data: Dict


def _age_cond(min_age=None, max_age=None):
    parts = []
    if min_age is not None:
        parts.append({"field": "member.age_on_jan1", "op": ">=", "value": int(min_age)})
    if max_age is not None:
        parts.append({"field": "member.age_on_jan1", "op": "<=", "value": int(max_age)})
    return {"all": parts} if parts else {}


def _eq(field, val):
    return {"field": field, "op": "eq", "value": val}


def _all(*conds):
    items = [c for c in conds if c]
    return {"all": items} if items else {}


def _asset(type_name):
    return {"func": "has_asset", "args": [type_name]}


def _base_line(pr: YearPricing, bill_to: str):
    return {
        "type": "add_line",
        "code": pr.code,
        "description": pr.description or pr.code,
        "unit_price_excl": str(pr.amount),
        "vat_rate": int(pr.vat_rate),
        "quantity": 1,
        "bill_to": bill_to,  # 'self' of 'household'
    }


def templates_for(pr: YearPricing) -> List[RuleTemplate]:
    """
    Bouw rule-templates per prijs-code. Onbekende codes krijgen een veilige 'fallback'
    die je nadien kan uitschakelen of verfijnen in de admin.
    """
    code = (pr.code or "").upper().strip()

    # --- CC lidmaatschap (individueel/partner/kind/young adult) ---
    if code == "LID_IND_CC":
        cond = _all(_age_cond(min_age=36), _eq("member.role", "individueel"))
        return [RuleTemplate(10, cond, "add_line", _base_line(pr, "self"))]

    if code == "LID_PRT_CC":
        cond = _all(_age_cond(min_age=36), _eq("member.role", "partner"))
        return [RuleTemplate(10, cond, "add_line", _base_line(pr, "household"))]

    if code == "KID_0-15":
        cond = _all(_age_cond(max_age=15), _eq("member.role", "child"))
        return [RuleTemplate(10, cond, "add_line", _base_line(pr, "household"))]

    if code == "KID_16-21":
        cond = _all(_age_cond(min_age=16, max_age=21), _eq("member.role", "child"))
        return [RuleTemplate(10, cond, "add_line", _base_line(pr, "household"))]

    if code == "YA_22_26":
        cond = _all(_age_cond(min_age=22, max_age=26))
        return [RuleTemplate(10, cond, "add_line", _base_line(pr, "household"))]

    if code == "YA_27_29":
        cond = _all(_age_cond(min_age=27, max_age=29))
        return [RuleTemplate(10, cond, "add_line", _base_line(pr, "household"))]

    if code == "YA_30_35":
        cond = _all(_age_cond(min_age=30, max_age=35))
        return [RuleTemplate(10, cond, "add_line", _base_line(pr, "household"))]

    # --- P3 lidmaatschap ---
    if code == "LID_IND_P3":
        cond = _all(_eq("member.role", "individueel"))
        return [RuleTemplate(10, cond, "add_line", _base_line(pr, "self"))]

    if code == "LID_P3_PRT":
        cond = _all(_eq("member.role", "partner"))
        return [RuleTemplate(10, cond, "add_line", _base_line(pr, "household"))]

    if code == "LID_P3-21":
        cond = _all(_age_cond(max_age=21))
        return [RuleTemplate(10, cond, "add_line", _base_line(pr, "household"))]

    # --- Investering vs Flex (alleen CC) ---
    if code == "INV_IND":
        cond = _all(_eq("member.membership_mode", "investment"), _eq("member.role", "individueel"))
        return [RuleTemplate(20, cond, "add_line", _base_line(pr, "self"))]

    if code == "INV_PRT":
        cond = _all(_eq("member.membership_mode", "investment"), _eq("member.role", "partner"))
        return [RuleTemplate(20, cond, "add_line", _base_line(pr, "household"))]

    if code == "INV_FLX_IND":
        cond = _all(_eq("member.membership_mode", "flex"), _eq("member.role", "individueel"))
        return [RuleTemplate(20, cond, "add_line", _base_line(pr, "self"))]

    if code == "INV_FLX_PRT":
        cond = _all(_eq("member.membership_mode", "flex"), _eq("member.role", "partner"))
        return [RuleTemplate(20, cond, "add_line", _base_line(pr, "household"))]

    # --- Federatiebijdrage ---
    if code == "FED__JGD":  # t/m 20 jaar
        cond = _all(_age_cond(max_age=20))
        return [RuleTemplate(30, cond, "add_line", _base_line(pr, "household"))]

    if code == "FED_VOLW":  # vanaf 21 jaar
        cond = _all(_age_cond(min_age=21))
        return [RuleTemplate(30, cond, "add_line", _base_line(pr, "household"))]

    # --- Assets (kasten/karren) ---
    if code == "VST_KAST":
        cond = {"all": [_asset("locker")]}
        data = _base_line(pr, "household")
        data["note_from_asset_field"] = "identifier"
        return [RuleTemplate(40, cond, "add_line", data)]

    if code == "KAR_KLN":
        cond = {"all": [_asset("trolley_locker")]}
        data = _base_line(pr, "household")
        data["note_from_asset_field"] = "identifier"
        return [RuleTemplate(40, cond, "add_line", data)]

    if code == "KAR_ELEC":
        cond = {"all": [_asset("e_trolley_locker")]}
        data = _base_line(pr, "household")
        data["note_from_asset_field"] = "identifier"
        return [RuleTemplate(40, cond, "add_line", data)]

    # — fallback voor onbekende codes —
    generic = RuleTemplate(
        90,
        {"all": []},  # altijd waar
        "add_line",
        {**_base_line(pr, "self"), "is_generic": True},
    )
    return [generic]


class Command(BaseCommand):
    help = "Maak Jaarregels (YearRule) op basis van Jaarprijzen (YearPricing) voor een jaar."

    def add_arguments(self, parser):
        parser.add_argument("--year", type=int, required=True)
        parser.add_argument("--apply", action="store_true", help="Voer effectief uit (anders enkel tonen).")
        parser.add_argument("--replace", action="store_true", help="Verwijder eerst bestaande regels voor dit jaar.")

    def handle(self, *args, **opts):
        year = opts["year"]
        do_apply = opts["apply"]
        do_replace = opts["replace"]

        prices = list(YearPricing.objects.filter(year=year, active=True).order_by("code"))
        if not prices:
            raise CommandError(f"Geen YearPricing records gevonden voor {year}.")

        plan: List[RuleTemplate] = []
        for pr in prices:
            # jouw vraag: 'Lidgeld CC Normaal' negeren
            if (pr.code or "").upper().strip() in {"LID_CC_NORM", "LID_CC_NORMAAL"}:
                continue
            plan.extend(templates_for(pr))

        self.stdout.write(self.style.NOTICE(f"Plan voor {year}: {len(plan)} rules (uit {len(prices)} prijzen)."))

        for rt in plan[:30]:
            self.stdout.write(
                f" - {rt.order:02d} · {rt.action} · code={rt.data.get('code')} · bill_to={rt.data.get('bill_to')} · cond={json.dumps(rt.condition)}"
            )
        if len(plan) > 30:
            self.stdout.write(f"   … ({len(plan)-30} extra regels niet getoond)")

        if not do_apply:
            self.stdout.write(self.style.WARNING("Dry-run: geen wijzigingen toegepast. Gebruik --apply om te schrijven."))
            return

        with transaction.atomic():
            if do_replace:
                YearRule.objects.filter(year=year).delete()

            for rt in plan:
                obj, created = YearRule.objects.get_or_create(
                    year=year,
                    code=rt.data.get("code", ""),
                    order=rt.order,
                    defaults={
                        "active": True,
                        "condition": json.dumps(rt.condition, ensure_ascii=False),
                        "action": rt.action,
                        "data": rt.data,
                    },
                )
                if not created:
                    obj.active = True
                    obj.condition = json.dumps(rt.condition, ensure_ascii=False)
                    obj.action = rt.action
                    obj.data = rt.data
                    obj.save(update_fields=["active", "condition", "action", "data"])

        self.stdout.write(self.style.SUCCESS(f"Geschreven: {len(plan)} regels voor {year}."))