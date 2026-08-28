#!/bin/bash

# Compatibility wrapper. The Python implementation owns environment parsing
# and behavior so shell sourcing cannot interpret secret values as code.

set -u
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="${INNOVATION_NEWS_WORKSPACE_DIR:-$(dirname "$SCRIPT_DIR")}" 

if [ -n "${INNOVATION_NEWS_ENV_FILE:-}" ]; then
    ENV_FILE="$INNOVATION_NEWS_ENV_FILE"
elif [ -f "$WORKSPACE_DIR/.env" ]; then
    ENV_FILE="$WORKSPACE_DIR/.env"
else
    ENV_FILE="$SCRIPT_DIR/.env"
fi

if [ ! -f "$ENV_FILE" ]; then
    echo "Configuration file not found: $ENV_FILE" >&2
    exit 78
fi

export INNOVATION_NEWS_WORKSPACE_DIR="$WORKSPACE_DIR"
export INNOVATION_NEWS_ENV_FILE="$ENV_FILE"

PYTHON_BIN="${PYTHON_BIN:-python3}"
exec "$PYTHON_BIN" "$SCRIPT_DIR/fetch-it24hrs-news.py"
