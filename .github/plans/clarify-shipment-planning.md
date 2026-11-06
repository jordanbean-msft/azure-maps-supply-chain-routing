# Clear shipment planning and readable routes

Explain the existing minimum-cost allocation without changing the solver,
cost model, persisted scenarios or authentication. Make the map show the
recommended shipment plan rather than all candidate routes by default.

- [x] Workspace and results (`App.tsx`, `RouteResults.tsx`, `style.css`):
  rename the action to Calculate shipment plan; explain total estimated cost,
  supply and capacity constraints, and that route inspection is not allocation.
  Identify recommended quantities and unallocated alternatives in results.
  Do not auto-inspect the first candidate or preview disruptions in Network.
  Complete: action has an accessible objective/constraint explanation; recommended
  rows and quantities are explicit and sorted first. Inspection does not submit
  another calculation or change allocations; Network never shows target previews.
- [x] Map (`MapView.tsx`, `MapView.css`; depends on allocation props from App):
  render all positive-quantity recommended routes in blue with white casing,
  optional slate dashed alternatives, purple inspection, magenta local target
  preview and red simulated closure. Label shipment quantities, not every lane.
  Use a quiet default basemap, a matching line-style legend and a default-off
  alternatives toggle; selected/targeted alternatives remain visible.
  Keep map instances, viewports, keyboard fallback and traffic controls stable.
  Global disruption previews must not recolor every route.
  Complete: five stable data sources separate positive allocations, unused
  candidates, inspection, local preview and closure. Only recommended/inspected
  routes have compact unit labels; no candidate-wide name/ETA label layer.
- [x] Validation/docs (depends on workspace/map): update focused SDK, schematic,
  results, workspace and browser regressions. Verify multiple recommendations,
  hidden/revealed alternatives, inspection without allocation changes and
  disruption-only targeting. Run frontend lint/format/types/tests/build and
  desktop/mobile Chromium flows; inspect screenshots. Update the walkthrough.
  Complete: 64 React tests, ESLint, Prettier, TypeScript and production build
  pass. Two Chromium workflows pass, including multiple recommendations,
  alternatives toggle, inspecting an unused option without changing the plan,
  closure/facility-delay recalculation, persistence and responsive overflow.
  Desktop/mobile screenshots inspected; removed long inspection labels after
  visual review and revalidated. Existing Maps bundle advisory remains.
- [x] Rollout (depends on validation): follow Azure prepare/validate/deploy for
  the existing environment, deploy web only through secure ACR, verify the new
  revision, frontend assets and auth smoke; preserve API/identity permissions.
  Record actual verification and interactive-user acceptance limitations.
  Complete: Azure workflow and full Terraform preflight passed. Provision made
  only eight diagnostic reconciliations, zero additions/destruction. Secure ACR
  web build deployed a healthy ready revision; deployed assets match the local
  validated build byte-for-byte. Standalone auth smoke and live data-role
  verification pass. API/refresh images are unchanged. Initial post-deploy HTTP
  timeouts cleared on standalone retry. Authenticated cloud visual acceptance
  still requires the user's interactive sign-in.
