from __future__ import annotations
from decimal import Decimal
from django.db import models
from django.utils import timezone

class OrganizationProfile(models.Model):
    PRINT_WITH_LOGO_FOOTER = "logo_footer"
    PRINT_PREPRINTED = "preprinted"
    PRINT_CHOICES = [
        (PRINT_WITH_LOGO_FOOTER, "Met logo & footer"),
        (PRINT_PREPRINTED, "Voorbedrukt papier"),
    ]
    name = models.CharField(max_length=200)
    address_line1 = models.CharField(max_length=200, blank=True)
    address_line2 = models.CharField(max_length=200, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default="Belgium", blank=True)
    iban = models.CharField(max_length=34, blank=True)
    bic = models.CharField(max_length=11, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    vat_number = models.CharField(max_length=20, blank=True)  # BTW
    enterprise_number = models.CharField(max_length=20, blank=True)
    default_print_mode = models.CharField(max_length=20, choices=PRINT_CHOICES, default=PRINT_WITH_LOGO_FOOTER)
    def __str__(self) -> str:
        return self.name

class InvoiceAccount(models.Model):
    TYPE_PERSON = "person"
    TYPE_COMPANY = "company"
    TYPE_CHOICES = [(TYPE_PERSON, "Particulier"), (TYPE_COMPANY, "Bedrijf")]
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_PERSON)
    name = models.CharField(max_length=200)
    vat_number = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    street = models.CharField(max_length=200, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default="Belgium", blank=True)
    def __str__(self) -> str:
        return self.name

class Household(models.Model):
    name = models.CharField(max_length=200, unique=True)
    head = models.ForeignKey("Member", related_name="headed_households", null=True, blank=True, on_delete=models.SET_NULL)
    account = models.ForeignKey(InvoiceAccount, null=True, blank=True, on_delete=models.SET_NULL,
                                help_text="Optioneel: factureren op deze account i.p.v. gezins-/ledennaam.")
    prefer_billing = models.BooleanField(default=True)
    def __str__(self) -> str:
        return self.name

class Member(models.Model):
    billing_account = models.ForeignKey('InvoiceAccount', null=True, blank=True, on_delete=models.SET_NULL, related_name='members_billed')
    household_head = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        related_name="household_members",
        on_delete=models.SET_NULL,
        help_text="Kies het gezinshoofd indien dit lid deel uitmaakt van een gezin."
    )
    ROLE_HEAD = "head"
    ROLE_PARTNER = "partner"
    ROLE_CHILD = "child"
    ROLE_OTHER = "other"
    ROLE_CHOICES = [(ROLE_HEAD,"Gezinshoofd"),(ROLE_PARTNER,"Partner"),(ROLE_CHILD,"Kind"),(ROLE_OTHER,"Overig")]
    MODE_INVEST = "investment"
    MODE_FLEX = "flex"
    MODE_CHOICES = [(MODE_INVEST,"Met investeringsbijdrage"),(MODE_FLEX,"Flexibel")]
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    email = models.EmailField(unique=False, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    street = models.CharField(max_length=200, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, default="Belgium", blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    membership_mode = models.CharField(max_length=20, choices=MODE_CHOICES, default=MODE_INVEST, blank=True)
    federation_via_club = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    household = models.ForeignKey(Household, null=True, blank=True, on_delete=models.SET_NULL)
    household_role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_OTHER, blank=True)
    def __str__(self) -> str:
        name = f"{self.first_name} {self.last_name}".strip()
        return name or f"Member #{self.pk}"
    @property
    def is_household_head(self):
        return self.household_head_id is None

class ImportMapping(models.Model):
    name = models.CharField(max_length=200, unique=True)
    model = models.CharField(max_length=100)  # b.v. "Member"
    mapping = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    def __str__(self) -> str:
        return f"{self.name} ({self.model})"

class MemberAsset(models.Model):
    active = models.BooleanField(default=True)
    assigned_on = models.DateField(null=True, blank=True)
    released_on = models.DateField(null=True, blank=True)
    ASSET_LOCKER = "locker"
    ASSET_TROLLEY = "trolley_locker"
    ASSET_E_TROLLEY = "e_trolley_locker"
    ASSET_CHOICES = [
        (ASSET_LOCKER, "Kast"),
        (ASSET_TROLLEY, "Kar-kast"),
        (ASSET_E_TROLLEY, "Elektrische kar-kast"),
    ]
    member = models.ForeignKey(Member, on_delete=models.CASCADE)
    asset_type = models.CharField(max_length=30, choices=ASSET_CHOICES)
    identifier = models.CharField(max_length=50, blank=True)
    year = models.PositiveIntegerField(default=timezone.now().year)
    price_excl = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    vat_rate = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("21.00"))
    def __str__(self) -> str:
        return f"{self.get_asset_type_display()} {self.identifier or ''}".strip()

class YearPlan(models.Model):
    year = models.PositiveIntegerField(unique=True)
    name = models.CharField(max_length=200, blank=True)
    membership_vat = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("6.00"))
    federation_vat = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("0.00"))
    def __str__(self) -> str:
        return f"{self.year} {self.name}".strip()

class YearPlanItem(models.Model):
    yearplan = models.ForeignKey(YearPlan, on_delete=models.CASCADE)
    code = models.CharField(max_length=40)
    description = models.CharField(max_length=200)
    price_excl = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    vat_rate = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("6.00"))
    class Meta:
        unique_together = ("yearplan", "code")
    def __str__(self) -> str:
        return f"{self.code} - {self.description}"

class Product(models.Model):
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=200)
    default_price_excl = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    default_vat_rate = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("21.00"))
    active = models.BooleanField(default=True)
    def __str__(self) -> str:
        return f"{self.code} - {self.name}"

class PricingRule(models.Model):
    ACTION_SET = "set"
    ACTION_ADD = "add"
    ACTION_MULTIPLY = "multiply"
    ACTION_CHOICES = [(ACTION_SET,"Zet prijs"),(ACTION_ADD,"Tel bij"),(ACTION_MULTIPLY,"Vermenigvuldig")]
    name = models.CharField(max_length=200)
    valid_from_year = models.PositiveIntegerField()
    valid_to_year = models.PositiveIntegerField(null=True, blank=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, default=ACTION_SET)
    value = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    priority = models.PositiveIntegerField(default=100)
    stackable = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    def __str__(self) -> str:
        return self.name

class YearSequence(models.Model):
    year = models.PositiveIntegerField(unique=True)
    last_number = models.PositiveIntegerField(default=0)
    def __str__(self) -> str:
        return f"{self.year} - {self.last_number}"

class Invoice(models.Model):
    TYPE_INVOICE = "INV"
    TYPE_CREDIT = "CN"
    DOC_TYPE_CHOICES = [(TYPE_INVOICE,"Factuur"),(TYPE_CREDIT,"Creditnota")]
    STATUS_DRAFT = "draft"
    STATUS_FINAL = "finalized"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [(STATUS_DRAFT,"Concept"),(STATUS_FINAL,"Gefinaliseerd"),(STATUS_CANCELLED,"Geannuleerd")]
    doc_type = models.CharField(max_length=3, choices=DOC_TYPE_CHOICES, default=TYPE_INVOICE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    issue_date = models.DateField(default=timezone.now)
    account = models.ForeignKey(InvoiceAccount, null=True, blank=True, on_delete=models.SET_NULL)
    household = models.ForeignKey(Household, null=True, blank=True, on_delete=models.SET_NULL)
    member = models.ForeignKey(Member, null=True, blank=True, on_delete=models.SET_NULL)
    number = models.CharField(max_length=20, unique=True, null=True, blank=True)  # 202500001
    payment_reference_raw = models.CharField(max_length=20, blank=True)  # 12 cijfers OGM
    notes = models.TextField(blank=True)
    def __str__(self) -> str:
        return self.number or f"{self.get_doc_type_display()} (concept)"
    @property
    def total_excl(self) -> Decimal:
        total = Decimal("0.00")
        for line in self.lines.all():
            total += (line.unit_price_excl * line.quantity)
        return total.quantize(Decimal("0.01"))
    @property
    def total_vat(self) -> Decimal:
        total = Decimal("0.00")
        for line in self.lines.all():
            line_base = line.unit_price_excl * line.quantity
            total += (line_base * (line.vat_rate / Decimal("100")))
        return total.quantize(Decimal("0.01"))
    @property
    def total_incl(self) -> Decimal:
        return (self.total_excl + self.total_vat).quantize(Decimal("0.01"))
    @staticmethod
    def _ogm_from_invoice_number(inv_number: str) -> str:
        digits = "".join(ch for ch in (inv_number or "") if ch.isdigit())
        base = digits.zfill(10)[-10:]
        check = int(base) % 97
        if check == 0:
            check = 97
        final12 = f"{base}{check:02d}"
        return f"+++{final12[0:3]}/{final12[3:7]}/{final12[7:12]}+++"
    def payment_reference_display(self) -> str:
        if self.payment_reference_raw:
            raw = self.payment_reference_raw.zfill(12)[-12:]
            return f"+++{raw[0:3]}/{raw[3:7]}/{raw[7:12]}+++"
        if self.number:
            return self._ogm_from_invoice_number(self.number)
        return ""
    def finalize(self):
        if self.status == self.STATUS_FINAL and self.number:
            return
        year = self.issue_date.year
        seq, _ = YearSequence.objects.get_or_create(year=year)
        seq.last_number += 1
        seq.save()
        self.number = f"{year}{seq.last_number:05d}"
        digits = "".join(ch for ch in self.number if ch.isdigit())
        base = digits.zfill(10)[-10:]
        check = int(base) % 97
        if check == 0:
            check = 97
        self.payment_reference_raw = f"{base}{check:02d}"
        self.status = self.STATUS_FINAL
        self.save()

class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, related_name="lines", on_delete=models.CASCADE)
    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.SET_NULL)
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1.00"))
    unit_price_excl = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    vat_rate = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("21.00"))
    def line_total_excl(self) -> Decimal:
        return (self.unit_price_excl * self.quantity).quantize(Decimal("0.01"))
    def line_total_vat(self) -> Decimal:
        return (self.line_total_excl() * (self.vat_rate / Decimal("100"))).quantize(Decimal("0.01"))
    def line_total_incl(self) -> Decimal:
        return (self.line_total_excl() + self.line_total_vat()).quantize(Decimal("0.01"))
    def __str__(self) -> str:
        return self.description or f"Regel #{self.pk}"

# ===== annual_v2: YearPricing =====
from django.db import models

VAT_CHOICES = [(0, "0%"), (6, "6%"), (12, "12%"), (21, "21%")]

class YearPricing(models.Model):
    year = models.PositiveIntegerField(db_index=True)
    code = models.CharField(max_length=32)  # vb. afkorting uit Excel
    description = models.CharField(max_length=255, blank=True)
    vat_rate = models.PositiveSmallIntegerField(choices=VAT_CHOICES, default=21)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("year", "code")
        ordering = ["year", "code"]
        verbose_name = "Jaarprijs"
        verbose_name_plural = "Jaarprijzen"

    def __str__(self):
        return f"{self.year} {self.code}: {self.amount} ({self.vat_rate}%)"

# annual-v2 rules
from .models import YearRule  # noqa: F401

# ---- YearRule (annual v2 “hoe factureren” regels) ----
from django.db import models as _models

class YearRule(_models.Model):
    year = _models.PositiveIntegerField()
    code = _models.CharField(max_length=40)
    order = _models.PositiveIntegerField(default=0)

    # vrije velden om je regels uit te drukken
    condition = _models.TextField(blank=True, default="")
    action = _models.TextField(blank=True, default="")
    data = _models.JSONField(blank=True, default=dict)

    active = _models.BooleanField(default=True)

    class Meta:
        unique_together = (("year", "code", "order"),)
        ordering = ["year", "order", "code"]

    def __str__(self):
        return f"{self.year} · {self.code} · #{self.order}"
