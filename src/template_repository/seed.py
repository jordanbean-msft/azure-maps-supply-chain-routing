from datetime import UTC, datetime, timedelta
from typing import Literal, cast
from uuid import uuid4

from template_repository.models.location import Location
from template_repository.models.scenario import Scenario


def seed_scenario() -> Scenario:
    return Scenario(
        id=f"demo-{uuid4().hex}",
        name="Pacific Northwest supply network",
        departure_time=datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        + timedelta(hours=1),
        locations=[
            Location(
                id=identifier,
                name=name,
                kind=cast(Literal["supplier", "factory"], kind),
                latitude=lat,
                longitude=lon,
                quantity=quantity,
                address=address,
            )
            for identifier, name, kind, lat, lon, quantity, address in [
                ("seattle", "Seattle supplier", "supplier", 47.6062, -122.3321, 25, "Seattle, WA"),
                ("tacoma", "Tacoma supplier", "supplier", 47.2529, -122.4443, 35, "Tacoma, WA"),
                ("spokane", "Spokane supplier", "supplier", 47.6588, -117.426, 20, "Spokane, WA"),
                ("portland", "Portland factory", "factory", 45.5152, -122.6784, 50, "Portland, OR"),
                ("yakima", "Yakima factory", "factory", 46.6021, -120.5059, 40, "Yakima, WA"),
            ]
        ],
    )
