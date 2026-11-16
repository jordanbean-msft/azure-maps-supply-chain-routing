---
description: Test standards for this repository
applyTo: "**/tests/**/*.py"
---

## Test Standards

* Cover happy paths and key failure paths.
* Mock external dependencies.
* Keep tests deterministic and independent.
* Use clear arrange-act-assert structure.
* Use async tests for async behavior.
* Use `httpx.MockTransport` with `httpx.AsyncClient` for REST client tests.

## Expected scope

* Unit tests for Fabric settings, sample normalization, Maps enrichment, and report definitions.
* Notebook execution tests that run locally with fake Fabric and Spark services.
