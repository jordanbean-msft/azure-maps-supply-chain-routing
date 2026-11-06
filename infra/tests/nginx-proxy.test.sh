#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/../.."

for upstream in 127.0.0.1 api.test.azurecontainerapps.io; do
    expected="browser.local:8080"
    if [ "$upstream" != "127.0.0.1" ]; then
        expected="$upstream:8081"
    fi
    docker run --rm -i --entrypoint sh \
        --add-host api.test.azurecontainerapps.io:127.0.0.1 \
        nginxinc/nginx-unprivileged:stable-alpine -eu -c '
        cat > /tmp/proxy-template
        export API_INTERNAL_URL="http://$1:8081"
        envsubst '\''${API_INTERNAL_URL}'\'' < /tmp/proxy-template > /tmp/proxy-server
        cat > /tmp/proxy-nginx.conf <<'\''CONF'\''
pid /tmp/proxy-nginx.pid;
error_log stderr warn;
events {}
http {
    access_log off;
    include /tmp/proxy-server;
    server {
        listen 8081;
        location / {
            return 200 "$http_host|$http_origin";
        }
    }
}
CONF
        nginx -c /tmp/proxy-nginx.conf
        actual="$(wget -qO- --header "Host: browser.local:8080" \
            --header "Origin: http://browser.local:8080" \
            http://127.0.0.1:8080/api/check)"
        test "$actual" = "$2|http://browser.local:8080"
        printf "Proxy Host and Origin verified for %s\n" "$1"
        nginx -s quit -c /tmp/proxy-nginx.conf
    ' _ "$upstream" "$expected" < frontend/nginx/default.conf.template
done
