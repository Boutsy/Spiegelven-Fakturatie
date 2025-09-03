from django.core.management.base import BaseCommand
from core.annual_engine import simulate_assets

class Command(BaseCommand):
    help = "Toon wat er voor kasten/karren gefactureerd zou worden."

    def add_arguments(self, parser):
        parser.add_argument("--year", type=int, required=True)

    def handle(self, *args, **opts):
        year = opts["year"]
        rows = simulate_assets(year)
        if not rows:
            self.stdout.write(self.style.WARNING("Geen matches gevonden."))
            return
        for member, asset_type, code, text in rows:
            self.stdout.write(f"- {member} · {asset_type} · {code} · {text}")
        self.stdout.write(self.style.SUCCESS(f"Totaal: {len(rows)} regels."))
