#!/usr/bin/env python3
"""Find canonical environment secrets copied into workspace text files.

The report contains only environment key names and file paths. Secret values
are never printed, including when an exception occurs.
"""

import argparse
import os
import re
import tempfile
from pathlib import Path
from typing import Dict, Iterable, List


TEXT_SUFFIXES = {
    '.env', '.html', '.js', '.json', '.md', '.php', '.ps1', '.py', '.sh',
    '.sql', '.txt', '.yaml', '.yml',
}
EXCLUDED_DIRS = {'.git', 'node_modules', '__pycache__'}
SENSITIVE_MARKERS = ('TOKEN', 'PASSWORD', 'PASS', 'SECRET', 'API_KEY', 'APP_PASSWORD', 'CHAT_ID')
PLACEHOLDERS = {'', 'changeme', 'example', 'placeholder', 'your_password', 'your_token'}
QUERY_CREDENTIAL_PATTERN = re.compile(
    r'([?&](?:api[_-]?key|access[_-]?token|token|password|secret|client[_-]?secret|signature|sig|auth)=)([^&#\s\'\"]+)',
    re.IGNORECASE,
)
ENV_REFERENCE_PATTERN = re.compile(r'^\$\{[A-Z_][A-Z0-9_]*\}$')


def load_sensitive_values(env_file: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for raw_line in env_file.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if '_API_KEY_HEADER_' in key.upper() or key.upper().endswith('_API_KEY_HEADER'):
            continue
        if not any(marker in key.upper() for marker in SENSITIVE_MARKERS):
            continue
        if len(value) < 6 or value.lower() in PLACEHOLDERS:
            continue
        values[key] = value
    return values


def iter_text_files(root: Path, excluded_files: Iterable[Path]):
    excluded = {path.resolve() for path in excluded_files}
    for path in root.rglob('*'):
        if not path.is_file() or path.resolve() in excluded:
            continue
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        if path.stat().st_size > 5 * 1024 * 1024:
            continue
        if (
            path.suffix.lower() not in TEXT_SUFFIXES
            and path.name != '.env'
            and not path.name.startswith('.env.')
            and '.backup' not in path.name
            and '.bak' not in path.name
        ):
            continue
        yield path


def find_secret_sprawl(root: Path, env_file: Path, legacy_env_file: Path = None) -> Dict[str, List[Path]]:
    secret_values = load_sensitive_values(env_file)
    excluded_files = [env_file]
    if legacy_env_file:
        excluded_files.append(legacy_env_file)

    findings: Dict[str, List[Path]] = {}
    for path in iter_text_files(root, excluded_files):
        try:
            content = path.read_text(encoding='utf-8', errors='replace')
        except OSError:
            continue
        for key, secret_value in secret_values.items():
            if secret_value in content:
                findings.setdefault(key, []).append(path)
        if any(
            not ENV_REFERENCE_PATTERN.fullmatch(match.group(2))
            and not re.fullmatch(r'\{[A-Za-z_][A-Za-z0-9_]*\}', match.group(2))
            and match.group(2).strip().lower() not in {
                'secret', 'token', 'password', 'test', 'example', 'placeholder', '[redacted]'
            }
            for match in QUERY_CREDENTIAL_PATTERN.finditer(content)
        ):
            findings.setdefault('QUERY_STRING_CREDENTIAL', []).append(path)

    canonical_legacy_env = legacy_env_file or root / 'scripts' / '.env'
    if canonical_legacy_env.is_file() and load_sensitive_values(canonical_legacy_env):
        findings.setdefault('LEGACY_ENV_FILE', []).append(canonical_legacy_env)
    return findings


def format_report(root: Path, findings: Dict[str, List[Path]]) -> str:
    if not findings:
        return 'Secret sprawl audit: PASS (no canonical secret values found outside env files)'

    lines = ['Secret sprawl audit: FINDINGS']
    for key in sorted(findings):
        paths = sorted({path.relative_to(root).as_posix() for path in findings[key]})
        lines.append(f'- {key}: {len(paths)} file(s)')
        lines.extend(f'  - {path}' for path in paths)
    return '\n'.join(lines)


def redact_keys(env_file: Path, findings: Dict[str, List[Path]], keys: Iterable[str]) -> Dict[str, int]:
    """Atomically replace selected canonical values with ${KEY} placeholders."""
    secret_values = load_sensitive_values(env_file)
    counts: Dict[str, int] = {}
    for key in keys:
        if key not in secret_values:
            raise ValueError(f'Cannot redact unknown or empty sensitive key: {key}')
        paths = findings.get(key, [])
        for path in paths:
            if path.name == '.env' or path.name.startswith('.env.'):
                continue
            original = path.read_text(encoding='utf-8', errors='replace')
            updated = original.replace(secret_values[key], '${' + key + '}')
            if updated == original:
                continue
            original_mode = path.stat().st_mode
            fd, temporary_name = tempfile.mkstemp(prefix=f'.{path.name}.', dir=str(path.parent))
            try:
                with os.fdopen(fd, 'w', encoding='utf-8', newline='') as handle:
                    handle.write(updated)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.chmod(temporary_name, original_mode)
                os.replace(temporary_name, path)
            finally:
                if os.path.exists(temporary_name):
                    os.unlink(temporary_name)
            counts[key] = counts.get(key, 0) + 1
    return counts


def redact_query_credentials(findings: Dict[str, List[Path]]) -> int:
    count = 0
    for path in findings.get('QUERY_STRING_CREDENTIAL', []):
        if (
            path.suffix.lower() not in {'.sql', '.md', '.txt'}
            and '.backup' not in path.name
            and '.bak' not in path.name
        ):
            continue
        original = path.read_text(encoding='utf-8', errors='replace')
        updated = QUERY_CREDENTIAL_PATTERN.sub(
            lambda match: (
                match.group(0)
                if ENV_REFERENCE_PATTERN.fullmatch(match.group(2))
                else match.group(1) + '${QUERY_STRING_CREDENTIAL}'
            ),
            original,
        )
        if updated == original:
            continue
        original_mode = path.stat().st_mode
        fd, temporary_name = tempfile.mkstemp(prefix=f'.{path.name}.', dir=str(path.parent))
        try:
            with os.fdopen(fd, 'w', encoding='utf-8', newline='') as handle:
                handle.write(updated)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary_name, original_mode)
            os.replace(temporary_name, path)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)
        count += 1
    return count


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--env-file', type=Path)
    parser.add_argument(
        '--redact-key',
        action='append',
        default=[],
        help='Replace this key value outside env files with a ${KEY} placeholder',
    )
    parser.add_argument(
        '--redact-query-credentials',
        action='store_true',
        help='Replace credential-like query values in text files with a placeholder',
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.workspace.resolve()
    env_file = (args.env_file or root / '.env').resolve()
    if not env_file.is_file():
        print('Secret sprawl audit: ERROR (canonical env file not found)')
        return 2

    findings = find_secret_sprawl(root, env_file)
    if args.redact_key:
        try:
            counts = redact_keys(env_file, findings, args.redact_key)
        except ValueError as exc:
            print(f'Secret sprawl audit: ERROR ({exc})')
            return 2
        for key in sorted(counts):
            print(f'Redacted {key} from {counts[key]} file(s)')
        findings = find_secret_sprawl(root, env_file)
    if args.redact_query_credentials:
        redacted_count = redact_query_credentials(findings)
        print(f'Redacted query-string credentials from {redacted_count} file(s)')
        findings = find_secret_sprawl(root, env_file)
    print(format_report(root, findings))
    return 0 if not findings else 1


if __name__ == '__main__':
    raise SystemExit(main())
