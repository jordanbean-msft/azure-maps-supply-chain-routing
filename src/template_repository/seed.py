from datetime import UTC, datetime, timedelta
from typing import Literal, cast
from uuid import uuid4

from template_repository.models.location import Location
from template_repository.models.scenario import Scenario


def seed_scenario() -> Scenario:
    return Scenario(
        id=f"demo-{uuid4().hex}",
        name="Houston supply network",
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
                ("houston", "Houston supplier", "supplier", 29.7604, -95.3698, 25, "Houston, TX"),
                ("katy", "Katy supplier", "supplier", 29.7858, -95.8245, 35, "Katy, TX"),
                (
                    "pasadena",
                    "Pasadena supplier",
                    "supplier",
                    29.6911,
                    -95.2091,
                    20,
                    "Pasadena, TX",
                ),
                ("baytown", "Baytown factory", "factory", 29.7355, -94.9774, 50, "Baytown, TX"),
                (
                    "sugar-land",
                    "Sugar Land factory",
                    "factory",
                    29.6197,
                    -95.6349,
                    40,
                    "Sugar Land, TX",
                ),
            ]
        ],
    )
