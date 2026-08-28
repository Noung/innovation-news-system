#!/bin/bash

# Read-only Phase 0 PM2 configuration preflight.

set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(dirname "$SCRIPT_DIR")"
ECOSYSTEM="$SCRIPT_DIR/ecosystem.config.js"

test -f "$WORKSPACE_DIR/.env" || {
    echo "ERROR: canonical root .env is missing" >&2
    exit 78
}
test -f "$WORKSPACE_DIR/scripts/fetch-innovation-news-mysql.py"
test -f "$SCRIPT_DIR/api/server.js"
test -f "$ECOSYSTEM"

node --check "$SCRIPT_DIR/api/server.js"
node --check "$ECOSYSTEM"

if grep -Eq "cron_restart|name:[[:space:]]*['\"](innovation-news-fetcher|it24hrs-news-fetcher)" "$ECOSYSTEM"; then
    echo "ERROR: PM2 ecosystem still contains a scheduled fetcher" >&2
    exit 65
fi

if command -v pm2 >/dev/null 2>&1; then
    if ! PM2_JSON=$(pm2 jlist); then
        echo "ERROR: unable to read the PM2 process list" >&2
        exit 69
    fi
    if printf '%s\n' "$PM2_JSON" | grep -Eq '"name"[[:space:]]*:[[:space:]]*"(innovation-news-fetcher|it24hrs-news-fetcher)"'; then
        echo "ERROR: a legacy PM2 fetcher is still registered" >&2
        exit 65
    fi
    echo "PM2 runtime: no legacy fetcher registered"
else
    echo "PM2 runtime check skipped: approved PM2 version is not installed"
fi

echo "PM2 Phase 0 preflight: PASS (API-only ecosystem)"
