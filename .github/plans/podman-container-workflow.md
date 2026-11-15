# Podman container workflow

- [x] Inspect existing container builds, azd configuration and machine tools.
  Rootless Podman works on ARM64; Docker resolves to a Windows executable.
  Both azd services already use ACR remote builds. No AMD64 binfmt handler exists.
- [x] Confirm scope and existing Azure target with the operator before execution.
  Operator approved both live app deployments, including uncommitted source.
- [x] Update container commands, VS Code tasks and proxy tests for explicit Podman
  support; preserve Docker-based GitHub CI and existing unrelated edits.
- [x] Build and run API/web locally with native ARM64 Podman images; verify
  liveness, API proxying and existing proxy regression tests. Stop only containers
  created for these checks. Health/config smoke and both proxy cases pass.
  Images use Docker format to preserve HEALTHCHECK; slirp4netns avoids the
  broken custom bridge helper path. No global machine changes.
- [x] Verify secretless ACR authentication and push uniquely tagged images if
  approved. Never deploy ARM64-only images to AMD64 Container Apps.
  Both pushes succeeded using tag `podman-check-0f783829-20261113`.
- [x] Validate the existing remote-build azd path and deploy approved AMD64 images
  to the existing apps; both ACR builds and azd deployment succeed. Latest-ready
  revisions match latest revisions; refresh job uses the deployed API image.
- [x] Verify Azure runtime health/auth. Resolved on operator follow-up:
  Azure CLI `az rest` POST to each app's `/start?api-version=2025-07-01`
  starts the stopped app without changing scale settings. Both replicas are
  ready/Running; web/root and proxied live/readiness endpoints return HTTP 200.
  Authentication smoke passes.
- [x] Record exact validation evidence and blockers here and in the active Azure
  deployment plan. No infrastructure, permissions or network policy changes.

Ownership: `scripts/`, `infra/tests/nginx-proxy.test.sh`, `.vscode/tasks.json`,
`README.md`, `docs/deployment.md`, and this plan. No application changes planned.
Local validation precedes any image push; Azure validation precedes deployment.

## Final evidence

2026-11-13: both images build/run rootlessly, push to ACR, pull back and pass
health/proxy smoke. Native ARM64 images retain health checks with Docker image
format. CI explicitly keeps Docker for its proxy test. Fully qualified image
names avoid Podman short-name prompts. Scoped Entra login uses
`DOCKER_COMMAND=podman az acr login`.

Both proxy regression cases and five deployment-hook tests pass; 198 Python
tests pass with warnings treated as errors. Application/test Ruff checks,
frontend ESLint/Prettier, TypeScript/container build, shell/VS Code JSON syntax
and diff whitespace checks pass. Full-repository Ruff has 25 unrelated existing
findings in untracked sample sources; frontend package audit reports ten moderate
findings and the existing Vite chunk-size advisory remains. No unrelated fixes.
Validation-generated package-index/provider-lock changes were restored exactly.

Approved Azure deployment: ACR runs `chd`/`che` are Linux AMD64/Succeeded.
API revision `ca-njk0ztnkmgrmn-api--azd-1794594036` and web revision
`ca-njk0ztnkmgrmn-web--azd-1794594098` are latest-ready. Runtime verification
passed 2026-11-13T12:33:28-06:00 after explicitly starting both apps.
`/`, `/health/web`, `/health/live` and `/health/ready` return HTTP 200;
readiness reports live mode. `scripts/smoke-auth.sh` verifies Entra discovery and
rejects anonymous, invalid and spoofed credentials. No scale, image, networking
or permission changes were needed for the start operations. Full evidence is in
the active `.azure/deployment-plan.md`.
