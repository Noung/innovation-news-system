import importlib.util
import os
import subprocess
import sys
import types
import unittest
import tempfile
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT_DIR / 'scripts'
sys.path.insert(0, str(SCRIPTS_DIR))

import line_integration as line  # noqa: E402
import wordpress_integration as wp  # noqa: E402


def load_fetcher_module():
    if 'bs4' not in sys.modules:
        try:
            import bs4  # noqa: F401
        except ModuleNotFoundError:
            bs4_stub = types.ModuleType('bs4')
            bs4_stub.BeautifulSoup = object
            sys.modules['bs4'] = bs4_stub

    script_path = SCRIPTS_DIR / 'fetch-innovation-news-mysql.py'
    spec = importlib.util.spec_from_file_location('phase0_fetcher_test', script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FETCHER = load_fetcher_module()


class FakeLockCursor:
    def __init__(self, lock_result=1, release_result=1):
        self.lock_result = lock_result
        self.release_result = release_result
        self.executions = []
        self.last_query = ''
        self.closed = False

    def execute(self, query, params=None):
        self.last_query = query
        self.executions.append((query, params))

    def fetchone(self):
        if 'RELEASE_LOCK' in self.last_query:
            return (self.release_result,)
        return (self.lock_result,)

    def close(self):
        self.closed = True


class FakeLockConnection:
    def __init__(self, cursor):
        self.lock_cursor = cursor
        self.closed = False

    def cursor(self):
        return self.lock_cursor

    def close(self):
        self.closed = True


class FakeFcntl:
    LOCK_EX = 1
    LOCK_NB = 2
    LOCK_UN = 4

    def __init__(self, busy=False):
        self.busy = busy
        self.calls = []

    def flock(self, file_descriptor, operation):
        self.calls.append((file_descriptor, operation))
        if self.busy and operation == self.LOCK_EX | self.LOCK_NB:
            raise BlockingIOError('local fetch lock is busy')


class GlobalFetchLockTests(unittest.TestCase):
    def _connection(self, lock_result=1, release_result=1):
        cursor = FakeLockCursor(lock_result, release_result)
        return FakeLockConnection(cursor), cursor

    def test_lock_is_parameterized_and_held_until_context_exit(self):
        connection, cursor = self._connection()
        with patch.object(FETCHER, 'DB_USER', 'test-user'), patch.object(
            FETCHER, 'get_db_connection', return_value=connection
        ):
            with FETCHER.global_fetch_lock() as acquired:
                self.assertTrue(acquired)
                self.assertFalse(connection.closed)
                get_lock_query = next(
                    execution for execution in cursor.executions
                    if execution[0] == 'SELECT GET_LOCK(%s, %s)'
                )
                self.assertEqual(
                    get_lock_query[1],
                    (FETCHER.FETCH_LOCK_NAME, FETCHER.FETCH_LOCK_TIMEOUT_SECONDS),
                )

        self.assertTrue(connection.closed)
        self.assertTrue(cursor.closed)
        self.assertEqual(cursor.executions[-1][0], 'SELECT RELEASE_LOCK(%s)')

    def test_busy_lock_does_not_attempt_release(self):
        connection, cursor = self._connection(lock_result=0)
        with patch.object(FETCHER, 'DB_USER', 'test-user'), patch.object(
            FETCHER, 'get_db_connection', return_value=connection
        ):
            with FETCHER.global_fetch_lock() as acquired:
                self.assertFalse(acquired)

        self.assertEqual(
            [query for query, _params in cursor.executions],
            ['SELECT GET_LOCK(%s, %s)'],
        )
        self.assertTrue(connection.closed)

    def test_busy_local_file_lock_short_circuits_before_mysql(self):
        fake_fcntl = FakeFcntl(busy=True)
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_path = Path(temp_dir) / 'fetch.lock'
            with patch.object(FETCHER, 'fcntl', fake_fcntl), patch.object(
                FETCHER, 'FETCH_FILE_LOCK_PATH', lock_path
            ), patch.object(FETCHER, 'get_db_connection') as get_connection:
                with FETCHER.global_fetch_lock() as acquired:
                    self.assertFalse(acquired)

            self.assertEqual(
                [fake_fcntl.LOCK_EX | fake_fcntl.LOCK_NB],
                [operation for _fd, operation in fake_fcntl.calls],
            )
            get_connection.assert_not_called()

    def test_local_file_lock_is_held_through_mysql_lock_context(self):
        fake_fcntl = FakeFcntl()
        connection, cursor = self._connection()
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_path = Path(temp_dir) / 'fetch.lock'
            with patch.object(FETCHER, 'fcntl', fake_fcntl), patch.object(
                FETCHER, 'FETCH_FILE_LOCK_PATH', lock_path
            ), patch.object(FETCHER, 'DB_USER', 'test-user'), patch.object(
                FETCHER, 'get_db_connection', return_value=connection
            ):
                with FETCHER.global_fetch_lock() as acquired:
                    self.assertTrue(acquired)
                    self.assertEqual(
                        [fake_fcntl.LOCK_EX | fake_fcntl.LOCK_NB],
                        [operation for _fd, operation in fake_fcntl.calls],
                    )

            self.assertEqual(
                [fake_fcntl.LOCK_EX | fake_fcntl.LOCK_NB, fake_fcntl.LOCK_UN],
                [operation for _fd, operation in fake_fcntl.calls],
            )
            self.assertEqual(cursor.executions[-1][0], 'SELECT RELEASE_LOCK(%s)')
            self.assertTrue(connection.closed)

    def test_null_lock_result_fails_closed(self):
        connection, _cursor = self._connection(lock_result=None)
        with patch.object(FETCHER, 'DB_USER', 'test-user'), patch.object(
            FETCHER, 'get_db_connection', return_value=connection
        ):
            with self.assertRaises(FETCHER.GlobalFetchLockError):
                with FETCHER.global_fetch_lock():
                    self.fail('fetch body must not start')
        self.assertTrue(connection.closed)

    def test_body_exception_still_releases_and_closes(self):
        connection, cursor = self._connection()
        with patch.object(FETCHER, 'DB_USER', 'test-user'), patch.object(
            FETCHER, 'get_db_connection', return_value=connection
        ):
            with self.assertRaisesRegex(RuntimeError, 'body failed'):
                with FETCHER.global_fetch_lock():
                    raise RuntimeError('body failed')

        self.assertIn('RELEASE_LOCK', cursor.executions[-1][0])
        self.assertTrue(connection.closed)

    def test_unconfirmed_release_is_a_lock_integrity_error(self):
        connection, _cursor = self._connection(release_result=0)
        with patch.object(FETCHER, 'DB_USER', 'test-user'), patch.object(
            FETCHER, 'get_db_connection', return_value=connection
        ):
            with self.assertRaises(FETCHER.GlobalFetchLockError):
                with FETCHER.global_fetch_lock() as acquired:
                    self.assertTrue(acquired)
        self.assertTrue(connection.closed)

    def test_main_skips_fetch_when_another_run_holds_lock(self):
        with patch.object(FETCHER, 'global_fetch_lock', return_value=nullcontext(False)), patch.object(
            FETCHER, '_run_fetch_cycle'
        ) as run_cycle:
            result = FETCHER.main()

        self.assertEqual(result, FETCHER.EXIT_FETCH_ALREADY_RUNNING)
        run_cycle.assert_not_called()

    def test_main_maps_lock_failure_to_software_exit(self):
        class FailingLock:
            def __enter__(self):
                raise FETCHER.GlobalFetchLockError('unavailable')

            def __exit__(self, *_args):
                return False

        with patch.object(FETCHER, 'global_fetch_lock', return_value=FailingLock()), patch.object(
            FETCHER, '_run_fetch_cycle'
        ) as run_cycle:
            result = FETCHER.main()

        self.assertEqual(result, FETCHER.EXIT_FETCH_LOCK_ERROR)
        run_cycle.assert_not_called()

    def test_main_maps_release_integrity_failure_to_lock_error(self):
        connection, _cursor = self._connection(release_result=0)
        with patch.object(FETCHER, 'DB_USER', 'test-user'), patch.object(
            FETCHER, 'get_db_connection', return_value=connection
        ), patch.object(FETCHER, '_run_fetch_cycle', return_value=FETCHER.EXIT_OK):
            result = FETCHER.main()

        self.assertEqual(result, FETCHER.EXIT_FETCH_LOCK_ERROR)


class FetchCycleExitTests(unittest.TestCase):
    def test_no_active_sources_returns_success_exit_code(self):
        with patch.object(FETCHER, 'get_sources_list', return_value=[]), patch.object(
            FETCHER, 'log_message'
        ):
            result = FETCHER._run_fetch_cycle()

        self.assertEqual(result, FETCHER.EXIT_OK)


class SourceUrlSecurityTests(unittest.TestCase):
    def _generic_config(self, source_url='https://news.example.test/v2/everything'):
        return {
            'source_url': source_url,
            'fetch_method': 'api',
            'api_variant': 'generic_json',
            'json_items_path': 'articles',
            'json_title_field': 'title',
            'json_link_field': 'url',
            'json_date_field': 'publishedAt',
            'json_summary_field': 'description',
        }

    def test_credentials_in_source_url_are_rejected_and_error_text_is_redacted(self):
        secret = 'query-secret-value'
        unsafe_url = f'https://news.example.test/feed?apiKey={secret}'
        self.assertTrue(FETCHER.source_url_has_credentials(unsafe_url))
        self.assertFalse(FETCHER.source_url_is_allowed(unsafe_url))

        sanitized = FETCHER.truncate_error_message(f'GET {unsafe_url} failed')
        self.assertNotIn(secret, sanitized)
        self.assertIn('[REDACTED]', sanitized)

    def test_non_https_and_credential_bearing_database_urls_fail_closed(self):
        for unsafe_url in (
            'http://news.example.test/feed',
            'https://user:password@news.example.test/feed',
            'https://news.example.test/feed?token=secret',
        ):
            with self.subTest(unsafe_url=unsafe_url), patch.object(
                FETCHER, 'run_mysql_query', return_value=unsafe_url
            ), patch.object(FETCHER, 'log_message'):
                self.assertIsNone(FETCHER.get_source_url('unsafe-source'))

    def test_generic_api_key_uses_header_and_redirects_are_disabled(self):
        class Response:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {
                    'articles': [{
                        'title': 'Secure API article',
                        'url': 'https://news.example.test/article',
                        'publishedAt': '2026-08-05T00:00:00Z',
                        'description': 'Summary',
                    }]
                }

        config = self._generic_config()
        with patch.object(FETCHER, 'get_source_runtime_config', return_value=config), patch.dict(
            os.environ,
            {
                'INNOVATION_NEWS_SOURCE_API_KEY_NEWSAPI': 'header-secret-value',
                'INNOVATION_NEWS_SOURCE_API_KEY_HEADER_NEWSAPI': 'X-Api-Key',
            },
            clear=False,
        ), patch.object(FETCHER.requests, 'get', return_value=Response()) as request_get:
            articles, errors = FETCHER.fetch_generic_json_api_articles('newsapi', 'News API')

        self.assertEqual(errors, [])
        self.assertEqual(len(articles), 1)
        request_kwargs = request_get.call_args.kwargs
        self.assertEqual(request_kwargs['headers']['X-Api-Key'], 'header-secret-value')
        self.assertIs(request_kwargs['allow_redirects'], False)

    def test_rejected_source_is_recorded_as_error_not_empty_success(self):
        with patch.object(
            FETCHER,
            'get_source_runtime_config',
            return_value={'api_variant': 'generic_json'},
        ), patch.object(
            FETCHER,
            'fetch_generic_json_api_articles',
            return_value=([], ['newsapi: source URL rejected']),
        ):
            fetcher = FETCHER.build_runtime_fetcher(
                'newsapi', 'News API', 'api', fallback_fetcher=None
            )
            articles, error = FETCHER.safe_fetch_articles('News API', fetcher)

        self.assertEqual(articles, [])
        self.assertIn('source URL rejected', error)


class TlsConfigurationTests(unittest.TestCase):
    def test_tls_verification_is_enabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIs(wp.get_wp_config()['verify_tls'], True)
            self.assertIs(line.get_line_config()['verify_tls'], True)

    def test_custom_ca_bundle_is_forwarded_to_requests(self):
        with patch.dict(os.environ, {'WP_CA_BUNDLE': '/ca/wp.pem'}, clear=True):
            self.assertEqual(wp.get_wp_config()['verify_tls'], '/ca/wp.pem')
        with patch.dict(os.environ, {'LINE_CA_BUNDLE': '/ca/line.pem'}, clear=True):
            self.assertEqual(line.get_line_config()['verify_tls'], '/ca/line.pem')

    def test_integrations_contain_no_hardcoded_tls_bypass(self):
        for filename in ('wordpress_integration.py', 'line_integration.py'):
            source = (SCRIPTS_DIR / filename).read_text(encoding='utf-8')
            self.assertNotIn('verify=False', source)

    def test_disable_flags_cannot_turn_off_verification(self):
        with patch.dict(os.environ, {'WP_VERIFY_TLS': '0'}, clear=True):
            self.assertIs(wp.get_wp_config()['verify_tls'], True)
        with patch.dict(os.environ, {'LINE_VERIFY_TLS': 'false'}, clear=True):
            self.assertIs(line.get_line_config()['verify_tls'], True)

    def test_credentialed_integrations_reject_plain_http(self):
        with patch.dict(
            os.environ,
            {'WP_API_URL': 'http://wp.example.test/wp-json', 'WP_USERNAME': 'u', 'WP_APP_PASSWORD': 'p'},
            clear=True,
        ):
            self.assertFalse(wp.is_wordpress_configured())
            self.assertEqual(wp.get_wp_config()['url'], '')
        with patch.dict(
            os.environ,
            {'LINE_API_URL': 'http://line.example.test/notify', 'LINE_API_KEY': 'secret'},
            clear=True,
        ):
            self.assertFalse(line.is_line_configured())
            self.assertEqual(line.get_line_config()['url'], '')

    def test_integration_endpoints_reject_url_embedded_credentials(self):
        for unsafe_url in (
            'https://user:password@wp.example.test/wp-json',
            'https://wp.example.test/wp-json?token=secret',
        ):
            with self.subTest(unsafe_url=unsafe_url), patch.dict(
                os.environ,
                {'WP_API_URL': unsafe_url, 'WP_USERNAME': 'u', 'WP_APP_PASSWORD': 'p'},
                clear=True,
            ):
                self.assertFalse(wp.is_wordpress_configured())

        for unsafe_url in (
            'https://user:password@line.example.test/notify',
            'https://line.example.test/notify?api_key=secret',
        ):
            with self.subTest(unsafe_url=unsafe_url), patch.dict(
                os.environ,
                {'LINE_API_URL': unsafe_url, 'LINE_API_KEY': 'secret'},
                clear=True,
            ):
                self.assertFalse(line.is_line_configured())


class SchedulerAndEnvironmentPolicyTests(unittest.TestCase):
    def test_pm2_contains_api_only_and_no_scheduler(self):
        ecosystem = (ROOT_DIR / 'fetch-innovation-news' / 'ecosystem.config.js').read_text(
            encoding='utf-8'
        )
        self.assertIn("name: 'innovation-news-api'", ecosystem)
        self.assertNotIn('cron_restart', ecosystem)
        self.assertNotIn("name: 'innovation-news-fetcher'", ecosystem)
        self.assertNotIn("name: 'it24hrs-news-fetcher'", ecosystem)

    def test_pm2_helpers_never_stop_or_delete_all_apps(self):
        for filename in ('pm2-setup.sh', 'pm2-setup-prod.sh'):
            source = (ROOT_DIR / 'fetch-innovation-news' / filename).read_text(
                encoding='utf-8'
            )
            self.assertNotIn('pm2 stop all', source)
            self.assertNotIn('pm2 delete all', source)

    def test_cron_installer_is_scoped_and_dry_run_by_default(self):
        source = (SCRIPTS_DIR / 'install-innovation-news-cron.sh').read_text(
            encoding='utf-8'
        )
        self.assertIn('MODE="dry-run"', source)
        self.assertIn('# BEGIN INNOVATION-NEWS MANAGED', source)
        self.assertIn('crontab -l', source)
        self.assertNotIn('crontab /tmp/crontab_new.txt', source)
        self.assertNotIn('diff -u', source)
        self.assertIn('Existing command lines are intentionally not printed', source)

    def test_node_env_loading_prefers_root_and_stops_after_first_file(self):
        source = (ROOT_DIR / 'fetch-innovation-news' / 'api' / 'server.js').read_text(
            encoding='utf-8'
        )
        root_candidate = "path.join(DEPLOY_WORKSPACE_DIR, '.env')"
        legacy_candidate = "path.join(SCRIPTS_DIR, '.env')"
        self.assertLess(source.index(root_candidate), source.index(legacy_candidate))
        self.assertIn('loadedEnvFile = true;\n            break;', source)
        self.assertNotIn("path.join(APP_DIR, '.env')", source)
        self.assertNotIn("path.join(process.cwd(), '.env')", source)
        self.assertIn("process.env[key] = value", source)

    def test_phase0_subscription_gates_are_disabled(self):
        values = {}
        for raw_line in (ROOT_DIR / '.env.example').read_text(encoding='utf-8').splitlines():
            if raw_line and not raw_line.startswith('#') and '=' in raw_line:
                key, value = raw_line.split('=', 1)
                values[key] = value

        self.assertEqual(values['ENABLE_SUBSCRIPTION_API'], '0')
        self.assertEqual(values['ENABLE_EMAIL_WORKER'], '0')
        self.assertEqual(values['EMAIL_SEND_MODE'], 'disabled')

    def test_deploy_is_read_only_by_default_and_never_copies_env(self):
        source = (ROOT_DIR / 'fetch-innovation-news' / 'deploy-to-prod.sh').read_text(
            encoding='utf-8'
        )
        self.assertIn('MODE="${1:---dry-run}"', source)
        bundle_start = source.index('BUNDLE_FILES=(')
        bundle_end = source.index('\n)', bundle_start)
        bundle = source[bundle_start:bundle_end]
        self.assertNotIn('".env"', bundle)
        self.assertNotIn('"scripts/.env"', bundle)
        self.assertNotIn('crontab_new', source)
        self.assertIn('sha256sum -c SHA256SUMS', source)
        self.assertIn('tests/test_phase0_runtime.py', bundle)
        self.assertIn('scripts/trigger-ksstat.sh', bundle)

    def test_public_health_response_does_not_return_database_error_details(self):
        source = (ROOT_DIR / 'fetch-innovation-news' / 'api' / 'server.js').read_text(
            encoding='utf-8'
        )
        health_start = source.index("app.get('/api/health'")
        health_end = source.index("app.post('/api/fetch/run-now'", health_start)
        health_handler = source[health_start:health_end]
        self.assertNotIn('error: error.message', health_handler)

    def test_admin_bind_host_is_configurable(self):
        source = (ROOT_DIR / 'fetch-innovation-news' / 'api' / 'server.js').read_text(
            encoding='utf-8'
        )
        self.assertIn("process.env.ADMIN_BIND_HOST || '127.0.0.1'", source)
        self.assertIn("allowedBindHosts", source)
        self.assertIn("'0.0.0.0'", source)
        self.assertIn('app.listen(port, bindHost', source)

    def test_dependency_free_admin_config_check_and_fail_closed_validation(self):
        server_path = ROOT_DIR / 'fetch-innovation-news' / 'api' / 'server.js'

        def run_check(env_text):
            with tempfile.TemporaryDirectory() as temp_dir:
                env_path = Path(temp_dir) / '.env'
                env_path.write_text(
                    env_text + 'ADMIN_USERNAME_2=\nADMIN_PASSWORD_2=\n',
                    encoding='utf-8',
                )
                environment = os.environ.copy()
                environment['INNOVATION_NEWS_ENV_FILE'] = str(env_path)
                return subprocess.run(
                    ['node', str(server_path), '--config-check'],
                    capture_output=True,
                    text=True,
                    env=environment,
                    timeout=15,
                )

        valid = run_check(
            'ADMIN_BIND_HOST=127.0.0.1\n'
            'ADMIN_TRUST_PROXY=loopback\n'
            'ADMIN_USERNAME=phase0-admin\n'
            'ADMIN_PASSWORD=V9b7-Q2m4-R8t6-X3p5\n'
            'ADMIN_SESSION_SECRET=Z8m4Q2p7R9t6V3x5K1n8C4b7L2s9D6f3\n'
        )
        self.assertEqual(valid.returncode, 0, valid.stderr)
        self.assertIn('Configuration OK', valid.stdout)

        valid_lan_bind = run_check(
            'ADMIN_BIND_HOST=0.0.0.0\n'
            'ADMIN_USERNAME=phase0-admin\n'
            'ADMIN_PASSWORD=V9b7-Q2m4-R8t6-X3p5\n'
            'ADMIN_SESSION_SECRET=Z8m4Q2p7R9t6V3x5K1n8C4b7L2s9D6f3\n'
        )
        self.assertEqual(valid_lan_bind.returncode, 0, valid_lan_bind.stderr)

        invalid_bind = run_check(
            'ADMIN_BIND_HOST=192.0.2.10\n'
            'ADMIN_USERNAME=phase0-admin\n'
            'ADMIN_PASSWORD=V9b7-Q2m4-R8t6-X3p5\n'
            'ADMIN_SESSION_SECRET=Z8m4Q2p7R9t6V3x5K1n8C4b7L2s9D6f3\n'
        )
        self.assertNotEqual(invalid_bind.returncode, 0)

        placeholder = run_check(
            'ADMIN_BIND_HOST=127.0.0.1\n'
            'ADMIN_USERNAME=phase0-admin\n'
            'ADMIN_PASSWORD=your_admin_password\n'
            'ADMIN_SESSION_SECRET=Z8m4Q2p7R9t6V3x5K1n8C4b7L2s9D6f3\n'
        )
        self.assertNotEqual(placeholder.returncode, 0)

    def test_admin_login_has_rate_limit_and_basic_security_headers(self):
        source = (ROOT_DIR / 'fetch-innovation-news' / 'api' / 'server.js').read_text(
            encoding='utf-8'
        )
        self.assertIn("res.status(429)", source)
        self.assertIn("'Retry-After'", source)
        self.assertIn("'X-Content-Type-Options', 'nosniff'", source)
        self.assertIn("bodyParser.json({ limit: '100kb' })", source)
        self.assertNotIn('app.use(cors())', source)
        self.assertIn("return res.status(403).json({ success: false, error: 'Origin not allowed' })", source)
        self.assertIn("readIntegerEnv('ADMIN_LOGIN_RATE_MAX_ATTEMPTS'", source)
        self.assertIn('ADMIN_SESSION_SECRET must contain at least 32 characters', source)

    def test_admin_rejects_url_credentials_and_redacts_audit_details(self):
        source = (ROOT_DIR / 'fetch-innovation-news' / 'api' / 'server.js').read_text(
            encoding='utf-8'
        )
        self.assertIn('hasCredentialQueryParameter(normalizedPayload.source_url)', source)
        self.assertIn('JSON.stringify(sanitizeAuditDetails(details))', source)
        self.assertIn("parsed.searchParams.set(key, '[REDACTED]')", source)
        self.assertIn('Boolean(parsed.username || parsed.password)', source)
        self.assertIn("source_url: redactUrlCredentials(row.source_url || '')", source)
        self.assertIn('res.json = (payload) => sendJson(sanitizeApiResponse(payload))', source)
        self.assertIn('function redactSensitiveText(rawValue)', source)

    def test_subscription_api_is_feature_gated_and_origin_scoped(self):
        source = (ROOT_DIR / 'fetch-innovation-news' / 'api' / 'server.js').read_text(
            encoding='utf-8'
        )
        self.assertIn("const subscriptionApiEnabled = process.env.ENABLE_SUBSCRIPTION_API === '1';", source)
        self.assertIn("req.path.startsWith('/api/subscriptions') && subscriptionOrigins.has(origin)", source)
        self.assertIn("app.post('/api/subscriptions'", source)
        self.assertIn("app.get('/api/subscriptions/confirm'", source)
        self.assertIn("app.get('/api/subscriptions/unsubscribe'", source)
        self.assertIn("crypto.createHmac('sha256', subscriptionTokenSecret)", source)
        self.assertIn("const genericResponse =", source)

    def test_runtime_environment_overrides_dotenv_values(self):
        fetcher = (SCRIPTS_DIR / 'fetch-innovation-news-mysql.py').read_text(
            encoding='utf-8'
        )
        server = (ROOT_DIR / 'fetch-innovation-news' / 'api' / 'server.js').read_text(
            encoding='utf-8'
        )
        self.assertIn("key not in os.environ", fetcher)
        self.assertIn("process.env[key] === undefined", server)
        self.assertIn("ENABLE_EMAIL_WORKER = env_flag('ENABLE_EMAIL_WORKER', False)", fetcher)

    def test_email_worker_is_gated_and_uses_idempotent_delivery_records(self):
        source = (
            ROOT_DIR / 'fetch-innovation-news' / 'api' / 'email-worker.js'
        ).read_text(encoding='utf-8')
        self.assertIn("const enabled = process.env.ENABLE_EMAIL_WORKER === '1';", source)
        self.assertIn("INSERT IGNORE INTO email_deliveries", source)
        self.assertIn("INNER JOIN article_benefits", source)
        self.assertIn("s.status = 'active'", source)
        self.assertIn("n.wordpress_url IS NOT NULL", source)
        self.assertIn("nodemailer.createTransport", source)
        self.assertIn('LIMIT ${batchSize}', source)
        self.assertNotIn('LIMIT ?`', source)

    def test_admin_assets_are_self_hosted_and_csp_blocks_external_scripts(self):
        html_source = (ROOT_DIR / 'fetch-innovation-news' / 'public' / 'index.html').read_text(
            encoding='utf-8'
        )
        server_source = (ROOT_DIR / 'fetch-innovation-news' / 'api' / 'server.js').read_text(
            encoding='utf-8'
        )
        css_path = ROOT_DIR / 'fetch-innovation-news' / 'public' / 'admin.css'

        self.assertNotIn('cdn.tailwindcss.com', html_source)
        self.assertNotIn('fonts.googleapis.com', html_source)
        self.assertIn('href="/admin.css"', html_source)
        self.assertGreater(css_path.stat().st_size, 10000)
        self.assertIn("Content-Security-Policy", server_source)
        self.assertIn("default-src 'self'", server_source)

    def test_unsafe_credential_editor_and_runtime_installer_are_retired(self):
        update_helper = (SCRIPTS_DIR / 'update-wp-env.sh').read_text(encoding='utf-8')
        start_helper = (ROOT_DIR / 'fetch-innovation-news' / 'start.sh').read_text(
            encoding='utf-8'
        )
        self.assertIn('RETIRED', update_helper)
        self.assertNotIn('sed -i', update_helper)
        self.assertNotIn('.env.backup', update_helper)
        self.assertNotIn('npm install', start_helper)
        self.assertNotIn('External:', start_helper)


class SecretSprawlAuditTests(unittest.TestCase):
    def test_legacy_env_is_reported_even_when_its_secret_differs_from_root(self):
        script_path = SCRIPTS_DIR / 'audit-secret-sprawl.py'
        spec = importlib.util.spec_from_file_location('legacy_env_audit_test', script_path)
        audit = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(audit)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / 'scripts').mkdir()
            env_file = root / '.env'
            legacy_env = root / 'scripts' / '.env'
            env_file.write_text('DB_PASS=current-secret-value\n', encoding='utf-8')
            legacy_env.write_text('DB_PASS=different-old-secret\n', encoding='utf-8')

            findings = audit.find_secret_sprawl(root, env_file)

        self.assertEqual(findings['LEGACY_ENV_FILE'], [legacy_env])

    def test_report_names_key_and_path_but_never_secret_value(self):
        script_path = SCRIPTS_DIR / 'audit-secret-sprawl.py'
        spec = importlib.util.spec_from_file_location('secret_sprawl_audit_test', script_path)
        audit = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(audit)

        secret_value = 'unit-test-secret-value'
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            env_file = root / '.env'
            env_file.write_text(f'LINE_API_KEY={secret_value}\n', encoding='utf-8')
            (root / 'unsafe.md').write_text(f'copied={secret_value}\n', encoding='utf-8')

            findings = audit.find_secret_sprawl(root, env_file)
            report = audit.format_report(root, findings)

        self.assertIn('LINE_API_KEY', report)
        self.assertIn('unsafe.md', report)
        self.assertNotIn(secret_value, report)

    def test_redaction_replaces_value_atomically_without_reporting_it(self):
        script_path = SCRIPTS_DIR / 'audit-secret-sprawl.py'
        spec = importlib.util.spec_from_file_location('secret_sprawl_redaction_test', script_path)
        audit = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(audit)

        secret_value = 'another-unit-test-secret'
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            env_file = root / '.env'
            unsafe_file = root / 'unsafe.md'
            env_file.write_text(f'DB_PASS={secret_value}\n', encoding='utf-8')
            unsafe_file.write_text(f'password={secret_value}\n', encoding='utf-8')
            findings = audit.find_secret_sprawl(root, env_file)

            counts = audit.redact_keys(env_file, findings, ['DB_PASS'])
            redacted = unsafe_file.read_text(encoding='utf-8')

        self.assertEqual(counts, {'DB_PASS': 1})
        self.assertIn('${DB_PASS}', redacted)
        self.assertNotIn(secret_value, redacted)

    def test_query_string_credentials_are_reported_and_redacted_without_value_output(self):
        script_path = SCRIPTS_DIR / 'audit-secret-sprawl.py'
        spec = importlib.util.spec_from_file_location('query_credential_audit_test', script_path)
        audit = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(audit)

        credential = 'query-unit-test-credential'
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            env_file = root / '.env'
            sql_file = root / 'snapshot.sql'
            env_file.write_text('DB_PASS=unrelated-test-password\n', encoding='utf-8')
            sql_file.write_text(
                "INSERT INTO source VALUES ('https://example.test/feed?api_"
                f"key={credential}');\n",
                encoding='utf-8',
            )
            findings = audit.find_secret_sprawl(root, env_file)
            report = audit.format_report(root, findings)
            count = audit.redact_query_credentials(findings)
            redacted = sql_file.read_text(encoding='utf-8')

        self.assertIn('QUERY_STRING_CREDENTIAL', report)
        self.assertNotIn(credential, report)
        self.assertEqual(count, 1)
        self.assertIn('${QUERY_STRING_CREDENTIAL}', redacted)
        self.assertNotIn(credential, redacted)


if __name__ == '__main__':
    unittest.main()
