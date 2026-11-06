"""Vienna providers by distance: demo providers and Stadt Wien open data."""

from math import asin, cos, radians, sin, sqrt

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Provider
from app.schemas import cards

# Rough bounding box of Vienna. Outside it, the postal code centre applies.
VIENNA_BOUNDS = ((48.10, 16.15), (48.35, 16.60))

# Approximate district centres suffice for the synthetic Vienna directory.
POSTAL_CODE_CENTRES = {
    "1010": (48.208, 16.373),
    "1020": (48.216, 16.399),
    "1030": (48.198, 16.398),
    "1040": (48.192, 16.370),
    "1050": (48.185, 16.355),
    "1060": (48.196, 16.350),
    "1070": (48.203, 16.350),
    "1080": (48.211, 16.347),
    "1090": (48.225, 16.357),
    "1100": (48.174, 16.377),
    "1110": (48.169, 16.430),
    "1120": (48.175, 16.329),
    "1130": (48.180, 16.273),
    "1140": (48.210, 16.260),
    "1150": (48.197, 16.325),
    "1160": (48.213, 16.318),
    "1170": (48.231, 16.297),
    "1180": (48.238, 16.321),
    "1190": (48.260, 16.343),
    "1200": (48.239, 16.377),
    "1210": (48.280, 16.413),
    "1220": (48.230, 16.470),
    "1230": (48.145, 16.294),
}


def in_vienna(lat: float, lon: float) -> bool:
    (south, west), (north, east) = VIENNA_BOUNDS
    return south <= lat <= north and west <= lon <= east


def _distance(lat: float, lon: float, centre: tuple[float, float]) -> float:
    latitude, longitude = map(radians, (lat, lon))
    centre_latitude, centre_longitude = map(radians, centre)
    haversine = (
        sin((latitude - centre_latitude) / 2) ** 2
        + cos(latitude)
        * cos(centre_latitude)
        * sin((longitude - centre_longitude) / 2) ** 2
    )
    return 6371.0 * 2 * asin(sqrt(min(1.0, haversine)))


class MockProviderDirectory:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, provider_id: str) -> cards.Provider | None:
        row = await self.db.get(Provider, provider_id)
        return cards.Provider.model_validate(row) if row is not None else None

    async def find(
        self,
        kind: cards.ProviderKind,
        postal_code: str,
        *,
        specialty: str | None = None,
        limit: int = 3,
        origin: tuple[float, float] | None = None,
    ) -> list[cards.Provider]:
        """Rank by distance from `origin` (shared location) or the postal code."""
        centre = origin if origin and in_vienna(*origin) else None
        centre = centre or POSTAL_CODE_CENTRES.get(postal_code)
        query = select(Provider).where(Provider.kind == kind)
        if centre is None:
            query = query.where(Provider.postal_code == postal_code)
        else:
            # Include neighbouring Vienna districts, then rank by distance.
            query = query.where(Provider.postal_code.in_(POSTAL_CODE_CENTRES))
        if specialty:
            # Open data names fields in full, e.g. "Innere Medizin u. Kardiologie".
            query = query.where(
                Provider.specialty.icontains(specialty, autoescape=True)
            )
        rows = await self.db.scalars(query.order_by(Provider.id))
        providers = []
        for row in rows:
            provider = cards.Provider.model_validate(row)
            if centre and row.lat is not None and row.lon is not None:
                provider.distance_km = round(_distance(row.lat, row.lon, centre), 3)
            providers.append(provider)
        providers.sort(
            key=lambda provider: (
                provider.distance_km
                if provider.distance_km is not None
                else float("inf"),
                provider.id,
            )
        )
        return providers[:limit]
