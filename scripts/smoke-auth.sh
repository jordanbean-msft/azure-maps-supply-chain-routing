#!/usr/bin/env bash
set -euo pipefail

base_url="${1:?Usage: bash scripts/smoke-auth.sh https://web-host}"
base_url="${base_url%/}"
headers="$(mktemp)"
body="$(mktemp)"
trap 'rm -f "$headers" "$body"' EXIT

http() {
  curl --silent --show-error --connect-timeout 5 --max-time 30 "$@"
}

http --fail "$base_url/" > "$body"
grep -qi '<html' "$body"
http --fail "$base_url/health/ready" >/dev/null
config="$(http --fail "$base_url/api/auth/config")"
jq -e '.enabled == true and
  (.tenant_id | test("^[0-9a-fA-F-]{36}$")) and
  (.client_id | test("^[0-9a-fA-F-]{36}$")) and
  (.scope | endswith("/access_as_user"))' <<< "$config" >/dev/null

expect_unauthorized() {
  local path="$1"
  shift
  local status
  status="$(http -D "$headers" -o "$body" -w '%{http_code}' \
    "$@" "$base_url$path")"
  if [ "$status" != "401" ]; then
    echo "Expected 401 for $path, received $status." >&2
    exit 1
  fi
  grep -Eqi '^www-authenticate:[[:space:]]*Bearer' "$headers"
}

expect_unauthorized /api/config
expect_unauthorized /api/scenarios
expect_unauthorized /api/scenarios/seed -X POST
expect_unauthorized /api/maps/token -H "Origin: $base_url"
expect_unauthorized /api/scenarios/unknown/runs/unknown/events
expect_unauthorized /api/config -H 'Authorization: Bearer invalid'
expect_unauthorized /api/config -H 'X-MS-CLIENT-PRINCIPAL: spoofed'

echo "Auth boundary verified: discovery/readiness available; anonymous, invalid and spoofed credentials rejected."
