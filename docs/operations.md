# Operations and demo safety

## What this demo does not promise

Public demo data is synthetic and disposable. The public API is not a
multi-tenant authorization system. Do not enter real supplier names, negotiated
rates, personal addresses, or sensitive factory information. Add sign-in,
per-user resource authorization, audit controls, and a reviewed retention policy
before accepting business data.

Cold starts, external API coverage, forecast availability, and throttling affect
freshness. A failed refresh must not masquerade as current data. Check the
displayed source, timestamps, warnings, and run status before interpreting
results.

## Observe

Use the shared Log Analytics workspace and Application Insights resource.
Check the API and refresh job's structured stdout logs alongside service
diagnostics. Typical workspace-based Application Insights queries:

```kusto
AppRequests
| where TimeGenerated > ago(1h)
| summarize requests=count(),
    failures=countif(Success == false),
    p95_duration_ms=percentile(DurationMs, 95) by Name
| order by p95_duration_ms desc
```

```kusto
AppDependencies
| where TimeGenerated > ago(1h)
| summarize calls=count(),
    failures=countif(Success == false),
    p95_duration_ms=percentile(DurationMs, 95) by Target, Name
| order by failures desc
```

```kusto
AppExceptions
| where TimeGenerated > ago(1h)
| project TimeGenerated, OperationId, ExceptionType, OuterMessage
| order by TimeGenerated desc
```

Use request correlation IDs to connect a user-visible error to API and upstream
logs. Never include authorization headers, Maps tokens, Cosmos credentials, or
full request bodies in logs. Changing log verbosity should not expose secrets.

Application metrics are `maps.requests`, `maps.duration`,
`optimization.duration`, `solver.duration`, `optimization.routes`,
`optimization.failures`, `cache.hits`, and `cosmos.request_charge`.
Durations are seconds; Cosmos charge is request units. A maximum-size cold
scenario can make **91 upstream HTTP requests before retries**: one matrix
request, 30 Directions requests, and up to 60 weather requests. Matrix billing
still counts its cells separately. Keep the two-optimization concurrency bound
and retry/refresh limits in mind when setting service quotas.

In the Azure portal, inspect:

- Azure Maps transactions by service/API and failed/throttled requests.
- Cosmos DB consumed request units, normalized RU consumption, `429` responses,
  storage, and TTL behavior.
- Container Apps replica counts, restarts, CPU/memory, ingress latency, and failed
  job executions.
- Application Insights request/dependency failures and latency.

Set a Cost Management budget and alerts appropriate to the demonstration.
Budgets notify; they do not automatically stop spending. Route shipment-cost
estimates in the application are unrelated to Azure hosting/API charges.

## Respond

| Symptom | First checks |
| --- | --- |
| No basemap | Demo mode deliberately has no live basemap. In live mode check Maps account client ID, token expiry, role assignment propagation, and allowed origins. |
| No routes | Verify road coverage, geographic coordinates, truck restrictions, departure time, closure targets, and upstream error details. |
| Infeasible allocation | Check supplier supply versus factory capacity and whether closures disconnected a supplier. This is a modeled result, not a server failure. |
| Stale scenario edit | Refetch after `412` ETag conflict; do not retry an unconditional overwrite. |
| Frequent throttling | Pause refresh, reduce active scenarios, inspect transaction/RU usage, and verify bounded retries and cache hits. |
| Run never finishes | Inspect run error/status and API replica restart logs; bounded in-process work is not a durable queue. |
| Web loads but API fails | Check Nginx `API_INTERNAL_URL`, internal API ingress, readiness probes, and identity configuration. |
| Scheduled refresh fails | Confirm the job image matches the deployed API image and that job identity has both Maps and Cosmos data access. |

## Limits and retention

Keep the MVP limit of 10 suppliers and 3 factories; avoid raising it without
reviewing matrix billing and all per-lane Directions/weather calls. Debounce
geocoding, do not refresh hidden/unused browser tabs unnecessarily, and bound
simultaneous optimization work. Pausing browser refresh does not disable a
separately scheduled Azure refresh job.

TTL is cleanup, not immediate deletion or a backup strategy. Cosmos expiration
and removal are asynchronous. Local memory storage disappears on process exit.
No database backup/restore or regional failover claim is made for this demo.

## Deployment and rollback

Use the manually dispatched, environment-protected GitHub deployment workflows
only after CI passes. Configure federation for the exact GitHub environment
subject and grant the deployment identity only the required control/data-plane
roles. Public ingress does not require public database access; private
deployments require existing networking and DNS policy prerequisites.

Deploy immutable application images, verify liveness/readiness through the web
proxy, load a seed scenario, and optimize it. Confirm Azure-backed source labels
in live mode. Roll back to a known-good container revision/image and keep the
scheduled refresh job on that same backend image.

See [deployment](deployment.md) for provisioning inputs. Clean up only the
reviewed demo resources; the resource group, networking, DNS policy, and remote
state storage may be shared and must not be deleted indiscriminately.
