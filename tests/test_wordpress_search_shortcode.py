import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
PLUGIN_DIR = (
    ROOT_DIR
    / 'wordpress-plugin'
    / 'innovation-tip-benefit-taxonomy'
)
PLUGIN_FILE = PLUGIN_DIR / 'innovation-tip-benefit-taxonomy.php'
SEARCH_FILE = PLUGIN_DIR / 'includes' / 'frontend-search.php'
STYLE_FILE = PLUGIN_DIR / 'assets' / 'innovation-tip-search.css'


class WordPressSearchShortcodeStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugin_source = PLUGIN_FILE.read_text(encoding='utf-8')
        cls.search_source = SEARCH_FILE.read_text(encoding='utf-8')
        cls.style_source = STYLE_FILE.read_text(encoding='utf-8')

    def test_plugin_loads_versioned_search_module_and_style(self):
        header_version = re.search(
            r'^\s*\*\s+Version:\s+([0-9.]+)\s*$',
            self.plugin_source,
            re.MULTILINE,
        ).group(1)
        constant_version = re.search(
            r"const OAR_INNOVATION_BENEFIT_PLUGIN_VERSION = '([0-9.]+)';",
            self.plugin_source,
        ).group(1)
        self.assertEqual(header_version, constant_version)
        self.assertIn(
            "'includes/frontend-search.php'",
            self.plugin_source,
        )
        self.assertIn(
            "'assets/innovation-tip-search.css'",
            self.search_source,
        )
        self.assertIn('is_readable($oar_innovation_search_module)', self.plugin_source)
        self.assertIn('.oar-innovation-search', self.style_source)

    def test_shortcode_query_is_scoped_to_published_innovation_tips(self):
        self.assertRegex(
            self.search_source,
            r"add_shortcode\(\s*OAR_INNOVATION_SEARCH_SHORTCODE",
        )
        self.assertIn(
            "'post_type' => OAR_INNOVATION_TIP_POST_TYPE",
            self.search_source,
        )
        self.assertIn("'post_status' => 'publish'", self.search_source)
        self.assertIn("'paged' => $filters['page']", self.search_source)
        self.assertIn("'oar_innovation_search' => true", self.search_source)
        self.assertIn(
            'foreach ($results->posts as $result_post)',
            self.search_source,
        )
        self.assertNotIn('$results->the_post()', self.search_source)
        self.assertNotIn('wp_reset_postdata();', self.search_source)

    def test_taxonomy_filter_uses_controlled_benefit_slug_not_tags(self):
        self.assertIn(
            '$allowed_benefits = oar_innovation_benefit_terms();',
            self.search_source,
        )
        self.assertIn(
            'isset($allowed_benefits[$raw_benefit])',
            self.search_source,
        )
        self.assertIn(
            "'taxonomy' => OAR_INNOVATION_BENEFIT_TAXONOMY",
            self.search_source,
        )
        self.assertIn("'field' => 'slug'", self.search_source)
        self.assertNotIn("'taxonomy' => 'post_tag'", self.search_source)

    def test_date_and_invalid_input_guards_are_present(self):
        self.assertIn('checkdate($month, $day, $year)', self.search_source)
        self.assertIn("strcmp($from, $to) > 0", self.search_source)
        self.assertIn("'inclusive' => true", self.search_source)
        self.assertIn("'post__in'] = array(0)", self.search_source)
        self.assertNotRegex(
            self.search_source,
            r"'before'\s*=>\s*\$filters\['to'\]",
        )

    def test_request_and_output_are_sanitized_and_escaped(self):
        self.assertIn('wp_unslash((string) $_GET[$key])', self.search_source)
        self.assertIn('sanitize_text_field(', self.search_source)
        self.assertIn('esc_attr($filters[', self.search_source)
        self.assertIn('esc_url($action_url)', self.search_source)
        self.assertIn('esc_html($title)', self.search_source)
        self.assertIn('wp_strip_all_tags(get_the_excerpt(', self.search_source)
        self.assertIn('wp_kses_post($pagination)', self.search_source)
        self.assertNotIn('the_excerpt();', self.search_source)
        self.assertNotIn('query_posts(', self.search_source)

    def test_namespaced_parameters_do_not_change_the_main_query(self):
        parameter_names = set(re.findall(r"'(it_[a-z]+)'", self.search_source))
        self.assertTrue(
            {'it_search', 'it_q', 'it_benefit', 'it_from', 'it_to', 'it_page'}
            <= parameter_names
        )
        self.assertNotIn("name=\"s\"", self.search_source)
        self.assertNotIn("name=\"paged\"", self.search_source)
        self.assertNotIn('pre_get_posts', self.search_source)
        self.assertIn('if (!$submitted)', self.search_source)
        self.assertIn('if (is_singular())', self.search_source)

    def test_plain_permalink_query_arguments_are_preserved(self):
        self.assertIn(
            'oar_innovation_tip_search_form_action($action_url)',
            self.search_source,
        )
        self.assertIn('wp_parse_url($action_url, PHP_URL_QUERY)', self.search_source)
        self.assertIn('wp_parse_str($query, $query_args)', self.search_source)
        self.assertIn(
            'remove_query_arg(array_keys($query_args), $action_url)',
            self.search_source,
        )

    def test_pagination_and_result_targets_are_instance_scoped(self):
        self.assertIn(
            "$results_id = 'innovation-search-results-' . $instance;",
            self.search_source,
        )
        self.assertIn("'add_fragment' => '#' . $results_id", self.search_source)
        self.assertIn(
            "'/([?&]it_page=)999999999(?=&|$)/'",
            self.search_source,
        )
        self.assertNotIn(
            "str_replace('999999999', '%#%', $url)",
            self.search_source,
        )
        self.assertIn(
            '.oar-innovation-search__pagination > ul.page-numbers',
            self.style_source,
        )

    def test_noindex_is_scoped_to_pages_containing_the_shortcode(self):
        self.assertIn(
            'function oar_innovation_tip_search_is_current_page()',
            self.search_source,
        )
        self.assertIn(
            'has_shortcode(',
            self.search_source,
        )
        self.assertIn(
            'get_post_meta($queried_object->ID)',
            self.search_source,
        )
        self.assertIn(
            'if (!oar_innovation_tip_search_is_current_page())',
            self.search_source,
        )
        self.assertNotIn("$robots['follow']", self.search_source)

    def test_ptb_style_author_meta_has_no_avatar_and_is_escaped(self):
        self.assertIn(
            '$author_id = (int) $result_post->post_author;',
            self.search_source,
        )
        self.assertIn(
            "get_the_author_meta(\n                            'display_name',",
            self.search_source,
        )
        self.assertNotIn('get_avatar(', self.search_source)
        self.assertNotIn('$author_avatar', self.search_source)
        self.assertNotIn('oar-innovation-search__author-avatar', self.style_source)
        self.assertIn('esc_html($author_name)', self.search_source)
        self.assertNotIn('get_the_author()', self.search_source)
        self.assertNotIn('the_author()', self.search_source)

    def test_results_do_not_show_redundant_read_more_link(self):
        self.assertNotIn("esc_html('อ่านเพิ่มเติม')", self.search_source)
        self.assertNotIn('oar-innovation-search__more', self.search_source)
        self.assertNotIn('oar-innovation-search__more', self.style_source)

    def test_ptb_style_form_and_pagination_are_responsive(self):
        self.assertIn(
            'minmax(250px, 1.15fr)',
            self.style_source,
        )
        self.assertIn(
            '.oar-innovation-search__form > input[type="hidden"]',
            self.style_source,
        )
        self.assertIn(
            '.oar-innovation-search .oar-innovation-search__form::before,',
            self.style_source,
        )
        self.assertIn('content: none !important;', self.style_source)
        self.assertRegex(
            self.style_source,
            r'\.oar-innovation-search__field--keyword\s*\{'
            r'[^}]*grid-area:\s*keyword;',
        )
        self.assertRegex(
            self.style_source,
            r'\.oar-innovation-search__field--benefit\s*\{'
            r'[^}]*grid-area:\s*benefit;',
        )
        self.assertRegex(
            self.style_source,
            r'\.oar-innovation-search__actions\s*\{'
            r'[^}]*grid-area:\s*actions;',
        )
        self.assertIn(
            'grid-template-areas: "keyword benefit dates actions";',
            self.style_source,
        )
        self.assertIn('flex-wrap: nowrap;', self.style_source)
        self.assertIn('@media (max-width: 1050px)', self.style_source)
        self.assertIn('@media (max-width: 640px)', self.style_source)
        self.assertIn('@media (max-width: 480px)', self.style_source)
        self.assertIn(
            '.oar-innovation-search__pagination .current',
            self.style_source,
        )
        self.assertIn(
            '.oar-innovation-search__pagination .prev,',
            self.style_source,
        )
        self.assertIn(
            '.oar-innovation-search__pagination .next,',
            self.style_source,
        )
        self.assertIn(
            '.oar-innovation-search__pagination a:focus-visible',
            self.style_source,
        )
        self.assertRegex(
            self.style_source,
            r'\.oar-innovation-search__pagination\s*\{'
            r'[^}]*display:\s*flex;'
            r'[^}]*width:\s*100%;'
            r'[^}]*justify-content:\s*center;',
        )
        self.assertRegex(
            self.style_source,
            r'\.oar-innovation-search__pagination > ul\.page-numbers\s*\{'
            r'[^}]*justify-content:\s*center;',
        )


@unittest.skipUnless(shutil.which('php'), 'PHP CLI is not installed')
class WordPressSearchShortcodePhpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        plugin_path = PLUGIN_FILE.as_posix().replace("'", "\\'")
        harness = f"""
define('ABSPATH', __DIR__);
class WP_Post {{}}
function plugin_dir_url($file) {{ return 'https://example.test/plugin/'; }}
function plugin_dir_path($file) {{ return dirname($file) . DIRECTORY_SEPARATOR; }}
function add_action() {{}}
function add_filter() {{}}
function add_shortcode() {{}}
function register_activation_hook() {{}}
function register_deactivation_hook() {{}}
function absint($value) {{ return abs((int) $value); }}
function sanitize_text_field($value) {{ return trim(strip_tags((string) $value)); }}
function wp_unslash($value) {{ return stripslashes((string) $value); }}
function sanitize_title($value) {{
    return preg_replace('/[^a-z0-9-]/', '', strtolower((string) $value));
}}
function add_query_arg($key, $value = null, $url = null) {{
    if (is_array($key)) {{
        $args = $key;
        $url = $value;
    }} else {{
        $args = array($key => $value);
    }}
    $parts = parse_url($url);
    $query = array();
    if (isset($parts['query'])) {{
        parse_str($parts['query'], $query);
    }}
    foreach ($args as $arg_key => $arg_value) {{
        $query[$arg_key] = $arg_value;
    }}
    $base = $parts['scheme'] . '://' . $parts['host'];
    if (isset($parts['path'])) {{
        $base .= $parts['path'];
    }}
    return $base . ($query ? '?' . http_build_query($query) : '');
}}
function wp_parse_url($url, $component = -1) {{ return parse_url($url, $component); }}
function wp_parse_str($string, &$result) {{ parse_str($string, $result); }}
function remove_query_arg($keys, $url) {{
    $parts = parse_url($url);
    $query = array();
    if (isset($parts['query'])) {{
        parse_str($parts['query'], $query);
    }}
    foreach ((array) $keys as $key) {{
        unset($query[$key]);
    }}
    $base = $parts['scheme'] . '://' . $parts['host'];
    if (isset($parts['path'])) {{
        $base .= $parts['path'];
    }}
    return $base . ($query ? '?' . http_build_query($query) : '');
}}
require '{plugin_path}';

$valid_filters = array(
    'keyword' => 'AI',
    'benefit' => 'generative-ai',
    'from' => '2026-02-01',
    'to' => '2026-02-28',
    'page' => 2,
    'errors' => array(),
);
$invalid_filters = $valid_filters;
$invalid_filters['errors'] = array('invalid');

$_GET = array(
    'it_search' => '1',
    'it_q' => 'AI ไทย',
    'it_benefit' => 'generative-ai',
    'it_from' => '2026-02-01',
    'it_to' => '2026-02-28',
    'it_page' => '2',
);
$parsed_filters = oar_innovation_tip_search_filters();

$_GET = array(
    'it_search' => '1',
    'it_benefit' => 'not-controlled',
);
$invalid_slug_filters = oar_innovation_tip_search_filters();

$_GET = array(
    'it_search' => '1',
    'it_from' => '2026-03-01',
    'it_to' => '2026-02-28',
);
$reversed_date_filters = oar_innovation_tip_search_filters();

$_GET = array(
    'it_search' => '1',
    'it_benefit' => array('generative-ai'),
);
$array_filters = oar_innovation_tip_search_filters();

$_GET = array(
    'it_q' => 'must be ignored without marker',
    'it_benefit' => 'generative-ai',
);
$unsubmitted_filters = oar_innovation_tip_search_filters();

$_GET = array(
    'it_search' => '1',
    'it_page' => '-5',
);
$negative_page_filters = oar_innovation_tip_search_filters();

$_GET = array(
    'it_search' => '1',
    'it_page' => '101',
);
$excessive_page_filters = oar_innovation_tip_search_filters();

$pagination_filters = $valid_filters;
$pagination_filters['keyword'] = '999999999';
$pagination_url = oar_innovation_tip_search_pagination_url(
    'https://example.test/search/',
    $pagination_filters
);
$form_action = oar_innovation_tip_search_form_action(
    'https://example.test/?page_id=42&lang=th'
);

echo json_encode(array(
    'valid_date' => oar_innovation_tip_search_normalize_date('2028-02-29'),
    'invalid_date' => oar_innovation_tip_search_normalize_date('2026-02-29'),
    'partial_date' => oar_innovation_tip_search_normalize_date('2026-02'),
    'query' => oar_innovation_tip_search_query_args($valid_filters, 99),
    'invalid_query' => oar_innovation_tip_search_query_args($invalid_filters, 12),
    'parsed_filters' => $parsed_filters,
    'invalid_slug_filters' => $invalid_slug_filters,
    'reversed_date_filters' => $reversed_date_filters,
    'array_filters' => $array_filters,
    'unsubmitted_filters' => $unsubmitted_filters,
    'negative_page_filters' => $negative_page_filters,
    'excessive_page_filters' => $excessive_page_filters,
    'limited_thai' => oar_innovation_tip_search_limit_text('กขคงจ', 3),
    'pagination_url' => $pagination_url,
    'form_action' => $form_action,
));
"""
        completed = subprocess.run(
            [shutil.which('php'), '-r', harness],
            check=True,
            capture_output=True,
            text=True,
        )
        cls.result = json.loads(completed.stdout)

    def test_strict_date_validation(self):
        self.assertEqual('2028-02-29', self.result['valid_date'])
        self.assertFalse(self.result['invalid_date'])
        self.assertFalse(self.result['partial_date'])

    def test_query_combines_keyword_taxonomy_date_and_pagination(self):
        query = self.result['query']

        self.assertEqual('innovation-tip', query['post_type'])
        self.assertEqual('publish', query['post_status'])
        self.assertEqual(24, query['posts_per_page'])
        self.assertEqual(2, query['paged'])
        self.assertEqual('AI', query['s'])
        self.assertEqual(
            'organization_benefit',
            query['tax_query'][0]['taxonomy'],
        )
        self.assertEqual('slug', query['tax_query'][0]['field'])
        self.assertEqual(['generative-ai'], query['tax_query'][0]['terms'])
        self.assertTrue(query['date_query'][0]['inclusive'])
        self.assertEqual(
            {'year': 2026, 'month': 2, 'day': 1},
            query['date_query'][0]['after'],
        )
        self.assertEqual(
            {'year': 2026, 'month': 2, 'day': 28},
            query['date_query'][0]['before'],
        )

    def test_invalid_input_is_fail_closed(self):
        query = self.result['invalid_query']

        self.assertEqual([0], query['post__in'])
        self.assertNotIn('s', query)
        self.assertNotIn('tax_query', query)
        self.assertNotIn('date_query', query)

    def test_real_request_parser_accepts_valid_combined_filters(self):
        filters = self.result['parsed_filters']

        self.assertEqual('AI ไทย', filters['keyword'])
        self.assertEqual('generative-ai', filters['benefit'])
        self.assertEqual('2026-02-01', filters['from'])
        self.assertEqual('2026-02-28', filters['to'])
        self.assertEqual(2, filters['page'])
        self.assertTrue(filters['submitted'])
        self.assertEqual([], filters['errors'])

    def test_real_request_parser_rejects_invalid_values(self):
        self.assertTrue(self.result['invalid_slug_filters']['errors'])
        self.assertEqual('', self.result['invalid_slug_filters']['benefit'])
        self.assertTrue(self.result['reversed_date_filters']['errors'])
        self.assertTrue(self.result['array_filters']['errors'])
        self.assertTrue(self.result['negative_page_filters']['errors'])
        self.assertEqual(1, self.result['negative_page_filters']['page'])
        self.assertTrue(self.result['excessive_page_filters']['errors'])
        self.assertEqual(1, self.result['excessive_page_filters']['page'])

    def test_filters_are_ignored_without_submission_marker(self):
        filters = self.result['unsubmitted_filters']

        self.assertFalse(filters['submitted'])
        self.assertEqual('', filters['keyword'])
        self.assertEqual('', filters['benefit'])
        self.assertEqual(1, filters['page'])

    def test_unicode_limit_and_pagination_placeholder(self):
        self.assertEqual('กขค', self.result['limited_thai'])
        pagination_url = self.result['pagination_url']
        self.assertIn('it_q=999999999', pagination_url)
        self.assertEqual(1, pagination_url.count('%#%'))
        self.assertIn('it_page=%#%', pagination_url)

    def test_plain_permalink_form_action_is_preserved_as_hidden_fields(self):
        form_action = self.result['form_action']

        self.assertEqual('https://example.test/', form_action['url'])
        self.assertEqual(
            {'page_id': '42', 'lang': 'th'},
            form_action['hidden'],
        )


if __name__ == '__main__':
    unittest.main()
