#!/usr/bin/env bash
set -euo pipefail

base_url="${1:-http://127.0.0.1:8000}"
base_url="${base_url%/}"
headers="$(mktemp)"
scenario_id=""

http() {
  curl --connect-timeout 5 --max-time 20 "$@"
}

cleanup() {
  if [ -n "$scenario_id" ]; then
    http --silent --show-error --fail -D "$headers" \
      "$base_url/api/scenarios/$scenario_id" >/dev/null || true
    etag="$(awk 'tolower($1) == "etag:" {sub("\r$", "", $2); print $2}' "$headers")"
    if [ -n "$etag" ]; then
      http --silent --show-error --fail -X DELETE \
        -H "If-Match: $etag" "$base_url/api/scenarios/$scenario_id" >/dev/null || true
    fi
  fi
  rm -f "$headers"
}
trap cleanup EXIT

http --silent --show-error --fail "$base_url/health/ready" >/dev/null
config="$(http --silent --show-error --fail "$base_url/api/config")"
scenario="$(http --silent --show-error --fail -X POST "$base_url/api/scenarios/seed")"
scenario_id="$(jq -er '.id' <<< "$scenario")"
run="$(http --silent --show-error --fail -X POST \
  -H "Idempotency-Key: smoke-$scenario_id" \
  "$base_url/api/scenarios/$scenario_id/optimize")"
run_id="$(jq -er '.id' <<< "$run")"

for attempt in $(seq 1 90); do
  run="$(http --silent --show-error --fail \
    "$base_url/api/scenarios/$scenario_id/runs/$run_id")"
  status="$(jq -er '.status' <<< "$run")"
  case "$status" in
    completed) break ;;
    failed|infeasible)
      jq '{status, error, warnings}' <<< "$run" >&2
      exit 1
      ;;
  esac
  sleep 2
done

jq -e '.status == "completed" and (.allocations | length > 0) and
  (.routes | length > 0) and .total_cost >= 0' <<< "$run" >/dev/null
supply="$(jq '[.locations[] | select(.kind == "supplier") | .quantity] | add' <<< "$scenario")"
jq -e --argjson supply "$supply" \
  '([.allocations[].quantity] | add) == $supply' <<< "$run" >/dev/null

events="$(http --silent --show-error --fail --max-time 10 \
  "$base_url/api/scenarios/$scenario_id/runs/$run_id/events")"
if ! grep -q '^event: progress' <<< "$events"; then
  echo "No persisted progress event received" >&2
  exit 1
fi

jq -n --argjson config "$config" --argjson run "$run" \
  '{mode: $config.mode, source: $config.routing_source,
    status: $run.status, routes: ($run.routes | length),
    allocations: ($run.allocations | length), total_cost: $run.total_cost}'
