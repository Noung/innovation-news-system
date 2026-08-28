#!/bin/bash
# ====================================
# PM2 Setup and Startup Script
# ====================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(dirname "$SCRIPT_DIR")"

echo "========================================"
echo "PM2 Setup for Innovation News"
echo "========================================"
echo ""

# Check if PM2 is installed. Dependency installation is intentionally kept
# separate from service changes so this script cannot pull an unpinned release.
if ! command -v pm2 &> /dev/null; then
    echo "ERROR: PM2 is not installed. Install the approved PM2 version first."
    exit 1
else
    echo "PM2 found: $(pm2 --version)"
fi

echo ""
echo "========================================"
echo "Starting PM2 Applications"
echo "========================================"
echo ""

# Navigate to ecosystem config
cd "$SCRIPT_DIR"

# Remove only the two legacy scheduler processes. OS cron is the sole owner of
# scheduled fetches; deleting these names also prevents pm2 save/resurrect from
# restoring a second scheduler after reboot.
for legacy_process in innovation-news-fetcher it24hrs-news-fetcher; do
    if pm2 describe "$legacy_process" >/dev/null 2>&1; then
        pm2 delete "$legacy_process"
    fi
done

PM2_JSON=$(pm2 jlist)
if printf '%s\n' "$PM2_JSON" | grep -Eq '"name"[[:space:]]*:[[:space:]]*"(innovation-news-fetcher|it24hrs-news-fetcher)"'; then
    echo "ERROR: a legacy PM2 fetcher is still registered" >&2
    exit 65
fi

# Start/reload only this project's API. Never stop or delete unrelated apps.
echo "Starting/Restarting Innovation News API..."
pm2 startOrReload ecosystem.config.js --only innovation-news-api --update-env

echo ""
echo "========================================"
echo "PM2 Status"
echo "========================================"
pm2 status

echo ""
echo "========================================"
echo "PM2 Save"
echo "========================================"
echo "Saving PM2 process list..."
pm2 save

echo ""
echo "========================================"
echo "PM2 Startup Configuration"
echo "========================================"
echo "Startup registration is a separate privileged operation."
echo "Run 'pm2 startup' manually, review its command, then run 'pm2 save'."

echo ""
echo "========================================"
echo "Setup Complete!"
echo "========================================"
echo ""
echo "API Server: innovation-news-api (PM2)"
echo "Dashboard: pm2 monit"
echo "Logs: pm2 logs innovation-news-api"
echo ""
