#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create an offline manual WordPress benefit backfill checklist.

Safety boundary:
- Reads a complete, checksummed PLAN JSON from local disk.
- Performs no HTTP requests and reads no environment credentials.
- Exports only records whose PLAN status is ``auto_ready``.
- Produces a checklist CSV; it is never a WordPress import file.
"""

import argparse
import csv
import hashlib
import io
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.parse import urlencode, urlsplit, urlunsplit

from benefit_classifier import (
    BENEFIT_TERM_SLUGS,
    BENEFITS_PER_ARTICLE,
    CLASSIFIER_VERSION,
)


WORKLIST_VERSION = '1.0.0'
SUPPORTED_PLAN_SCHEMA_VERSION = '2'
SUPPORTED_CLASSIFIER_MODE = 'strict'
EXPECTED_POST_TYPE = 'innovation-tip'
EXPECTED_TAXONOMY = 'organization_benefit'
EXPECTED_TAXONOMY_REST_BASE = 'organization-benefits'
KNOWN_PLAN_STATUSES = {'auto_ready', 'review', 'skip_existing'}
DEFAULT_BATCH_SIZE = 5
DEFAULT_MAX_PLAN_AGE_HOURS = 24
SHA256_RE = re.compile(r'^[0-9a-f]{64}$')
RUN_ID_RE = re.compile(r'^benefit-backfill-plan-\d{8}T\d{6}Z$')
ISO_UTC_RE = re.compile(
    r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})'
    r'(?:\.(\d{1,6}))?'
    r'(Z|[+-]\d{2}:\d{2})$'
)

CSV_FIELDS = [
    'work_order',
    'batch',
    'workflow_status',
    'reviewer',
    'wp_post_id',
    'title',
    'wp_admin_edit_url',
    'rest_verification_url',
    'public_url',
    'benefit_1',
    'benefit_1_slug',
    'benefit_1_term_id',
    'benefit_2',
    'benefit_2_slug',
    'benefit_2_term_id',
    'benefit_3',
    'benefit_3_slug',
    'benefit_3_term_id',
    'legacy_source',
    'summary_source',
    'observed_modified_gmt',
    'wp_updated_at',
    'rest_verified',
    'verified_at',
    'notes',
    'source_plan_run_id',
    'source_plan_sha256',
]


class ManualWorklistError(RuntimeError):
    """Raised when a safe manual checklist cannot be produced."""


def _reject_duplicate_json_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ManualWorklistError(
                'Plan JSON contains a duplicate key: {0}'.format(key)
            )
        result[key] = value
    return result


def _is_positive_int(value) -> bool:
    return type(value) is int and value > 0


def _safe_csv_cell(value) -> str:
    if isinstance(value, (list, dict)):
        value = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(',', ':'),
        )
    text = str(value if value is not None else '')
    text = text.replace('\x00', '').replace('\r', ' ').replace('\n', ' ')
    if text.lstrip().startswith(('=', '+', '-', '@')):
        text = "'" + text
    return text


def _canonical_records_sha256(records: List[Dict[str, object]]) -> str:
    payload = json.dumps(
        records,
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
    ).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()


def _parse_plan_datetime(value: str) -> datetime:
    if not isinstance(value, str):
        raise ManualWorklistError('Plan generated_at_utc is invalid')
    match = ISO_UTC_RE.fullmatch(value)
    if not match:
        raise ManualWorklistError('Plan generated_at_utc is invalid')
    try:
        timestamp = match.group(1)
        parsed = datetime(
            int(timestamp[0:4]),
            int(timestamp[5:7]),
            int(timestamp[8:10]),
            int(timestamp[11:13]),
            int(timestamp[14:16]),
            int(timestamp[17:19]),
        )
        fraction = match.group(2) or ''
        microsecond = int(fraction.ljust(6, '0')) if fraction else 0
        zone_text = match.group(3)
        if zone_text == 'Z':
            zone = timezone.utc
        else:
            sign = 1 if zone_text[0] == '+' else -1
            hours = int(zone_text[1:3])
            minutes = int(zone_text[4:6])
            if hours > 23 or minutes > 59:
                raise ValueError('invalid timezone offset')
            zone = timezone(
                sign * timedelta(hours=hours, minutes=minutes)
            )
        return parsed.replace(
            microsecond=microsecond,
            tzinfo=zone,
        ).astimezone(timezone.utc)
    except (TypeError, ValueError) as exc:
        raise ManualWorklistError('Plan generated_at_utc is invalid') from exc


def load_verified_plan(plan_path: Path) -> Tuple[Dict[str, object], str, Path]:
    """Read a PLAN only when its adjacent checksum sidecar is exact."""
    resolved = plan_path.expanduser().resolve()
    if resolved.suffix.lower() != '.json':
        raise ManualWorklistError('Plan path must end with .json')
    if not resolved.is_file():
        raise ManualWorklistError('Plan JSON not found: {0}'.format(resolved))

    checksum_path = resolved.with_suffix('.sha256')
    if not checksum_path.is_file():
        raise ManualWorklistError(
            'Plan checksum sidecar not found: {0}'.format(checksum_path)
        )

    try:
        checksum_text = checksum_path.read_text(encoding='ascii')
    except (OSError, UnicodeError) as exc:
        raise ManualWorklistError(
            'Could not read plan checksum sidecar'
        ) from exc

    match = re.fullmatch(
        r'([0-9a-f]{64})  ([^\r\n/\\]+)\r?\n?',
        checksum_text,
    )
    if not match or match.group(2) != resolved.name:
        raise ManualWorklistError(
            'Plan checksum sidecar must contain the exact JSON filename'
        )

    try:
        raw_plan = resolved.read_bytes()
    except OSError as exc:
        raise ManualWorklistError('Could not read plan JSON') from exc
    actual_sha256 = hashlib.sha256(raw_plan).hexdigest()
    if actual_sha256 != match.group(1):
        raise ManualWorklistError('Plan JSON SHA256 does not match its sidecar')

    try:
        plan = json.loads(
            raw_plan.decode('utf-8'),
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except ManualWorklistError:
        raise
    except (UnicodeError, ValueError) as exc:
        raise ManualWorklistError('Plan JSON is not valid UTF-8 JSON') from exc
    if not isinstance(plan, dict):
        raise ManualWorklistError('Plan JSON root must be an object')
    return plan, actual_sha256, resolved


def _normalize_api_url(value: str) -> Tuple[str, object]:
    if not isinstance(value, str) or not value.strip():
        raise ManualWorklistError('WordPress API URL must be a non-empty string')
    try:
        parts = urlsplit(value.strip())
        hostname = parts.hostname
        parts.port
    except ValueError as exc:
        raise ManualWorklistError('WordPress API URL is invalid') from exc
    if (
        parts.scheme.lower() != 'https'
        or not parts.netloc
        or not hostname
        or parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
    ):
        raise ManualWorklistError(
            'WordPress API URL must be a credential-free HTTPS URL'
        )
    normalized_path = parts.path.rstrip('/')
    if not normalized_path.endswith('/wp-json/wp/v2'):
        raise ManualWorklistError(
            'WordPress API URL must end with /wp-json/wp/v2'
        )
    normalized = urlunsplit(
        (parts.scheme.lower(), parts.netloc, normalized_path, '', '')
    )
    return normalized, parts._replace(path=normalized_path)


def _controlled_terms_by_slug(metadata: Dict[str, object]) -> Dict[str, Dict[str, object]]:
    snapshot = metadata.get('term_snapshot')
    if not isinstance(snapshot, list) or len(snapshot) != len(BENEFIT_TERM_SLUGS):
        raise ManualWorklistError(
            'Plan term snapshot must contain the exact controlled vocabulary'
        )

    by_slug = {}
    term_ids = set()
    for term in snapshot:
        if not isinstance(term, dict):
            raise ManualWorklistError('Plan term snapshot contains a non-object')
        term_id = term.get('id')
        name = term.get('name')
        slug = term.get('slug')
        if (
            not _is_positive_int(term_id)
            or not isinstance(name, str)
            or not isinstance(slug, str)
            or slug in by_slug
            or term_id in term_ids
        ):
            raise ManualWorklistError(
                'Plan term snapshot contains invalid or duplicate terms'
            )
        by_slug[slug] = {'id': term_id, 'name': name, 'slug': slug}
        term_ids.add(term_id)

    expected_slugs = set(BENEFIT_TERM_SLUGS.values())
    if set(by_slug) != expected_slugs:
        raise ManualWorklistError(
            'Plan term snapshot slugs differ from the controlled vocabulary'
        )
    for expected_name, expected_slug in BENEFIT_TERM_SLUGS.items():
        if by_slug[expected_slug]['name'] != expected_name:
            raise ManualWorklistError(
                'Plan term name/slug mapping differs from the controlled vocabulary'
            )
    return by_slug


def validate_full_plan(
    plan: Dict[str, object],
    *,
    expected_api_url: str,
    expected_count: int,
    max_plan_age_hours: int = DEFAULT_MAX_PLAN_AGE_HOURS,
    now_utc: datetime = None,
) -> Tuple[List[Dict[str, object]], Dict[str, object], str]:
    """Validate the complete manifest and return exact auto-ready records."""
    metadata = plan.get('metadata')
    records = plan.get('records')
    if not isinstance(metadata, dict) or not isinstance(records, list):
        raise ManualWorklistError('Plan must contain metadata and records')

    required_metadata = {
        'schema_version': SUPPORTED_PLAN_SCHEMA_VERSION,
        'mode': 'plan_read_only',
        'post_type': EXPECTED_POST_TYPE,
        'taxonomy': EXPECTED_TAXONOMY,
        'taxonomy_rest_base': EXPECTED_TAXONOMY_REST_BASE,
        'classifier_version': CLASSIFIER_VERSION,
        'classifier_mode': SUPPORTED_CLASSIFIER_MODE,
    }
    for key, expected in required_metadata.items():
        if metadata.get(key) != expected:
            raise ManualWorklistError(
                'Plan metadata mismatch for {0}'.format(key)
            )
    if metadata.get('truncated') is not False:
        raise ManualWorklistError('Manual worklist requires an untruncated full plan')

    plan_api_url, normalized_parts = _normalize_api_url(
        metadata.get('site_api_url')
    )
    normalized_expected, _ = _normalize_api_url(expected_api_url)
    if plan_api_url != normalized_expected:
        raise ManualWorklistError(
            'Plan WordPress site does not match --expected-api-url'
        )

    run_id = metadata.get('run_id')
    if not isinstance(run_id, str) or not RUN_ID_RE.fullmatch(run_id):
        raise ManualWorklistError('Plan run_id is invalid')
    generated_at = _parse_plan_datetime(metadata.get('generated_at_utc'))
    if generated_at.strftime(
        'benefit-backfill-plan-%Y%m%dT%H%M%SZ'
    ) != run_id:
        raise ManualWorklistError(
            'Plan run_id does not match generated_at_utc'
        )
    if (
        type(max_plan_age_hours) is not int
        or max_plan_age_hours < 1
        or max_plan_age_hours > 168
    ):
        raise ManualWorklistError(
            'Maximum plan age must be between 1 and 168 hours'
        )
    now_utc = now_utc or datetime.now(timezone.utc)
    if not isinstance(now_utc, datetime) or now_utc.tzinfo is None:
        raise ManualWorklistError('Current UTC time must be timezone-aware')
    age_seconds = (
        now_utc.astimezone(timezone.utc) - generated_at
    ).total_seconds()
    if age_seconds < -300:
        raise ManualWorklistError('Plan generation time is in the future')
    if age_seconds > max_plan_age_hours * 3600:
        raise ManualWorklistError(
            'Plan is older than {0} hours; create a fresh read-only plan'.format(
                max_plan_age_hours
            )
        )

    records_sha256 = metadata.get('records_sha256')
    if (
        not isinstance(records_sha256, str)
        or not SHA256_RE.fullmatch(records_sha256)
        or records_sha256 != _canonical_records_sha256(records)
    ):
        raise ManualWorklistError('Plan records SHA256 is invalid')

    counts = metadata.get('counts')
    if not isinstance(counts, dict):
        raise ManualWorklistError('Plan counts are missing')
    count_keys = ('wp_total', 'included', 'auto_ready', 'review', 'skip_existing')
    for key in count_keys:
        if type(counts.get(key)) is not int or counts[key] < 0:
            raise ManualWorklistError('Plan count is invalid: {0}'.format(key))
    if counts['included'] != len(records) or counts['wp_total'] != len(records):
        raise ManualWorklistError(
            'Manual worklist requires a complete plan containing every WordPress post'
        )

    term_by_slug = _controlled_terms_by_slug(metadata)
    seen_post_ids = set()
    calculated_counts = {status: 0 for status in KNOWN_PLAN_STATUSES}
    auto_ready = []
    for record in records:
        if not isinstance(record, dict):
            raise ManualWorklistError('Plan contains a non-object record')
        post_id = record.get('wp_post_id')
        if not _is_positive_int(post_id) or post_id in seen_post_ids:
            raise ManualWorklistError('Plan contains an invalid or duplicate post ID')
        seen_post_ids.add(post_id)

        plan_status = record.get('plan_status')
        if plan_status not in KNOWN_PLAN_STATUSES:
            raise ManualWorklistError(
                'Plan contains an unknown record status for post {0}'.format(post_id)
            )
        calculated_counts[plan_status] += 1
        if plan_status != 'auto_ready':
            continue

        if record.get('status') != 'publish':
            raise ManualWorklistError(
                'Auto-ready post {0} is not published'.format(post_id)
            )
        if record.get('existing_term_ids') != []:
            raise ManualWorklistError(
                'Auto-ready post {0} already has taxonomy terms'.format(post_id)
            )
        if record.get('legacy_conflict') is not False:
            raise ManualWorklistError(
                'Auto-ready post {0} has conflicting legacy data'.format(post_id)
            )
        if record.get('review_reasons') != []:
            raise ManualWorklistError(
                'Auto-ready post {0} unexpectedly requires review'.format(post_id)
            )

        names = record.get('suggested_names')
        slugs = record.get('suggested_slugs')
        term_ids = record.get('suggested_term_ids')
        legacy_names = record.get('legacy_benefits')
        if not all(isinstance(value, list) for value in (
            names,
            slugs,
            term_ids,
            legacy_names,
        )):
            raise ManualWorklistError(
                'Auto-ready post {0} has invalid term arrays'.format(post_id)
            )
        if (
            len(names) != BENEFITS_PER_ARTICLE
            or len(slugs) != BENEFITS_PER_ARTICLE
            or len(term_ids) != BENEFITS_PER_ARTICLE
            or len(set(names)) != BENEFITS_PER_ARTICLE
            or len(set(slugs)) != BENEFITS_PER_ARTICLE
            or len(set(term_ids)) != BENEFITS_PER_ARTICLE
            or names != legacy_names
        ):
            raise ManualWorklistError(
                'Auto-ready post {0} does not have three exact legacy terms'.format(
                    post_id
                )
            )
        for name, slug, term_id in zip(names, slugs, term_ids):
            if (
                not isinstance(name, str)
                or not isinstance(slug, str)
                or not _is_positive_int(term_id)
                or BENEFIT_TERM_SLUGS.get(name) != slug
                or slug not in term_by_slug
                or term_by_slug[slug]['id'] != term_id
            ):
                raise ManualWorklistError(
                    'Auto-ready post {0} has a mismatched term mapping'.format(post_id)
                )

        fallback_count = record.get('classifier_fallback_count')
        if type(fallback_count) is not int or fallback_count < 0:
            raise ManualWorklistError(
                'Auto-ready post {0} has invalid classifier diagnostics'.format(
                    post_id
                )
            )
        if (
            not isinstance(record.get('title'), str)
            or not record['title'].strip()
            or not isinstance(record.get('observed_modified_gmt'), str)
            or not record['observed_modified_gmt'].strip()
            or not isinstance(record.get('input_text_sha256'), str)
            or not SHA256_RE.fullmatch(record['input_text_sha256'])
            or not isinstance(record.get('permalink'), str)
            or not isinstance(record.get('legacy_source'), str)
            or not isinstance(record.get('summary_source'), str)
        ):
            raise ManualWorklistError(
                'Auto-ready post {0} is missing required source fields'.format(post_id)
            )
        auto_ready.append(record)

    for status, actual in calculated_counts.items():
        if counts[status] != actual:
            raise ManualWorklistError(
                'Plan count does not match records for status {0}'.format(status)
            )
    if len(auto_ready) != expected_count or counts['auto_ready'] != expected_count:
        raise ManualWorklistError(
            'Expected {0} auto-ready posts but the plan contains {1}'.format(
                expected_count,
                len(auto_ready),
            )
        )
    if not auto_ready:
        raise ManualWorklistError('Plan contains no auto-ready posts')

    auto_ready.sort(key=lambda item: item['wp_post_id'])
    return auto_ready, metadata, plan_api_url


def _site_urls(api_url: str, post_id: int) -> Tuple[str, str]:
    normalized, parts = _normalize_api_url(api_url)
    del normalized
    site_path = parts.path[:-len('/wp-json/wp/v2')].rstrip('/')
    admin_path = (site_path + '/wp-admin/post.php') or '/wp-admin/post.php'
    rest_path = (
        site_path
        + '/wp-json/wp/v2/'
        + EXPECTED_POST_TYPE
        + '/'
        + str(post_id)
    )
    edit_url = urlunsplit((
        parts.scheme,
        parts.netloc,
        admin_path,
        urlencode((('post', str(post_id)), ('action', 'edit'))),
        '',
    ))
    verification_url = urlunsplit((
        parts.scheme,
        parts.netloc,
        rest_path,
        urlencode((
            (
                '_fields',
                'id,title,organization-benefits,modified_gmt',
            ),
        )),
        '',
    ))
    return edit_url, verification_url


def build_worklist_bytes(
    records: List[Dict[str, object]],
    metadata: Dict[str, object],
    plan_sha256: str,
    *,
    batch_size: int,
) -> bytes:
    if type(batch_size) is not int or batch_size < 1 or batch_size > 100:
        raise ManualWorklistError('Batch size must be between 1 and 100')

    output = io.StringIO(newline='')
    writer = csv.DictWriter(
        output,
        fieldnames=CSV_FIELDS,
        lineterminator='\n',
    )
    writer.writeheader()
    for index, record in enumerate(records, start=1):
        names = record['suggested_names']
        slugs = record['suggested_slugs']
        term_ids = record['suggested_term_ids']
        edit_url, verification_url = _site_urls(
            metadata['site_api_url'],
            record['wp_post_id'],
        )
        row = {
            'work_order': index,
            'batch': ((index - 1) // batch_size) + 1,
            'workflow_status': 'pending',
            'reviewer': '',
            'wp_post_id': record['wp_post_id'],
            'title': record['title'],
            'wp_admin_edit_url': edit_url,
            'rest_verification_url': verification_url,
            'public_url': record['permalink'],
            'benefit_1': names[0],
            'benefit_1_slug': slugs[0],
            'benefit_1_term_id': term_ids[0],
            'benefit_2': names[1],
            'benefit_2_slug': slugs[1],
            'benefit_2_term_id': term_ids[1],
            'benefit_3': names[2],
            'benefit_3_slug': slugs[2],
            'benefit_3_term_id': term_ids[2],
            'legacy_source': record['legacy_source'],
            'summary_source': record['summary_source'],
            'observed_modified_gmt': record['observed_modified_gmt'],
            'wp_updated_at': '',
            'rest_verified': '',
            'verified_at': '',
            'notes': '',
            'source_plan_run_id': metadata['run_id'],
            'source_plan_sha256': plan_sha256,
        }
        writer.writerow({
            field: _safe_csv_cell(row.get(field, ''))
            for field in CSV_FIELDS
        })
    return output.getvalue().encode('utf-8-sig')


def write_worklist_atomic(output_path: Path, payload: bytes) -> Dict[str, Path]:
    resolved = output_path.expanduser().resolve()
    if resolved.suffix.lower() != '.csv':
        raise ManualWorklistError('Worklist output path must end with .csv')
    checksum_path = resolved.with_suffix('.sha256')
    lock_path = resolved.with_suffix('.lock')
    destinations = (resolved, checksum_path)

    resolved.parent.mkdir(parents=True, exist_ok=True)
    existing = [str(path) for path in destinations if path.exists()]
    if existing:
        raise ManualWorklistError(
            'Refusing to overwrite existing worklist files: {0}'.format(
                ', '.join(existing)
            )
        )
    try:
        lock_handle = lock_path.open('x', encoding='utf-8')
    except FileExistsError as exc:
        raise ManualWorklistError(
            'Another worklist run or stale lock exists: {0}'.format(lock_path)
        ) from exc
    try:
        lock_handle.write('pid={0}\n'.format(os.getpid()))
        lock_handle.flush()
    except Exception:
        lock_handle.close()
        if lock_path.exists():
            lock_path.unlink()
        raise

    checksum = hashlib.sha256(payload).hexdigest()
    checksum_payload = (
        '{0}  {1}\n'.format(checksum, resolved.name)
    ).encode('ascii')
    temp_csv = resolved.with_name(
        '.{0}.{1}.tmp'.format(resolved.name, os.getpid())
    )
    temp_checksum = checksum_path.with_name(
        '.{0}.{1}.tmp'.format(checksum_path.name, os.getpid())
    )
    committed = []
    try:
        temp_csv.write_bytes(payload)
        temp_checksum.write_bytes(checksum_payload)
        os.replace(str(temp_checksum), str(checksum_path))
        committed.append(checksum_path)
        os.replace(str(temp_csv), str(resolved))
        committed.append(resolved)
    except Exception:
        for path in reversed(committed):
            if path.exists():
                path.unlink()
        raise
    finally:
        for path in (temp_csv, temp_checksum):
            if path.exists():
                path.unlink()
        lock_handle.close()
        if lock_path.exists():
            lock_path.unlink()
    return {'csv': resolved, 'sha256': checksum_path}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            'Create an offline CSV checklist from auto_ready records in a '
            'verified full WordPress benefit backfill PLAN.'
        )
    )
    parser.add_argument(
        '--plan',
        required=True,
        help='Full PLAN JSON; its adjacent .sha256 file is required.',
    )
    parser.add_argument(
        '--output',
        required=True,
        help='New CSV path. Existing CSV/checksum files are never overwritten.',
    )
    parser.add_argument(
        '--expected-api-url',
        required=True,
        help='Exact production WordPress Core REST API URL.',
    )
    parser.add_argument(
        '--expected-count',
        required=True,
        type=int,
        help='Expected number of auto_ready records (23 for the reviewed plan).',
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help='Rows per manual batch (default: 5).',
    )
    parser.add_argument(
        '--max-plan-age-hours',
        type=int,
        default=DEFAULT_MAX_PLAN_AGE_HOURS,
        help='Reject older plans (default: 24; maximum: 168).',
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.expected_count < 1:
        raise ManualWorklistError('--expected-count must be at least 1')
    plan, plan_sha256, plan_path = load_verified_plan(Path(args.plan))
    records, metadata, _ = validate_full_plan(
        plan,
        expected_api_url=args.expected_api_url,
        expected_count=args.expected_count,
        max_plan_age_hours=args.max_plan_age_hours,
    )
    payload = build_worklist_bytes(
        records,
        metadata,
        plan_sha256,
        batch_size=args.batch_size,
    )
    paths = write_worklist_atomic(Path(args.output), payload)
    batches = (len(records) + args.batch_size - 1) // args.batch_size
    print('Mode: MANUAL WORKLIST (offline; no WordPress requests)')
    print('Source PLAN: {0}'.format(plan_path))
    print('Source run ID: {0}'.format(metadata['run_id']))
    print('Auto-ready rows: {0}'.format(len(records)))
    print('Batches: {0} (up to {1} rows each)'.format(
        batches,
        args.batch_size,
    ))
    print('CSV: {0}'.format(paths['csv']))
    print('SHA256: {0}'.format(paths['sha256']))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except ManualWorklistError as error:
        print('ERROR: {0}'.format(error), file=sys.stderr)
        sys.exit(1)
