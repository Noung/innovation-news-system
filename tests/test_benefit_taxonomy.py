import importlib.util
import re
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT_DIR / 'scripts'
sys.path.insert(0, str(SCRIPTS_DIR))

import wordpress_integration as wp  # noqa: E402
import line_integration as line  # noqa: E402


def load_fetcher_module():
    # The fetcher imports BeautifulSoup for its crawling path. These unit tests
    # exercise only the dependency-free benefit classifier, so keep collection
    # runnable even when optional crawler packages are not installed.
    if 'bs4' not in sys.modules:
        try:
            import bs4  # noqa: F401
        except ModuleNotFoundError:
            bs4_stub = types.ModuleType('bs4')
            bs4_stub.BeautifulSoup = object
            sys.modules['bs4'] = bs4_stub

    script_path = SCRIPTS_DIR / 'fetch-innovation-news-mysql.py'
    spec = importlib.util.spec_from_file_location('innovation_news_fetcher_test', script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FETCHER = load_fetcher_module()


class FakeResponse:
    def __init__(self, status_code, payload=None, text=''):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class BenefitSelectionTests(unittest.TestCase):
    def test_no_match_uses_exactly_three_controlled_fallbacks(self):
        benefits = FETCHER.generate_benefits('', '')

        self.assertEqual(FETCHER.DEFAULT_BENEFITS, benefits)
        self.assertEqual(3, len(benefits))
        self.assertEqual(3, len(set(benefits)))

    def test_generative_ai_selects_general_and_specific_ai_terms(self):
        benefits = FETCHER.generate_benefits(
            'Generative AI and autonomous AI agents',
            'A foundation model powers an AI assistant and copilot.',
        )

        self.assertEqual(3, len(benefits))
        self.assertIn('การใช้งาน AI และเทคโนโลยีขั้นสูง', benefits)
        self.assertIn('การใช้ปัญญาประดิษฐ์แบบสร้างสรรค์', benefits)

    def test_short_ai_token_does_not_match_inside_other_words(self):
        benefits = FETCHER.generate_benefits(
            'Thailand training and retail report',
            'A learning programme for staff.',
        )

        self.assertNotIn('การใช้งาน AI และเทคโนโลยีขั้นสูง', benefits)
        self.assertEqual(3, len(benefits))

    def test_results_are_deterministic_and_whitelisted(self):
        first = FETCHER.generate_benefits(
            'Digital transformation with cloud data analytics',
            'The project improves productivity, cybersecurity and customer service.',
        )
        second = FETCHER.generate_benefits(
            'Digital transformation with cloud data analytics',
            'The project improves productivity, cybersecurity and customer service.',
        )

        self.assertEqual(first, second)
        self.assertEqual(3, len(first))
        self.assertTrue(all(benefit in FETCHER.BENEFIT_EMOJI_MAP for benefit in first))


class LineWordPressUrlTests(unittest.TestCase):
    def test_line_message_uses_wordpress_url_not_source_url(self):
        message = line.format_line_message({
            'title': 'Example innovation news',
            'summary': 'Example summary',
            'source': 'Example',
            'link': 'https://source.example/original',
            'wordpress_url': 'https://wordpress.example/innovation-tip/example',
        })

        self.assertIn('https://wordpress.example/innovation-tip/example', message)
        self.assertNotIn('https://source.example/original', message)

    def test_line_message_rejects_source_url_fallback(self):
        with self.assertRaises(ValueError):
            line.format_line_message({
                'title': 'Example innovation news',
                'link': 'https://source.example/original',
            })


class WordPressBenefitTaxonomyTests(unittest.TestCase):
    def setUp(self):
        wp._BENEFIT_TERM_ID_CACHE.clear()
        self.config = {
            'url': 'https://wordpress.example/wp-json',
            'user': 'bot',
            'pwd': 'application-password',
            'benefit_taxonomy_rest_base': 'organization-benefits',
        }

    def test_slug_mapping_contains_twenty_unique_ascii_slugs(self):
        slugs = list(wp.BENEFIT_TERM_SLUGS.values())

        self.assertEqual(20, len(slugs))
        self.assertEqual(20, len(set(slugs)))
        self.assertTrue(all(re.fullmatch(r'[a-z0-9-]+', slug) for slug in slugs))

    def test_controlled_vocabulary_matches_fetcher_and_wordpress_plugin(self):
        self.assertEqual(
            list(FETCHER.BENEFIT_EMOJI_MAP),
            list(wp.BENEFIT_TERM_SLUGS),
        )
        self.assertEqual(
            list(FETCHER.BENEFIT_EMOJI_MAP),
            list(line.BENEFIT_EMOJI_MAP),
        )
        self.assertEqual(FETCHER.DEFAULT_BENEFITS, wp.DEFAULT_BENEFITS)
        self.assertEqual(FETCHER.DEFAULT_BENEFITS, line.DEFAULT_BENEFITS)

        plugin_path = (
            ROOT_DIR
            / 'wordpress-plugin'
            / 'innovation-tip-benefit-taxonomy'
            / 'innovation-tip-benefit-taxonomy.php'
        )
        plugin_source = plugin_path.read_text(encoding='utf-8')
        plugin_slug_by_name = {
            name: slug
            for slug, name in re.findall(
                r"'([a-z0-9-]+)'\s*=>\s*array\('name'\s*=>\s*'([^']+)'",
                plugin_source,
            )
        }

        self.assertEqual(wp.BENEFIT_TERM_SLUGS, plugin_slug_by_name)

    def test_normalize_filters_invalid_values_and_fills_to_three(self):
        normalized = wp.normalize_article_benefits([
            'การพัฒนาทักษะและการเรียนรู้',
            'หมวดที่ไม่ได้รับอนุญาต',
            'การพัฒนาทักษะและการเรียนรู้',
        ])

        self.assertEqual(3, len(normalized))
        self.assertEqual(3, len(set(normalized)))
        self.assertEqual('การพัฒนาทักษะและการเรียนรู้', normalized[0])
        self.assertTrue(all(value in wp.BENEFIT_TERM_SLUGS for value in normalized))

    @patch.object(wp.requests, 'get')
    def test_resolve_term_ids_by_slug(self, mock_get):
        ids_by_slug = {
            'innovation-change': 11,
            'research-knowledge-development': 12,
            'trends-market-adaptation': 13,
        }

        def get_term(_url, **kwargs):
            slug = kwargs['params']['slug']
            return FakeResponse(200, [{'id': ids_by_slug[slug], 'slug': slug}])

        mock_get.side_effect = get_term
        term_ids = wp.resolve_wordpress_benefit_term_ids([], config=self.config)

        self.assertEqual([11, 12, 13], term_ids)
        self.assertEqual(3, mock_get.call_count)

    @patch.object(wp.requests, 'post')
    @patch.object(wp.requests, 'get')
    def test_missing_terms_are_created_idempotently(self, mock_get, mock_post):
        mock_get.return_value = FakeResponse(200, [])
        created_ids = iter([21, 22, 23])
        mock_post.side_effect = lambda *_args, **_kwargs: FakeResponse(
            201,
            {'id': next(created_ids)},
        )

        term_ids = wp.resolve_wordpress_benefit_term_ids([], config=self.config)

        self.assertEqual([21, 22, 23], term_ids)
        self.assertEqual(3, mock_post.call_count)

    @patch.object(wp.requests, 'get')
    def test_transient_term_lookup_is_retried(self, mock_get):
        mock_get.side_effect = [
            FakeResponse(503, {'message': 'temporary'}),
            FakeResponse(200, [{'id': 51}]),
            FakeResponse(200, [{'id': 52}]),
            FakeResponse(200, [{'id': 53}]),
        ]

        term_ids = wp.resolve_wordpress_benefit_term_ids(
            [],
            config=self.config,
            max_retries=1,
        )

        self.assertEqual([51, 52, 53], term_ids)
        self.assertEqual(4, mock_get.call_count)

    @patch.object(wp, 'check_duplicate_in_wordpress', return_value=None)
    @patch.object(wp, 'resolve_wordpress_benefit_term_ids', return_value=[31, 32, 33])
    @patch.object(wp.requests, 'post')
    @patch.object(wp, 'get_wp_config')
    def test_new_post_payload_contains_exactly_three_term_ids(
        self,
        mock_config,
        mock_post,
        _mock_resolve,
        _mock_duplicate,
    ):
        mock_config.return_value = self.config
        mock_post.return_value = FakeResponse(
            201,
            {'id': 501, 'link': 'https://wordpress.example/innovation-tip/501'},
        )
        article = {
            'title': 'AI for university services',
            'summary': 'Summary',
            'link': 'https://source.example/article',
            'date': '2026-07-21',
            'source': 'Example',
            'benefits': ['การใช้งาน AI และเทคโนโลยีขั้นสูง'],
        }

        result = wp.save_to_wordpress_result(article, max_retries=0)

        self.assertEqual('created', result['status'])
        self.assertEqual(501, result['post_id'])
        self.assertEqual(
            'https://wordpress.example/innovation-tip/501',
            result['wordpress_url'],
        )
        payload = mock_post.call_args.kwargs['json']
        self.assertEqual([31, 32, 33], payload['organization-benefits'])
        self.assertEqual(3, len(article['benefits']))

    @patch.object(
        wp,
        'get_wordpress_post_url',
        return_value='https://wordpress.example/innovation-tip/777',
    )
    @patch.object(wp, 'update_wordpress_post_benefits', return_value=True)
    @patch.object(wp, 'check_duplicate_in_wordpress', return_value=777)
    @patch.object(wp, 'resolve_wordpress_benefit_term_ids', return_value=[41, 42, 43])
    @patch.object(wp, 'get_wp_config')
    def test_duplicate_post_receives_taxonomy_update(
        self,
        mock_config,
        _mock_resolve,
        _mock_duplicate,
        mock_update,
        _mock_post_url,
    ):
        mock_config.return_value = self.config
        article = {'title': 'Existing article', 'benefits': []}

        result = wp.save_to_wordpress_result(article)

        self.assertEqual('duplicate', result['status'])
        self.assertTrue(result['taxonomy_updated'])
        self.assertEqual(
            'https://wordpress.example/innovation-tip/777',
            result['wordpress_url'],
        )
        mock_update.assert_called_once_with(777, [41, 42, 43], config=self.config)

    def test_canonical_wordpress_url_requires_credential_free_https(self):
        self.assertEqual(
            'https://wordpress.example/innovation-tip/1',
            wp.canonical_wordpress_url(
                {'link': 'https://wordpress.example/innovation-tip/1'}
            ),
        )
        self.assertIsNone(
            wp.canonical_wordpress_url(
                {'link': 'http://wordpress.example/innovation-tip/1'}
            )
        )
        self.assertIsNone(
            wp.canonical_wordpress_url(
                {'link': 'https://user:password@wordpress.example/innovation-tip/1'}
            )
        )

    @patch.object(wp, 'resolve_wordpress_benefit_term_ids', return_value=None)
    @patch.object(wp, 'get_wp_config')
    def test_publish_stops_when_three_terms_cannot_be_resolved(self, mock_config, _mock_resolve):
        mock_config.return_value = self.config

        result = wp.save_to_wordpress_result({'title': 'Unclassified article', 'benefits': []})

        self.assertEqual('failed', result['status'])
        self.assertIsNone(result['post_id'])

    @patch.object(wp, 'save_to_wordpress_result')
    def test_legacy_wrapper_does_not_mask_failed_duplicate_update(self, mock_save_result):
        mock_save_result.return_value = {
            'post_id': 777,
            'created': False,
            'status': 'failed',
        }

        self.assertIsNone(wp.save_to_wordpress({'title': 'Existing article'}))

    @patch.object(wp.requests, 'options')
    @patch.object(wp.requests, 'get')
    @patch.object(wp, 'get_wp_config')
    def test_connection_check_requires_taxonomy_in_cpt_schema(
        self,
        mock_config,
        mock_get,
        mock_options,
    ):
        mock_config.return_value = self.config
        terms = [
            {'id': index, 'slug': slug}
            for index, slug in enumerate(wp.BENEFIT_TERM_SLUGS.values(), start=1)
        ]
        mock_get.side_effect = [
            FakeResponse(200, []),
            FakeResponse(200, terms),
        ]
        mock_options.return_value = FakeResponse(200, {
            'schema': {
                'properties': {
                    'title': {},
                    'organization-benefits': {},
                },
            },
        })

        self.assertTrue(wp.test_wordpress_connection())

        mock_get.side_effect = [
            FakeResponse(200, []),
            FakeResponse(200, terms),
        ]
        mock_options.return_value = FakeResponse(200, {
            'schema': {'properties': {'title': {}}},
        })

        self.assertFalse(wp.test_wordpress_connection())


if __name__ == '__main__':
    unittest.main()
