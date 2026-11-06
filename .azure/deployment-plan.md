# Supply chain routing preparation

Status: Foundation only; infrastructure and deployment validation deferred.

The user approved React/TypeScript, FastAPI, Cosmos DB, Azure Maps and Container
Apps with Terraform/azd. This change establishes contracts and local/container
scaffolds only. Do not provision resources or deploy.

- [x] Foundation: domain contracts, local runtime, React scaffold, Dockerfiles and azd service mappings.
- [ ] Infrastructure: assigned to the later infrastructure workstream.
- [ ] Full application verification and azure-validate: after backend, frontend and infrastructure integration.

Detailed progress: `.github/plans/supply-chain-routing-demo.md`.

Python lint/format/types, 26 warning-free tests and package build pass. Frontend
lint/types, 3 tests, formatting and production build pass on Node 22 LTS. The
local Vite-to-API smoke passed. Docker runtime validation is blocked by the
unavailable Docker Desktop daemon; no container execution is claimed.
