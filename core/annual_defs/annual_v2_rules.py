from django.db import models

class YearRule(models.Model):
    year = models.PositiveIntegerField()
    code = models.CharField(max_length=40)
    order = models.PositiveIntegerField(default=0)

    # "Hoe factureren" onderdelen
    condition = models.TextField(blank=True, default="")
    action = models.TextField(blank=True, default="")
    data = models.JSONField(blank=True, default=dict)

    active = models.BooleanField(default=True)

    class Meta:
        unique_together = (("year", "code", "order"),)
        ordering = ["year", "order", "code"]

    def __str__(self) -> str:
        return f"{self.year} · {self.code} · #{self.order}"
