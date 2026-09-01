-- Local-only safety/runtime overlay.
-- Apply this after either the synthetic baseline or a sanitized PROD snapshot.
-- Never apply this file to PROD.

SET NAMES utf8mb4;
SET time_zone = '+07:00';

ALTER TABLE innovation_news
    ADD COLUMN IF NOT EXISTS wordpress_url VARCHAR(1000) NULL
    AFTER line_status;

UPDATE news_sources
SET source_url = CONCAT('https://mock-integrations:8443/source/', slug),
    is_active = 0,
    last_test_status = 'pending',
    last_test_articles_found = NULL,
    last_test_at = NULL,
    last_test_error = NULL
WHERE slug <> 'local-mock';

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
)
ON DUPLICATE KEY UPDATE
    source_url = 'https://mock-integrations:8443/api/news',
    fetch_method = 'api',
    api_variant = 'generic_json',
    json_items_path = 'items',
    json_title_field = 'title',
    json_link_field = 'link',
    json_date_field = 'published_at',
    json_summary_field = 'summary',
    is_active = 1,
    last_test_status = 'passed',
    last_test_articles_found = 2,
    last_test_at = NOW(),
    last_test_error = NULL;

DROP PROCEDURE IF EXISTS save_article;
DROP PROCEDURE IF EXISTS log_fetch_operation;

DELIMITER //

CREATE PROCEDURE save_article(
    IN p_source_slug VARCHAR(100),
    IN p_title VARCHAR(500),
    IN p_summary TEXT,
    IN p_link VARCHAR(1000),
    IN p_date_published VARCHAR(100),
    IN p_content_hash CHAR(32),
    OUT p_article_id BIGINT UNSIGNED,
    OUT p_is_new TINYINT
)
save_article_proc: BEGIN
    DECLARE v_source_id INT UNSIGNED DEFAULT NULL;
    DECLARE v_existing_id BIGINT UNSIGNED DEFAULT NULL;

    SELECT id INTO v_source_id
    FROM news_sources
    WHERE slug = p_source_slug
    LIMIT 1;

    IF v_source_id IS NULL THEN
        SET p_article_id = 0;
        SET p_is_new = 0;
        LEAVE save_article_proc;
    END IF;

    SELECT id INTO v_existing_id
    FROM innovation_news
    WHERE content_hash = p_content_hash
       OR (title = p_title AND link = p_link)
    ORDER BY id DESC
    LIMIT 1;

    IF v_existing_id IS NOT NULL THEN
        SET p_article_id = v_existing_id;
        SET p_is_new = 0;
        LEAVE save_article_proc;
    END IF;

    INSERT INTO innovation_news (
        source_id, title, summary, link, date_published, content_hash
    ) VALUES (
        v_source_id, p_title, p_summary, p_link, p_date_published, p_content_hash
    );

    SET p_article_id = LAST_INSERT_ID();
    SET p_is_new = 1;
END//

CREATE PROCEDURE log_fetch_operation(
    IN p_source_slug VARCHAR(100),
    IN p_status VARCHAR(16),
    IN p_articles_found INT,
    IN p_articles_sent INT,
    IN p_new_articles INT,
    IN p_error_message TEXT,
    IN p_duration_ms INT
)
BEGIN
    DECLARE v_source_id INT UNSIGNED DEFAULT NULL;

    SELECT id INTO v_source_id
    FROM news_sources
    WHERE slug = p_source_slug
    LIMIT 1;

    INSERT INTO fetch_logs (
        source_id, status, articles_found, articles_sent, new_articles,
        error_message, duration_ms
    ) VALUES (
        v_source_id,
        IF(p_status IN ('success', 'partial', 'failed', 'error'), p_status, 'error'),
        GREATEST(IFNULL(p_articles_found, 0), 0),
        GREATEST(IFNULL(p_articles_sent, 0), 0),
        GREATEST(IFNULL(p_new_articles, 0), 0),
        p_error_message,
        GREATEST(IFNULL(p_duration_ms, 0), 0)
    );

    IF v_source_id IS NOT NULL THEN
        UPDATE news_sources
        SET fetch_count = fetch_count + 1,
            success_count = success_count + IF(p_status IN ('success', 'partial'), 1, 0),
            error_count = error_count + IF(p_status IN ('failed', 'error'), 1, 0),
            last_fetched_at = IF(p_status IN ('success', 'partial'), NOW(), last_fetched_at),
            updated_at = NOW()
        WHERE id = v_source_id;
    END IF;
END//

DELIMITER ;
