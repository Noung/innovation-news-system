#!/bin/bash
# Manual foreground startup for Innovation News Admin.

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "${SCRIPT_DIR}/api"

export PORT="${PORT:-3001}"

if [ ! -d "node_modules" ]; then
    echo "ERROR: dependencies are not installed; run the reviewed npm ci step first." >&2
    exit 69
fi

echo "Starting Innovation News Admin on the configured loopback bind address."
echo "External access must use the approved HTTPS reverse proxy."
exec npm start
