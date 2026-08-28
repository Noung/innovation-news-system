#!/bin/bash

# Phase 0 patch-bundle staging helper.
# Default mode is read-only. --apply uploads only to an isolated release
# directory, verifies a local-origin checksum manifest, and runs preflight
# checks. It never copies .env, promotes live files, edits cron, or restarts a
# service.

set -euo pipefail
umask 077

MODE="${1:---dry-run}"
if [[ "$MODE" != "--dry-run" && "$MODE" != "--apply" ]]; then
    echo "Usage: $0 [--dry-run|--apply]" >&2
    exit 64
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(dirname "$SCRIPT_DIR")"
PROD_HOST="${INNOVATION_NEWS_PROD_HOST:-192.168.160.19}"
PROD_PORT="${INNOVATION_NEWS_PROD_PORT:-24}"
PROD_USER="${INNOVATION_NEWS_PROD_USER:-kittisak}"
PROD_DIR="${INNOVATION_NEWS_PROD_DIR:-/home/kittisak/.openclaw/workspace}"
REMOTE="$PROD_USER@$PROD_HOST"

BUNDLE_FILES=(
    ".env.example"
    "scripts/.env.example"
    "scripts/fetch-innovation-news-mysql.py"
    "scripts/wordpress_integration.py"
    "scripts/line_integration.py"
    "scripts/fetch-it24hrs-news.py"
    "scripts/fetch-it24hrs-news.sh"
    "scripts/run-fetch-innovation-news.sh"
    "scripts/install-innovation-news-cron.sh"
    "scripts/trigger-ksstat.sh"
    "scripts/test-integrations.py"
    "scripts/audit-secret-sprawl.py"
    "scripts/update-wp-env.sh"
    "scripts/fix-openclaw-path.sh"
    "scripts/fix-telegram-prod.sh"
    "scripts/test-telegram-prod.sh"
    "scripts/master-deploy-fix.sh"
    "scripts/quick-deploy.sh"
    "scripts/thai_file_encrypt.py"
    "tests/test_phase0_runtime.py"
    "fetch-innovation-news/api/server.js"
    "fetch-innovation-news/api/package.json"
    "fetch-innovation-news/api/package-lock.json"
    "fetch-innovation-news/assets/admin.css"
    "fetch-innovation-news/tailwind.config.js"
    "fetch-innovation-news/public/index.html"
    "fetch-innovation-news/public/admin.css"
    "fetch-innovation-news/ecosystem.config.js"
    "fetch-innovation-news/pm2-setup.sh"
    "fetch-innovation-news/pm2-setup-prod.sh"
    "fetch-innovation-news/pm2-test.sh"
    "fetch-innovation-news/start.sh"
    "fetch-innovation-news/deploy-to-prod.sh"
    "docs/phase0-rollout.md"
    "docs/fetch-innovation-news/SCHEDULING.md"
    "docs/fetch-innovation-news/ADMIN_README.md"
    "docs/fetch-innovation-news/MIGRATIONS_AND_FLAGS.md"
    "sql/migrations/README.md"
)

echo "Innovation News Phase 0 patch staging"
echo "Target: $REMOTE:$PROD_DIR"
echo "Mode: ${MODE#--}"
echo "Secrets: the canonical root .env is validated remotely and never copied"

if [[ "$MODE" == "--dry-run" ]]; then
    echo "No network calls or file changes were made."
    echo "Planned patch files: ${#BUNDLE_FILES[@]}"
    echo "Review docs/phase0-rollout.md, then rerun with --apply only when authorized."
    exit 0
fi

for command_name in ssh scp sha256sum find sort xargs mktemp cp; do
    if ! command -v "$command_name" >/dev/null 2>&1; then
        echo "ERROR: required command is not available: $command_name" >&2
        exit 69
    fi
done

ssh -p "$PROD_PORT" "$REMOTE" "
    set -eu
    test -f '$PROD_DIR/.env'
    test -d '$PROD_DIR/scripts'
    test -d '$PROD_DIR/fetch-innovation-news/api'
    test \"\$(stat -c %U '$PROD_DIR/.env')\" = \"\$(id -un)\"
    root_mode=\$(stat -c %a '$PROD_DIR/.env')
    test \"\$root_mode\" = 600 || test \"\$root_mode\" = 400
    if [ -f '$PROD_DIR/scripts/.env' ]; then
        test \"\$(stat -c %U '$PROD_DIR/scripts/.env')\" = \"\$(id -un)\"
        legacy_mode=\$(stat -c %a '$PROD_DIR/scripts/.env')
        test \"\$legacy_mode\" = 600 || test \"\$legacy_mode\" = 400
    fi
" || {
    echo "ERROR: canonical root .env, permissions, owner, or target directories failed validation" >&2
    exit 78
}

LOCAL_STAGE_DIR="$(mktemp -d "${TMPDIR:-/tmp}/innovation-news-phase0.XXXXXX")"
cleanup() {
    rm -rf -- "$LOCAL_STAGE_DIR"
}
trap cleanup EXIT HUP INT TERM

for relative_path in "${BUNDLE_FILES[@]}"; do
    source_path="$WORKSPACE_DIR/$relative_path"
    if [[ ! -f "$source_path" ]]; then
        echo "ERROR: patch file is missing: $relative_path" >&2
        exit 66
    fi
    mkdir -p "$LOCAL_STAGE_DIR/$(dirname "$relative_path")"
    cp -p -- "$source_path" "$LOCAL_STAGE_DIR/$relative_path"
done

(
    cd "$LOCAL_STAGE_DIR"
    find . -type f ! -name SHA256SUMS -print0 \
        | LC_ALL=C sort -z \
        | xargs -0 sha256sum > SHA256SUMS
)

RELEASE_ID="phase0-$(date +%Y%m%d-%H%M%S)"
REMOTE_RELEASE_DIR="$PROD_DIR/releases/$RELEASE_ID"
ssh -p "$PROD_PORT" "$REMOTE" "
    set -eu
    umask 077
    mkdir -p '$PROD_DIR/releases'
    test ! -e '$REMOTE_RELEASE_DIR'
    mkdir '$REMOTE_RELEASE_DIR'
"
scp -P "$PROD_PORT" -r "$LOCAL_STAGE_DIR/." "$REMOTE:$REMOTE_RELEASE_DIR/"

ssh -p "$PROD_PORT" "$REMOTE" "
    set -eu
    cd '$REMOTE_RELEASE_DIR'
    sha256sum -c SHA256SUMS
    python3 -m py_compile \
        scripts/fetch-innovation-news-mysql.py \
        scripts/wordpress_integration.py \
        scripts/line_integration.py \
        scripts/fetch-it24hrs-news.py \
        scripts/test-integrations.py \
        scripts/audit-secret-sprawl.py \
        scripts/thai_file_encrypt.py
    node --check fetch-innovation-news/api/server.js
    node --check fetch-innovation-news/tailwind.config.js
    sh -n \
        scripts/fetch-it24hrs-news.sh \
        scripts/install-innovation-news-cron.sh \
        scripts/update-wp-env.sh \
        scripts/fix-openclaw-path.sh \
        scripts/fix-telegram-prod.sh \
        scripts/test-telegram-prod.sh \
        scripts/master-deploy-fix.sh \
        scripts/quick-deploy.sh
    bash -n \
        scripts/run-fetch-innovation-news.sh \
        scripts/trigger-ksstat.sh \
        fetch-innovation-news/start.sh \
        fetch-innovation-news/deploy-to-prod.sh \
        fetch-innovation-news/pm2-setup.sh \
        fetch-innovation-news/pm2-setup-prod.sh \
        fetch-innovation-news/pm2-test.sh
    INNOVATION_NEWS_ENV_FILE='$PROD_DIR/.env' \
        python3 -m unittest tests.test_phase0_runtime
    INNOVATION_NEWS_ENV_FILE='$PROD_DIR/.env' \
        node fetch-innovation-news/api/server.js --config-check
    chmod 700 \
        scripts/run-fetch-innovation-news.sh \
        scripts/install-innovation-news-cron.sh \
        scripts/trigger-ksstat.sh \
        fetch-innovation-news/start.sh \
        fetch-innovation-news/pm2-setup.sh \
        fetch-innovation-news/pm2-setup-prod.sh \
        fetch-innovation-news/pm2-test.sh
"

echo "Verified patch bundle uploaded to an isolated release directory."
echo "No live file, scheduler, environment file, database, or service was changed."
echo "Release: $REMOTE_RELEASE_DIR"
echo "Promotion is intentionally separate; follow docs/phase0-rollout.md in an approved maintenance window."
