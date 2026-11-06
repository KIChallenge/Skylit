"""Download the Vienna doctor locations once and write them as a static seed file.

Source: Stadt Wien – data.wien.gv.at, WFS layer `ogdwien:ARZTOGD` (CC BY 4.0).
The app never calls the WFS at runtime. Run this script only to refresh the file:

    cd backend && uv run python -m scripts.fetch_vienna_doctors
"""

import json
import re
import sys
import urllib.request
from pathlib import Path

URL = (
    "https://data.wien.gv.at/daten/geo?service=WFS&request=GetFeature"
    "&version=1.1.0&typeName=ogdwien:ARZTOGD&srsName=EPSG:4326&outputFormat=json"
)
OUT = Path(__file__).resolve().parents[1] / "seed" / "vienna_doctors.json"
GP = {"Allgemeinmedizin", "Allgemein- und Familienmedizin"}
# Fields without patient care, and entries without a field.
SKIP = {
    "unbekannt",
    "Anatomie",
    "Gerichtsmedizin",
    "Physiologie",
    "Neuropathologie",
    "Virologie",
    "Transfusionsmedizin",
}
ADDRESS = re.compile(r"^(\d{1,2})\.,\s*(.+)$")


def convert(feature: dict) -> dict | None:
    props = feature["properties"]
    field = (props.get("FACH") or "").strip()
    match = ADDRESS.match((props.get("ADRESSE") or "").strip())
    geometry = feature.get("geometry") or {}
    if field in SKIP or not field or match is None or geometry.get("type") != "Point":
        return None
    district = int(match.group(1))
    if not 1 <= district <= 23:
        return None
    postal_code = f"1{district:02d}0"
    lon, lat = geometry["coordinates"][:2]
    return {
        "id": f"wien-arzt-{props['OBJECTID']}",
        "name": props["NAME"].strip(),
        "kind": "gp" if field in GP else "specialist",
        "specialty": field,
        "address": f"{match.group(2).strip()}, {postal_code} Wien",
        "postal_code": postal_code,
        "lat": round(lat, 6),
        "lon": round(lon, 6),
        "phone": (props.get("TELEFON") or "").strip() or None,
        "website": (props.get("INTERNET") or "").strip() or None,
    }


def main() -> int:
    with urllib.request.urlopen(URL, timeout=120) as response:  # noqa: S310
        data = json.load(response)
    records = [r for f in data["features"] if (r := convert(f)) is not None]
    records.sort(key=lambda record: record["id"])
    with OUT.open("w", encoding="utf-8") as target:
        target.write("[\n")
        target.write(",\n".join(json.dumps(r, ensure_ascii=False) for r in records))
        target.write("\n]\n")
    print(f"{len(records)} von {len(data['features'])} Einträgen geschrieben: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
