#!/bin/bash
# ====================================
# Innovation News Fetcher (Daily at 09:00)
# ====================================
# Legacy compatibility wrapper for manual execution only.
# Scheduled execution is owned exclusively by OS cron.

set -e
set -o pipefail

SCRIPT_DIR="/home/kittisak/.openclaw/workspace/scripts"
LOG_FILE="/home/kittisak/.openclaw/workspace/logs/cron-innovation-news-mysql.log"

echo "========================================" | tee -a "$LOG_FILE"
echo "Innovation News Fetcher Started" | tee -a "$LOG_FILE"
echo "Time: $(date '+%Y-%m-%d %H:%M:%S %Z')" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

# Run the fetch script
cd "$SCRIPT_DIR"
/usr/bin/python3 fetch-innovation-news-mysql.py 2>&1 | tee -a "$LOG_FILE"

echo "========================================" | tee -a "$LOG_FILE"
echo "Innovation News Fetcher Completed" | tee -a "$LOG_FILE"
echo "Time: $(date '+%Y-%m-%d %H:%M:%S %Z')" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
