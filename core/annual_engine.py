from __future__ import annotations
import datetime
from decimal import Decimal
from typing import Dict, List, Tuple
from django.db import transaction
from .models import Member, MemberAsset, Invoice, InvoiceLine, YearPricing, YearRule, InvoiceAccount

ALIASES = {'KAE_KLN': 'KAR_KLN'}  # oude -> nieuwe code

def _price_code(code: str) -> str:
    return ALIASES.get(code, code)

def _find_household_head(member: Member) -> Member | None:
    # 1) factuur op gezinshoofd; zoniet lid zelf
    if member.household_id and getattr(member.household, "head_id", None):
        return member.household.head
    if getattr(member, "household_head_id", None):
        return member.household_head
    return member

def _preferred_account(member: Member) -> InvoiceAccount | None:
    # factureer bij voorkeur op Household.account; anders op member.billing_account
    if member.household_id and getattr(member.household, "account_id", None):
        return member.household.account
    return member.billing_account

def _ensure_draft_invoice(year: int, target_member: Member) -> Invoice:
    inv = Invoice.objects.filter(
        member=target_member, issue_date__year=year, status=Invoice.STATUS_DRAFT
    ).first()
    if inv:
        return inv
    inv = Invoice(
        member=target_member,
        household=getattr(target_member, "household", None),
        account=_preferred_account(target_member),
        issue_date=datetime.date(year, 1, 1),
        status=Invoice.STATUS_DRAFT,
    )
    inv.save()
    return inv

def _line_desc(template: str, asset: MemberAsset) -> str:
    # 5) nummer in omschrijving
    ident = (asset.identifier or "").strip()
    return (template or "").replace("{asset_identifier}", ident).strip()

def _add_line(year: int, invoice: Invoice, code: str, description: str, quantity: Decimal = Decimal("1")) -> InvoiceLine:
    code = _price_code(code)  # alias toepassen
    pricing = YearPricing.objects.filter(year=year, code=code, active=True).first()
    if not pricing:
        raise ValueError(f"Geen YearPricing voor {year}/{code}")
    return InvoiceLine.objects.create(
        invoice=invoice,
        product=None,
        description=description,
        quantity=quantity,
        unit_price_excl=pricing.amount,              # 3) leeftijd speelt geen rol
        vat_rate=Decimal(str(pricing.vat_rate)),
    )

def build_asset_rule_index(year: int) -> Dict[str, dict]:
    """
    Lees YearRule.data en bouw index per asset_type.
    data per regel verwacht:
    {
      "asset_type": "locker" | "trolley_locker" | "e_trolley_locker",
      "price_code": "VST_KAST" | "KAR_KLN" | "KAR_ELEC",
      "description": "Vestiaire kast {asset_identifier}",
      "bill_to": "head" | "self",
      "quantity": 1
    }
    """
    idx: Dict[str, dict] = {}
    for r in YearRule.objects.filter(year=year, active=True):
        data = r.data or {}
        at = data.get("asset_type")
        pc = data.get("price_code") or r.code
        if not at or not pc:
            continue
        idx[at] = {
            "price_code": pc,
            "description": data.get("description") or r.code,
            "bill_to": (data.get("bill_to") or "head"),
            "quantity": Decimal(str(data.get("quantity", 1))),
        }
    return idx

def iter_member_assets_for_year(year: int):
    # 4) aanrekenen als asset bestaat voor dit jaar en actief is
    return MemberAsset.objects.select_related("member", "member__household").filter(
        active=True, year=year
    )

def simulate_assets(year: int) -> List[Tuple[str, str, str, str]]:
    """ Voorbeeldresultaten zonder te schrijven """
    idx = build_asset_rule_index(year)
    rows: List[Tuple[str, str, str, str]] = []
    for asset in iter_member_assets_for_year(year):
        rule = idx.get(asset.asset_type)
        if not rule:
            continue
        target = _find_household_head(asset.member) if rule["bill_to"] == "head" else asset.member
        desc = _line_desc(rule["description"], asset)
        rows.append((f"{asset.member}", asset.asset_type, rule["price_code"], f"{desc} → factuur: {target}"))
    return rows

@transaction.atomic
def apply_assets(year: int) -> int:
    """ Schrijf factuurlijnen weg (conceptfacturen). Retourneert aantal regels. """
    idx = build_asset_rule_index(year)
    count = 0
    for asset in iter_member_assets_for_year(year):
        rule = idx.get(asset.asset_type)
        if not rule:
            continue
        target = _find_household_head(asset.member) if rule["bill_to"] == "head" else asset.member
        inv = _ensure_draft_invoice(year, target)
        desc = _line_desc(rule["description"], asset)
        _add_line(year, inv, rule["price_code"], desc, rule["quantity"])
        count += 1
    return count
