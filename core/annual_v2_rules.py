from django.db import models
from django.apps import apps

ROLE_CHOICES = [
    ("IND", "Individueel"),
    ("HEAD","Gezinshoofd"),
    ("PRT", "Partner"),
    ("KID", "Kind"),
]

COURSE_CHOICES = [
    ("CC", "Championship"),
    ("P3", "Par-3"),
]

AGE_CHOICES = [
    ("KID_0_15",  "Kid t/m 15"),
    ("KID_16_21", "Kid 16–21"),
    ("YA_22_26",  "YA 22–26"),
    ("YA_27_29",  "YA 27–29"),
    ("YA_30_35",  "YA 30–35"),
    ("NORMAL",    "Normaal (36–59)"),
    ("P60",       "60 Plus"),
    ("P70",       "70 Plus"),
]

YNANY_CHOICES = [
    ("ANY", "Onverschillig"),
    ("YES", "Ja vereist"),
    ("NO",  "Nee vereist"),
]

INV_CHOICES = [
    ("ANY",  "Onverschillig"),
    ("NORM", "Normaal (in 1 keer)"),
    ("FLEX", "Flex (gespreid)"),
]

BILL_CHOICES = [
    ("SELF", "Op eigen factuur"),
    ("HEAD", "Op factuur van het gezinshoofd"),
]

class YearRule(models.Model):
    """
    'Hoe factureren'-regel voor jaar X:
    - Conditionele velden (wie/waarop van toepassing)
    - Doel: welke YearPricing-code aanrekenen
    """
    year = models.PositiveIntegerField()

    # Doelprijs (koppeling naar YearPricing)
    code = models.CharField(max_length=40, help_text="YearPricing.code")
    pricing = models.ForeignKey(
        "core.YearPricing", null=True, blank=True, on_delete=models.PROTECT, related_name="rules",
        help_text="Optioneel: wordt automatisch gezet op save als year+code gevonden wordt."
    )

    # Voorwaarden (leeg = 'maakt niet uit')
    applies_role   = models.CharField(max_length=5,  choices=ROLE_CHOICES, blank=True)
    course         = models.CharField(max_length=3,  choices=COURSE_CHOICES, blank=True)
    age_bucket     = models.CharField(max_length=20, choices=AGE_CHOICES, blank=True,
                                      help_text="Leeftijdscategorie (meestal volgend jaar).")
    federation     = models.CharField(max_length=3, choices=YNANY_CHOICES, default="ANY",
                                      help_text="Federatie alleen als YES én course=CC.")
    invest_mode    = models.CharField(max_length=4, choices=INV_CHOICES, default="ANY")
    use_next_year_age = models.BooleanField(default=True, help_text="Meestal leeftijd volgend jaar.")

    # Flex (alleen bij invest_mode=FLEX)
    flex_year_min  = models.PositiveSmallIntegerField(null=True, blank=True, help_text="1..7")
    flex_year_max  = models.PositiveSmallIntegerField(null=True, blank=True, help_text="1..7")

    # Hoe op de factuur
    bill_to        = models.CharField(max_length=5, choices=BILL_CHOICES, default="SELF")
    quantity       = models.DecimalField(max_digits=9, decimal_places=2, default=1)
    desc_suffix    = models.CharField(max_length=120, blank=True, help_text="Bijv. '(jaar 3/7)'")
    order          = models.SmallIntegerField(default=0)
    active         = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["year", "code"]),
            models.Index(fields=["year", "applies_role", "course"]),
        ]
        verbose_name = "Jaarregel"
        verbose_name_plural = "Jaarregels"

    def __str__(self):
        return f"{self.year} · {self.code} · cond(role={self.applies_role or '*'}, course={self.course or '*'}, age={self.age_bucket or '*'}, fed={self.federation}, inv={self.invest_mode})"

    def _sync_pricing_fk(self):
        """Probeer pricing-FK te zetten obv year+code."""
        YP = apps.get_model("core", "YearPricing")
        try:
            self.pricing = YP.objects.get(year=self.year, code=self.code)
        except YP.DoesNotExist:
            self.pricing = None

    def save(self, *args, **kwargs):
        if self.code and self.year and not self.pricing:
            self._sync_pricing_fk()
        super().save(*args, **kwargs)
