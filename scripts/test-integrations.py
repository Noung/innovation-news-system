#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script for Telegram, WordPress, and LINE integrations
"""

import sys
import os
import json
import re
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

# Add scripts directory to path
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

# Load env vars
def load_env_file(env_path: Path) -> bool:
    if not env_path.exists():
        return False
    with env_path.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', key):
                    continue
                value = value.strip().strip('"').strip("'").strip()
                if key != 'INNOVATION_NEWS_ENV_FILE':
                    os.environ[key] = value
    return True

# Load one environment source only: explicit -> workspace root -> legacy file.
WORKSPACE_DIR = SCRIPT_DIR.parent
explicit_env_file = os.getenv('INNOVATION_NEWS_ENV_FILE', '').strip()
if explicit_env_file:
    explicit_env_path = Path(explicit_env_file).expanduser()
    if not load_env_file(explicit_env_path):
        raise SystemExit(
            f'Explicit INNOVATION_NEWS_ENV_FILE does not exist: {explicit_env_path}'
        )
else:
    loaded_env_file = False
    for env_candidate in (WORKSPACE_DIR / '.env', SCRIPT_DIR / '.env'):
        if load_env_file(env_candidate):
            loaded_env_file = True
            break
    if not loaded_env_file:
        raise SystemExit(
            'No Innovation News environment file found; expected workspace-root .env '
            'or temporary scripts/.env fallback'
        )

ALLOW_SEND = '--send' in sys.argv


def is_secure_credential_endpoint(raw_url: str) -> bool:
    parsed = urlparse(raw_url or '')
    sensitive_query_key = re.compile(
        r'^(?:api[_-]?key|access[_-]?token|token|password|secret|client[_-]?secret|auth)$',
        re.IGNORECASE,
    )
    return bool(
        parsed.scheme.lower() == 'https'
        and parsed.hostname
        and not parsed.username
        and not parsed.password
        and not any(
            sensitive_query_key.fullmatch(key or '')
            for key, _value in parse_qsl(parsed.query, keep_blank_values=True)
        )
    )

print("=" * 60)
print("INTEGRATION TEST")
print("=" * 60)

# ====================================
# Telegram Test
# ====================================
print("\n[TELEGRAM]")
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
OPENCLAW_BIN = os.getenv('OPENCLAW_BIN', 'openclaw')
ENABLE_TELEGRAM = os.getenv('ENABLE_TELEGRAM', '1').strip().lower() in {'1', 'true', 'yes', 'on'}

print(f"  ENABLE_TELEGRAM: {ENABLE_TELEGRAM}")
print(f"  TELEGRAM_TOKEN: {'✅ Set' if TELEGRAM_TOKEN else '❌ Not set'}")
print(f"  TELEGRAM_CHAT_ID: {'✅ Set' if TELEGRAM_CHAT_ID else '❌ Not set'}")
print(f"  OPENCLAW_BIN: {OPENCLAW_BIN}")

if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID and ALLOW_SEND:
    try:
        import subprocess
        test_msg = "🧪 Integration Test - Telegram OK!"
        cmd = [OPENCLAW_BIN, 'message', 'send', '--channel', 'telegram', '--target', TELEGRAM_CHAT_ID, '--message', test_msg]
        result = subprocess.run(cmd, capture_output=True, timeout=15, text=True)
        if result.returncode == 0:
            print(f"  ✅ Telegram Send: SUCCESS")
        else:
            print(f"  ❌ Telegram Send: FAILED - {result.stderr[-100:]}")
    except subprocess.TimeoutExpired:
        print(f"  ❌ Telegram Send: TIMEOUT (15s)")
    except Exception as e:
        print(f"  ❌ Telegram Send: ERROR - {str(e)}")
elif TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
    print("  ℹ️ Telegram send skipped (pass --send to authorize an external test message)")
else:
    print(f"  ⚠️ Telegram: Not configured")

# ====================================
# WordPress Test
# ====================================
print("\n[WORDPRESS]")
WP_API_URL = os.getenv('WP_API_URL', '').strip().rstrip('/')
if WP_API_URL and not is_secure_credential_endpoint(WP_API_URL):
    print("  ❌ WP_API_URL must use HTTPS")
    WP_API_URL = ''
WP_USERNAME = os.getenv('WP_USERNAME', '').strip()
WP_APP_PASSWORD = os.getenv('WP_APP_PASSWORD', '').strip()
WP_BENEFIT_TAXONOMY_REST_BASE = os.getenv(
    'WP_BENEFIT_TAXONOMY_REST_BASE',
    'organization-benefits'
).strip().strip('/')
ENABLE_WORDPRESS = os.getenv('ENABLE_WORDPRESS', '1').strip().lower() in {'1', 'true', 'yes', 'on'}
WP_CA_BUNDLE = os.getenv('WP_CA_BUNDLE', '').strip()
WP_VERIFY_TLS = WP_CA_BUNDLE if WP_CA_BUNDLE else True

print(f"  ENABLE_WORDPRESS: {ENABLE_WORDPRESS}")
print(f"  WP_API_URL: {'✅ Set' if WP_API_URL else '❌ Not set'}")
print(f"  WP_USERNAME: {'✅ Set' if WP_USERNAME else '❌ Not set'}")
print(f"  WP_APP_PASSWORD: {'✅ Set' if WP_APP_PASSWORD else '❌ Not set'}")

if all([WP_API_URL, WP_USERNAME, WP_APP_PASSWORD]):
    try:
        import requests
        from requests.auth import HTTPBasicAuth
        auth = HTTPBasicAuth(WP_USERNAME, WP_APP_PASSWORD)
        post_response = requests.get(
            f"{WP_API_URL}/wp/v2/innovation-tip",
            auth=auth,
            params={'per_page': 1},
            timeout=10,
            verify=WP_VERIFY_TLS
        )
        taxonomy_response = requests.get(
            f"{WP_API_URL}/wp/v2/{WP_BENEFIT_TAXONOMY_REST_BASE}",
            auth=auth,
            params={'per_page': 100},
            timeout=10,
            verify=WP_VERIFY_TLS
        )
        schema_response = requests.options(
            f"{WP_API_URL}/wp/v2/innovation-tip",
            auth=auth,
            timeout=10,
            verify=WP_VERIFY_TLS
        )
        taxonomy_terms = taxonomy_response.json() if taxonomy_response.status_code == 200 else []
        taxonomy_slugs = {
            term.get('slug')
            for term in taxonomy_terms
            if isinstance(term, dict)
        }
        schema_payload = schema_response.json() if schema_response.status_code == 200 else {}
        schema_properties = schema_payload.get('schema', {}).get('properties', {})

        from wordpress_integration import BENEFIT_TERM_SLUGS
        expected_slugs = set(BENEFIT_TERM_SLUGS.values())
        taxonomy_field_ready = WP_BENEFIT_TAXONOMY_REST_BASE in schema_properties
        vocabulary_ready = expected_slugs.issubset(taxonomy_slugs)

        if all([
            post_response.status_code == 200,
            taxonomy_response.status_code == 200,
            schema_response.status_code == 200,
            taxonomy_field_ready,
            vocabulary_ready,
        ]):
            print("  ✅ WordPress CPT + Benefit Taxonomy + 20 terms: SUCCESS")
        else:
            print(
                "  ❌ WordPress Connection: FAILED - "
                f"CPT HTTP {post_response.status_code}, "
                f"Taxonomy HTTP {taxonomy_response.status_code}, "
                f"Schema HTTP {schema_response.status_code}, "
                f"taxonomy field={'yes' if taxonomy_field_ready else 'no'}, "
                f"terms={len(expected_slugs & taxonomy_slugs)}/{len(expected_slugs)}"
            )
    except Exception as e:
        print(f"  ❌ WordPress Connection: ERROR - {str(e)}")
else:
    print(f"  ⚠️ WordPress: Not configured")

# ====================================
# LINE Test
# ====================================
print("\n[LINE]")
LINE_API_URL = os.getenv('LINE_API_URL', '').strip()
if LINE_API_URL and not is_secure_credential_endpoint(LINE_API_URL):
    print("  ❌ LINE_API_URL must use HTTPS")
    LINE_API_URL = ''
LINE_API_KEY = os.getenv('LINE_API_KEY', '').strip()
ENABLE_LINE = os.getenv('ENABLE_LINE', '1').strip().lower() in {'1', 'true', 'yes', 'on'}
LINE_CA_BUNDLE = os.getenv('LINE_CA_BUNDLE', '').strip()
LINE_VERIFY_TLS = LINE_CA_BUNDLE if LINE_CA_BUNDLE else True

print(f"  ENABLE_LINE: {ENABLE_LINE}")
print(f"  LINE_API_URL: {'✅ Set' if LINE_API_URL else '❌ Not set'}")
print(f"  LINE_API_KEY: {'✅ Set' if LINE_API_KEY else '❌ Not set'}")

if all([LINE_API_URL, LINE_API_KEY]) and ALLOW_SEND:
    try:
        import requests
        headers = {'Authorization': f"Bearer {LINE_API_KEY}", 'Content-Type': 'application/json; charset=utf-8'}
        # Test connection
        test_data = {'msg_detail': '🧪 Integration Test - LINE OK!'}
        binary_payload = json.dumps(test_data, ensure_ascii=False).encode('utf-8')
        response = requests.post(
            LINE_API_URL,
            headers=headers,
            data=binary_payload,
            timeout=10,
            verify=LINE_VERIFY_TLS,
        )
        if response.status_code == 200:
            result = response.json()
            if result.get('status') == 'success':
                print(f"  ✅ LINE Connection: SUCCESS")
            else:
                print(f"  ❌ LINE API Error: {result.get('message', 'Unknown')}")
        else:
            print(f"  ❌ LINE Connection: FAILED - HTTP {response.status_code}")
    except Exception as e:
        print(f"  ❌ LINE Connection: ERROR - {str(e)}")
elif all([LINE_API_URL, LINE_API_KEY]):
    print("  ℹ️ LINE send skipped (pass --send to authorize an external test message)")
else:
    print(f"  ⚠️ LINE: Not configured")

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
