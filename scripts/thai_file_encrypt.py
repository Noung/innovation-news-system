#!/usr/bin/env python3
"""Retired unsafe utility.

The previous implementation did not encrypt file contents and exposed a
reversible password. It must not be used for backups or credentials.
"""

import sys


def main() -> int:
    print(
        'RETIRED: thai_file_encrypt.py did not provide authenticated encryption. '
        'Use the organization-approved encrypted backup mechanism.',
        file=sys.stderr,
    )
    return 78


if __name__ == '__main__':
    raise SystemExit(main())
