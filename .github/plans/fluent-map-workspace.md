# Fluent map workspace

Replace the marketing-style page with a restrained Microsoft Fluent UI workspace.
Use one Segoe UI type family, square surfaces, compact controls and a dominant map.
Preserve scenario editing, authentication, cost transparency and simulation labels.
Deploy the integrated result to the existing demo without changing its security boundary.

- [x] Foundation (main): add Microsoft Fluent UI v9, shared square-corner theme,
  provider and `mapTarget.ts` contract. Validate dependency resolution and types.
- [ ] Map (isolated map worktree): own `MapView.tsx`, `MapView.test.tsx` and
  optional `MapView.css` only. Add facility selection/popups, named routes,
  persistent target/applied-disruption highlights, fit-network/fit-selection,
  traffic and basemap controls. Keep the schematic accessible and interactive.
  Selection changes must not recreate the map or reset the user's camera.
  Props retain the existing contract and add optional `selectedLocation`,
  `onSelectLocation`, `target: MapTarget | null`, and `disruptions`.
  Validate focused mocked-SDK tests and TypeScript.
- [ ] Account (isolated account worktree): own `AuthGate*`, new account-header/
  profile modules/tests/CSS, Entra module/tests and authentication docs only.
  Provide an aligned Fluent account header, Microsoft profile photo and
  `Howdy First Last!`; use initials when a photo is absent. Request only delegated
  Graph `User.Read` with separate resource tokens, no secrets or app permissions.
  Existing sessions must remain usable without profile consent; offer an explicit
  profile-consent action instead of redirect loops. Keep photo/profile data in
  memory, revoke object URLs, and abort pending work on logout.
  Validate auth/profile tests, lint/types, warning-free Terraform validation/tests.
- [ ] Workspace (main): rebuild `App`, `ScenarioEditor`, `DisruptionEditor`,
  `RouteResults` and CSS with Fluent controls, a map-first split workspace,
  compact route results and plain labels. Integrate the account header.
  Disruption kind and target are controlled by App. Route/facility selections
  synchronize with the matching disruption mode; global weather/fuel explicitly
  target the entire network. Show human-readable targets and a map preview
  before applying; never silently apply to a different target.
- [ ] Houston (main): replace backend seed locations, frontend default coordinates
  and matching fixtures/walkthroughs with Houston and nearby industrial areas.
  Do not rewrite users' existing saved scenarios. Validate geography and existing
  optimizer/conservation tests.
- [ ] Integration (main; depends on all above): integrate worktree commits, update
  focused tests and browser walkthroughs, VS Code tasks/docs as needed. Run Ruff,
  strict Python tests, frontend lint/format/types/tests/build, Terraform checks,
  and real Chromium desktop/mobile flows. Inspect actual rendered layout.
- [ ] Rollout (main; depends on integration): revalidate the existing azd project,
  provision the minimal Graph permission metadata change, deploy API/web through
  ACR, verify healthy revisions, public auth boundaries and the real sign-in
  entry. Record that real profile access requires the user's delegated consent.

## Shared interaction contract

`MapTarget = { kind: "route" | "facility"; id: string } |
{ kind: "network"; id: null }`.
The map uses blue for inspected routes, a distinct outlined target preview,
and explicit closed/delayed indicators for enabled persisted disruptions.
Map clicks are inspection actions; only a matching disruption mode updates its
target. Target controls can also select the map item, supporting keyboard use.
No live road closure is submitted to Azure Maps: disruptions remain simulations.

## Acceptance

Houston seed → edit/save → optimize → inspect a route on map/table → select
a clearly named closure target → see the map preview → apply → re-optimize.
Repeat a facility delay using a map marker. Verify global controls identify
network-wide scope, stale results remain labeled, and logout clears the workspace.
On mobile, controls remain reachable and the map is not hidden beneath long forms.
No remote font downloads or decorative hero/cards remain. User profile tests use
deterministic mocks; never claim an interactive cloud sign-in without observing it.
