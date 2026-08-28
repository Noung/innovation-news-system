#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Safely apply approved WordPress benefit-taxonomy backfill records.

The command is a no-write preflight unless ``--execute`` is supplied.
It never creates posts or taxonomy terms and only accepts ``auto_ready``
records from a complete, checksummed schema-v2 planner manifest.
"""

import argparse
import hashlib
import hmac
import importlib.util
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from urllib.parse import urlsplit, urlunsplit

import requests
from requests.auth import HTTPBasicAuth

from benefit_classifier import (
    BENEFIT_TERM_SLUGS,
    BENEFITS_PER_ARTICLE,
    CLASSIFIER_VERSION,
)


APPLY_TOOL_VERSION = '1.1.0'
SUPPORTED_PLAN_SCHEMA_VERSION = '2'
SUPPORTED_CLASSIFIER_MODE = 'strict'
MAX_PLAN_AGE_HOURS = 24
RETRYABLE_HTTP_STATUSES = {429, 500, 502, 503, 504}
GUARDED_REST_NAMESPACE = 'oar-innovation/v1'
GUARDED_CONTRACT_VERSION = '2'
MINIMUM_GUARDED_PLUGIN_VERSION = (1, 2, 0)
GUARDED_STRATEGY = 'innodb-row-lock-and-expected-state'
GUARDED_ISOLATION = 'serializable'
GUARDED_SOURCE = 'sha256-length-prefixed-raw-post-and-ptb-meta'
WORDPRESS_ENV_KEYS = (
    'WP_API_URL',
    'WP_USERNAME',
    'WP_APP_PASSWORD',
    'WP_INNOVATION_TIP_POST_TYPE',
    'WP_BENEFIT_TAXONOMY',
    'WP_BENEFIT_TAXONOMY_REST_BASE',
)


class BackfillApplyError(RuntimeError):
    """Raised when APPLY cannot prove that an operation is safe."""


class GuardedWriteRejected(BackfillApplyError):
    """The guarded endpoint definitively rejected the write."""

    def __init__(self, message, *, http_status=None, error_code=''):
        super().__init__(message)
        self.http_status = http_status
        self.error_code = error_code


class GuardedWriteAmbiguous(BackfillApplyError):
    """The request may have reached WordPress, so it must not be retried."""

    def __init__(self, message, *, http_status=None, error_code=''):
        super().__init__(message)
        self.http_status = http_status
        self.error_code = error_code


def _load_planner_module():
    planner_path = Path(__file__).with_name(
        'plan-wordpress-benefit-backfill.py'
    )
    if not planner_path.is_file():
        raise BackfillApplyError(f'Planner module not found: {planner_path}')
    spec = importlib.util.spec_from_file_location(
        'wordpress_benefit_backfill_plan_for_apply',
        planner_path,
    )
    if spec is None or spec.loader is None:
        raise BackfillApplyError('Planner module could not be loaded')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PLANNER = _load_planner_module()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_records_sha256(records: List[Dict[str, object]]) -> str:
    payload = json.dumps(
        records,
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
    ).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()


def _reject_duplicate_json_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise BackfillApplyError(
                f'Plan JSON contains duplicate key: {key}'
            )
        result[key] = value
    return result


def load_isolated_wordpress_env(env_path: Path) -> None:
    """Prevent missing .env keys from inheriting stale shell credentials."""
    for key in WORDPRESS_ENV_KEYS:
        os.environ.pop(key, None)
    PLANNER.load_explicit_env_file(env_path)


def load_verified_manifest(plan_path: Path):
    """Verify the adjacent sha256 sidecar and parse those exact bytes."""
    plan_candidate = plan_path.expanduser()
    if plan_candidate.is_symlink():
        raise BackfillApplyError('Plan JSON symlinks are not allowed')
    plan_path = plan_candidate.resolve()
    if (
        plan_path.suffix.lower() != '.json'
        or not plan_path.is_file()
        or plan_path.is_symlink()
    ):
        raise BackfillApplyError(f'Plan JSON not found: {plan_path}')

    checksum_path = plan_path.with_suffix('.sha256')
    if not checksum_path.is_file() or checksum_path.is_symlink():
        raise BackfillApplyError(
            f'Plan checksum sidecar not found: {checksum_path}'
        )

    try:
        checksum_lines = checksum_path.read_text(
            encoding='ascii'
        ).splitlines()
    except (OSError, UnicodeError) as exc:
        raise BackfillApplyError('Plan checksum sidecar is unreadable') from exc
    if len(checksum_lines) != 1:
        raise BackfillApplyError(
            'Plan checksum sidecar must contain exactly one line'
        )
    match = re.fullmatch(
        r'([0-9a-fA-F]{64})  ([^/\\]+)',
        checksum_lines[0],
    )
    if not match or match.group(2) != plan_path.name:
        raise BackfillApplyError(
            'Plan checksum sidecar has an invalid filename or format'
        )

    plan_bytes = plan_path.read_bytes()
    actual_digest = hashlib.sha256(plan_bytes).hexdigest()
    expected_digest = match.group(1).lower()
    if not hmac.compare_digest(actual_digest, expected_digest):
        raise BackfillApplyError('Plan JSON checksum mismatch')

    try:
        manifest = json.loads(
            plan_bytes.decode('utf-8'),
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise BackfillApplyError('Plan JSON is invalid') from exc
    if not isinstance(manifest, dict):
        raise BackfillApplyError('Plan manifest root must be an object')
    return manifest, actual_digest, plan_path


def _validate_counts(
    counts: Dict[str, object],
    records: List[Dict[str, object]],
) -> None:
    if not isinstance(counts, dict):
        raise BackfillApplyError('Plan counts are missing')
    expected = {
        'included': len(records),
        'auto_ready': sum(
            record.get('plan_status') == 'auto_ready'
            for record in records
        ),
        'review': sum(
            record.get('plan_status') == 'review'
            for record in records
        ),
        'skip_existing': sum(
            record.get('plan_status') == 'skip_existing'
            for record in records
        ),
    }
    for key, value in expected.items():
        if counts.get(key) != value:
            raise BackfillApplyError(f'Plan count mismatch for {key}')
    try:
        wp_total = int(counts.get('wp_total'))
    except (TypeError, ValueError) as exc:
        raise BackfillApplyError('Plan wp_total is invalid') from exc
    if wp_total != len(records):
        raise BackfillApplyError(
            'APPLY requires a complete manifest whose wp_total equals included'
        )


def validate_manifest(
    manifest: Dict[str, object],
    config: Dict[str, str],
    env_path: Path,
) -> Dict[int, Dict[str, object]]:
    """Validate manifest identity and return records keyed by post ID."""
    metadata = manifest.get('metadata')
    records = manifest.get('records')
    if not isinstance(metadata, dict) or not isinstance(records, list):
        raise BackfillApplyError('Plan metadata or records are invalid')

    required_metadata = {
        'schema_version': SUPPORTED_PLAN_SCHEMA_VERSION,
        'mode': 'plan_read_only',
        'site_api_url': config['api_url'],
        'post_type': config['post_type'],
        'taxonomy': config['taxonomy'],
        'taxonomy_rest_base': config['taxonomy_rest_base'],
        'classifier_version': CLASSIFIER_VERSION,
        'classifier_mode': SUPPORTED_CLASSIFIER_MODE,
        'truncated': False,
    }
    for key, expected in required_metadata.items():
        if metadata.get(key) != expected:
            raise BackfillApplyError(
                f'Plan metadata mismatch for {key}'
            )

    try:
        planned_env = Path(
            str(metadata.get('environment_file', ''))
        ).expanduser().resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        raise BackfillApplyError(
            'Plan environment_file is invalid'
        ) from exc
    if planned_env != env_path:
        raise BackfillApplyError(
            'Plan was generated from a different environment file'
        )

    run_id = metadata.get('run_id')
    if not isinstance(run_id, str) or not re.fullmatch(
        r'benefit-backfill-plan-\d{8}T\d{6}Z',
        run_id,
    ):
        raise BackfillApplyError('Plan run_id is invalid')
    try:
        generated_at = datetime.fromisoformat(
            str(metadata.get('generated_at_utc', ''))
        )
    except ValueError as exc:
        raise BackfillApplyError(
            'Plan generated_at_utc is invalid'
        ) from exc
    if generated_at.tzinfo is None:
        raise BackfillApplyError(
            'Plan generated_at_utc must include a timezone'
        )
    age_seconds = (
        datetime.now(timezone.utc)
        - generated_at.astimezone(timezone.utc)
    ).total_seconds()
    if age_seconds < -300:
        raise BackfillApplyError('Plan timestamp is unexpectedly in the future')
    if age_seconds > MAX_PLAN_AGE_HOURS * 3600:
        raise BackfillApplyError(
            f'Plan is older than {MAX_PLAN_AGE_HOURS} hours; '
            'generate a fresh PLAN'
        )

    records_digest = _canonical_records_sha256(records)
    if not hmac.compare_digest(
        records_digest,
        str(metadata.get('records_sha256', '')),
    ):
        raise BackfillApplyError('Plan records checksum mismatch')
    _validate_counts(metadata.get('counts'), records)

    records_by_id = {}
    for record in records:
        if not isinstance(record, dict):
            raise BackfillApplyError('Plan contains a non-object record')
        raw_post_id = record.get('wp_post_id')
        if type(raw_post_id) is not int:
            raise BackfillApplyError(
                'Plan contains a non-integer WordPress post ID'
            )
        post_id = raw_post_id
        if post_id <= 0 or post_id in records_by_id:
            raise BackfillApplyError(
                'Plan contains a duplicate or invalid WordPress post ID'
            )
        if record.get('plan_status') not in {
            'auto_ready',
            'review',
            'skip_existing',
        }:
            raise BackfillApplyError(
                f'Plan post {post_id} has an invalid plan_status'
            )
        records_by_id[post_id] = record
    return records_by_id


def _validate_auto_ready_record(record: Dict[str, object]) -> None:
    post_id = int(record['wp_post_id'])
    if record.get('plan_status') != 'auto_ready':
        raise BackfillApplyError(
            f'Post {post_id} is not auto_ready and cannot be applied'
        )
    if record.get('status') != 'publish':
        raise BackfillApplyError(
            f'Post {post_id} was not planned as published'
        )
    if record.get('existing_term_ids') != []:
        raise BackfillApplyError(
            f'Post {post_id} did not have an empty taxonomy in the plan'
        )
    if record.get('legacy_conflict') is not False:
        raise BackfillApplyError(
            f'Post {post_id} has conflicting legacy benefit sources'
        )
    if record.get('review_reasons') != []:
        raise BackfillApplyError(
            f'Post {post_id} unexpectedly contains review reasons'
        )

    legacy = record.get('legacy_benefits')
    names = record.get('suggested_names')
    slugs = record.get('suggested_slugs')
    term_ids = record.get('suggested_term_ids')
    if (
        not isinstance(legacy, list)
        or not isinstance(names, list)
        or not isinstance(slugs, list)
        or not isinstance(term_ids, list)
        or len(legacy) != BENEFITS_PER_ARTICLE
        or names != legacy
        or len(set(names)) != BENEFITS_PER_ARTICLE
        or any(name not in BENEFIT_TERM_SLUGS for name in names)
        or slugs != [BENEFIT_TERM_SLUGS[name] for name in names]
    ):
        raise BackfillApplyError(
            f'Post {post_id} does not contain three exact legacy benefits'
        )
    if any(type(value) is not int for value in term_ids):
        raise BackfillApplyError(
            f'Post {post_id} has invalid proposed term IDs'
        )
    normalized_term_ids = list(term_ids)
    if (
        any(value <= 0 for value in normalized_term_ids)
        or len(set(normalized_term_ids)) != BENEFITS_PER_ARTICLE
    ):
        raise BackfillApplyError(
            f'Post {post_id} proposed term IDs are not three unique IDs'
        )

    modified_gmt = record.get('observed_modified_gmt')
    input_digest = record.get('input_text_sha256')
    if not isinstance(modified_gmt, str) or not modified_gmt:
        raise BackfillApplyError(
            f'Post {post_id} is missing observed_modified_gmt'
        )
    if not isinstance(input_digest, str) or not re.fullmatch(
        r'[0-9a-f]{64}',
        input_digest,
    ):
        raise BackfillApplyError(
            f'Post {post_id} has an invalid input text checksum'
        )


def select_records(
    records_by_id: Dict[int, Dict[str, object]],
    *,
    post_ids: Optional[Iterable[int]] = None,
    all_auto_ready: bool = False,
) -> List[Dict[str, object]]:
    if all_auto_ready:
        selected = [
            record for record in records_by_id.values()
            if record.get('plan_status') == 'auto_ready'
        ]
    else:
        normalized_ids = [int(value) for value in (post_ids or [])]
        if not normalized_ids:
            raise BackfillApplyError(
                'Select --post-id or --all-auto-ready'
            )
        if len(normalized_ids) != len(set(normalized_ids)):
            raise BackfillApplyError('Duplicate --post-id values are not allowed')
        missing = sorted(set(normalized_ids) - set(records_by_id))
        if missing:
            raise BackfillApplyError(
                f'Requested post IDs are absent from the plan: {missing}'
            )
        selected = [records_by_id[value] for value in normalized_ids]

    selected.sort(key=lambda item: int(item['wp_post_id']))
    if not selected:
        raise BackfillApplyError('No auto_ready records were selected')
    for record in selected:
        _validate_auto_ready_record(record)
    return selected


def _guarded_api_url(core_api_url: str) -> str:
    """Derive a sibling custom namespace without broad string replacement."""
    parsed = urlsplit(core_api_url.rstrip('/'))
    core_suffix = '/wp-json/wp/v2'
    if not parsed.path.endswith(core_suffix):
        raise BackfillApplyError(
            'WordPress core API URL does not end with /wp-json/wp/v2'
        )
    wp_json_path = parsed.path[:-len('/wp/v2')]
    guarded_path = f'{wp_json_path}/{GUARDED_REST_NAMESPACE}'
    return urlunsplit((
        parsed.scheme,
        parsed.netloc,
        guarded_path,
        '',
        '',
    ))


def _safe_wordpress_error_code(response) -> str:
    try:
        payload = response.json()
    except (TypeError, ValueError):
        return ''
    if not isinstance(payload, dict):
        return ''
    code = payload.get('code')
    if (
        isinstance(code, str)
        and re.fullmatch(r'[A-Za-z0-9_.:-]{1,100}', code)
    ):
        return code
    return ''


class ApplyWordPressClient:
    """REST client with retried GET and one non-retried guarded POST."""

    def __init__(
        self,
        api_url: str,
        username: str,
        app_password: str,
        *,
        verify=True,
        timeout: int = 20,
        max_retries: int = 2,
        session=None,
        sleep_fn=time.sleep,
    ):
        self.api_url = api_url.rstrip('/')
        self.guarded_api_url = _guarded_api_url(self.api_url)
        self.verify = verify
        self.timeout = max(1, int(timeout))
        self.max_retries = max(0, int(max_retries))
        self.sleep_fn = sleep_fn
        self.session = session or requests.Session()
        self.session.auth = HTTPBasicAuth(username, app_password)
        self.session.headers.update({
            'Accept': 'application/json',
            'User-Agent': (
                f'Innovation-News-Backfill-Apply/{APPLY_TOOL_VERSION}'
            ),
        })

    def _get_json_url(self, url: str, *, label: str, params=None):
        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.request(
                    'GET',
                    url,
                    params=params or {},
                    timeout=self.timeout,
                    verify=self.verify,
                    allow_redirects=False,
                )
            except requests.RequestException as exc:
                if attempt < self.max_retries:
                    self.sleep_fn(min(2 ** attempt, 4))
                    continue
                raise BackfillApplyError(
                    'WordPress GET failed after retries'
                ) from exc
            if response.status_code == 200:
                try:
                    return response.json(), response.headers
                except (TypeError, ValueError) as exc:
                    raise BackfillApplyError(
                        f'WordPress returned invalid JSON for {label}'
                    ) from exc
            if (
                response.status_code in RETRYABLE_HTTP_STATUSES
                and attempt < self.max_retries
            ):
                self.sleep_fn(min(2 ** attempt, 4))
                continue
            raise BackfillApplyError(
                f'WordPress GET returned HTTP {response.status_code} '
                f'for {label}'
            )
        raise BackfillApplyError('WordPress GET retry loop ended unexpectedly')

    def get_json(self, relative_path: str, *, params=None):
        url = f"{self.api_url}/{relative_path.lstrip('/')}"
        return self._get_json_url(
            url,
            label=relative_path,
            params=params,
        )

    def get_guard_json(self, relative_path: str, *, params=None):
        url = f"{self.guarded_api_url}/{relative_path.lstrip('/')}"
        return self._get_json_url(
            url,
            label=f'{GUARDED_REST_NAMESPACE}/{relative_path.lstrip("/")}',
            params=params,
        )

    def apply_guarded_benefits(
        self,
        post_id: int,
        taxonomy_rest_base: str,
        *,
        expected_modified_gmt: str,
        expected_term_ids: List[int],
        target_term_ids: List[int],
        target_term_slugs: List[str],
        expected_source_sha256: str,
        plan_run_id: str,
    ):
        """Send one compare-and-set request; never retry this mutation."""
        normalized_expected = sorted(
            int(value) for value in expected_term_ids
        )
        normalized_target = sorted(
            int(value) for value in target_term_ids
        )
        if normalized_expected:
            raise BackfillApplyError(
                'Guarded backfill only accepts an empty expected taxonomy'
            )
        if (
            len(normalized_target) != BENEFITS_PER_ARTICLE
            or len(set(normalized_target)) != BENEFITS_PER_ARTICLE
            or any(value <= 0 for value in normalized_target)
        ):
            raise BackfillApplyError(
                'Guarded backfill target must contain three unique term IDs'
            )
        if (
            not isinstance(target_term_slugs, list)
            or len(target_term_slugs) != BENEFITS_PER_ARTICLE
            or len(set(target_term_slugs)) != BENEFITS_PER_ARTICLE
            or any(
                slug not in BENEFIT_TERM_SLUGS.values()
                for slug in target_term_slugs
            )
        ):
            raise BackfillApplyError(
                'Guarded backfill target must contain three controlled slugs'
            )
        if not re.fullmatch(
            r'benefit-backfill-plan-\d{8}T\d{6}Z',
            plan_run_id,
        ):
            raise BackfillApplyError('Guarded backfill plan run ID is invalid')
        if not re.fullmatch(r'[0-9a-f]{64}', expected_source_sha256):
            raise BackfillApplyError(
                'Guarded backfill source fingerprint is invalid'
            )

        url = f'{self.guarded_api_url}/benefit-backfill/{int(post_id)}'
        request_payload = {
            'expected_modified_gmt': expected_modified_gmt,
            'expected_term_ids': normalized_expected,
            'target_term_ids': normalized_target,
            'target_term_slugs': list(target_term_slugs),
            'expected_source_sha256': expected_source_sha256,
            'plan_run_id': plan_run_id,
        }
        try:
            response = self.session.request(
                'POST',
                url,
                json=request_payload,
                timeout=self.timeout,
                verify=self.verify,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            raise GuardedWriteAmbiguous(
                f'Guarded WordPress POST transport failed for post {post_id}'
            ) from exc
        if response.status_code != 200:
            error_code = _safe_wordpress_error_code(response)
            error_type = (
                GuardedWriteAmbiguous
                if response.status_code in RETRYABLE_HTTP_STATUSES
                or response.status_code >= 500
                else GuardedWriteRejected
            )
            raise error_type(
                f'Guarded WordPress POST returned HTTP '
                f'{response.status_code} for post {post_id}',
                http_status=response.status_code,
                error_code=error_code,
            )
        try:
            payload = response.json()
        except (TypeError, ValueError) as exc:
            raise GuardedWriteAmbiguous(
                f'Guarded WordPress POST returned invalid JSON '
                f'for post {post_id}',
                http_status=200,
            ) from exc
        if not isinstance(payload, dict):
            raise GuardedWriteAmbiguous(
                f'Guarded WordPress response identity mismatch '
                f'for post {post_id}',
                http_status=200,
            )
        try:
            response_post_id = int(payload.get('id', 0))
        except (TypeError, ValueError) as exc:
            raise GuardedWriteAmbiguous(
                f'Guarded WordPress response identity mismatch '
                f'for post {post_id}',
                http_status=200,
            ) from exc
        response_valid = (
            response_post_id == post_id
            and payload.get('status') == 'publish'
            and payload.get('modified_gmt') == expected_modified_gmt
            and payload.get('contract_version') == GUARDED_CONTRACT_VERSION
            and payload.get('plan_run_id') == plan_run_id
            and payload.get('source_sha256') == expected_source_sha256
            and payload.get('target_term_slugs') == target_term_slugs
        )
        try:
            response_ids = _taxonomy_ids(payload, taxonomy_rest_base)
        except BackfillApplyError:
            response_ids = None
        if not response_valid or response_ids != normalized_target:
            raise GuardedWriteAmbiguous(
                f'Guarded WordPress success response failed validation '
                f'for post {post_id}',
                http_status=200,
            )
        return payload


def _semantic_version_tuple(value: object):
    if not isinstance(value, str) or not re.fullmatch(
        r'\d+\.\d+\.\d+',
        value,
    ):
        raise BackfillApplyError(
            'Guarded WordPress plugin version is invalid'
        )
    return tuple(int(part) for part in value.split('.'))


def validate_guard_capability(
    payload: object,
    config: Dict[str, str],
) -> Dict[str, object]:
    """Require the exact guarded contract before any record is READY."""
    if not isinstance(payload, dict):
        raise BackfillApplyError(
            'Guarded WordPress capability response is invalid'
        )
    required = {
        'contract_version': GUARDED_CONTRACT_VERSION,
        'post_type': config['post_type'],
        'taxonomy': config['taxonomy'],
        'taxonomy_rest_base': config['taxonomy_rest_base'],
        'guard_strategy': GUARDED_STRATEGY,
        'transaction_isolation': GUARDED_ISOLATION,
        'source_guard': GUARDED_SOURCE,
    }
    for key, expected in required.items():
        if payload.get(key) != expected:
            raise BackfillApplyError(
                f'Guarded WordPress capability mismatch for {key}'
            )
    if payload.get('storage_ready') is not True:
        raise BackfillApplyError(
            'Guarded WordPress storage is not transaction-ready'
        )
    if payload.get('controlled_terms_ready') is not True:
        raise BackfillApplyError(
            'Guarded WordPress controlled vocabulary is not ready'
        )
    plugin_version = payload.get('plugin_version')
    if (
        _semantic_version_tuple(plugin_version)
        < MINIMUM_GUARDED_PLUGIN_VERSION
    ):
        raise BackfillApplyError(
            'Guarded WordPress plugin version is too old'
        )
    return {
        'contract_version': payload['contract_version'],
        'plugin_version': plugin_version,
        'post_type': payload['post_type'],
        'taxonomy': payload['taxonomy'],
        'taxonomy_rest_base': payload['taxonomy_rest_base'],
        'storage_ready': True,
        'controlled_terms_ready': True,
        'guard_strategy': payload['guard_strategy'],
        'transaction_isolation': payload['transaction_isolation'],
        'source_guard': payload['source_guard'],
    }


def fetch_and_validate_guard_capability(
    client: ApplyWordPressClient,
    config: Dict[str, str],
) -> Dict[str, object]:
    payload, _ = client.get_guard_json('benefit-backfill-capability')
    return validate_guard_capability(payload, config)


def _term_snapshot_by_slug(metadata: Dict[str, object]):
    snapshot = metadata.get('term_snapshot')
    if not isinstance(snapshot, list):
        raise BackfillApplyError('Plan term snapshot is invalid')
    result = {}
    for item in snapshot:
        if not isinstance(item, dict):
            raise BackfillApplyError('Plan term snapshot contains an invalid row')
        slug = str(item.get('slug', ''))
        try:
            term_id = int(item.get('id'))
        except (TypeError, ValueError) as exc:
            raise BackfillApplyError(
                'Plan term snapshot contains an invalid term ID'
            ) from exc
        if not slug or slug in result:
            raise BackfillApplyError(
                'Plan term snapshot contains a duplicate slug'
            )
        result[slug] = {
            'id': term_id,
            'slug': slug,
            'name': str(item.get('name', '')),
        }
    return result


def validate_term_snapshot(
    metadata: Dict[str, object],
    current_terms: Dict[str, Dict[str, object]],
) -> None:
    snapshot = _term_snapshot_by_slug(metadata)
    if snapshot != current_terms:
        raise BackfillApplyError(
            'WordPress controlled terms changed after the plan was generated'
        )


def fetch_post_for_guard(
    client: ApplyWordPressClient,
    config: Dict[str, str],
    post_id: int,
) -> Dict[str, object]:
    fields = [
        'id',
        'status',
        'modified_gmt',
        'title',
        'content',
        'excerpt',
        'meta',
        config['taxonomy_rest_base'],
    ]
    payload, _ = client.get_json(
        f"{config['post_type']}/{int(post_id)}",
        params={
            'context': 'edit',
            '_fields': ','.join(fields),
        },
    )
    if not isinstance(payload, dict):
        raise BackfillApplyError(
            f'WordPress post {post_id} response is invalid'
        )
    return payload


def _taxonomy_ids(post: Dict[str, object], rest_base: str) -> List[int]:
    values = post.get(rest_base)
    if not isinstance(values, list):
        raise BackfillApplyError(
            f"WordPress post is missing the '{rest_base}' taxonomy field"
        )
    try:
        result = sorted({int(value) for value in values})
    except (TypeError, ValueError) as exc:
        raise BackfillApplyError(
            'WordPress post contains invalid taxonomy IDs'
        ) from exc
    if len(result) != len(values):
        raise BackfillApplyError(
            'WordPress post contains duplicate taxonomy IDs'
        )
    return result


def _strict_id_list(value: object, *, label: str) -> List[int]:
    if not isinstance(value, list):
        raise BackfillApplyError(f'{label} is not an array')
    if any(type(item) is not int or item <= 0 for item in value):
        raise BackfillApplyError(f'{label} contains invalid term IDs')
    normalized = sorted(value)
    if len(normalized) != len(set(normalized)):
        raise BackfillApplyError(f'{label} contains duplicate term IDs')
    return normalized


def source_guard_sha256(post: Dict[str, object]) -> str:
    """Match the plugin's length-prefixed raw source-field fingerprint."""
    values = []
    for field_name in ('title', 'content', 'excerpt'):
        field = post.get(field_name)
        if not isinstance(field, dict) or not isinstance(
            field.get('raw'),
            str,
        ):
            raise BackfillApplyError(
                f"WordPress post lacks raw '{field_name}' for source guard"
            )
        values.append(field['raw'])

    meta = post.get('meta')
    if not isinstance(meta, dict):
        raise BackfillApplyError(
            'WordPress post lacks edit-context meta for source guard'
        )
    ptb_value = meta.get('ptb_innovation_tip_content', '')
    if ptb_value is None:
        ptb_value = ''
    if not isinstance(ptb_value, (str, int, float, bool)):
        raise BackfillApplyError(
            'WordPress PTB source meta is not a scalar value'
        )
    if isinstance(ptb_value, bool):
        ptb_value = '1' if ptb_value else ''
    else:
        ptb_value = str(ptb_value)
    values.append(ptb_value)

    framed = bytearray()
    for value in values:
        encoded = value.encode('utf-8')
        framed.extend(str(len(encoded)).encode('ascii'))
        framed.extend(b':')
        framed.extend(encoded)
    return hashlib.sha256(bytes(framed)).hexdigest()


def fetch_guarded_state(
    client: ApplyWordPressClient,
    post_id: int,
) -> Dict[str, object]:
    payload, _ = client.get_guard_json(
        f'benefit-backfill-state/{int(post_id)}'
    )
    if not isinstance(payload, dict):
        raise BackfillApplyError(
            f'Guarded WordPress state for post {post_id} is invalid'
        )
    return payload


def validate_guarded_state(
    state: Dict[str, object],
    post: Dict[str, object],
    record: Dict[str, object],
    config: Dict[str, str],
) -> str:
    """Prove that core REST and the server-owned DB guard see one state."""
    post_id = int(record['wp_post_id'])
    try:
        state_post_id = int(state.get('id'))
    except (TypeError, ValueError) as exc:
        raise BackfillApplyError(
            f'Guarded WordPress state ID is invalid for post {post_id}'
        ) from exc
    if (
        state_post_id != post_id
        or state.get('post_type') != config['post_type']
        or state.get('status') != record.get('status')
        or state.get('modified_gmt') != post.get('modified_gmt')
        or state.get('modified_gmt') != record.get('observed_modified_gmt')
        or state.get('contract_version') != GUARDED_CONTRACT_VERSION
    ):
        raise BackfillApplyError(
            f'Guarded WordPress state identity changed for post {post_id}'
        )
    state_ids = _strict_id_list(
        state.get('current_term_ids'),
        label=f'Guarded WordPress state taxonomy for post {post_id}',
    )
    core_ids = _taxonomy_ids(post, config['taxonomy_rest_base'])
    if state_ids != core_ids or state_ids != record.get('existing_term_ids'):
        raise BackfillApplyError(
            f'Guarded WordPress taxonomy state changed for post {post_id}'
        )
    expected_source = source_guard_sha256(post)
    if (
        state.get('source_sha256') != expected_source
        or not re.fullmatch(
            r'[0-9a-f]{64}',
            str(state.get('source_sha256', '')),
        )
    ):
        raise BackfillApplyError(
            f'Guarded WordPress source state changed for post {post_id}'
        )
    return expected_source


def validate_guarded_applied_state(
    state: Dict[str, object],
    post: Dict[str, object],
    record: Dict[str, object],
    config: Dict[str, str],
) -> None:
    """Verify the committed target through the plugin's direct DB view."""
    post_id = int(record['wp_post_id'])
    try:
        state_post_id = int(state.get('id'))
    except (TypeError, ValueError) as exc:
        raise BackfillApplyError(
            f'Guarded post-APPLY state ID is invalid for post {post_id}'
        ) from exc
    expected_ids = sorted(int(value) for value in record['suggested_term_ids'])
    if (
        state_post_id != post_id
        or state.get('post_type') != config['post_type']
        or state.get('status') != 'publish'
        or state.get('modified_gmt') != post.get('modified_gmt')
        or state.get('contract_version') != GUARDED_CONTRACT_VERSION
        or _strict_id_list(
            state.get('current_term_ids'),
            label=f'Guarded post-APPLY taxonomy for post {post_id}',
        ) != expected_ids
        or state.get('source_sha256') != source_guard_sha256(post)
    ):
        raise BackfillApplyError(
            f'Guarded post-APPLY verification failed for post {post_id}'
        )


def non_taxonomy_snapshot_sha256(post: Dict[str, object]) -> str:
    """Hash stable stored fields, never volatile REST rendered output."""
    snapshot = {
        'id': post.get('id'),
        'status': post.get('status'),
        'source_sha256': source_guard_sha256(post),
    }
    payload = json.dumps(
        snapshot,
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
    ).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()


def validate_live_post(
    post: Dict[str, object],
    record: Dict[str, object],
    config: Dict[str, str],
    current_terms: Dict[str, Dict[str, object]],
) -> None:
    """Fail if the post or controlled terms changed since PLAN."""
    post_id = int(record['wp_post_id'])
    try:
        live_post_id = int(post.get('id'))
    except (TypeError, ValueError) as exc:
        raise BackfillApplyError(
            f'WordPress post {post_id} has an invalid ID'
        ) from exc
    if live_post_id != post_id:
        raise BackfillApplyError(
            f'WordPress response identity mismatch for post {post_id}'
        )
    if post.get('status') != record.get('status'):
        raise BackfillApplyError(
            f'WordPress post {post_id} status changed after PLAN'
        )
    if post.get('modified_gmt') != record.get('observed_modified_gmt'):
        raise BackfillApplyError(
            f'WordPress post {post_id} modified_gmt changed after PLAN'
        )

    current_ids = _taxonomy_ids(post, config['taxonomy_rest_base'])
    if current_ids != record.get('existing_term_ids') or current_ids:
        raise BackfillApplyError(
            f'WordPress post {post_id} taxonomy changed after PLAN'
        )

    extracted = PLANNER.extract_post_inputs(post)
    input_digest = hashlib.sha256(
        (
            extracted['title']
            + '\n'
            + extracted['summary']
        ).encode('utf-8')
    ).hexdigest()
    if input_digest != record.get('input_text_sha256'):
        raise BackfillApplyError(
            f'WordPress post {post_id} content changed after PLAN'
        )
    if (
        extracted['legacy_benefits'] != record.get('legacy_benefits')
        or extracted['legacy_conflict'] != record.get('legacy_conflict')
    ):
        raise BackfillApplyError(
            f'WordPress post {post_id} legacy benefits changed after PLAN'
        )

    for name, slug, term_id in zip(
        record['suggested_names'],
        record['suggested_slugs'],
        record['suggested_term_ids'],
    ):
        current = current_terms.get(slug)
        if (
            current is None
            or current['name'] != name
            or int(current['id']) != int(term_id)
        ):
            raise BackfillApplyError(
                f'WordPress term mapping changed for post {post_id}'
            )


def validate_applied_post(
    post: Dict[str, object],
    record: Dict[str, object],
    config: Dict[str, str],
    before_non_taxonomy_sha256: str,
) -> str:
    post_id = int(record['wp_post_id'])
    try:
        live_post_id = int(post.get('id'))
    except (TypeError, ValueError) as exc:
        raise BackfillApplyError(
            f'WordPress verification response for post {post_id} is invalid'
        ) from exc
    if live_post_id != post_id or post.get('status') != 'publish':
        raise BackfillApplyError(
            f'WordPress post-verification identity failed for post {post_id}'
        )
    expected_ids = sorted(int(value) for value in record['suggested_term_ids'])
    if _taxonomy_ids(post, config['taxonomy_rest_base']) != expected_ids:
        raise BackfillApplyError(
            f'WordPress taxonomy verification failed for post {post_id}'
        )
    if (
        non_taxonomy_snapshot_sha256(post)
        != before_non_taxonomy_sha256
    ):
        raise BackfillApplyError(
            f'WordPress non-taxonomy fields changed for post {post_id}'
        )
    modified_gmt = post.get('modified_gmt')
    if not isinstance(modified_gmt, str) or not modified_gmt:
        raise BackfillApplyError(
            f'WordPress post {post_id} verification lacks modified_gmt'
        )
    if modified_gmt != record.get('observed_modified_gmt'):
        raise BackfillApplyError(
            f'WordPress post {post_id} modified_gmt changed during APPLY'
        )
    return modified_gmt


def preflight_selected_records(
    client: ApplyWordPressClient,
    config: Dict[str, str],
    current_terms: Dict[str, Dict[str, object]],
    selected: List[Dict[str, object]],
) -> List[int]:
    """Validate every selected record before the first POST is possible."""
    ready_ids = []
    for record in selected:
        post_id = int(record['wp_post_id'])
        live_post = fetch_post_for_guard(client, config, post_id)
        validate_live_post(live_post, record, config, current_terms)
        guarded_state = fetch_guarded_state(client, post_id)
        validate_guarded_state(
            guarded_state,
            live_post,
            record,
            config,
        )
        ready_ids.append(post_id)
    return ready_ids


class AuditJournal:
    """Durable, non-overwriting JSON audit journal for mutating runs."""

    def __init__(
        self,
        output_path: Path,
        document: Dict[str, object],
        *,
        lock_path: Optional[Path] = None,
    ):
        self.output_path = output_path.expanduser().resolve()
        if self.output_path.suffix.lower() != '.json':
            raise BackfillApplyError('Audit output path must end with .json')
        self.lock_path = (
            lock_path.expanduser().resolve()
            if lock_path is not None
            else self.output_path.with_suffix('.lock')
        )
        self.checksum_path = self.output_path.with_suffix('.sha256')
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        if self.output_path.exists() or self.checksum_path.exists():
            raise BackfillApplyError(
                'Refusing to overwrite existing audit or checksum: '
                f'{self.output_path}'
            )
        try:
            self.lock_handle = self.lock_path.open('x', encoding='utf-8')
        except FileExistsError as exc:
            raise BackfillApplyError(
                f'Another APPLY run or stale lock exists: {self.lock_path}'
            ) from exc
        self.lock_handle.write(f'pid={os.getpid()}\n')
        self.lock_handle.flush()
        os.fsync(self.lock_handle.fileno())
        os.chmod(self.lock_path, 0o600)
        self.document = document
        self.write()

    def write(self) -> None:
        payload = (
            json.dumps(
                self.document,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            + '\n'
        ).encode('utf-8')
        checksum_payload = (
            hashlib.sha256(payload).hexdigest()
            + f'  {self.output_path.name}\n'
        ).encode('ascii')
        temp_path = self.output_path.with_name(
            f'.{self.output_path.name}.{os.getpid()}.tmp'
        )
        checksum_temp_path = self.checksum_path.with_name(
            f'.{self.checksum_path.name}.{os.getpid()}.tmp'
        )
        try:
            with temp_path.open('wb') as temp_file:
                temp_file.write(payload)
                temp_file.flush()
                os.fsync(temp_file.fileno())
            os.chmod(temp_path, 0o600)
            with checksum_temp_path.open('wb') as checksum_file:
                checksum_file.write(checksum_payload)
                checksum_file.flush()
                os.fsync(checksum_file.fileno())
            os.chmod(checksum_temp_path, 0o600)
            os.replace(temp_path, self.output_path)
            os.replace(checksum_temp_path, self.checksum_path)
        finally:
            if temp_path.exists():
                temp_path.unlink()
            if checksum_temp_path.exists():
                checksum_temp_path.unlink()

    def close(self, *, remove_lock: bool = True) -> None:
        if getattr(self, 'lock_handle', None):
            self.lock_handle.close()
            self.lock_handle = None
        if remove_lock and self.lock_path.exists():
            self.lock_path.unlink()


def _build_audit_document(
    manifest: Dict[str, object],
    plan_path: Path,
    plan_digest: str,
    env_path: Path,
    selected: List[Dict[str, object]],
    guard_capability: Dict[str, object],
) -> Dict[str, object]:
    return {
        'metadata': {
            'apply_tool_version': APPLY_TOOL_VERSION,
            'status': 'in_progress',
            'started_at_utc': _utc_now(),
            'completed_at_utc': None,
            'plan_path': str(plan_path),
            'plan_sha256': plan_digest,
            'plan_run_id': manifest['metadata']['run_id'],
            'environment_file': str(env_path),
            'site_api_url': manifest['metadata']['site_api_url'],
            'taxonomy_rest_base': manifest['metadata']['taxonomy_rest_base'],
            'selected_count': len(selected),
            'guard_namespace': GUARDED_REST_NAMESPACE,
            'guard_capability': dict(guard_capability),
        },
        'results': [],
    }


def execute_records(
    client: ApplyWordPressClient,
    config: Dict[str, str],
    current_terms: Dict[str, Dict[str, object]],
    selected: List[Dict[str, object]],
    journal: AuditJournal,
    *,
    plan_run_id: str,
    guard_capability: Dict[str, object],
) -> None:
    """Apply selected records sequentially, stopping at the first failure."""
    validate_guard_capability(guard_capability, config)
    if not re.fullmatch(
        r'benefit-backfill-plan-\d{8}T\d{6}Z',
        plan_run_id,
    ):
        raise BackfillApplyError('Cannot execute without a valid plan run ID')
    try:
        for record in selected:
            post_id = int(record['wp_post_id'])
            # Re-check immediately before the only mutating call.
            before = fetch_post_for_guard(client, config, post_id)
            validate_live_post(before, record, config, current_terms)
            guarded_before = fetch_guarded_state(client, post_id)
            source_sha256 = validate_guarded_state(
                guarded_before,
                before,
                record,
                config,
            )
            before_non_taxonomy_sha256 = non_taxonomy_snapshot_sha256(before)
            result = {
                'wp_post_id': post_id,
                'status': 'post_started',
                'started_at_utc': _utc_now(),
                'completed_at_utc': None,
                'previous_term_ids': [],
                'applied_term_ids': [
                    int(value) for value in record['suggested_term_ids']
                ],
                'before_modified_gmt': before['modified_gmt'],
                'after_modified_gmt': None,
                'before_non_taxonomy_sha256': (
                    before_non_taxonomy_sha256
                ),
                'expected_source_sha256': source_sha256,
                'guard_http_status': None,
                'guard_error_code': '',
            }
            journal.document['results'].append(result)
            journal.write()

            try:
                target_slug_by_id = {
                    int(term_id): slug
                    for term_id, slug in zip(
                        record['suggested_term_ids'],
                        record['suggested_slugs'],
                    )
                }
                sorted_target_ids = sorted(target_slug_by_id)
                sorted_target_slugs = [
                    target_slug_by_id[term_id]
                    for term_id in sorted_target_ids
                ]
                client.apply_guarded_benefits(
                    post_id,
                    config['taxonomy_rest_base'],
                    expected_modified_gmt=before['modified_gmt'],
                    expected_term_ids=_taxonomy_ids(
                        before,
                        config['taxonomy_rest_base'],
                    ),
                    target_term_ids=sorted_target_ids,
                    target_term_slugs=sorted_target_slugs,
                    expected_source_sha256=source_sha256,
                    plan_run_id=plan_run_id,
                )
            except GuardedWriteRejected as update_error:
                result['status'] = 'guard_rejected'
                result['guard_http_status'] = update_error.http_status
                result['guard_error_code'] = update_error.error_code
                result['completed_at_utc'] = _utc_now()
                journal.write()
                raise BackfillApplyError(
                    f'Guarded endpoint rejected post {post_id}; '
                    'no automatic retry was attempted'
                ) from update_error
            except GuardedWriteAmbiguous as update_error:
                result['guard_http_status'] = update_error.http_status
                result['guard_error_code'] = update_error.error_code
                # Never retry a write whose outcome may be ambiguous. A GET
                # can prove success, but seeing the original state is still
                # treated as unknown because the request may complete later.
                reconciliation = fetch_post_for_guard(
                    client,
                    config,
                    post_id,
                )
                try:
                    result['after_modified_gmt'] = validate_applied_post(
                        reconciliation,
                        record,
                        config,
                        before_non_taxonomy_sha256,
                    )
                    guarded_after = fetch_guarded_state(client, post_id)
                    validate_guarded_applied_state(
                        guarded_after,
                        reconciliation,
                        record,
                        config,
                    )
                except BackfillApplyError:
                    current_ids = _taxonomy_ids(
                        reconciliation,
                        config['taxonomy_rest_base'],
                    )
                    if current_ids == []:
                        result['status'] = 'ambiguous_original_observed'
                    else:
                        result['status'] = 'conflict_after_update_error'
                    result['completed_at_utc'] = _utc_now()
                    journal.write()
                    raise BackfillApplyError(
                        f'Post {post_id} update outcome is unresolved; '
                        'do not retry this plan automatically'
                    ) from update_error
                else:
                    result['status'] = 'state_verified_after_ambiguous'
                    result['completed_at_utc'] = _utc_now()
                    journal.write()
                    raise BackfillApplyError(
                        f'Post {post_id} reached the target state after an '
                        'ambiguous response; stop and inspect the audit'
                    ) from update_error
            after = fetch_post_for_guard(client, config, post_id)
            result['after_modified_gmt'] = validate_applied_post(
                after,
                record,
                config,
                before_non_taxonomy_sha256,
            )
            guarded_after = fetch_guarded_state(client, post_id)
            validate_guarded_applied_state(
                guarded_after,
                after,
                record,
                config,
            )
            result['status'] = 'applied_verified'
            result['completed_at_utc'] = _utc_now()
            journal.write()

        journal.document['metadata']['status'] = 'completed'
        journal.document['metadata']['completed_at_utc'] = _utc_now()
        journal.write()
    except Exception as exc:
        journal.document['metadata']['status'] = 'failed'
        journal.document['metadata']['completed_at_utc'] = _utc_now()
        journal.document['metadata']['error'] = (
            f'{type(exc).__name__}: {str(exc)}'
        )
        if journal.document['results']:
            last_result = journal.document['results'][-1]
            if last_result.get('status') == 'post_started':
                last_result['status'] = 'failed_unverified'
                last_result['completed_at_utc'] = _utc_now()
        journal.write()
        raise


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            'Preflight or apply an exact-legacy WordPress benefit backfill. '
            'Without --execute, this command sends GET requests only.'
        )
    )
    parser.add_argument('--env-file', required=True, type=Path)
    parser.add_argument('--plan', required=True, type=Path)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument(
        '--post-id',
        action='append',
        type=int,
        default=[],
        help='Select one auto_ready post ID; repeat only after canary.',
    )
    selection.add_argument(
        '--all-auto-ready',
        action='store_true',
        help='Select every auto_ready record in the complete plan.',
    )
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Enable guarded compare-and-set WordPress POST requests.',
    )
    parser.add_argument(
        '--confirm-run-id',
        help='Required with --execute; must equal the plan run_id.',
    )
    parser.add_argument(
        '--confirm-count',
        type=int,
        help='Required when executing more than one selected post.',
    )
    parser.add_argument(
        '--audit-output',
        type=Path,
        help='Required with --execute; new JSON audit path.',
    )
    parser.add_argument('--ca-bundle', type=Path)
    parser.add_argument('--timeout', type=int, default=20)
    parser.add_argument('--max-retries', type=int, default=2)
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    env_path = args.env_file.expanduser().resolve()
    load_isolated_wordpress_env(env_path)
    config = PLANNER.build_wordpress_config()
    manifest, plan_digest, plan_path = load_verified_manifest(args.plan)
    records_by_id = validate_manifest(
        manifest,
        config,
        env_path,
    )
    selected = select_records(
        records_by_id,
        post_ids=args.post_id,
        all_auto_ready=args.all_auto_ready,
    )

    if not args.execute and (
        args.confirm_run_id is not None
        or args.confirm_count is not None
        or args.audit_output is not None
    ):
        raise BackfillApplyError(
            'Confirmation and audit arguments are only valid with --execute'
        )
    if args.execute:
        if args.confirm_run_id != manifest['metadata']['run_id']:
            raise BackfillApplyError(
                '--confirm-run-id must exactly match the plan run_id'
            )
        if args.audit_output is None:
            raise BackfillApplyError('--audit-output is required with --execute')
        if len(selected) > 1 and args.confirm_count != len(selected):
            raise BackfillApplyError(
                '--confirm-count must equal the selected post count'
            )
        if len(selected) == 1 and args.confirm_count not in {None, 1}:
            raise BackfillApplyError(
                '--confirm-count must be 1 for a one-post canary'
            )

    verify = True
    if args.ca_bundle:
        ca_bundle = args.ca_bundle.expanduser().resolve()
        if not ca_bundle.is_file():
            raise BackfillApplyError(f'CA bundle not found: {ca_bundle}')
        verify = str(ca_bundle)

    client = ApplyWordPressClient(
        config['api_url'],
        config['username'],
        config['app_password'],
        verify=verify,
        timeout=args.timeout,
        max_retries=args.max_retries,
    )

    mode = (
        'EXECUTE (guarded taxonomy compare-and-set POST enabled)'
        if args.execute
        else 'PREFLIGHT (read-only; WordPress GET requests only)'
    )
    print(f'Mode: {mode}')
    print(f'Environment: {env_path}')
    print(f'WordPress API: {config["api_url"]}')
    print(f'Plan: {plan_path}')
    print(f'Plan SHA256: {plan_digest}')
    print(f'Plan run_id: {manifest["metadata"]["run_id"]}')
    print(f'Selected: {len(selected)}')

    guard_capability = fetch_and_validate_guard_capability(client, config)
    print(
        'Guarded endpoint: '
        f'{GUARDED_REST_NAMESPACE} contract '
        f'{guard_capability["contract_version"]} '
        f'(plugin {guard_capability["plugin_version"]})'
    )
    PLANNER.validate_wordpress_schema(client, config)
    current_terms = PLANNER.fetch_and_validate_terms(
        client,
        config['taxonomy_rest_base'],
    )
    validate_term_snapshot(manifest['metadata'], current_terms)
    ready_ids = preflight_selected_records(
        client,
        config,
        current_terms,
        selected,
    )
    for post_id in ready_ids:
        print(f'READY: post_id={post_id}')

    if not args.execute:
        print('Result: PREFLIGHT PASS (no WordPress changes)')
        return 0

    journal = AuditJournal(
        args.audit_output,
        _build_audit_document(
            manifest,
            plan_path,
            plan_digest,
            env_path,
            selected,
            guard_capability,
        ),
        lock_path=plan_path.with_suffix('.apply.lock'),
    )
    try:
        execute_records(
            client,
            config,
            current_terms,
            selected,
            journal,
            plan_run_id=manifest['metadata']['run_id'],
            guard_capability=guard_capability,
        )
    finally:
        journal.close(
            remove_lock=(
                journal.document['metadata'].get('status') == 'completed'
            )
        )
    print(f'Result: APPLY PASS ({len(selected)} posts verified)')
    print(f'Audit: {journal.output_path}')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (BackfillApplyError, PLANNER.BackfillPlanError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        raise SystemExit(1)
