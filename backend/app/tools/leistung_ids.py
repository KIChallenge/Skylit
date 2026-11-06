"""Catalogue ids for every `leistung_id` field: the model cannot guess them."""

from app.seed import SEED_DIR, load_records

LEISTUNG_IDS = tuple(
    record["id"]
    for record in load_records(SEED_DIR / "leistungen.json", optional=True)
)
LEISTUNG_ID_HINT = "Id aus dem Leistungskatalog: " + ", ".join(LEISTUNG_IDS) + "."
