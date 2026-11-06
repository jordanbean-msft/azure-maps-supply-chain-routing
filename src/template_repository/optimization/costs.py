from template_repository.models.cost_breakdown import CostBreakdown
from template_repository.models.cost_profile import CostProfile
from template_repository.models.route_candidate import RouteCandidate


def route_cost(route: RouteCandidate, profile: CostProfile) -> CostBreakdown:
    liters = route.distance_km * profile.fuel_liters_per_100_km / 100
    components = {
        "distance_cost": route.distance_km * profile.distance_cost_per_km,
        # Duration already includes traffic. Delay penalties are business penalties,
        # not a second charge for driver time; weather/simulation extend driver time.
        "driver_time_cost": (
            route.duration_minutes + route.weather_delay_minutes + route.simulated_delay_minutes
        )
        / 60
        * profile.driver_cost_per_hour,
        "toll_cost": route.toll_estimate,
        "fuel_cost": liters * profile.fuel_price_per_liter,
        "carbon_cost": liters * profile.emissions_kg_per_liter * profile.carbon_cost_per_kg,
        "traffic_delay_penalty": route.traffic_delay_minutes / 60 * profile.delay_penalty_per_hour,
        "weather_delay_penalty": route.weather_delay_minutes / 60 * profile.delay_penalty_per_hour,
        "simulated_disruption_penalty": route.simulated_delay_minutes
        / 60
        * profile.delay_penalty_per_hour,
    }
    return CostBreakdown(**components, total=sum(components.values()))
