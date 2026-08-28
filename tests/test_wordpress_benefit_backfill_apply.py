import copy
import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import requests


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / 'scripts'
APPLY_FILE = SCRIPTS_DIR / 'apply-wordpress-benefit-backfill.py'
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


APPLY = load_module('wordpress_benefit_backfill_apply', APPLY_FILE)
PLANNER = APPLY.PLANNER
PLAN_RUN_ID = 'benefit-backfill-plan-20260726T120000Z'


def config():
    return {
        'api_url': 'https://example.test/wp-json/wp/v2',
        'username': 'bot',
        'app_password': 'application-password',
        'post_type': 'innovation-tip',
        'taxonomy': 'organization_benefit',
        'taxonomy_rest_base': 'organization-benefits',
    }


def guard_capability(**overrides):
    payload = {
        'contract_version': APPLY.GUARDED_CONTRACT_VERSION,
        'plugin_version': '1.2.0',
        'post_type': 'innovation-tip',
        'taxonomy': 'organization_benefit',
        'taxonomy_rest_base': 'organization-benefits',
        'storage_ready': True,
        'controlled_terms_ready': True,
        'guard_strategy': APPLY.GUARDED_STRATEGY,
        'transaction_isolation': APPLY.GUARDED_ISOLATION,
        'source_guard': APPLY.GUARDED_SOURCE,
    }
    payload.update(overrides)
    return payload


def guarded_state(post):
    return {
        'id': post['id'],
        'post_type': 'innovation-tip',
        'status': post['status'],
        'modified_gmt': post['modified_gmt'],
        'current_term_ids': list(post['organization-benefits']),
        'source_sha256': APPLY.source_guard_sha256(post),
        'contract_version': APPLY.GUARDED_CONTRACT_VERSION,
    }


def terms():
    return {
        slug: {'id': 3000 + index, 'slug': slug, 'name': name}
        for index, (name, slug) in enumerate(
            APPLY.BENEFIT_TERM_SLUGS.items(),
            start=1,
        )
    }


def legacy_content(names):
    heading = (
        '\u0e1b\u0e23\u0e30\u0e42\u0e22\u0e0a\u0e19\u0e4c'
        '\u0e15\u0e48\u0e2d\u0e2d\u0e07\u0e04\u0e4c\u0e01\u0e23'
    )
    return (
        '<p>Detailed innovation knowledge for deterministic backfill '
        'verification and organizational learning.</p>'
        f'<strong>{heading}:</strong><ul>'
        + ''.join(f'<li>{name}</li>' for name in names)
        + '</ul>'
    )


def make_post(post_id=700, *, modified=None, taxonomy=None):
    names = list(APPLY.BENEFIT_TERM_SLUGS)[:3]
    content = legacy_content(names)
    modified = modified or datetime.now(timezone.utc).strftime(
        '%Y-%m-%dT%H:%M:%S'
    )
    return {
        'id': post_id,
        'status': 'publish',
        'slug': f'post-{post_id}',
        'link': f'https://example.test/post-{post_id}/',
        'date_gmt': '2026-07-20T02:00:00',
        'modified_gmt': modified,
        'title': {
            'raw': 'Backfill test article',
            'rendered': 'Backfill test article',
        },
        'content': {'raw': content, 'rendered': content},
        'excerpt': {'raw': '', 'rendered': ''},
        'meta': {'ptb_innovation_tip_content': content},
        'organization-benefits': (
            [] if taxonomy is None else list(taxonomy)
        ),
    }


def make_manifest(env_path, posts=None, *, generated_at=None):
    posts = posts or [make_post()]
    return PLANNER.build_manifest(
        posts,
        config(),
        terms(),
        env_path=str(Path(env_path).resolve()),
        generated_at=generated_at or datetime.now(timezone.utc),
    )


class FakeResponse:
    def __init__(self, payload, status_code=200, headers=None):
        self._payload = payload
        self.status_code = status_code
        self.headers = headers or {}

    def json(self):
        return copy.deepcopy(self._payload)


class RecordingSession:
    def __init__(self, response):
        self.response = response
        self.calls = []
        self.headers = {}
        self.auth = None

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.response


class ManifestSafetyTests(unittest.TestCase):
    def test_verified_manifest_accepts_exact_planner_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / '.env'
            env_path.write_text('placeholder=1\n', encoding='utf-8')
            manifest = make_manifest(env_path)
            plan_path = Path(temp_dir) / 'plan.json'
            PLANNER.write_manifest_atomic(manifest, plan_path)

            loaded, digest, resolved = APPLY.load_verified_manifest(plan_path)
            records = APPLY.validate_manifest(
                loaded,
                config(),
                env_path.resolve(),
            )

            self.assertEqual(plan_path.resolve(), resolved)
            self.assertEqual(64, len(digest))
            self.assertEqual([700], sorted(records))

    def test_tampered_plan_is_rejected_before_parsing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / '.env'
            env_path.write_text('placeholder=1\n', encoding='utf-8')
            plan_path = Path(temp_dir) / 'plan.json'
            PLANNER.write_manifest_atomic(
                make_manifest(env_path),
                plan_path,
            )
            plan_path.write_bytes(plan_path.read_bytes() + b' ')

            with self.assertRaisesRegex(
                APPLY.BackfillApplyError,
                'checksum mismatch',
            ):
                APPLY.load_verified_manifest(plan_path)

    def test_checksum_sidecar_filename_must_match(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / '.env'
            env_path.write_text('placeholder=1\n', encoding='utf-8')
            plan_path = Path(temp_dir) / 'plan.json'
            PLANNER.write_manifest_atomic(
                make_manifest(env_path),
                plan_path,
            )
            checksum = plan_path.with_suffix('.sha256')
            checksum.write_text(
                '0' * 64 + '  other.json\n',
                encoding='ascii',
            )
            with self.assertRaisesRegex(
                APPLY.BackfillApplyError,
                'filename or format',
            ):
                APPLY.load_verified_manifest(plan_path)

    def test_duplicate_json_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            plan_path = Path(temp_dir) / 'plan.json'
            payload = b'{"metadata":{},"metadata":{},"records":[]}\n'
            plan_path.write_bytes(payload)
            plan_path.with_suffix('.sha256').write_text(
                hashlib.sha256(payload).hexdigest()
                + '  plan.json\n',
                encoding='ascii',
            )
            with self.assertRaisesRegex(
                APPLY.BackfillApplyError,
                'duplicate key',
            ):
                APPLY.load_verified_manifest(plan_path)

    def test_truncated_or_stale_manifest_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / '.env'
            env_path.write_text('placeholder=1\n', encoding='utf-8')
            truncated = make_manifest(env_path)
            truncated['metadata']['truncated'] = True
            with self.assertRaisesRegex(
                APPLY.BackfillApplyError,
                'truncated',
            ):
                APPLY.validate_manifest(
                    truncated,
                    config(),
                    env_path.resolve(),
                )

            stale = make_manifest(
                env_path,
                generated_at=(
                    datetime.now(timezone.utc) - timedelta(hours=25)
                ),
            )
            with self.assertRaisesRegex(
                APPLY.BackfillApplyError,
                'older than',
            ):
                APPLY.validate_manifest(
                    stale,
                    config(),
                    env_path.resolve(),
                )

    def test_review_record_cannot_be_selected(self):
        record = PLANNER.plan_post(
            make_post(taxonomy=[]),
            'organization-benefits',
            terms(),
        )
        record['plan_status'] = 'review'
        record['review_reasons'] = ['manual_review']
        with self.assertRaisesRegex(
            APPLY.BackfillApplyError,
            'not auto_ready',
        ):
            APPLY.select_records(
                {700: record},
                post_ids=[700],
            )

    def test_environment_loading_does_not_inherit_stale_credentials(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / '.env'
            env_path.write_text(
                'WP_API_URL=https://example.test\n',
                encoding='utf-8',
            )
            with mock.patch.dict(
                os.environ,
                {
                    'WP_USERNAME': 'stale-user',
                    'WP_APP_PASSWORD': 'stale-password',
                },
                clear=False,
            ):
                APPLY.load_isolated_wordpress_env(env_path)
                with self.assertRaises(PLANNER.BackfillPlanError):
                    PLANNER.build_wordpress_config()


class WordPressGuardTests(unittest.TestCase):
    def setUp(self):
        self.post = make_post()
        self.record = PLANNER.plan_post(
            self.post,
            'organization-benefits',
            terms(),
        )

    def test_live_post_guard_accepts_unchanged_post(self):
        APPLY.validate_live_post(
            self.post,
            self.record,
            config(),
            terms(),
        )

    def test_live_post_guard_rejects_taxonomy_or_modified_change(self):
        changed_terms = copy.deepcopy(self.post)
        changed_terms['organization-benefits'] = [
            self.record['suggested_term_ids'][0]
        ]
        with self.assertRaisesRegex(
            APPLY.BackfillApplyError,
            'taxonomy changed',
        ):
            APPLY.validate_live_post(
                changed_terms,
                self.record,
                config(),
                terms(),
            )

        changed_modified = copy.deepcopy(self.post)
        changed_modified['modified_gmt'] = '2099-01-01T00:00:00'
        with self.assertRaisesRegex(
            APPLY.BackfillApplyError,
            'modified_gmt changed',
        ):
            APPLY.validate_live_post(
                changed_modified,
                self.record,
                config(),
                terms(),
            )

    def test_live_post_guard_rejects_hidden_content_change(self):
        changed = copy.deepcopy(self.post)
        changed_content = (
            '<p>Changed content that is still long enough for extraction.</p>'
        )
        changed['content'] = {
            'raw': changed_content,
            'rendered': changed_content,
        }
        changed['meta'] = {
            'ptb_innovation_tip_content': changed_content,
        }
        with self.assertRaisesRegex(
            APPLY.BackfillApplyError,
            'content changed',
        ):
            APPLY.validate_live_post(
                changed,
                self.record,
                config(),
                terms(),
            )

    def test_term_snapshot_must_match_current_wordpress(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / '.env'
            manifest = make_manifest(env_path)
            changed_terms = copy.deepcopy(terms())
            first_slug = next(iter(changed_terms))
            changed_terms[first_slug]['id'] += 100
            with self.assertRaisesRegex(
                APPLY.BackfillApplyError,
                'controlled terms changed',
            ):
                APPLY.validate_term_snapshot(
                    manifest['metadata'],
                    changed_terms,
                )

    def test_post_client_uses_exact_guarded_payload(self):
        target_ids = self.record['suggested_term_ids']
        source_sha256 = APPLY.source_guard_sha256(self.post)
        target_slug_by_id = dict(zip(
            target_ids,
            self.record['suggested_slugs'],
        ))
        target_slugs = [
            target_slug_by_id[term_id]
            for term_id in sorted(target_ids)
        ]
        response = FakeResponse({
            'id': 700,
            'status': 'publish',
            'modified_gmt': self.record['observed_modified_gmt'],
            'organization-benefits': target_ids,
            'contract_version': APPLY.GUARDED_CONTRACT_VERSION,
            'plan_run_id': PLAN_RUN_ID,
            'source_sha256': source_sha256,
            'target_term_slugs': target_slugs,
        })
        session = RecordingSession(response)
        client = APPLY.ApplyWordPressClient(
            config()['api_url'],
            'bot',
            'password',
            session=session,
            sleep_fn=lambda _: None,
        )

        client.apply_guarded_benefits(
            700,
            'organization-benefits',
            expected_modified_gmt=self.record['observed_modified_gmt'],
            expected_term_ids=[],
            target_term_ids=target_ids,
            target_term_slugs=target_slugs,
            expected_source_sha256=source_sha256,
            plan_run_id=PLAN_RUN_ID,
        )

        self.assertEqual(1, len(session.calls))
        method, url, kwargs = session.calls[0]
        self.assertEqual('POST', method)
        self.assertEqual(
            (
                'https://example.test/wp-json/oar-innovation/v1/'
                'benefit-backfill/700'
            ),
            url,
        )
        self.assertEqual(
            {
                'expected_modified_gmt': (
                    self.record['observed_modified_gmt']
                ),
                'expected_term_ids': [],
                'target_term_ids': sorted(target_ids),
                'target_term_slugs': target_slugs,
                'expected_source_sha256': source_sha256,
                'plan_run_id': PLAN_RUN_ID,
            },
            kwargs['json'],
        )
        self.assertTrue(kwargs['verify'])
        self.assertFalse(kwargs['allow_redirects'])

    def test_guarded_namespace_derivation_preserves_subdirectory(self):
        self.assertEqual(
            (
                'https://example.test/site/wp-json/'
                'oar-innovation/v1'
            ),
            APPLY._guarded_api_url(
                'https://example.test/site/wp-json/wp/v2'
            ),
        )

    def test_capability_requires_contract_and_boolean_storage(self):
        validated = APPLY.validate_guard_capability(
            guard_capability(plugin_version='1.2.1'),
            config(),
        )
        self.assertEqual('1.2.1', validated['plugin_version'])

        for changed in (
            {'contract_version': '1'},
            {'storage_ready': 1},
            {'controlled_terms_ready': False},
            {'guard_strategy': 'best-effort'},
            {'transaction_isolation': 'read-committed'},
            {'source_guard': 'none'},
        ):
            with self.subTest(changed=changed):
                with self.assertRaises(APPLY.BackfillApplyError):
                    APPLY.validate_guard_capability(
                        guard_capability(**changed),
                        config(),
                    )

    def test_guarded_client_distinguishes_rejection_from_ambiguity(self):
        target_ids = self.record['suggested_term_ids']
        target_slug_by_id = dict(zip(
            target_ids,
            self.record['suggested_slugs'],
        ))
        target_slugs = [
            target_slug_by_id[term_id]
            for term_id in sorted(target_ids)
        ]
        source_sha256 = APPLY.source_guard_sha256(self.post)

        rejected_session = RecordingSession(FakeResponse(
            {
                'code': 'oar_backfill_post_stale',
                'message': 'stale',
            },
            status_code=409,
        ))
        rejected_client = APPLY.ApplyWordPressClient(
            config()['api_url'],
            'bot',
            'password',
            session=rejected_session,
            sleep_fn=lambda _: None,
        )
        with self.assertRaises(APPLY.GuardedWriteRejected) as rejected:
            rejected_client.apply_guarded_benefits(
                700,
                'organization-benefits',
                expected_modified_gmt=self.record['observed_modified_gmt'],
                expected_term_ids=[],
                target_term_ids=target_ids,
                target_term_slugs=target_slugs,
                expected_source_sha256=source_sha256,
                plan_run_id=PLAN_RUN_ID,
            )
        self.assertEqual(409, rejected.exception.http_status)
        self.assertEqual(
            'oar_backfill_post_stale',
            rejected.exception.error_code,
        )

        bad_success = FakeResponse({
            'id': 700,
            'status': 'publish',
            'modified_gmt': self.record['observed_modified_gmt'],
            'organization-benefits': target_ids,
            'contract_version': 'wrong',
            'plan_run_id': PLAN_RUN_ID,
            'source_sha256': source_sha256,
            'target_term_slugs': target_slugs,
        })
        ambiguous_client = APPLY.ApplyWordPressClient(
            config()['api_url'],
            'bot',
            'password',
            session=RecordingSession(bad_success),
            sleep_fn=lambda _: None,
        )
        with self.assertRaises(APPLY.GuardedWriteAmbiguous):
            ambiguous_client.apply_guarded_benefits(
                700,
                'organization-benefits',
                expected_modified_gmt=self.record['observed_modified_gmt'],
                expected_term_ids=[],
                target_term_ids=target_ids,
                target_term_slugs=target_slugs,
                expected_source_sha256=source_sha256,
                plan_run_id=PLAN_RUN_ID,
            )

    def test_guarded_state_must_match_core_source_and_taxonomy(self):
        state = guarded_state(self.post)
        self.assertEqual(
            APPLY.source_guard_sha256(self.post),
            APPLY.validate_guarded_state(
                state,
                self.post,
                self.record,
                config(),
            ),
        )
        changed = copy.deepcopy(state)
        changed['source_sha256'] = '0' * 64
        with self.assertRaisesRegex(
            APPLY.BackfillApplyError,
            'source state changed',
        ):
            APPLY.validate_guarded_state(
                changed,
                self.post,
                self.record,
                config(),
            )


class StatefulClient:
    def __init__(
        self,
        post,
        record,
        *,
        fail_after_apply=False,
        mutate_meta_after_apply=False,
        mutate_rendered_after_apply=False,
        reject_guard=False,
    ):
        self.post = copy.deepcopy(post)
        self.record = record
        self.fail_after_apply = fail_after_apply
        self.mutate_meta_after_apply = mutate_meta_after_apply
        self.mutate_rendered_after_apply = mutate_rendered_after_apply
        self.reject_guard = reject_guard
        self.post_calls = 0
        self.get_calls = 0

    def get_json(self, relative_path, *, params=None):
        self.get_calls += 1
        return copy.deepcopy(self.post), {}

    def get_guard_json(self, relative_path, *, params=None):
        if relative_path == 'benefit-backfill-capability':
            return guard_capability(), {}
        if relative_path == f'benefit-backfill-state/{self.post["id"]}':
            return guarded_state(copy.deepcopy(self.post)), {}
        raise AssertionError(f'Unexpected guarded GET: {relative_path}')

    def apply_guarded_benefits(
        self,
        post_id,
        taxonomy_rest_base,
        *,
        expected_modified_gmt,
        expected_term_ids,
        target_term_ids,
        target_term_slugs,
        expected_source_sha256,
        plan_run_id,
    ):
        self.post_calls += 1
        if self.reject_guard:
            raise APPLY.GuardedWriteRejected(
                'simulated guarded conflict',
                http_status=409,
                error_code='oar_backfill_post_stale',
            )
        if (
            self.post['modified_gmt'] != expected_modified_gmt
            or sorted(self.post[taxonomy_rest_base])
            != sorted(expected_term_ids)
            or APPLY.source_guard_sha256(self.post)
            != expected_source_sha256
        ):
            raise APPLY.GuardedWriteRejected(
                'simulated guarded conflict',
                http_status=409,
                error_code='oar_backfill_source_stale',
            )
        self.post[taxonomy_rest_base] = list(target_term_ids)
        if self.mutate_meta_after_apply:
            self.post['meta']['ptb_innovation_tip_content'] = (
                '<p>unexpected guarded-source change</p>'
            )
        if self.mutate_rendered_after_apply:
            self.post['content']['rendered'] = (
                '<p>Rendered output changed because taxonomy changed.</p>'
            )
        if self.fail_after_apply:
            raise APPLY.GuardedWriteAmbiguous(
                'simulated transport failure'
            )
        return {
            'id': post_id,
            taxonomy_rest_base: list(target_term_ids),
            'target_term_slugs': list(target_term_slugs),
        }


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.post = make_post()
        self.record = PLANNER.plan_post(
            self.post,
            'organization-benefits',
            terms(),
        )

    def test_execute_writes_and_verifies_one_record(self):
        client = StatefulClient(self.post, self.record)
        with tempfile.TemporaryDirectory() as temp_dir:
            audit_path = Path(temp_dir) / 'audit.json'
            lock_path = Path(temp_dir) / 'plan.apply.lock'
            journal = APPLY.AuditJournal(
                audit_path,
                {
                    'metadata': {'status': 'in_progress'},
                    'results': [],
                },
                lock_path=lock_path,
            )
            try:
                APPLY.execute_records(
                    client,
                    config(),
                    terms(),
                    [self.record],
                    journal,
                    plan_run_id=PLAN_RUN_ID,
                    guard_capability=guard_capability(),
                )
                self.assertEqual(
                    'completed',
                    journal.document['metadata']['status'],
                )
                self.assertEqual(
                    'applied_verified',
                    journal.document['results'][0]['status'],
                )
            finally:
                journal.close()
            self.assertFalse(lock_path.exists())
            checksum_path = audit_path.with_suffix('.sha256')
            self.assertTrue(checksum_path.is_file())
            expected_checksum = hashlib.sha256(
                audit_path.read_bytes()
            ).hexdigest()
            self.assertEqual(
                f'{expected_checksum}  audit.json',
                checksum_path.read_text(encoding='ascii').strip(),
            )
            self.assertEqual(1, client.post_calls)

    def test_ambiguous_transport_is_reconciled_without_retry(self):
        client = StatefulClient(
            self.post,
            self.record,
            fail_after_apply=True,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            journal = APPLY.AuditJournal(
                Path(temp_dir) / 'audit.json',
                {
                    'metadata': {'status': 'in_progress'},
                    'results': [],
                },
                lock_path=Path(temp_dir) / 'plan.apply.lock',
            )
            try:
                with self.assertRaisesRegex(
                    APPLY.BackfillApplyError,
                    'ambiguous response',
                ):
                    APPLY.execute_records(
                        client,
                        config(),
                        terms(),
                        [self.record],
                        journal,
                        plan_run_id=PLAN_RUN_ID,
                        guard_capability=guard_capability(),
                    )
                self.assertEqual(1, client.post_calls)
                self.assertEqual(
                    'state_verified_after_ambiguous',
                    journal.document['results'][0]['status'],
                )
            finally:
                journal.close()

    def test_post_hook_non_taxonomy_change_fails_verification(self):
        client = StatefulClient(
            self.post,
            self.record,
            mutate_meta_after_apply=True,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_path = Path(temp_dir) / 'plan.apply.lock'
            journal = APPLY.AuditJournal(
                Path(temp_dir) / 'audit.json',
                {
                    'metadata': {'status': 'in_progress'},
                    'results': [],
                },
                lock_path=lock_path,
            )
            with self.assertRaisesRegex(
                APPLY.BackfillApplyError,
                'non-taxonomy fields changed',
            ):
                try:
                    APPLY.execute_records(
                        client,
                        config(),
                        terms(),
                        [self.record],
                        journal,
                        plan_run_id=PLAN_RUN_ID,
                        guard_capability=guard_capability(),
                    )
                finally:
                    journal.close(remove_lock=False)
            self.assertTrue(lock_path.exists())
            self.assertEqual(
                'failed',
                journal.document['metadata']['status'],
            )

    def test_rendered_output_change_does_not_fail_stored_state_guard(self):
        client = StatefulClient(
            self.post,
            self.record,
            mutate_rendered_after_apply=True,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            journal = APPLY.AuditJournal(
                Path(temp_dir) / 'audit.json',
                {
                    'metadata': {'status': 'in_progress'},
                    'results': [],
                },
                lock_path=Path(temp_dir) / 'plan.apply.lock',
            )
            try:
                APPLY.execute_records(
                    client,
                    config(),
                    terms(),
                    [self.record],
                    journal,
                    plan_run_id=PLAN_RUN_ID,
                    guard_capability=guard_capability(),
                )
                self.assertEqual(
                    'applied_verified',
                    journal.document['results'][0]['status'],
                )
            finally:
                journal.close()

    def test_rendered_only_legacy_content_never_becomes_auto_ready(self):
        rendered_only_post = make_post()
        legacy_rendered = rendered_only_post['content']['rendered']
        rendered_only_post['content']['raw'] = ''
        rendered_only_post['meta']['ptb_innovation_tip_content'] = ''
        rendered_only_post['content']['rendered'] = legacy_rendered
        rendered_only_record = PLANNER.plan_post(
            rendered_only_post,
            'organization-benefits',
            terms(),
        )
        self.assertEqual('review', rendered_only_record['plan_status'])
        self.assertEqual([], rendered_only_record['legacy_benefits'])

    def test_atomic_guard_rejection_stops_without_reconciliation(self):
        client = StatefulClient(
            self.post,
            self.record,
            reject_guard=True,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_path = Path(temp_dir) / 'plan.apply.lock'
            journal = APPLY.AuditJournal(
                Path(temp_dir) / 'audit.json',
                {
                    'metadata': {'status': 'in_progress'},
                    'results': [],
                },
                lock_path=lock_path,
            )
            with self.assertRaisesRegex(
                APPLY.BackfillApplyError,
                'rejected post 700',
            ):
                try:
                    APPLY.execute_records(
                        client,
                        config(),
                        terms(),
                        [self.record],
                        journal,
                        plan_run_id=PLAN_RUN_ID,
                        guard_capability=guard_capability(),
                    )
                finally:
                    journal.close(remove_lock=False)
            result = journal.document['results'][0]
            self.assertEqual(1, client.post_calls)
            self.assertEqual(1, client.get_calls)
            self.assertEqual([], client.post['organization-benefits'])
            self.assertEqual('guard_rejected', result['status'])
            self.assertEqual(409, result['guard_http_status'])
            self.assertEqual(
                'oar_backfill_post_stale',
                result['guard_error_code'],
            )
            self.assertTrue(lock_path.exists())

    def test_batch_preflight_checks_all_posts_before_any_write(self):
        second_post = make_post(post_id=701)
        second_record = PLANNER.plan_post(
            second_post,
            'organization-benefits',
            terms(),
        )
        stale_second = copy.deepcopy(second_post)
        stale_second['modified_gmt'] = '2099-01-01T00:00:00'

        class PreflightClient:
            def __init__(self):
                self.posts = {
                    700: copy.deepcopy(self.post_one),
                    701: stale_second,
                }
                self.post_calls = 0

            def get_json(self, relative_path, *, params=None):
                post_id = int(relative_path.rsplit('/', 1)[1])
                return copy.deepcopy(self.posts[post_id]), {}

            def get_guard_json(self, relative_path, *, params=None):
                post_id = int(relative_path.rsplit('/', 1)[1])
                return guarded_state(copy.deepcopy(self.posts[post_id])), {}

            def apply_guarded_benefits(self, *args, **kwargs):
                self.post_calls += 1

        PreflightClient.post_one = self.post
        client = PreflightClient()
        with self.assertRaisesRegex(
            APPLY.BackfillApplyError,
            'modified_gmt changed',
        ):
            APPLY.preflight_selected_records(
                client,
                config(),
                terms(),
                [self.record, second_record],
            )
        self.assertEqual(0, client.post_calls)

    def test_audit_refuses_existing_output_and_competing_plan_lock(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            lock_path = temp_path / 'plan.apply.lock'
            first = APPLY.AuditJournal(
                temp_path / 'first.json',
                {'metadata': {}, 'results': []},
                lock_path=lock_path,
            )
            try:
                with self.assertRaisesRegex(
                    APPLY.BackfillApplyError,
                    'stale lock',
                ):
                    APPLY.AuditJournal(
                        temp_path / 'second.json',
                        {'metadata': {}, 'results': []},
                        lock_path=lock_path,
                    )
            finally:
                first.close()

            existing = temp_path / 'existing.json'
            existing.write_text('{}\n', encoding='utf-8')
            with self.assertRaisesRegex(
                APPLY.BackfillApplyError,
                'overwrite existing audit',
            ):
                APPLY.AuditJournal(
                    existing,
                    {'metadata': {}, 'results': []},
                    lock_path=lock_path,
                )

    def test_source_has_no_term_creation_or_generic_mutation_helpers(self):
        source = APPLY_FILE.read_text(encoding='utf-8')
        self.assertNotIn('wordpress_integration', source)
        self.assertNotIn('resolve_wordpress_benefit_term_ids', source)
        self.assertNotIn('requests.post(', source)
        self.assertNotRegex(source, r'\.(?:put|patch|delete)\(')


class MainPreflightTests(unittest.TestCase):
    def test_default_main_mode_uses_get_only(self):
        post = make_post()

        class PreflightClient:
            def __init__(self):
                self.calls = []

            def get_json(self, relative_path, *, params=None):
                self.calls.append((relative_path, params))
                if relative_path == 'types/innovation-tip':
                    return {
                        'taxonomies': [
                            'post_tag',
                            'organization_benefit',
                        ],
                    }, {}
                if relative_path == 'taxonomies/organization_benefit':
                    return {
                        'rest_base': 'organization-benefits',
                        'types': ['innovation-tip'],
                    }, {}
                if relative_path == 'organization-benefits':
                    return list(terms().values()), {}
                if relative_path == 'innovation-tip/700':
                    return copy.deepcopy(post), {}
                raise AssertionError(f'Unexpected GET path: {relative_path}')

            def get_guard_json(self, relative_path, *, params=None):
                self.calls.append((relative_path, params))
                if relative_path == 'benefit-backfill-capability':
                    return guard_capability(), {}
                if relative_path == 'benefit-backfill-state/700':
                    return guarded_state(copy.deepcopy(post)), {}
                raise AssertionError(
                    f'Unexpected guarded GET path: {relative_path}'
                )

            def apply_guarded_benefits(self, *args, **kwargs):
                raise AssertionError('Preflight must not issue POST')

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            env_path = temp_path / '.env'
            env_path.write_text(
                '\n'.join([
                    'WP_API_URL=https://example.test',
                    'WP_USERNAME=bot',
                    'WP_APP_PASSWORD=application-password',
                    'WP_INNOVATION_TIP_POST_TYPE=innovation-tip',
                    'WP_BENEFIT_TAXONOMY=organization_benefit',
                    (
                        'WP_BENEFIT_TAXONOMY_REST_BASE='
                        'organization-benefits'
                    ),
                ])
                + '\n',
                encoding='utf-8',
            )
            plan_path = temp_path / 'plan.json'
            PLANNER.write_manifest_atomic(
                make_manifest(env_path, posts=[post]),
                plan_path,
            )
            fake_client = PreflightClient()
            with mock.patch.object(
                APPLY,
                'ApplyWordPressClient',
                return_value=fake_client,
            ), mock.patch('builtins.print'):
                result = APPLY.main([
                    '--env-file',
                    str(env_path),
                    '--plan',
                    str(plan_path),
                    '--post-id',
                    '700',
                ])
            self.assertEqual(0, result)
            self.assertGreaterEqual(len(fake_client.calls), 4)

    def test_execute_requires_exact_run_id_before_client_creation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            env_path = temp_path / '.env'
            env_path.write_text(
                '\n'.join([
                    'WP_API_URL=https://example.test',
                    'WP_USERNAME=bot',
                    'WP_APP_PASSWORD=application-password',
                ])
                + '\n',
                encoding='utf-8',
            )
            plan_path = temp_path / 'plan.json'
            PLANNER.write_manifest_atomic(
                make_manifest(env_path),
                plan_path,
            )
            with mock.patch.object(
                APPLY,
                'ApplyWordPressClient',
            ) as client_constructor:
                with self.assertRaisesRegex(
                    APPLY.BackfillApplyError,
                    'confirm-run-id',
                ):
                    APPLY.main([
                        '--env-file',
                        str(env_path),
                        '--plan',
                        str(plan_path),
                        '--post-id',
                        '700',
                        '--execute',
                        '--confirm-run-id',
                        'wrong-run-id',
                        '--audit-output',
                        str(temp_path / 'audit.json'),
                    ])
            client_constructor.assert_not_called()


if __name__ == '__main__':
    unittest.main()
