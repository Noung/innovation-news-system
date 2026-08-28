import codecs
import copy
import csv
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / 'scripts'
sys.path.insert(0, str(SCRIPTS_DIR))

from benefit_classifier import (  # noqa: E402
    BENEFIT_TERM_SLUGS,
    CLASSIFIER_VERSION,
)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


WORKLIST = load_module(
    'wordpress_benefit_manual_worklist_test',
    SCRIPTS_DIR / 'create-wordpress-benefit-manual-worklist.py',
)

API_URL = 'https://innovation.example.test/wp-json/wp/v2'
TEST_GENERATED_AT = datetime.now(timezone.utc).replace(microsecond=0)
TEST_GENERATED_AT_TEXT = TEST_GENERATED_AT.isoformat()
TEST_RUN_ID = TEST_GENERATED_AT.strftime(
    'benefit-backfill-plan-%Y%m%dT%H%M%SZ'
)


def term_snapshot():
    return [
        {
            'id': 1000 + index,
            'name': name,
            'slug': slug,
            'count': 0,
        }
        for index, (name, slug) in enumerate(
            BENEFIT_TERM_SLUGS.items(),
            start=1,
        )
    ]


def term_details():
    return {
        item['name']: (item['slug'], item['id'])
        for item in term_snapshot()
    }


def auto_record(post_id, title=None):
    names = list(BENEFIT_TERM_SLUGS)[:3]
    details = term_details()
    return {
        'wp_post_id': post_id,
        'title': title or 'ข่าวทดสอบ {0}'.format(post_id),
        'slug': 'post-{0}'.format(post_id),
        'status': 'publish',
        'permalink': 'https://innovation.example.test/post-{0}/'.format(post_id),
        'date_gmt': '2026-07-01T02:00:00',
        'observed_modified_gmt': '2026-07-26T02:00:00',
        'existing_term_ids': [],
        'legacy_benefits': list(names),
        'legacy_source': 'ptb_meta',
        'legacy_candidates': [],
        'legacy_conflict': False,
        'summary_source': 'ptb_meta',
        'summary_preview': 'เนื้อหาสรุปข่าวสำหรับการทดสอบ',
        'input_text_sha256': 'a' * 64,
        'suggested_names': list(names),
        'suggested_slugs': [details[name][0] for name in names],
        'suggested_term_ids': [details[name][1] for name in names],
        'evidence': [],
        'classifier_fallback_count': 0,
        'plan_status': 'auto_ready',
        'review_reasons': [],
    }


def other_record(post_id, plan_status):
    record = auto_record(post_id)
    record['plan_status'] = plan_status
    if plan_status == 'review':
        record['review_reasons'] = ['incomplete_legacy_benefits']
        record['legacy_benefits'] = record['legacy_benefits'][:1]
    elif plan_status == 'skip_existing':
        record['existing_term_ids'] = [record['suggested_term_ids'][0]]
        record['suggested_names'] = []
        record['suggested_slugs'] = []
        record['suggested_term_ids'] = []
        record['legacy_benefits'] = []
    return record


def make_plan(records, api_url=API_URL):
    counts = {
        'wp_total': len(records),
        'included': len(records),
        'auto_ready': sum(
            record['plan_status'] == 'auto_ready' for record in records
        ),
        'review': sum(record['plan_status'] == 'review' for record in records),
        'skip_existing': sum(
            record['plan_status'] == 'skip_existing' for record in records
        ),
    }
    return {
        'metadata': {
            'schema_version': '2',
            'mode': 'plan_read_only',
            'generated_at_utc': TEST_GENERATED_AT_TEXT,
            'run_id': TEST_RUN_ID,
            'site_api_url': api_url,
            'environment_file': '/not/exported/.env',
            'post_type': 'innovation-tip',
            'taxonomy': 'organization_benefit',
            'taxonomy_rest_base': 'organization-benefits',
            'classifier_version': CLASSIFIER_VERSION,
            'classifier_mode': 'strict',
            'records_sha256': WORKLIST._canonical_records_sha256(records),
            'truncated': False,
            'counts': counts,
            'term_snapshot': term_snapshot(),
        },
        'records': records,
    }


def write_plan(temp_path, plan, raw=None):
    path = temp_path / 'plan.json'
    payload = (
        raw
        if raw is not None
        else (
            json.dumps(
                plan,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            + '\n'
        ).encode('utf-8')
    )
    path.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    path.with_suffix('.sha256').write_text(
        '{0}  {1}\n'.format(digest, path.name),
        encoding='ascii',
    )
    return path, digest


class ManualWorklistTests(unittest.TestCase):
    def test_valid_full_plan_exports_only_auto_ready_in_five_row_batches(self):
        records = [auto_record(post_id) for post_id in range(101, 107)]
        records.extend([
            other_record(201, 'review'),
            other_record(202, 'skip_existing'),
        ])
        plan = make_plan(records)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            plan_path, digest = write_plan(temp_path, plan)
            loaded, actual_digest, _ = WORKLIST.load_verified_plan(plan_path)
            selected, metadata, _ = WORKLIST.validate_full_plan(
                loaded,
                expected_api_url=API_URL,
                expected_count=6,
            )
            payload = WORKLIST.build_worklist_bytes(
                selected,
                metadata,
                actual_digest,
                batch_size=5,
            )

        self.assertEqual(digest, actual_digest)
        self.assertTrue(payload.startswith(codecs.BOM_UTF8))
        rows = list(csv.DictReader(io.StringIO(payload.decode('utf-8-sig'))))
        self.assertEqual(6, len(rows))
        self.assertEqual(
            ['101', '102', '103', '104', '105', '106'],
            [row['wp_post_id'] for row in rows],
        )
        self.assertEqual(['1'] * 5 + ['2'], [row['batch'] for row in rows])
        self.assertTrue(all(row['workflow_status'] == 'pending' for row in rows))
        self.assertTrue(all(row['reviewer'] == '' for row in rows))
        self.assertEqual(
            'https://innovation.example.test/wp-admin/post.php'
            '?post=101&action=edit',
            rows[0]['wp_admin_edit_url'],
        )
        self.assertIn(
            '_fields=id%2Ctitle%2Corganization-benefits%2Cmodified_gmt',
            rows[0]['rest_verification_url'],
        )
        self.assertTrue(
            all(row['source_plan_sha256'] == digest for row in rows)
        )

    def test_subdirectory_wordpress_urls_are_preserved(self):
        api_url = 'https://example.test/wordpress/wp-json/wp/v2/'
        plan = make_plan([auto_record(101)], api_url=api_url)
        selected, metadata, normalized = WORKLIST.validate_full_plan(
            plan,
            expected_api_url=api_url,
            expected_count=1,
        )
        payload = WORKLIST.build_worklist_bytes(
            selected,
            metadata,
            'b' * 64,
            batch_size=5,
        )
        row = next(csv.DictReader(io.StringIO(payload.decode('utf-8-sig'))))
        self.assertEqual(
            'https://example.test/wordpress/wp-json/wp/v2',
            normalized,
        )
        self.assertEqual(
            'https://example.test/wordpress/wp-admin/post.php'
            '?post=101&action=edit',
            row['wp_admin_edit_url'],
        )

    def test_checksum_filename_digest_and_duplicate_json_keys_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            plan = make_plan([auto_record(101)])
            plan_path, _ = write_plan(temp_path, plan)

            plan_path.with_suffix('.sha256').write_text(
                '{0}  wrong.json\n'.format('0' * 64),
                encoding='ascii',
            )
            with self.assertRaises(WORKLIST.ManualWorklistError):
                WORKLIST.load_verified_plan(plan_path)

            duplicate_raw = (
                b'{"metadata":{},"metadata":{},"records":[]}\n'
            )
            write_plan(temp_path, plan, raw=duplicate_raw)
            with self.assertRaisesRegex(
                WORKLIST.ManualWorklistError,
                'duplicate key',
            ):
                WORKLIST.load_verified_plan(plan_path)

    def test_full_manifest_metadata_and_record_digests_are_required(self):
        base = make_plan([auto_record(101)])
        mutations = [
            ('schema_version', lambda plan: plan['metadata'].__setitem__(
                'schema_version',
                '1',
            )),
            ('truncated', lambda plan: plan['metadata'].__setitem__(
                'truncated',
                True,
            )),
            ('site', lambda plan: plan['metadata'].__setitem__(
                'site_api_url',
                'https://other.example.test/wp-json/wp/v2',
            )),
            ('count', lambda plan: plan['metadata']['counts'].__setitem__(
                'included',
                9,
            )),
            ('records_digest', lambda plan: plan['metadata'].__setitem__(
                'records_sha256',
                '0' * 64,
            )),
            ('run_id_time', lambda plan: plan['metadata'].__setitem__(
                'run_id',
                'benefit-backfill-plan-20000101T000000Z',
            )),
        ]
        for label, mutate in mutations:
            with self.subTest(label=label):
                plan = copy.deepcopy(base)
                mutate(plan)
                with self.assertRaises(WORKLIST.ManualWorklistError):
                    WORKLIST.validate_full_plan(
                        plan,
                        expected_api_url=API_URL,
                        expected_count=1,
                    )

    def test_stale_or_future_plan_is_rejected(self):
        stale_plan = make_plan([auto_record(101)])
        stale_time = datetime.now(timezone.utc) - timedelta(hours=25)
        stale_plan['metadata']['generated_at_utc'] = stale_time.isoformat()
        stale_plan['metadata']['run_id'] = stale_time.strftime(
            'benefit-backfill-plan-%Y%m%dT%H%M%SZ'
        )
        with self.assertRaisesRegex(
            WORKLIST.ManualWorklistError,
            'older than 24 hours',
        ):
            WORKLIST.validate_full_plan(
                stale_plan,
                expected_api_url=API_URL,
                expected_count=1,
            )

        future_plan = make_plan([auto_record(101)])
        future_time = datetime.now(timezone.utc) + timedelta(minutes=6)
        future_plan['metadata']['generated_at_utc'] = future_time.isoformat()
        future_plan['metadata']['run_id'] = future_time.strftime(
            'benefit-backfill-plan-%Y%m%dT%H%M%SZ'
        )
        with self.assertRaisesRegex(
            WORKLIST.ManualWorklistError,
            'in the future',
        ):
            WORKLIST.validate_full_plan(
                future_plan,
                expected_api_url=API_URL,
                expected_count=1,
            )

    def test_auto_ready_invariants_fail_closed(self):
        mutations = [
            ('draft', lambda record: record.__setitem__('status', 'draft')),
            (
                'existing_terms',
                lambda record: record.__setitem__('existing_term_ids', [1001]),
            ),
            (
                'legacy_conflict',
                lambda record: record.__setitem__('legacy_conflict', True),
            ),
            (
                'review_reason',
                lambda record: record.__setitem__(
                    'review_reasons',
                    ['manual_review'],
                ),
            ),
            (
                'two_terms',
                lambda record: record.__setitem__(
                    'suggested_names',
                    record['suggested_names'][:2],
                ),
            ),
            (
                'slug_mismatch',
                lambda record: record['suggested_slugs'].__setitem__(
                    0,
                    record['suggested_slugs'][1],
                ),
            ),
            (
                'boolean_id',
                lambda record: record['suggested_term_ids'].__setitem__(0, True),
            ),
        ]
        for label, mutate in mutations:
            with self.subTest(label=label):
                record = auto_record(101)
                mutate(record)
                plan = make_plan([record])
                with self.assertRaises(WORKLIST.ManualWorklistError):
                    WORKLIST.validate_full_plan(
                        plan,
                        expected_api_url=API_URL,
                        expected_count=1,
                    )

    def test_classifier_fallback_diagnostic_does_not_reject_exact_legacy_terms(self):
        record = auto_record(101)
        record['classifier_fallback_count'] = 2
        plan = make_plan([record])
        selected, _, _ = WORKLIST.validate_full_plan(
            plan,
            expected_api_url=API_URL,
            expected_count=1,
        )
        self.assertEqual([101], [item['wp_post_id'] for item in selected])

    def test_duplicate_post_ids_and_controlled_term_drift_are_rejected(self):
        duplicate_plan = make_plan([auto_record(101), auto_record(101)])
        with self.assertRaises(WORKLIST.ManualWorklistError):
            WORKLIST.validate_full_plan(
                duplicate_plan,
                expected_api_url=API_URL,
                expected_count=2,
            )

        drifted_plan = make_plan([auto_record(101)])
        drifted_plan['metadata']['term_snapshot'][0]['name'] = 'Wrong name'
        with self.assertRaises(WORKLIST.ManualWorklistError):
            WORKLIST.validate_full_plan(
                drifted_plan,
                expected_api_url=API_URL,
                expected_count=1,
            )

    def test_csv_is_formula_safe_and_preserves_thai_utf8(self):
        record = auto_record(101, title=' \n=HYPERLINK("bad") ภาษาไทย')
        plan = make_plan([record])
        selected, metadata, _ = WORKLIST.validate_full_plan(
            plan,
            expected_api_url=API_URL,
            expected_count=1,
        )
        payload = WORKLIST.build_worklist_bytes(
            selected,
            metadata,
            'c' * 64,
            batch_size=5,
        )
        rows = list(csv.DictReader(io.StringIO(payload.decode('utf-8-sig'))))
        self.assertEqual(1, len(rows))
        self.assertTrue(rows[0]['title'].startswith("'"))
        self.assertNotIn('\n', rows[0]['title'])
        self.assertIn('ภาษาไทย', rows[0]['title'])
        self.assertFalse(rows[0]['wp_admin_edit_url'].startswith('='))
        for payload_prefix in ('=', '+', '-', '@', ' \t='):
            with self.subTest(payload_prefix=payload_prefix):
                safe = WORKLIST._safe_csv_cell(
                    payload_prefix + 'FORMULA()\r\nnext\x00'
                )
                self.assertTrue(safe.startswith("'"))
                self.assertNotIn('\r', safe)
                self.assertNotIn('\n', safe)
                self.assertNotIn('\x00', safe)

    def test_atomic_writer_refuses_overwrite_and_cleans_failed_commit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            output = temp_path / 'manual.csv'
            paths = WORKLIST.write_worklist_atomic(output, b'one\n')
            self.assertTrue(paths['csv'].is_file())
            self.assertTrue(paths['sha256'].is_file())
            with self.assertRaises(WORKLIST.ManualWorklistError):
                WORKLIST.write_worklist_atomic(output, b'two\n')

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / 'failed.csv'
            original_replace = WORKLIST.os.replace
            calls = {'count': 0}

            def fail_second_replace(source, destination):
                calls['count'] += 1
                if calls['count'] == 2:
                    raise OSError('simulated final commit failure')
                return original_replace(source, destination)

            with mock.patch.object(
                WORKLIST.os,
                'replace',
                side_effect=fail_second_replace,
            ):
                with self.assertRaises(OSError):
                    WORKLIST.write_worklist_atomic(output, b'payload\n')
            self.assertFalse(output.exists())
            self.assertFalse(output.with_suffix('.sha256').exists())
            self.assertFalse(output.with_suffix('.lock').exists())
            self.assertEqual([], list(output.parent.glob('.*.tmp')))

    def test_source_has_no_network_or_wordpress_mutation_client(self):
        source = (
            SCRIPTS_DIR / 'create-wordpress-benefit-manual-worklist.py'
        ).read_text(encoding='utf-8')
        self.assertNotIn('import requests', source)
        self.assertNotIn('urllib.request', source)
        self.assertNotIn('HTTPBasicAuth', source)
        self.assertNotIn('.post(', source)
        self.assertNotIn('WP_APP_PASSWORD', source)
        self.assertIn('Mode: MANUAL WORKLIST (offline;', source)


if __name__ == '__main__':
    unittest.main()
