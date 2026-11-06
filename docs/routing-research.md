# Routing research and design decisions

The MVP optimizes a small transportation network, not a delivery fleet.
These sources informed the architecture; check live API schemas, regional
coverage, pricing, and terms again when deploying.

| Requirement | Selected approach | Why / boundary |
| --- | --- | --- |
| Interactive road map | Azure Maps Web SDK directly in React | Microsoft-maintained control, layers, markers, attribution, traffic display. |
| Supplier/factory comparison | Azure Maps Route Matrix | Efficient origin/destination travel measures; no geometry. |
| Road alternatives | Azure Maps Route Directions | Geometry, truck routing, departure time, traffic-aware alternatives. Alternatives are not guaranteed for every pair. |
| Address input | Azure Maps Search/geocoding | Persist the selected coordinates; ambiguous addresses require user selection. |
| Traffic | Routing traffic-aware duration and traffic context | Route duration already includes traffic; avoid double counting. |
| Weather | Route weather plus explicit delay assumptions | Weather context is not itself a guaranteed ETA adjustment. |
| Shipment allocation | Capacitated min-cost flow | Fits fixed supplier supplies and bounded factory receiving capacity. |
| Future vehicle dispatch | Capacitated VRP with time windows | Only needed for vehicle assignments, pickup sequences, and operating constraints. Deferred. |

## Algorithm alternatives

**Shortest path (Dijkstra/A*)** solves one road-network traversal objective.
Azure Maps already owns the road graph and its restrictions. Rebuilding that
graph is unnecessary for this demo.

**Bipartite assignment** fits one-to-one pairing, but the demo allows a supplier
to split shipment volume across factories and allows multiple suppliers per
factory. A transportation/min-cost-flow model better represents that.

**Min-cost flow** represents supply, receiving capacity, and linear route costs.
It gives an optimal allocation for the supplied graph and integer-scaled costs,
not an absolute guarantee that all physically possible roads were examined.
Candidate selection and uncertain cost assumptions still matter.

**Mixed-integer programming** becomes useful for fixed facility-opening costs,
minimum shipment sizes, integer truck counts, or multiple commodity constraints.
Those are not modeled in the MVP.

**VRP/TSP heuristics** solve sequencing and fleet-routing problems and can become
computationally expensive. OR-Tools supports capacity and time-window variants,
but that is a different product scope from lane planning.

**Multi-objective comparison** should expose cost/time/risk tradeoffs rather
than pretend a single arbitrary weighted score is universally best. For the
MVP, route alternatives and explicit cost assumptions let users explore these
tradeoffs; a future Pareto-front analysis can make them more formal.

## Traffic, weather, and disrupted routes

Keep three concepts separate:

- The routing provider's traffic-aware duration.
- A transparent, estimated incremental weather delay.
- A user-injected simulated delay or route exclusion.

Do not add traffic delay to a duration that already includes it. Do not equate
a missing weather response with good weather. Do not describe a simulated road
closure as an actual reported incident. A simulated exclusion removes a
candidate route; only an actual provider reroute can establish a legal detour.

For future optimization, use scenario analysis or robust optimization instead
of claiming precise probability distributions without historical calibration.
Date/time inputs need explicit time zones and forecasts should be matched to
the planned passage time, not just current weather at the origin.

## Maps/API best practices

Use stable version-specific schemas behind an application-owned adapter.
The best-practices page contains legacy examples alongside current APIs:
do not combine v1 request parameters with a newer response schema.

Shortlist detail requests, bound weather samples, reuse valid results, and honor
throttling. Azure Maps Route Matrix billing is `ceil(origin_count *
destination_count / 4)` routing transactions under the currently documented
meter. Batch calls do not remove per-query billing. Map tiles, search, traffic,
and weather have their own meters. This is separate from route shipment costs.

Use Entra/managed identity server-side and short-lived browser authorization,
not subscription keys in frontend bundles. A public token endpoint still
requires an abuse model: origin restrictions are defense in depth, not
authentication. Apply service quotas and monitor usage.

## First-party and algorithm references

- [Azure Maps overview](https://learn.microsoft.com/azure/azure-maps/about-azure-maps)
- [Routing best practices](https://learn.microsoft.com/azure/azure-maps/how-to-use-best-practices-for-routing)
- [Route Matrix API](https://learn.microsoft.com/rest/api/maps/route/post-route-matrix)
- [Azure Maps REST versions](https://learn.microsoft.com/azure/azure-maps/rest-api-azure-maps)
- [Azure Maps transactions](https://learn.microsoft.com/azure/azure-maps/understanding-azure-maps-transactions)
- [Azure Maps authentication](https://learn.microsoft.com/azure/azure-maps/azure-maps-authentication)
- [Cosmos partitioning](https://learn.microsoft.com/azure/cosmos-db/partitioning)
- [Container Apps architecture practices](https://learn.microsoft.com/azure/well-architected/service-guides/azure-container-apps)
- [OR-Tools min-cost flow](https://developers.google.com/optimization/flow/mincostflow)
- [OR-Tools vehicle routing](https://developers.google.com/optimization/routing/)

OR-Tools is an approved non-Microsoft dependency because Microsoft does not
provide an equivalent maintained Python constrained-network solver. React's
ecosystem build/test tools are used where Microsoft does not provide suitable
equivalents; Playwright is Microsoft-maintained.
