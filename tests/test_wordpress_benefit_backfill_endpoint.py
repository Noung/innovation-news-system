import base64
import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_FILE = (
    ROOT
    / 'wordpress-plugin'
    / 'innovation-tip-benefit-taxonomy'
    / 'innovation-tip-benefit-taxonomy.php'
)
APPLY_FILE = ROOT / 'scripts' / 'apply-wordpress-benefit-backfill.py'
SCRIPTS_DIR = ROOT / 'scripts'
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


APPLY = load_module('benefit_backfill_apply_for_endpoint_tests', APPLY_FILE)


class GuardedEndpointStaticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PLUGIN_FILE.read_text(encoding='utf-8')
        match = re.search(
            r'function oar_innovation_benefit_backfill_apply\(\$request\)'
            r'\s*\{(?P<body>.*?)\n\}\n\n/\*\*'
            r'\n \* Register the authenticated guarded backfill REST contract',
            cls.source,
            re.DOTALL,
        )
        if not match:
            raise AssertionError('Could not isolate guarded APPLY callback')
        cls.apply_body = match.group('body')

    def test_plugin_and_contract_versions_are_explicit(self):
        self.assertRegex(self.source, r'\* Version: 1\.2\.0')
        self.assertIn(
            "const OAR_INNOVATION_BENEFIT_PLUGIN_VERSION = '1.2.0';",
            self.source,
        )
        self.assertIn(
            "const OAR_INNOVATION_BENEFIT_BACKFILL_CONTRACT_VERSION = '2';",
            self.source,
        )
        self.assertRegex(self.source, r'\* Requires at least: 5\.9')
        self.assertRegex(self.source, r'\* Requires PHP: 7\.2')

    def test_routes_have_authenticated_permission_callbacks(self):
        self.assertIn("'/benefit-backfill-capability'", self.source)
        self.assertIn(
            "'/benefit-backfill-state/(?P<id>\\d+)'",
            self.source,
        )
        self.assertIn("'/benefit-backfill/(?P<id>\\d+)'", self.source)
        self.assertGreaterEqual(
            self.source.count("'permission_callback' => ("),
            3,
        )
        self.assertIn(
            "current_user_can($taxonomy->cap->assign_terms)",
            self.source,
        )
        self.assertIn("current_user_can('edit_post', $post_id)", self.source)

    def test_route_id_cannot_be_overridden_by_body_or_query(self):
        self.assertIn('$request->get_url_params()', self.source)
        self.assertNotIn("$request->get_param('id')", self.source)
        self.assertIn('$request->get_json_params()', self.source)
        self.assertIn('$request->get_body_params()', self.source)
        self.assertIn('$request->get_query_params()', self.source)
        self.assertIn(
            "'oar_backfill_conflicting_post_id'",
            self.source,
        )
        self.assertIn(
            'oar_innovation_benefit_backfill_route_post_id($request)',
            self.apply_body,
        )

    def test_storage_guard_requires_every_mutated_table_to_be_innodb(self):
        for table in (
            '$wpdb->posts',
            '$wpdb->postmeta',
            '$wpdb->terms',
            '$wpdb->term_taxonomy',
            '$wpdb->term_relationships',
        ):
            self.assertIn(table, self.source)
        self.assertIn('SHOW TABLE STATUS WHERE Name = %s', self.source)
        self.assertNotIn('SHOW TABLE STATUS LIKE %s', self.source)
        self.assertIn(
            "strtolower((string) $table_status->Engine) !== 'innodb'",
            self.source,
        )

    def test_apply_uses_serializable_locked_compare_and_set(self):
        required_fragments = (
            'SET TRANSACTION ISOLATION LEVEL SERIALIZABLE',
            "START TRANSACTION",
            'SAVEPOINT oar_backfill_mutation',
            'RELEASE SAVEPOINT oar_backfill_mutation',
            'FOR UPDATE',
            'expected_modified_gmt',
            'expected_term_ids',
            'target_term_ids',
            'target_term_slugs',
            'expected_source_sha256',
            'oar_innovation_benefit_backfill_controlled_terms_state',
            'oar_innovation_benefit_backfill_db_current_ids',
            'oar_backfill_relationship_lock_failed',
            'wp_set_post_terms(',
            "'ROLLBACK'",
            "'COMMIT'",
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, self.apply_body)
        self.assertNotIn('wp_insert_term(', self.apply_body)
        self.assertNotIn('wp_update_post(', self.apply_body)

    def test_exact_vocabulary_and_non_taxonomy_hook_changes_fail_closed(self):
        self.assertIn(
            'count($rows) !== count($expected)',
            self.source,
        )
        self.assertIn(
            "'oar_backfill_controlled_terms_changed'",
            self.source,
        )
        self.assertIn(
            "'oar_backfill_term_mapping_changed'",
            self.source,
        )
        self.assertIn(
            "'oar_backfill_non_taxonomy_side_effect'",
            self.apply_body,
        )
        self.assertIn(
            'oar_innovation_benefit_backfill_lock_all_meta',
            self.apply_body,
        )
        self.assertIn(
            'oar_innovation_benefit_backfill_other_relationships_hash',
            self.apply_body,
        )
        self.assertGreaterEqual(
            self.apply_body.count(
                'oar_innovation_benefit_backfill_controlled_terms_state'
            ),
            2,
        )
        self.assertIn('$controlled_after_hash', self.apply_body)
        self.assertIn('$other_relationships_after_hash', self.apply_body)
        self.assertIn(
            'oar_innovation_benefit_backfill_connection_guard',
            self.apply_body,
        )
        self.assertNotIn('@@session.in_transaction', self.source)
        self.assertIn('$committed_ids', self.apply_body)
        self.assertIn('$committed_source', self.apply_body)
        self.assertIn('clean_post_cache($post_id)', self.apply_body)
        self.assertIn('clean_object_term_cache(', self.apply_body)
        self.assertIn('wp_cache_set_terms_last_changed()', self.apply_body)

    def test_python_source_contains_no_core_rest_mutation_method(self):
        source = APPLY_FILE.read_text(encoding='utf-8')
        self.assertNotIn('def post_benefits(', source)
        self.assertIn('def apply_guarded_benefits(', source)
        self.assertIn(
            "f'{self.guarded_api_url}/benefit-backfill/{int(post_id)}'",
            source,
        )


@unittest.skipUnless(shutil.which('php'), 'PHP CLI is not installed')
class GuardedEndpointPhpTests(unittest.TestCase):
    def test_plugin_php_lints(self):
        result = subprocess.run(
            ['php', '-l', str(PLUGIN_FILE)],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('No syntax errors detected', result.stdout)

    def test_python_and_php_source_fingerprints_match(self):
        post = {
            'title': {'raw': 'ชื่อข่าว AI'},
            'content': {'raw': '<p>เนื้อหาเพื่อองค์กร</p>'},
            'excerpt': {'raw': 'สรุป'},
            'meta': {
                'ptb_innovation_tip_content': (
                    '<strong>ประโยชน์ต่อองค์กร</strong>'
                ),
            },
        }
        expected = APPLY.source_guard_sha256(post)
        values = [
            post['title']['raw'],
            post['content']['raw'],
            post['excerpt']['raw'],
            post['meta']['ptb_innovation_tip_content'],
        ]
        encoded_values = [
            base64.b64encode(value.encode('utf-8')).decode('ascii')
            for value in values
        ]
        plugin_path = PLUGIN_FILE.as_posix().replace("'", "\\'")
        php_values = ','.join(
            f"base64_decode('{value}')"
            for value in encoded_values
        )
        harness = f"""<?php
define('ABSPATH', __DIR__);
function plugin_dir_url($file) {{ return 'https://example.test/plugin/'; }}
function plugin_dir_path($file) {{ return dirname($file) . DIRECTORY_SEPARATOR; }}
function add_action() {{}}
function add_filter() {{}}
function add_shortcode() {{}}
function register_activation_hook() {{}}
function register_deactivation_hook() {{}}
require '{plugin_path}';
$values = array({php_values});
$row = array(
    'post_title' => $values[0],
    'post_content' => $values[1],
    'post_excerpt' => $values[2],
);
echo oar_innovation_benefit_backfill_source_sha256($row, $values[3]);
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            script_path = Path(temp_dir) / 'source-guard.php'
            script_path.write_text(harness, encoding='utf-8')
            result = subprocess.run(
                ['php', str(script_path)],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                check=False,
            )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(expected, result.stdout.strip())


if __name__ == '__main__':
    unittest.main()
