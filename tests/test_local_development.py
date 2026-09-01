import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class LocalDevelopmentScaffoldTests(unittest.TestCase):
    def read(self, relative_path):
        return (ROOT / relative_path).read_text(encoding="utf-8")

    def test_compose_is_loopback_only_and_runtime_network_is_internal(self):
        compose = self.read("compose.yaml")
        self.assertIn('"127.0.0.1:3001:8080"', compose)
        self.assertEqual(compose.count('"127.0.0.1:'), 1)
        self.assertIn("internal: true", compose)
        self.assertIn("host-access:", compose)
        self.assertIn("no-new-privileges:true", compose)
        self.assertNotIn("192.168.160.19", compose)
        self.assertNotIn("/home/kittisak", compose)

    def test_local_environment_is_fail_safe_and_uses_only_mock_endpoints(self):
        env_text = self.read("docker/local.env.example")
        values = {}
        for raw_line in env_text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key] = value

        self.assertEqual(values["DRY_RUN"], "1")
        self.assertEqual(values["ENABLE_SUBSCRIPTION_API"], "0")
        self.assertEqual(values["ENABLE_EMAIL_WORKER"], "0")
        self.assertEqual(values["EMAIL_SEND_MODE"], "json")
        self.assertEqual(values["DB_HOST"], "mysql")
        self.assertEqual(
            values["INNOVATION_NEWS_ENV_FILE"],
            "/workspace/docker/local.env.example",
        )
        self.assertTrue(values["WP_API_URL"].startswith("https://mock-integrations:"))
        self.assertTrue(values["LINE_API_URL"].startswith("https://mock-integrations:"))
        self.assertEqual(values["OPENCLAW_BIN"], "/workspace/docker/mock/openclaw-mock")
        self.assertGreaterEqual(len(values["ADMIN_PASSWORD"]), 16)
        self.assertNotIn("password", values["ADMIN_PASSWORD"].casefold())
        self.assertNotIn("placeholder", values["ADMIN_PASSWORD"].casefold())
        self.assertNotIn("192.168.160.19", env_text)
        self.assertNotIn("/home/kittisak", env_text)
        self.assertNotIn("MYSQL_ROOT_PASSWORD", env_text)

        mysql_env = self.read("docker/mysql.env.example")
        self.assertIn("MYSQL_ROOT_PASSWORD=local-only-root-password", mysql_env)
        self.assertNotIn("WP_APP_PASSWORD", mysql_env)
        self.assertNotIn("LINE_API_KEY", mysql_env)
        self.assertNotIn("ADMIN_SESSION_SECRET", mysql_env)

    def test_sanitized_baseline_covers_application_tables_and_columns(self):
        schema = self.read("docker/mysql/init/001_local_baseline.sql")
        required_tables = (
            "news_sources",
            "innovation_news",
            "fetch_logs",
            "admin_audit_logs",
            "article_benefits",
            "subscribers",
            "subscriber_benefits",
            "subscription_tokens",
            "email_deliveries",
            "email_delivery_attempts",
        )
        required_columns = (
            "api_variant",
            "json_items_path",
            "last_test_status",
            "telegram_status",
            "wordpress_status",
            "line_status",
            "details_json",
            "wordpress_url",
            "email_normalized",
            "benefit_slug",
            "token_hash",
        )
        for table in required_tables:
            self.assertIn(f"CREATE TABLE {table}", schema)
        for column in required_columns:
            self.assertIn(column, schema)
        self.assertIn("CREATE PROCEDURE save_article", schema)
        self.assertIn("CREATE PROCEDURE log_fetch_operation", schema)
        self.assertNotIn("CREATE DEFINER", schema)
        self.assertNotIn("192.168.160.19", schema)
        self.assertNotIn("/home/kittisak", schema)

    def test_seed_is_synthetic_and_points_only_to_local_mock(self):
        seed = self.read("docker/mysql/init/002_local_seed.sql")
        self.assertIn("Local Mock Innovation Source", seed)
        self.assertIn("https://mock-integrations:8443/", seed)
        self.assertNotIn("192.168.160.19", seed)
        self.assertNotIn("/home/kittisak", seed)
        self.assertNotIn("newsapi", seed.casefold())

    def test_runtime_overlay_disables_imported_sources_and_restores_procedures(self):
        overlay = self.read("docker/mysql/init/003_local_runtime_overlay.sql")
        self.assertIn("WHERE slug <> 'local-mock'", overlay)
        self.assertIn("is_active = 0", overlay)
        self.assertIn("https://mock-integrations:8443/api/news", overlay)
        self.assertIn("ON DUPLICATE KEY UPDATE", overlay)
        self.assertIn("CREATE PROCEDURE save_article", overlay)
        self.assertIn("CREATE PROCEDURE log_fetch_operation", overlay)
        self.assertNotIn("192.168.160.19", overlay)
        self.assertNotIn("/home/kittisak", overlay)

    def test_prod_snapshot_drop_zone_is_excluded_from_git_and_docker_builds(self):
        gitignore = self.read(".gitignore")
        dockerignore = self.read(".dockerignore")
        self.assertIn("local-data/", gitignore)
        self.assertIn("local-data", dockerignore)

    def test_mock_has_complete_controlled_benefit_vocabulary(self):
        module_path = ROOT / "docker" / "mock" / "server.py"
        spec = importlib.util.spec_from_file_location("local_mock_server", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(len(module.BENEFIT_TERMS), 20)
        self.assertEqual(len({slug for _name, slug in module.BENEFIT_TERMS}), 20)

    def test_php56_subscription_form_has_no_api_secret_or_storage(self):
        form = self.read(
            "wordpress-plugin/innovation-news-subscription-form/"
            "innovation-news-subscription-form.php"
        )
        self.assertIn("Requires PHP: 5.6", form)
        self.assertIn("add_shortcode('innovation_news_subscribe'", form)
        self.assertIn("benefits[]", form)
        self.assertIn("XMLHttpRequest", form)
        self.assertNotIn("SMTP_PASSWORD", form)
        self.assertNotIn("wp_insert_user", form)


if __name__ == "__main__":
    unittest.main()
