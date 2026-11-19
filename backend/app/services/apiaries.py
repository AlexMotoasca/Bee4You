from typing import Any

from sqlalchemy import cast, func

from app.models.db.tables import Geography
from app.services.errors import OpRejected


def point(lat: float, lng: float) -> Any:
    return cast(
        func.extensions.st_setsrid(func.extensions.st_makepoint(lng, lat), 4326), Geography()
    )


def apiary_to_db(values: dict[str, Any]) -> dict[str, Any]:
    """Devices send lat/lng (SQLite has no PostGIS); Postgres stores a geography point."""
    has_lat, has_lng = "lat" in values, "lng" in values
    if has_lat != has_lng:
        raise OpRejected("lat and lng must be sent together")
    if has_lat:
        lat, lng = values.pop("lat"), values.pop("lng")
        if (lat is None) != (lng is None):
            raise OpRejected("lat and lng must be given together")
        values["location"] = None if lat is None else point(lat, lng)
    return values
