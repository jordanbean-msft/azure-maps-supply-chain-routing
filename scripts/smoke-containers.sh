#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."

container_engine="${CONTAINER_ENGINE:-podman}"
api_image="${API_IMAGE:-localhost/supply-chain-api:local}"
web_image="${WEB_IMAGE:-localhost/supply-chain-web:local}"
api=""
web=""

cleanup() {
    set +e
    if [ -n "$web" ]; then "$container_engine" rm -f "$web" >/dev/null; fi
    if [ -n "$api" ]; then "$container_engine" rm -f "$api" >/dev/null; fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

network_mode=bridge
if [ "$container_engine" = podman ]; then network_mode=slirp4netns; fi
api="$("$container_engine" create --network "$network_mode" \
    -p 127.0.0.1::8000 -p 127.0.0.1::8080 \
    -e APP_MODE=demo -e AUTH_ENABLED=false "$api_image")"
"$container_engine" start "$api" >/dev/null
web="$("$container_engine" create --network "container:$api" \
    -e API_INTERNAL_URL=http://127.0.0.1:8000 "$web_image")"
"$container_engine" start "$web" >/dev/null
api_port="$("$container_engine" port "$api" 8000/tcp)"
web_port="$("$container_engine" port "$api" 8080/tcp)"

for endpoint in "http://$api_port/health/live" \
    "http://$web_port/health/web" "http://$web_port/health" \
    "http://$web_port/api/config"; do
    ready=false
    for attempt in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
        if curl --fail --silent --show-error --max-time 3 "$endpoint"; then
            ready=true
            break
        fi
        sleep 2
    done
    if [ "$ready" != true ]; then
        "$container_engine" logs "$api"
        "$container_engine" logs "$web"
        exit 1
    fi
    printf '\nVerified %s\n' "$endpoint"
done
