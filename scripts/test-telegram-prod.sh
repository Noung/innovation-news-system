#!/bin/sh

echo "RETIRED: use 'python3 scripts/test-integrations.py' for a non-sending preflight." >&2
echo "Only pass --send after an external test message has been explicitly authorized." >&2
exit 78
