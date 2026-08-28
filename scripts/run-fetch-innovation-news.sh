#!/bin/bash

set -u
umask 077

# Cron job wrapper for fetch-innovation-news-mysql.py
# Uses relative paths by default and supports environment overrides.

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DEFAULT_WORKSPACE_DIR="$( dirname "${SCRIPT_DIR}" )"
WORKSPACE_DIR="${INNOVATION_NEWS_WORKSPACE_DIR:-${DEFAULT_WORKSPACE_DIR}}"

if [ -n "${INNOVATION_NEWS_ENV_FILE:-}" ]; then
    ENV_FILE="${INNOVATION_NEWS_ENV_FILE}"
elif [ -f "${WORKSPACE_DIR}/.env" ]; then
    ENV_FILE="${WORKSPACE_DIR}/.env"
else
    # Temporary rollback compatibility. Remove after PROD has used root .env
    # successfully through at least one scheduled cycle.
    ENV_FILE="${SCRIPT_DIR}/.env"
fi

MAIN_SCRIPT="${INNOVATION_NEWS_MAIN_SCRIPT:-${SCRIPT_DIR}/fetch-innovation-news-mysql.py}"
LOG_DIR="${INNOVATION_NEWS_LOG_DIR:-${WORKSPACE_DIR}/logs}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

export INNOVATION_NEWS_WORKSPACE_DIR="${WORKSPACE_DIR}"
export INNOVATION_NEWS_ENV_FILE="${ENV_FILE}"

if [ ! -f "${ENV_FILE}" ]; then
    echo "Configuration file not found: ${ENV_FILE}" >&2
    exit 78
fi

mkdir -p "${LOG_DIR}"

"${PYTHON_BIN}" "${MAIN_SCRIPT}" >> "${LOG_DIR}/cron-innovation-news-mysql.log" 2>&1
