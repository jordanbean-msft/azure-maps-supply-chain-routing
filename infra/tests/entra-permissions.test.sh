#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

# Complement the mocked plan's exact scope/role assertions: consent grants and
# secrets must not be added as separate resources alongside the registration.
actual="$(sed -n 's/^resource "\([^"]*\)" "\([^"]*\)".*/\1 \2/p' infra/modules/entra/main.tf | sort)"
expected="$(printf '%s\n' \
  'azuread_application_api_access profile' \
  'azuread_application_identifier_uri api' \
  'azuread_application_owner deployer' \
  'azuread_application_permission_scope access_as_user' \
  'azuread_application_registration app' \
  'azuread_service_principal app' | sort)"

if [[ "$actual" != "$expected" ]]; then
  echo "Entra resources changed: review for secrets, extra permissions, preauthorization or consent grants." >&2
  exit 1
fi

echo "Entra resource allowlist passed: no secrets, admin grants or preauthorization."
