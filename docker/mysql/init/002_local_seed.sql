-- Synthetic local data only. No URLs, articles, identifiers, or credentials came from PROD.

SET NAMES utf8mb4;

INSERT INTO news_sources (
    name,
    slug,
    source_url,
    fetch_method,
    api_variant,
    json_items_path,
    json_title_field,
    json_link_field,
    json_date_field,
    json_summary_field,
    is_active,
    last_test_status,
    last_test_articles_found,
    last_test_at
) VALUES (
    'Local Mock Innovation Source',
    'local-mock',
    'https://mock-integrations:8443/api/news',
    'api',
    'generic_json',
    'items',
    'title',
    'link',
    'published_at',
    'summary',
    1,
    'passed',
    2,
    NOW()
);

INSERT INTO innovation_news (
    source_id,
    title,
    summary,
    link,
    date_published,
    content_hash,
    telegram_status,
    wordpress_status,
    line_status
)
SELECT
    id,
    'บทความสังเคราะห์สำหรับตรวจหน้า Admin',
    'ข้อมูลตัวอย่างที่สร้างขึ้นสำหรับ local development เท่านั้น',
    'https://mock-integrations:8443/articles/local-seeded',
    DATE_FORMAT(NOW(), '%Y-%m-%dT%H:%i:%s+00:00'),
    MD5('local-synthetic-seed'),
    'dry_run',
    'dry_run',
    'dry_run'
FROM news_sources
WHERE slug = 'local-mock';

INSERT INTO fetch_logs (
    source_id,
    articles_found,
    mysql_status,
    new_articles,
    articles_sent,
    telegram_status,
    wordpress_status,
    line_status,
    status,
    duration_ms
)
SELECT
    id,
    1,
    'saved',
    1,
    0,
    'dry_run',
    'dry_run',
    'dry_run',
    'success',
    25
FROM news_sources
WHERE slug = 'local-mock';
