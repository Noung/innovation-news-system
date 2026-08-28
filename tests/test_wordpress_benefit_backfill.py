import ast
import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / 'scripts'
PLANNER_FILE = SCRIPTS_DIR / 'plan-wordpress-benefit-backfill.py'
FETCHER_FILE = SCRIPTS_DIR / 'fetch-innovation-news-mysql.py'

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PLANNER = load_module('wordpress_benefit_backfill_planner', PLANNER_FILE)
BS4_STUB = types.ModuleType('bs4')
BS4_STUB.BeautifulSoup = object
with mock.patch.dict(sys.modules, {'bs4': BS4_STUB}):
    FETCHER = load_module('wordpress_benefit_backfill_fetcher', FETCHER_FILE)


class FakeResponse:
    def __init__(self, payload, status_code=200, headers=None):
        self._payload = payload
        self.status_code = status_code
        self.headers = headers or {}

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responder):
        self.responder = responder
        self.calls = []
        self.headers = {}
        self.auth = None

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if method != 'GET':
            raise AssertionError(f'Mutating HTTP method attempted: {method}')
        return self.responder(method, url, kwargs)


def term_map():
    return {
        slug: {'id': 2000 + index, 'slug': slug, 'name': name}
        for index, (name, slug) in enumerate(
            PLANNER.BENEFIT_TERM_SLUGS.items(),
            start=1,
        )
    }


def make_post(
    post_id,
    *,
    taxonomy=None,
    title='ข่าวนวัตกรรม',
    content='<p>รายละเอียดข่าวทั่วไปสำหรับใช้ประกอบการทดสอบระบบ</p>',
    modified='2026-07-24T01:00:00',
):
    return {
        'id': post_id,
        'status': 'publish',
        'slug': f'post-{post_id}',
        'link': f'https://example.test/post-{post_id}/',
        'date_gmt': '2026-07-20T02:00:00',
        'modified_gmt': modified,
        'title': {'raw': title, 'rendered': title},
        'content': {'raw': content, 'rendered': content},
        'excerpt': {'raw': '', 'rendered': ''},
        'meta': {},
        'organization-benefits': [] if taxonomy is None else taxonomy,
    }


class BenefitClassifierParityTests(unittest.TestCase):
    def test_planner_classifier_matches_live_fetcher_cases(self):
        cases = [
            ('', ''),
            (
                'AI research drives innovation',
                'Generative AI and knowledge creation improve productivity.',
            ),
            (
                'Cybersecurity and data privacy',
                'Zero trust protection for a digital workplace.',
            ),
            (
                'Smart city healthtech',
                'Research collaboration for sustainable healthcare.',
            ),
            ('Chair design', 'A normal article without the short AI token.'),
        ]
        for title, summary in cases:
            with self.subTest(title=title):
                self.assertEqual(
                    FETCHER.generate_benefits(title, summary),
                    PLANNER.classify_benefits(title, summary)['selected'],
                )


class ReadOnlyRestTests(unittest.TestCase):
    def test_wp_json_root_is_normalized_to_core_v2_namespace(self):
        with mock.patch.dict(
            'os.environ',
            {
                'WP_API_URL': 'https://example.test/wp-json',
                'WP_USERNAME': 'reader',
                'WP_APP_PASSWORD': 'not-serialized',
            },
            clear=False,
        ):
            config = PLANNER.build_wordpress_config()
        self.assertEqual(
            'https://example.test/wp-json/wp/v2',
            config['api_url'],
        )

    def test_client_issues_get_only(self):
        session = FakeSession(
            lambda method, url, kwargs: FakeResponse({'ok': True})
        )
        client = PLANNER.ReadOnlyWordPressClient(
            'https://example.test/wp-json/wp/v2',
            'reader',
            'secret',
            session=session,
            max_retries=0,
        )
        payload, _ = client.get_json('types/innovation-tip')
        self.assertEqual({'ok': True}, payload)
        self.assertEqual(['GET'], [call[0] for call in session.calls])

    def test_source_contains_no_mutating_http_calls_or_helpers(self):
        source = PLANNER_FILE.read_text(encoding='utf-8')
        tree = ast.parse(source)
        mutating_attributes = {'post', 'put', 'patch', 'delete'}
        called_attributes = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
        }
        self.assertTrue(mutating_attributes.isdisjoint(called_attributes))
        self.assertNotIn('save_to_wordpress_result', source)
        self.assertNotIn('update_wordpress_post_benefits', source)
        self.assertNotIn('resolve_wordpress_benefit_term_ids', source)

    def test_fetches_every_rest_page_at_maximum_page_size(self):
        pages = {
            1: [make_post(post_id) for post_id in range(1, 101)],
            2: [make_post(post_id) for post_id in range(101, 201)],
            3: [make_post(post_id) for post_id in range(201, 206)],
        }

        def responder(method, url, kwargs):
            page = kwargs['params']['page']
            return FakeResponse(
                pages[page],
                headers={
                    'X-WP-Total': '205',
                    'X-WP-TotalPages': '3',
                },
            )

        session = FakeSession(responder)
        client = PLANNER.ReadOnlyWordPressClient(
            'https://example.test/wp-json/wp/v2',
            'reader',
            'secret',
            session=session,
            max_retries=0,
        )
        posts = PLANNER.fetch_all_posts(
            client,
            'innovation-tip',
            'organization-benefits',
        )
        self.assertEqual(205, len(posts))
        self.assertEqual([1, 2, 3], [
            call[2]['params']['page'] for call in session.calls
        ])
        self.assertTrue(all(
            call[2]['params']['per_page'] == 100
            for call in session.calls
        ))

    def test_missing_taxonomy_field_fails_closed(self):
        post = make_post(10)
        del post['organization-benefits']
        session = FakeSession(
            lambda method, url, kwargs: FakeResponse(
                [post],
                headers={'X-WP-Total': '1', 'X-WP-TotalPages': '1'},
            )
        )
        client = PLANNER.ReadOnlyWordPressClient(
            'https://example.test/wp-json/wp/v2',
            'reader',
            'secret',
            session=session,
            max_retries=0,
        )
        with self.assertRaises(PLANNER.BackfillPlanError):
            PLANNER.fetch_all_posts(
                client,
                'innovation-tip',
                'organization-benefits',
            )

    def test_missing_pagination_headers_fails_closed(self):
        session = FakeSession(
            lambda method, url, kwargs: FakeResponse(
                [make_post(post_id) for post_id in range(1, 101)],
                headers={},
            )
        )
        client = PLANNER.ReadOnlyWordPressClient(
            'https://example.test/wp-json/wp/v2',
            'reader',
            'secret',
            session=session,
            max_retries=0,
        )
        with self.assertRaises(PLANNER.BackfillPlanError):
            PLANNER.fetch_all_posts(
                client,
                'innovation-tip',
                'organization-benefits',
            )

    def test_empty_collection_with_zero_pages_is_valid(self):
        session = FakeSession(
            lambda method, url, kwargs: FakeResponse(
                [],
                headers={'X-WP-Total': '0', 'X-WP-TotalPages': '0'},
            )
        )
        client = PLANNER.ReadOnlyWordPressClient(
            'https://example.test/wp-json/wp/v2',
            'reader',
            'secret',
            session=session,
            max_retries=0,
        )
        self.assertEqual(
            [],
            PLANNER.fetch_all_posts(
                client,
                'innovation-tip',
                'organization-benefits',
            ),
        )

    def test_missing_controlled_term_aborts_the_plan(self):
        terms = [
            {'id': item['id'], 'slug': slug, 'name': item['name']}
            for slug, item in term_map().items()
        ][:-1]
        session = FakeSession(
            lambda method, url, kwargs: FakeResponse(terms)
        )
        client = PLANNER.ReadOnlyWordPressClient(
            'https://example.test/wp-json/wp/v2',
            'reader',
            'secret',
            session=session,
            max_retries=0,
        )
        with self.assertRaises(PLANNER.BackfillPlanError):
            PLANNER.fetch_and_validate_terms(
                client,
                'organization-benefits',
            )


class ExtractionAndPlanningTests(unittest.TestCase):
    def test_extracts_exact_terms_only_inside_benefit_section(self):
        outside = 'การจัดการข้อมูลและวิเคราะห์ข้อมูล'
        benefits = [
            'การใช้งาน AI และเทคโนโลยีขั้นสูง',
            'การสร้างนวัตกรรมและการเปลี่ยนแปลง',
            'การวิจัยและพัฒนาองค์ความรู้',
        ]
        content = (
            f'<p>{outside} เป็นข้อความสรุปที่อยู่นอกส่วนรายการหมวด</p>'
            '<strong>ประโยชน์ต่อองค์กร:</strong><ul>'
            + ''.join(f'<li>{name}</li>' for name in benefits)
            + '</ul><strong>ที่มา:</strong> Example'
        )
        self.assertEqual(
            benefits,
            PLANNER.extract_legacy_benefits(content),
        )
        summary = PLANNER.extract_summary(content)
        self.assertIn(outside, summary)
        self.assertNotIn('ประโยชน์ต่อองค์กร', summary)

    def test_nonempty_taxonomy_is_always_skipped(self):
        record = PLANNER.plan_post(
            make_post(11, taxonomy=[1350]),
            'organization-benefits',
            term_map(),
        )
        self.assertEqual('skip_existing', record['plan_status'])
        self.assertEqual([1350], record['existing_term_ids'])
        self.assertEqual([], record['suggested_term_ids'])

    def test_exact_three_legacy_terms_are_auto_ready(self):
        benefits = [
            'การวิจัยและพัฒนาองค์ความรู้',
            'การสร้างนวัตกรรมและการเปลี่ยนแปลง',
            'การใช้งาน AI และเทคโนโลยีขั้นสูง',
        ]
        content = (
            '<p>สรุปงานวิจัยและนวัตกรรมปัญญาประดิษฐ์ฉบับนี้</p>'
            '<strong>ประโยชน์ต่อองค์กร:</strong><ul>'
            + ''.join(f'<li>{name}</li>' for name in benefits)
            + '</ul><strong>ที่มา:</strong> Example'
        )
        record = PLANNER.plan_post(
            make_post(12, content=content),
            'organization-benefits',
            term_map(),
        )
        self.assertEqual('auto_ready', record['plan_status'])
        self.assertEqual(benefits, record['suggested_names'])
        self.assertEqual(3, len(set(record['suggested_term_ids'])))

    def test_more_than_three_legacy_terms_is_deterministic_review(self):
        benefits = [
            'การใช้งาน AI และเทคโนโลยีขั้นสูง',
            'การใช้ปัญญาประดิษฐ์แบบสร้างสรรค์',
            'การวิจัยและพัฒนาองค์ความรู้',
            'การสร้างนวัตกรรมและการเปลี่ยนแปลง',
            'การจัดการข้อมูลและวิเคราะห์ข้อมูล',
        ]

        def planned(order):
            content = (
                '<p>Generative AI research uses data to create innovation.</p>'
                '<strong>ประโยชน์ต่อองค์กร:</strong><ul>'
                + ''.join(f'<li>{name}</li>' for name in order)
                + '</ul><strong>ที่มา:</strong> Example'
            )
            return PLANNER.plan_post(
                make_post(
                    13,
                    title='Generative AI research innovation',
                    content=content,
                ),
                'organization-benefits',
                term_map(),
            )

        first = planned(benefits)
        second = planned(reversed(benefits))
        self.assertEqual('review', first['plan_status'])
        self.assertIn(
            'more_than_three_legacy_benefits',
            first['review_reasons'],
        )
        self.assertEqual(first['suggested_names'], second['suggested_names'])
        self.assertEqual(3, len(first['suggested_names']))

    def test_classifier_fallback_never_becomes_auto_ready(self):
        record = PLANNER.plan_post(
            make_post(
                14,
                title='ประกาศประชาสัมพันธ์ทั่วไป',
                content=(
                    '<p>รายละเอียดประกาศทั่วไปสำหรับบุคลากร'
                    'โดยไม่มีคำสำคัญที่ใช้จำแนกหมวด</p>'
                ),
            ),
            'organization-benefits',
            term_map(),
        )
        self.assertEqual('review', record['plan_status'])
        self.assertEqual(3, record['classifier_fallback_count'])
        self.assertIn('classifier_fallback_used', record['review_reasons'])

    def test_classifier_only_never_becomes_auto_ready_with_three_matches(self):
        record = PLANNER.plan_post(
            make_post(
                140,
                title='AI research innovation',
                content=(
                    '<p>Artificial intelligence research creates '
                    'innovation for organizations.</p>'
                ),
            ),
            'organization-benefits',
            term_map(),
        )
        self.assertEqual('review', record['plan_status'])
        self.assertEqual(0, record['classifier_fallback_count'])
        self.assertIn('classifier_only', record['review_reasons'])

    def test_strict_classifier_does_not_match_defi_inside_define(self):
        record = PLANNER.plan_post(
            make_post(
                141,
                title='Design Thinking for organizational growth',
                content=(
                    '<p>Design thinking uses empathize, define, ideate, '
                    'prototype, and test to create innovation for a market.</p>'
                ),
            ),
            'organization-benefits',
            term_map(),
        )
        blockchain = (
            'การประยุกต์บล็อกเชนและเทคโนโลยีทางการเงิน'
        )
        self.assertNotIn(blockchain, record['suggested_names'])
        self.assertEqual('review', record['plan_status'])
        self.assertIn('classifier_only', record['review_reasons'])
        self.assertIn(
            'classifier_fallback_used',
            record['review_reasons'],
        )

    def test_conflicting_legacy_sources_require_review(self):
        controlled = list(PLANNER.BENEFIT_TERM_SLUGS)
        heading = (
            '\u0e1b\u0e23\u0e30\u0e42\u0e22\u0e0a\u0e19\u0e4c'
            '\u0e15\u0e48\u0e2d\u0e2d\u0e07\u0e04\u0e4c\u0e01\u0e23'
        )

        def legacy_section(names):
            return (
                f'<strong>{heading}:</strong><ul>'
                + ''.join(f'<li>{name}</li>' for name in names)
                + '</ul>'
            )

        post = make_post(142, content=legacy_section(controlled[1:4]))
        post['meta'] = {
            'ptb_innovation_tip_content': legacy_section(controlled[:3]),
        }
        record = PLANNER.plan_post(
            post,
            'organization-benefits',
            term_map(),
        )
        self.assertTrue(record['legacy_conflict'])
        self.assertEqual('review', record['plan_status'])
        self.assertIn(
            'conflicting_legacy_benefits',
            record['review_reasons'],
        )

    def test_short_summary_is_treated_as_title_only_review(self):
        record = PLANNER.plan_post(
            make_post(
                15,
                title='AI research innovation',
                content='<p>x</p>',
            ),
            'organization-benefits',
            term_map(),
        )
        self.assertEqual('review', record['plan_status'])
        self.assertEqual('title_only', record['summary_source'])
        self.assertIn('title_only', record['review_reasons'])

    def test_duplicate_titles_remain_distinct_by_post_id(self):
        config = {
            'api_url': 'https://example.test/wp-json/wp/v2',
            'post_type': 'innovation-tip',
            'taxonomy': 'organization_benefit',
            'taxonomy_rest_base': 'organization-benefits',
        }
        generated_at = datetime(2026, 7, 24, tzinfo=timezone.utc)
        manifest = PLANNER.build_manifest(
            [
                make_post(71, title='ชื่อซ้ำ'),
                make_post(70, title='ชื่อซ้ำ'),
            ],
            config,
            term_map(),
            env_path='/safe/example.env',
            generated_at=generated_at,
        )
        self.assertEqual(
            [70, 71],
            [record['wp_post_id'] for record in manifest['records']],
        )


class ManifestTests(unittest.TestCase):
    def test_manifest_write_is_atomic_and_csv_cells_are_formula_safe(self):
        self.assertTrue(PLANNER._safe_csv_cell('=HYPERLINK("x")').startswith("'"))
        config = {
            'api_url': 'https://example.test/wp-json/wp/v2',
            'username': 'private-user-sentinel',
            'app_password': 'private-password-sentinel',
            'post_type': 'innovation-tip',
            'taxonomy': 'organization_benefit',
            'taxonomy_rest_base': 'organization-benefits',
        }
        manifest = PLANNER.build_manifest(
            [make_post(80, title='=HYPERLINK("bad")\x00')],
            config,
            term_map(),
            env_path='/safe/example.env',
            generated_at=datetime(2026, 7, 24, tzinfo=timezone.utc),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / 'plan.json'
            written = PLANNER.write_manifest_atomic(manifest, output)
            self.assertTrue(all(path.is_file() for path in written.values()))
            parsed = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(80, parsed['records'][0]['wp_post_id'])
            self.assertEqual(
                PLANNER.CLASSIFIER_VERSION,
                parsed['metadata']['classifier_version'],
            )
            self.assertEqual(
                'strict',
                parsed['metadata']['classifier_mode'],
            )
            all_output = b''.join(
                path.read_bytes() for path in written.values()
            )
            self.assertNotIn(b'private-user-sentinel', all_output)
            self.assertNotIn(b'private-password-sentinel', all_output)

    def test_failed_final_commit_removes_sidecars_and_lock(self):
        config = {
            'api_url': 'https://example.test/wp-json/wp/v2',
            'post_type': 'innovation-tip',
            'taxonomy': 'organization_benefit',
            'taxonomy_rest_base': 'organization-benefits',
        }
        manifest = PLANNER.build_manifest(
            [make_post(81)],
            config,
            term_map(),
            env_path='/safe/example.env',
            generated_at=datetime(2026, 7, 24, tzinfo=timezone.utc),
        )
        real_replace = os.replace

        def fail_json_commit(source, destination):
            if Path(destination).suffix == '.json':
                raise OSError('simulated final commit failure')
            return real_replace(source, destination)

        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / 'plan.json'
            with mock.patch.object(
                PLANNER.os,
                'replace',
                side_effect=fail_json_commit,
            ):
                with self.assertRaises(OSError):
                    PLANNER.write_manifest_atomic(manifest, output)
            self.assertFalse(output.exists())
            self.assertFalse(output.with_suffix('.csv').exists())
            self.assertFalse(output.with_suffix('.sha256').exists())
            self.assertFalse(output.with_suffix('.lock').exists())

    def test_records_checksum_is_independent_of_input_order(self):
        config = {
            'api_url': 'https://example.test/wp-json/wp/v2',
            'post_type': 'innovation-tip',
            'taxonomy': 'organization_benefit',
            'taxonomy_rest_base': 'organization-benefits',
        }
        generated_at = datetime(2026, 7, 24, tzinfo=timezone.utc)
        first = PLANNER.build_manifest(
            [make_post(91), make_post(90)],
            config,
            term_map(),
            env_path='/safe/example.env',
            generated_at=generated_at,
        )
        second = PLANNER.build_manifest(
            [make_post(90), make_post(91)],
            config,
            term_map(),
            env_path='/safe/example.env',
            generated_at=generated_at,
        )
        self.assertEqual(
            first['metadata']['records_sha256'],
            second['metadata']['records_sha256'],
        )
        self.assertEqual(first['records'], second['records'])


if __name__ == '__main__':
    unittest.main()
