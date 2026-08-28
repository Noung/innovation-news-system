#!/bin/bash
# ====================================
# PM2 Setup Script for PROD (192.168.160.19)
# ====================================

set -e

echo "========================================"
echo "PM2 Setup for Innovation News (PROD)"
echo "========================================"
echo ""

# Dependency installation is intentionally separate and version-controlled.
if ! command -v pm2 >/dev/null 2>&1; then
    echo "ERROR: PM2 is not installed. Install the approved PM2 version first."
    exit 1
fi

# Verify PM2 installation
echo "PM2 version: $(pm2 --version)"
echo ""

# Create logs directory
mkdir -p /home/kittisak/.openclaw/workspace/logs

# Start PM2 with ecosystem config
echo "========================================"
echo "Starting PM2 Applications"
echo "========================================"
cd /home/kittisak/.openclaw/workspace/fetch-innovation-news

# Remove only legacy Innovation News scheduler processes. Other PM2 apps on the
# host must remain untouched. Scheduling is owned by OS cron.
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

# Start/reload only the Innovation News API process.
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
pm2 save

echo ""
echo "========================================"
echo "PM2 Startup Configuration"
echo "========================================"
echo "Startup registration is intentionally manual. Run 'pm2 startup', review the generated command, then run 'pm2 save'."

echo ""
echo "========================================"
echo "Setup Complete!"
echo "========================================"
echo ""
echo "API Server: innovation-news-api (PM2)"
echo "PM2 Dashboard: pm2 monit"
echo "PM2 Logs: pm2 logs"
echo ""
echo "To restart: pm2 restart innovation-news-api"
echo "To stop: pm2 stop innovation-news-api"
echo "To view logs: pm2 logs innovation-news-api --lines 100"
echo ""
