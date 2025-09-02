from __future__ import annotations

# Aliassen op basis van omschrijving (case-insensitive key).
# Linkerzijde = ALIAS (zoals het soms binnenkomt), rechterzijde = CANONIEKE omschrijving.
ALIASES_BY_DESC = {
    "lidgeld cc normaal": "Lidgeld CC Individueel",
    # voeg hier later gerust meer aan toe…
}

def canonical_desc(description: str) -> str:
    """Geef de canonieke omschrijving terug op basis van ALIASES_BY_DESC."""
    if not description:
        return description
    key = description.strip().lower()
    canon = ALIASES_BY_DESC.get(key)
    return canon or description.strip()
