#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create a read-only plan for backfilling WordPress benefit taxonomy.

Safety boundary:
- WordPress is accessed with authenticated GET requests only.
- No WordPress term or post is created or updated.
- No LINE, Telegram, fetcher, or MySQL workflow is invoked.
- Output is an audit manifest for human review and the separate fail-closed
  APPLY workflow.
"""

import argparse
import csv
import hashlib
import html
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

import requests
from requests.auth import HTTPBasicAuth

from benefit_classifier import (
    BENEFIT_KEYWORDS,
    BENEFIT_TERM_SLUGS,
    BENEFITS_PER_ARTICLE,
    CLASSIFIER_VERSION,
    classify_benefits,
)


PLAN_SCHEMA_VERSION = '2'
PLANNER_CLASSIFIER_MODE = 'strict'
DEFAULT_POST_TYPE = 'innovation-tip'
DEFAULT_TAXONOMY = 'organization_benefit'
DEFAULT_TAXONOMY_REST_BASE = 'organization-benefits'
REST_PER_PAGE = 100
MIN_SUMMARY_LENGTH = 30
RETRYABLE_HTTP_STATUSES = {429, 500, 502, 503, 504}
FOOTER_MARKERS = (
    'ที่มา:',
    'เผยแพร่เมื่อ:',
    'วันที่:',
    'ลิงก์:',
)


class BackfillPlanError(RuntimeError):
    """Raised when the planner cannot safely produce a complete manifest."""


def load_explicit_env_file(env_path: Path) -> None:
    """Load one explicitly selected env file without printing its values."""
    if not env_path.is_file():
        raise BackfillPlanError(f'Environment file not found: {env_path}')

    with env_path.open('r', encoding='utf-8') as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            key = key.strip()
            if not key:
                continue
            value = value.strip().strip('"').strip("'").strip()
            # --env-file is explicit and therefore authoritative for this
            # one-shot planner process.
            os.environ[key] = value


def build_wordpress_config() -> Dict[str, str]:
    """Read and validate the minimum configuration needed for GET requests."""
    configured_api_url = os.getenv('WP_API_URL', '').strip().rstrip('/')
    parsed_configured_url = urlparse(configured_api_url)
    if (
        parsed_configured_url.scheme.lower() != 'https'
        or not parsed_configured_url.netloc
        or parsed_configured_url.username is not None
        or parsed_configured_url.password is not None
        or parsed_configured_url.query
        or parsed_configured_url.fragment
    ):
        raise BackfillPlanError(
            'WP_API_URL must be HTTPS without credentials, query, or fragment'
        )

    configured_path = parsed_configured_url.path.rstrip('/')
    if configured_path.endswith('/wp-json/wp/v2'):
        wordpress_v2_path = configured_path
    elif configured_path.endswith('/wp-json'):
        wordpress_v2_path = configured_path + '/wp/v2'
    elif configured_path == '':
        wordpress_v2_path = '/wp-json/wp/v2'
    else:
        raise BackfillPlanError(
            'WP_API_URL path must be the site root, /wp-json, '
            'or /wp-json/wp/v2'
        )
    wordpress_v2_api_url = (
        f'{parsed_configured_url.scheme}://'
        f'{parsed_configured_url.netloc}'
        f'{wordpress_v2_path}'
    )

    config = {
        'api_url': wordpress_v2_api_url,
        'username': os.getenv('WP_USERNAME', '').strip(),
        'app_password': os.getenv('WP_APP_PASSWORD', '').strip(),
        'post_type': os.getenv(
            'WP_INNOVATION_TIP_POST_TYPE',
            DEFAULT_POST_TYPE,
        ).strip().strip('/'),
        'taxonomy': os.getenv(
            'WP_BENEFIT_TAXONOMY',
            DEFAULT_TAXONOMY,
        ).strip(),
        'taxonomy_rest_base': os.getenv(
            'WP_BENEFIT_TAXONOMY_REST_BASE',
            DEFAULT_TAXONOMY_REST_BASE,
        ).strip().strip('/'),
    }
    missing = [
        key for key in ('api_url', 'username', 'app_password')
        if not config[key]
    ]
    if missing:
        raise BackfillPlanError(
            'Missing WordPress configuration: ' + ', '.join(missing)
        )

    if not config['post_type'] or not config['taxonomy_rest_base']:
        raise BackfillPlanError('WordPress REST base configuration is incomplete')
    return config


class ReadOnlyWordPressClient:
    """Small REST client whose public surface permits GET requests only."""

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
        self.verify = verify
        self.timeout = max(1, int(timeout))
        self.max_retries = max(0, int(max_retries))
        self.sleep_fn = sleep_fn
        self.session = session or requests.Session()
        self.session.auth = HTTPBasicAuth(username, app_password)
        self.session.headers.update({
            'Accept': 'application/json',
            'User-Agent': 'Innovation-News-Backfill-Planner/1.0',
        })

    def get(self, relative_path: str, *, params=None):
        """Issue a retried GET and return the response."""
        url = f"{self.api_url}/{relative_path.lstrip('/')}"
        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.request(
                    'GET',
                    url,
                    params=params or {},
                    timeout=self.timeout,
                    verify=self.verify,
                )
            except requests.RequestException as exc:
                if attempt < self.max_retries:
                    self.sleep_fn(min(2 ** attempt, 4))
                    continue
                raise BackfillPlanError(
                    f'WordPress GET failed after retries: {type(exc).__name__}'
                ) from exc

            if response.status_code == 200:
                return response
            if (
                response.status_code in RETRYABLE_HTTP_STATUSES
                and attempt < self.max_retries
            ):
                self.sleep_fn(min(2 ** attempt, 4))
                continue
            raise BackfillPlanError(
                f'WordPress GET returned HTTP {response.status_code} '
                f'for {relative_path}'
            )

        raise BackfillPlanError('WordPress GET retry loop ended unexpectedly')

    def get_json(self, relative_path: str, *, params=None):
        response = self.get(relative_path, params=params)
        try:
            return response.json(), response.headers
        except (TypeError, ValueError) as exc:
            raise BackfillPlanError(
                f'WordPress returned invalid JSON for {relative_path}'
            ) from exc


def validate_wordpress_schema(
    client: ReadOnlyWordPressClient,
    config: Dict[str, str],
) -> None:
    """Fail closed unless the CPT/taxonomy REST relationship is exact."""
    post_type_data, _ = client.get_json(
        f"types/{config['post_type']}"
    )
    if not isinstance(post_type_data, dict):
        raise BackfillPlanError('WordPress post type schema is invalid')
    if config['taxonomy'] not in post_type_data.get('taxonomies', []):
        raise BackfillPlanError(
            f"Taxonomy {config['taxonomy']} is not attached to "
            f"post type {config['post_type']}"
        )

    taxonomy_data, _ = client.get_json(
        f"taxonomies/{config['taxonomy']}"
    )
    if not isinstance(taxonomy_data, dict):
        raise BackfillPlanError('WordPress taxonomy schema is invalid')
    if taxonomy_data.get('rest_base') != config['taxonomy_rest_base']:
        raise BackfillPlanError(
            'WordPress taxonomy REST base does not match configuration'
        )
    if config['post_type'] not in taxonomy_data.get('types', []):
        raise BackfillPlanError(
            'WordPress taxonomy does not list the innovation post type'
        )


def fetch_and_validate_terms(
    client: ReadOnlyWordPressClient,
    taxonomy_rest_base: str,
) -> Dict[str, Dict[str, object]]:
    """Read the controlled vocabulary and require the exact 20 terms."""
    payload, _ = client.get_json(
        taxonomy_rest_base,
        params={
            'hide_empty': 'false',
            'per_page': REST_PER_PAGE,
            'orderby': 'id',
            'order': 'asc',
        },
    )
    if not isinstance(payload, list):
        raise BackfillPlanError('WordPress benefit term response is invalid')

    terms_by_slug = {}
    term_ids = set()
    for term in payload:
        if not isinstance(term, dict):
            raise BackfillPlanError('WordPress returned an invalid benefit term')
        slug = str(term.get('slug', '')).strip()
        name = html.unescape(str(term.get('name', '')).strip())
        try:
            term_id = int(term.get('id'))
        except (TypeError, ValueError) as exc:
            raise BackfillPlanError(
                f'WordPress returned an invalid term ID for {slug or "unknown"}'
            ) from exc
        if (
            not slug
            or term_id <= 0
            or slug in terms_by_slug
            or term_id in term_ids
        ):
            raise BackfillPlanError('WordPress benefit terms are duplicated')
        terms_by_slug[slug] = {
            'id': term_id,
            'slug': slug,
            'name': name,
        }
        term_ids.add(term_id)

    expected_slugs = set(BENEFIT_TERM_SLUGS.values())
    actual_slugs = set(terms_by_slug)
    if actual_slugs != expected_slugs:
        missing = sorted(expected_slugs - actual_slugs)
        unexpected = sorted(actual_slugs - expected_slugs)
        raise BackfillPlanError(
            'Controlled WordPress benefit terms do not match. '
            f'Missing={missing}; unexpected={unexpected}'
        )

    for expected_name, slug in BENEFIT_TERM_SLUGS.items():
        if terms_by_slug[slug]['name'] != expected_name:
            raise BackfillPlanError(
                f"WordPress term name mismatch for slug '{slug}'"
            )
    return terms_by_slug


def fetch_all_posts(
    client: ReadOnlyWordPressClient,
    post_type_rest_base: str,
    taxonomy_rest_base: str,
    *,
    status: str = 'publish',
) -> List[Dict[str, object]]:
    """Fetch a complete, ordered post inventory using REST pagination."""
    fields = [
        'id',
        'status',
        'slug',
        'link',
        'date_gmt',
        'modified_gmt',
        'title',
        'content',
        'excerpt',
        'meta',
        taxonomy_rest_base,
    ]
    base_params = {
        'context': 'edit',
        'status': status,
        'per_page': REST_PER_PAGE,
        'orderby': 'id',
        'order': 'asc',
        '_fields': ','.join(fields),
    }

    posts = []
    expected_total = None
    total_pages = None
    page = 1
    while True:
        params = dict(base_params)
        params['page'] = page
        payload, headers = client.get_json(
            post_type_rest_base,
            params=params,
        )
        if not isinstance(payload, list):
            raise BackfillPlanError('WordPress post collection is invalid')

        if (
            headers.get('X-WP-Total') is None
            or headers.get('X-WP-TotalPages') is None
        ):
            raise BackfillPlanError(
                'WordPress pagination headers are missing; '
                'refusing to create a potentially incomplete plan'
            )
        try:
            response_total = int(headers.get('X-WP-Total'))
            response_total_pages = int(headers.get('X-WP-TotalPages'))
        except (TypeError, ValueError) as exc:
            raise BackfillPlanError(
                'WordPress pagination headers are invalid'
            ) from exc

        if page == 1:
            expected_total = response_total
            total_pages = response_total_pages
            valid_empty_collection = expected_total == 0 and total_pages == 0
            valid_nonempty_collection = expected_total > 0 and total_pages >= 1
            if not (valid_empty_collection or valid_nonempty_collection):
                raise BackfillPlanError(
                    'WordPress pagination totals are inconsistent'
                )
        elif (
            response_total != expected_total
            or response_total_pages != total_pages
        ):
            raise BackfillPlanError(
                'WordPress pagination totals changed during inventory'
            )

        posts.extend(payload)
        if total_pages == 0:
            break
        if page >= total_pages:
            break
        page += 1

    ids = []
    for post in posts:
        if not isinstance(post, dict) or 'id' not in post:
            raise BackfillPlanError('WordPress returned an invalid post')
        if taxonomy_rest_base not in post:
            raise BackfillPlanError(
                f"WordPress post {post.get('id')} is missing "
                f"the '{taxonomy_rest_base}' REST field"
            )
        try:
            ids.append(int(post['id']))
        except (TypeError, ValueError) as exc:
            raise BackfillPlanError('WordPress returned a non-integer post ID') from exc

    if len(ids) != len(set(ids)):
        raise BackfillPlanError('WordPress returned duplicate post IDs')
    if expected_total is not None and len(posts) != expected_total:
        raise BackfillPlanError(
            f'WordPress inventory count mismatch: expected {expected_total}, '
            f'fetched {len(posts)}'
        )
    return sorted(posts, key=lambda item: int(item['id']))


def _wp_stored_field_values(field) -> List[str]:
    """Return stored/raw values only; rendered REST output is not a CAS input."""
    if isinstance(field, str):
        return [field]
    if isinstance(field, dict):
        raw_value = field.get('raw')
        return (
            [raw_value]
            if isinstance(raw_value, str) and raw_value.strip()
            else []
        )
    if isinstance(field, (list, tuple)):
        values = []
        for value in field:
            values.extend(_wp_stored_field_values(value))
        return values
    return []


class _VisibleTextParser(HTMLParser):
    """Small stdlib HTML-to-text parser with block/list separators."""

    BLOCK_TAGS = {
        'address', 'article', 'aside', 'blockquote', 'br', 'div', 'dl',
        'dt', 'dd', 'fieldset', 'figcaption', 'figure', 'footer', 'form',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'header', 'hr', 'li', 'main',
        'nav', 'ol', 'p', 'pre', 'section', 'table', 'tbody', 'td', 'tfoot',
        'th', 'thead', 'tr', 'ul',
    }
    IGNORED_TAGS = {'script', 'style', 'noscript'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.ignored_depth = 0

    def handle_starttag(self, tag, attrs):
        normalized_tag = tag.lower()
        if normalized_tag in self.IGNORED_TAGS:
            self.ignored_depth += 1
            return
        if not self.ignored_depth and normalized_tag in self.BLOCK_TAGS:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        normalized_tag = tag.lower()
        if normalized_tag in self.IGNORED_TAGS:
            self.ignored_depth = max(0, self.ignored_depth - 1)
            return
        if not self.ignored_depth and normalized_tag in self.BLOCK_TAGS:
            self.parts.append('\n')

    def handle_data(self, data):
        if not self.ignored_depth:
            self.parts.append(data)

    def text(self) -> str:
        return ''.join(self.parts)


def _plain_text(value: str) -> str:
    parser = _VisibleTextParser()
    raw_value = str(value or '')
    try:
        parser.feed(raw_value)
        parser.close()
        text = parser.text()
    except Exception:
        text = re.sub(r'<[^>]*>', '\n', raw_value)
    text = html.unescape(text)
    text = unicodedata.normalize('NFKC', text)
    text = text.replace('\x00', '').replace('\r\n', '\n').replace('\r', '\n')
    return '\n'.join(
        re.sub(r'[ \t]+', ' ', line).strip()
        for line in text.split('\n')
        if line.strip()
    )


def _content_candidates(post: Dict[str, object]) -> List[Tuple[str, str]]:
    candidates = []
    meta = post.get('meta')
    if isinstance(meta, dict):
        for value in _wp_stored_field_values(
            meta.get('ptb_innovation_tip_content')
        ):
            candidates.append(('ptb_meta', value))

    for value in _wp_stored_field_values(post.get('content')):
        candidates.append(('wordpress_content', value))
    for value in _wp_stored_field_values(post.get('excerpt')):
        candidates.append(('wordpress_excerpt', value))

    unique = []
    seen = set()
    for source, value in candidates:
        normalized = str(value).strip()
        digest = hashlib.sha256(normalized.encode('utf-8')).hexdigest()
        if not normalized or digest in seen:
            continue
        seen.add(digest)
        unique.append((source, normalized))
    return unique


def _strip_bullet(line: str) -> str:
    value = re.sub(r'^[\s•●▪◦\-–—*]+', '', line).strip()
    value = re.sub(r'^[^\wก-๙]+', '', value, flags=re.UNICODE).strip()
    return value.strip(' \t:;,.')


def extract_legacy_benefits(value: str) -> List[str]:
    """Extract exact controlled names only from the legacy benefit section."""
    text = _plain_text(value).replace('•', '\n•')
    lines = text.split('\n')
    section_lines = []
    in_section = False

    for line in lines:
        if not in_section:
            if 'ประโยชน์ต่อองค์กร' not in line:
                continue
            in_section = True
            remainder = line.split('ประโยชน์ต่อองค์กร', 1)[1].lstrip(' :')
            if remainder:
                section_lines.append(remainder)
            continue

        if any(line.startswith(marker) for marker in FOOTER_MARKERS):
            break
        section_lines.append(line)

    found = []
    controlled_names = set(BENEFIT_TERM_SLUGS)
    for line in section_lines:
        candidate = _strip_bullet(line)
        if candidate in controlled_names and candidate not in found:
            found.append(candidate)
    return found


def extract_summary(value: str) -> str:
    """Return visible content before legacy benefits/footer boilerplate."""
    text = _plain_text(value)
    if 'ประโยชน์ต่อองค์กร' in text:
        text = text.split('ประโยชน์ต่อองค์กร', 1)[0]
    for marker in FOOTER_MARKERS:
        if marker in text:
            text = text.split(marker, 1)[0]
    return re.sub(r'\s+', ' ', text).strip()


def extract_post_inputs(post: Dict[str, object]) -> Dict[str, object]:
    """Extract title, historical labels, and uncontaminated summary text."""
    title_values = _wp_stored_field_values(post.get('title'))
    title = _plain_text(title_values[0]) if title_values else ''

    legacy_candidates = []
    summary = ''
    summary_source = ''
    for source, value in _content_candidates(post):
        extracted = extract_legacy_benefits(value)
        if extracted:
            legacy_candidates.append({
                'source': source,
                'benefits': extracted,
            })
        if not summary:
            extracted_summary = extract_summary(value)
            if extracted_summary:
                summary = extracted_summary
                summary_source = source

    legacy_benefits = (
        list(legacy_candidates[0]['benefits'])
        if legacy_candidates
        else []
    )
    legacy_source = (
        str(legacy_candidates[0]['source'])
        if legacy_candidates
        else ''
    )
    distinct_legacy_sets = {
        frozenset(candidate['benefits'])
        for candidate in legacy_candidates
    }
    legacy_conflict = len(distinct_legacy_sets) > 1

    if summary and title and summary.casefold() == title.casefold():
        summary = ''
        summary_source = ''
    if summary and len(summary) < MIN_SUMMARY_LENGTH:
        summary = ''
        summary_source = ''

    return {
        'title': title,
        'legacy_benefits': legacy_benefits,
        'legacy_source': legacy_source,
        'legacy_candidates': legacy_candidates,
        'legacy_conflict': legacy_conflict,
        'summary': summary,
        'summary_source': summary_source or 'title_only',
    }


def _select_from_more_than_three(
    legacy_benefits: Iterable[str],
    diagnostics: Dict[str, object],
) -> List[str]:
    score_by_name = {
        item['benefit']: int(item['score'])
        for item in diagnostics['ranked_matches']
    }
    canonical_order = {
        name: index for index, name in enumerate(BENEFIT_KEYWORDS)
    }
    unique_legacy = sorted(
        set(legacy_benefits),
        key=lambda name: (
            -score_by_name.get(name, 0),
            canonical_order[name],
        ),
    )
    return unique_legacy[:BENEFITS_PER_ARTICLE]


def _fill_to_three(
    initial: Iterable[str],
    diagnostics: Dict[str, object],
) -> List[str]:
    selected = []
    for name in list(initial) + list(diagnostics['selected']):
        if name in BENEFIT_TERM_SLUGS and name not in selected:
            selected.append(name)
        if len(selected) == BENEFITS_PER_ARTICLE:
            break
    return selected


def _has_cutoff_tie(diagnostics: Dict[str, object]) -> bool:
    ranked = diagnostics['ranked_matches']
    return (
        len(ranked) > BENEFITS_PER_ARTICLE
        and ranked[BENEFITS_PER_ARTICLE - 1]['score']
        == ranked[BENEFITS_PER_ARTICLE]['score']
    )


def plan_post(
    post: Dict[str, object],
    taxonomy_rest_base: str,
    terms_by_slug: Dict[str, Dict[str, object]],
) -> Dict[str, object]:
    """Build one deterministic plan record without mutating WordPress."""
    post_id = int(post['id'])
    current_value = post[taxonomy_rest_base]
    if not isinstance(current_value, list):
        raise BackfillPlanError(
            f"WordPress post {post_id} has an invalid taxonomy field"
        )
    try:
        current_term_ids = sorted({int(value) for value in current_value})
    except (TypeError, ValueError) as exc:
        raise BackfillPlanError(
            f"WordPress post {post_id} has invalid taxonomy IDs"
        ) from exc

    extracted = extract_post_inputs(post)
    record = {
        'wp_post_id': post_id,
        'title': extracted['title'],
        'slug': str(post.get('slug', '')),
        'status': str(post.get('status', '')),
        'permalink': str(post.get('link', '')),
        'date_gmt': str(post.get('date_gmt', '')),
        'observed_modified_gmt': str(post.get('modified_gmt', '')),
        'existing_term_ids': current_term_ids,
        'legacy_benefits': extracted['legacy_benefits'],
        'legacy_source': extracted['legacy_source'],
        'legacy_candidates': extracted['legacy_candidates'],
        'legacy_conflict': extracted['legacy_conflict'],
        'summary_source': extracted['summary_source'],
        'summary_preview': extracted['summary'][:240],
        'input_text_sha256': hashlib.sha256(
            (
                extracted['title']
                + '\n'
                + extracted['summary']
            ).encode('utf-8')
        ).hexdigest(),
        'suggested_names': [],
        'suggested_slugs': [],
        'suggested_term_ids': [],
        'evidence': [],
        'classifier_fallback_count': 0,
        'plan_status': 'skip_existing',
        'review_reasons': [],
    }
    if not record['observed_modified_gmt']:
        raise BackfillPlanError(
            f'WordPress post {post_id} is missing modified_gmt'
        )
    if current_term_ids:
        return record

    diagnostics = classify_benefits(
        extracted['title'],
        extracted['summary'],
        strict=True,
    )
    legacy_benefits = extracted['legacy_benefits']
    review_reasons = []

    if len(legacy_benefits) == BENEFITS_PER_ARTICLE:
        proposed = list(legacy_benefits)
        plan_status = 'auto_ready'
    elif len(legacy_benefits) > BENEFITS_PER_ARTICLE:
        proposed = _select_from_more_than_three(
            legacy_benefits,
            diagnostics,
        )
        plan_status = 'review'
        review_reasons.append('more_than_three_legacy_benefits')
    elif legacy_benefits:
        proposed = _fill_to_three(legacy_benefits, diagnostics)
        plan_status = 'review'
        review_reasons.append('incomplete_legacy_benefits')
    else:
        proposed = list(diagnostics['selected'])
        # A classifier-only proposal is useful for bulk review but is not
        # strong enough to mutate historical posts without human approval.
        plan_status = 'review'
        review_reasons.append('classifier_only')

    if len(legacy_benefits) != BENEFITS_PER_ARTICLE:
        if diagnostics['fallback_count']:
            review_reasons.append('classifier_fallback_used')
        if extracted['summary_source'] == 'title_only':
            review_reasons.append('title_only')
        if _has_cutoff_tie(diagnostics):
            review_reasons.append('cutoff_score_tie')
        if len(diagnostics['ranked_matches']) < BENEFITS_PER_ARTICLE:
            review_reasons.append('fewer_than_three_direct_matches')
        plan_status = 'review'

    if extracted['legacy_conflict']:
        review_reasons.append('conflicting_legacy_benefits')
        plan_status = 'review'

    proposed = _fill_to_three(proposed, diagnostics)
    if len(proposed) != BENEFITS_PER_ARTICLE:
        raise BackfillPlanError(
            f'Planner could not produce three controlled benefits for post {post_id}'
        )

    detail_by_name = {
        item['benefit']: item
        for item in diagnostics['selected_details']
    }
    ranked_by_name = {
        item['benefit']: item
        for item in diagnostics['ranked_matches']
    }
    evidence = []
    for name in proposed:
        slug = BENEFIT_TERM_SLUGS[name]
        detail = ranked_by_name.get(name) or detail_by_name.get(name, {})
        evidence.append({
            'name': name,
            'slug': slug,
            'term_id': terms_by_slug[slug]['id'],
            'legacy': name in legacy_benefits,
            'origin': (
                'legacy'
                if name in legacy_benefits
                else detail.get('origin', 'fallback')
            ),
            'score': int(detail.get('score', 0)),
            'title_keywords': list(detail.get('title_keywords', [])),
            'summary_keywords': list(detail.get('summary_keywords', [])),
        })

    record.update({
        'suggested_names': proposed,
        'suggested_slugs': [BENEFIT_TERM_SLUGS[name] for name in proposed],
        'suggested_term_ids': [
            terms_by_slug[BENEFIT_TERM_SLUGS[name]]['id']
            for name in proposed
        ],
        'evidence': evidence,
        'classifier_fallback_count': diagnostics['fallback_count'],
        'plan_status': plan_status,
        'review_reasons': sorted(set(review_reasons)),
    })
    return record


def build_manifest(
    posts: List[Dict[str, object]],
    config: Dict[str, str],
    terms_by_slug: Dict[str, Dict[str, object]],
    *,
    env_path: str,
    generated_at: Optional[datetime] = None,
    post_ids: Optional[Iterable[int]] = None,
    limit: Optional[int] = None,
) -> Dict[str, object]:
    generated_at = generated_at or datetime.now(timezone.utc)
    requested_ids = {int(value) for value in (post_ids or [])}

    records = [
        plan_post(post, config['taxonomy_rest_base'], terms_by_slug)
        for post in posts
        if not requested_ids or int(post['id']) in requested_ids
    ]
    records.sort(key=lambda item: item['wp_post_id'])

    missing_requested_ids = sorted(
        requested_ids - {record['wp_post_id'] for record in records}
    )
    if missing_requested_ids:
        raise BackfillPlanError(
            f'Requested WordPress post IDs were not found: {missing_requested_ids}'
        )

    truncated = False
    if limit is not None and limit >= 0 and len(records) > limit:
        records = records[:limit]
        truncated = True

    records_bytes = json.dumps(
        records,
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
    ).encode('utf-8')
    counts = {
        'wp_total': len(posts),
        'included': len(records),
        'auto_ready': sum(
            record['plan_status'] == 'auto_ready' for record in records
        ),
        'review': sum(
            record['plan_status'] == 'review' for record in records
        ),
        'skip_existing': sum(
            record['plan_status'] == 'skip_existing' for record in records
        ),
    }

    term_snapshot = [
        terms_by_slug[slug]
        for slug in BENEFIT_TERM_SLUGS.values()
    ]
    return {
        'metadata': {
            'schema_version': PLAN_SCHEMA_VERSION,
            'mode': 'plan_read_only',
            'generated_at_utc': generated_at.isoformat(),
            'run_id': generated_at.strftime(
                'benefit-backfill-plan-%Y%m%dT%H%M%SZ'
            ),
            'site_api_url': config['api_url'],
            'environment_file': str(env_path),
            'post_type': config['post_type'],
            'taxonomy': config['taxonomy'],
            'taxonomy_rest_base': config['taxonomy_rest_base'],
            'classifier_version': CLASSIFIER_VERSION,
            'classifier_mode': PLANNER_CLASSIFIER_MODE,
            'records_sha256': hashlib.sha256(records_bytes).hexdigest(),
            'truncated': truncated,
            'counts': counts,
            'term_snapshot': term_snapshot,
        },
        'records': records,
    }


def _safe_csv_cell(value) -> str:
    if isinstance(value, (list, dict)):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    text = str(value if value is not None else '')
    text = text.replace('\x00', '').replace('\r', ' ').replace('\n', ' ')
    if text.lstrip().startswith(('=', '+', '-', '@')):
        text = "'" + text
    return text


def _manifest_csv_bytes(records: List[Dict[str, object]]) -> bytes:
    import io

    output = io.StringIO(newline='')
    fieldnames = [
        'wp_post_id',
        'plan_status',
        'title',
        'observed_modified_gmt',
        'existing_term_ids',
        'legacy_benefits',
        'legacy_conflict',
        'summary_source',
        'suggested_names',
        'suggested_slugs',
        'suggested_term_ids',
        'classifier_fallback_count',
        'review_reasons',
        'permalink',
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator='\n')
    writer.writeheader()
    for record in records:
        writer.writerow({
            key: _safe_csv_cell(record.get(key, ''))
            for key in fieldnames
        })
    return output.getvalue().encode('utf-8-sig')


def write_manifest_atomic(manifest: Dict[str, object], output_path: Path) -> Dict[str, Path]:
    """Write JSON, CSV, and checksum sidecar without overwriting prior plans."""
    output_path = output_path.resolve()
    if output_path.suffix.lower() != '.json':
        raise BackfillPlanError('Plan output path must end with .json')
    csv_path = output_path.with_suffix('.csv')
    checksum_path = output_path.with_suffix('.sha256')
    lock_path = output_path.with_suffix('.lock')
    destinations = [output_path, csv_path, checksum_path]

    json_bytes = (
        json.dumps(
            manifest,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + '\n'
    ).encode('utf-8')
    csv_bytes = _manifest_csv_bytes(manifest['records'])
    checksum = hashlib.sha256(json_bytes).hexdigest()
    checksum_bytes = f'{checksum}  {output_path.name}\n'.encode('ascii')

    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        lock_handle = lock_path.open('x', encoding='utf-8')
    except FileExistsError as exc:
        raise BackfillPlanError(
            f'Another plan run or stale lock exists: {lock_path}'
        ) from exc

    lock_handle.write(f'pid={os.getpid()}\n')
    lock_handle.flush()

    existing = [str(path) for path in destinations if path.exists()]
    if existing:
        lock_handle.close()
        lock_path.unlink()
        raise BackfillPlanError(
            'Refusing to overwrite existing plan files: ' + ', '.join(existing)
        )

    temp_paths = {
        output_path: output_path.with_name(f'.{output_path.name}.{os.getpid()}.tmp'),
        csv_path: csv_path.with_name(f'.{csv_path.name}.{os.getpid()}.tmp'),
        checksum_path: checksum_path.with_name(
            f'.{checksum_path.name}.{os.getpid()}.tmp'
        ),
    }
    committed_paths = []
    try:
        for destination, payload in (
            (csv_path, csv_bytes),
            (checksum_path, checksum_bytes),
            (output_path, json_bytes),
        ):
            temp_paths[destination].write_bytes(payload)
        os.replace(temp_paths[csv_path], csv_path)
        committed_paths.append(csv_path)
        os.replace(temp_paths[checksum_path], checksum_path)
        committed_paths.append(checksum_path)
        os.replace(temp_paths[output_path], output_path)
        committed_paths.append(output_path)
    except Exception:
        for committed_path in reversed(committed_paths):
            if committed_path.exists():
                committed_path.unlink()
        raise
    finally:
        for temp_path in temp_paths.values():
            if temp_path.exists():
                temp_path.unlink()
        lock_handle.close()
        if lock_path.exists():
            lock_path.unlink()

    return {
        'json': output_path,
        'csv': csv_path,
        'sha256': checksum_path,
    }


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            'Create a read-only WordPress benefit taxonomy backfill plan. '
            'This command never updates WordPress.'
        )
    )
    parser.add_argument(
        '--env-file',
        required=True,
        type=Path,
        help='Explicit .env file to load; no other .env path is scanned.',
    )
    parser.add_argument(
        '--output',
        required=True,
        type=Path,
        help='New .json plan path; matching .csv/.sha256 files are also created.',
    )
    parser.add_argument(
        '--post-id',
        action='append',
        type=int,
        default=[],
        help='Include only this published WordPress post ID; repeat as needed.',
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit manifest rows for preview; metadata will mark it truncated.',
    )
    parser.add_argument(
        '--ca-bundle',
        type=Path,
        help='Optional CA bundle for HTTPS verification.',
    )
    parser.add_argument('--timeout', type=int, default=20)
    parser.add_argument('--max-retries', type=int, default=2)
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.limit is not None and args.limit < 1:
        raise BackfillPlanError('--limit must be at least 1')

    env_path = args.env_file.expanduser().resolve()
    load_explicit_env_file(env_path)
    config = build_wordpress_config()

    verify = True
    if args.ca_bundle:
        ca_bundle = args.ca_bundle.expanduser().resolve()
        if not ca_bundle.is_file():
            raise BackfillPlanError(f'CA bundle not found: {ca_bundle}')
        verify = str(ca_bundle)

    client = ReadOnlyWordPressClient(
        config['api_url'],
        config['username'],
        config['app_password'],
        verify=verify,
        timeout=args.timeout,
        max_retries=args.max_retries,
    )

    print('Mode: PLAN (read-only; WordPress GET requests only)')
    print(f'Environment: {env_path}')
    print(f"WordPress API: {config['api_url']}")

    validate_wordpress_schema(client, config)
    terms_by_slug = fetch_and_validate_terms(
        client,
        config['taxonomy_rest_base'],
    )
    posts = fetch_all_posts(
        client,
        config['post_type'],
        config['taxonomy_rest_base'],
    )
    manifest = build_manifest(
        posts,
        config,
        terms_by_slug,
        env_path=str(env_path),
        post_ids=args.post_id,
        limit=args.limit,
    )
    written = write_manifest_atomic(manifest, args.output)

    counts = manifest['metadata']['counts']
    print(
        'Plan summary: '
        f"wp_total={counts['wp_total']}, "
        f"included={counts['included']}, "
        f"auto_ready={counts['auto_ready']}, "
        f"review={counts['review']}, "
        f"skip_existing={counts['skip_existing']}"
    )
    print(f"JSON: {written['json']}")
    print(f"CSV: {written['csv']}")
    print(f"SHA256: {written['sha256']}")
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except BackfillPlanError as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        raise SystemExit(1)
