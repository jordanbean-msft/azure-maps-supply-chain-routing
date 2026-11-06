from datetime import datetime
from itertools import pairwise

from template_repository.models.route_candidate import Coordinate
from template_repository.routing.simulated import distance_km


def forecast_samples(
    geometry: list[Coordinate],
    duration_minutes: float,
    departure: datetime,
    now: datetime,
) -> tuple[list[tuple[float, float, float]], float, list[str]]:
    """Sample actual road vertices; elapsed time is estimated by path distance.

    Weather Along Route 1.1 uses latitude,longitude,minutes-from-now, not a
    departure timestamp. Its documented forecast horizon is 0..120 minutes.
    """
    cumulative = [0.0]
    for previous, point in pairwise(geometry):
        cumulative.append(
            cumulative[-1] + distance_km(previous[1], previous[0], point[1], point[0])
        )
    total_distance = cumulative[-1]
    departure_offset = max(0.0, (departure - now).total_seconds() / 60)
    timed = (
        [
            (point[1], point[0], departure_offset + duration_minutes * distance / total_distance)
            for point, distance in zip(geometry, cumulative, strict=True)
        ]
        if total_distance
        else [
            (point[1], point[0], departure_offset + duration_minutes * index / (len(geometry) - 1))
            for index, point in enumerate(geometry)
        ]
    )
    eligible = [point for point in timed if 0 <= point[2] <= 120]
    if len(eligible) < 2:
        return (
            [],
            0,
            [
                "Weather forecast unavailable: fewer than two actual road vertices fall within "
                "the 0..120-minute forecast horizon; zero adjustment is not an observation."
            ],
        )
    # One request per candidate, at most twelve actual vertices (API maximum sixty).
    if len(eligible) > 12:
        eligible = [eligible[round(index * (len(eligible) - 1) / 11)] for index in range(12)]
    covered_minutes = eligible[-1][2] - eligible[0][2]
    warnings = []
    if eligible[-1] != timed[-1]:
        warnings.append(
            f"Weather forecast covers only {covered_minutes:.1f} of {duration_minutes:.1f} "
            "driving minutes; travel beyond the 120-minute horizon is unpriced, not hazard-free."
        )
    return eligible, covered_minutes, warnings
