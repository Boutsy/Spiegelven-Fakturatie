from django.core.management.base import BaseCommand
from core.annual_engine import apply_assets

class Command(BaseCommand):
    help = "Maak factuurlijnen voor kasten/karren (conceptfacturen)."

    def add_arguments(self, parser):
        parser.add_argument("--year", type=int, required=True)

    def handle(self, *args, **opts):
        year = opts["year"]
        n = apply_assets(year)
        self.stdout.write(self.style.SUCCESS(f"Aangemaakte regels: {n}"))
