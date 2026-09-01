-- Local-only sanitized baseline derived from current application query contracts.
-- This is not a PROD export and must never be applied as a production migration.

SET NAMES utf8mb4;
SET time_zone = '+07:00';

CREATE TABLE news_sources (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(100) NOT NULL,
    source_url VARCHAR(2000) NOT NULL,
    fetch_method ENUM('rss', 'html', 'api') NOT NULL,
    api_variant ENUM('wordpress', 'generic_json') NOT NULL DEFAULT 'wordpress',
    json_items_path VARCHAR(255) NULL,
    json_title_field VARCHAR(255) NULL,
    json_link_field VARCHAR(255) NULL,
    json_date_field VARCHAR(255) NULL,
    json_summary_field VARCHAR(255) NULL,
    is_active TINYINT(1) NOT NULL DEFAULT 0,
    last_fetched_at DATETIME NULL,
    fetch_count INT UNSIGNED NOT NULL DEFAULT 0,
    success_count INT UNSIGNED NOT NULL DEFAULT 0,
    error_count INT UNSIGNED NOT NULL DEFAULT 0,
    last_test_status ENUM('pending', 'passed', 'failed') NOT NULL DEFAULT 'pending',
    last_test_articles_found INT UNSIGNED NULL,
    last_test_at DATETIME NULL,
    last_test_error TEXT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_news_sources_name (name),
    UNIQUE KEY uq_news_sources_slug (slug),
    KEY idx_news_sources_active (is_active),
    KEY idx_news_sources_last_fetched (last_fetched_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE innovation_news (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    source_id INT UNSIGNED NOT NULL,
    title VARCHAR(500) NOT NULL,
    summary TEXT NOT NULL,
    link VARCHAR(1000) NOT NULL,
    date_published VARCHAR(100) NULL,
    date_sent DATETIME NULL,
    content_hash CHAR(32) NOT NULL,
    is_sent TINYINT(1) NOT NULL DEFAULT 0,
    telegram_status ENUM('sent', 'failed', 'skipped', 'dry_run', 'not_configured', 'disabled') NOT NULL DEFAULT 'skipped',
    wordpress_status ENUM('created', 'duplicate', 'failed', 'skipped', 'dry_run', 'not_configured', 'disabled') NOT NULL DEFAULT 'skipped',
    line_status ENUM('sent', 'failed', 'skipped', 'dry_run', 'blocked_by_wordpress', 'not_configured', 'disabled') NOT NULL DEFAULT 'skipped',
    wordpress_url VARCHAR(1000) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_innovation_news_link (link(768)),
    KEY idx_innovation_news_source (source_id),
    KEY idx_innovation_news_hash (content_hash),
    KEY idx_innovation_news_date_sent (date_sent),
    KEY idx_innovation_news_line_status (line_status),
    KEY idx_innovation_news_source_created (source_id, created_at),
    CONSTRAINT fk_innovation_news_source
        FOREIGN KEY (source_id) REFERENCES news_sources(id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE fetch_logs (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    source_id INT UNSIGNED NULL,
    articles_found INT UNSIGNED NOT NULL DEFAULT 0,
    mysql_status ENUM('saved', 'failed', 'skipped') NOT NULL DEFAULT 'skipped',
    new_articles INT UNSIGNED NOT NULL DEFAULT 0,
    articles_sent INT UNSIGNED NOT NULL DEFAULT 0,
    telegram_status ENUM('sent', 'failed', 'skipped', 'dry_run', 'not_configured', 'disabled') NOT NULL DEFAULT 'skipped',
    wordpress_status ENUM('created', 'duplicate', 'failed', 'skipped', 'dry_run', 'not_configured', 'disabled') NOT NULL DEFAULT 'skipped',
    line_status ENUM('sent', 'failed', 'skipped', 'dry_run', 'blocked_by_wordpress', 'not_configured', 'disabled') NOT NULL DEFAULT 'skipped',
    status ENUM('success', 'partial', 'failed', 'error') NOT NULL,
    error_message TEXT NULL,
    duration_ms INT UNSIGNED NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_fetch_logs_source (source_id),
    KEY idx_fetch_logs_status (status),
    KEY idx_fetch_logs_created (created_at),
    KEY idx_fetch_logs_source_status (source_id, status),
    CONSTRAINT fk_fetch_logs_source
        FOREIGN KEY (source_id) REFERENCES news_sources(id)
        ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE admin_audit_logs (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    username VARCHAR(100) NOT NULL,
    action VARCHAR(100) NOT NULL,
    target_type VARCHAR(100) NOT NULL,
    target_id BIGINT UNSIGNED NULL,
    target_name VARCHAR(255) NULL,
    details_json JSON NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_admin_audit_created (created_at),
    KEY idx_admin_audit_username (username),
    KEY idx_admin_audit_target (target_type, target_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE article_benefits (
    article_id BIGINT UNSIGNED NOT NULL,
    benefit_slug VARCHAR(64) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (article_id, benefit_slug),
    KEY idx_article_benefits_slug_article (benefit_slug, article_id),
    CONSTRAINT fk_article_benefits_article
        FOREIGN KEY (article_id) REFERENCES innovation_news(id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE subscribers (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    email_normalized VARCHAR(254) NOT NULL,
    status ENUM('pending', 'active', 'unsubscribed') NOT NULL DEFAULT 'pending',
    consented_at DATETIME NULL,
    consent_version VARCHAR(32) NOT NULL,
    confirmed_at DATETIME NULL,
    unsubscribed_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_subscribers_email_normalized (email_normalized),
    KEY idx_subscribers_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE subscriber_benefits (
    subscriber_id BIGINT UNSIGNED NOT NULL,
    benefit_slug VARCHAR(64) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (subscriber_id, benefit_slug),
    KEY idx_subscriber_benefits_slug_subscriber (benefit_slug, subscriber_id),
    CONSTRAINT fk_subscriber_benefits_subscriber
        FOREIGN KEY (subscriber_id) REFERENCES subscribers(id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE subscription_tokens (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    subscriber_id BIGINT UNSIGNED NOT NULL,
    token_type ENUM('confirm', 'unsubscribe') NOT NULL,
    token_hash CHAR(64) NOT NULL,
    expires_at DATETIME NOT NULL,
    used_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_subscription_tokens_hash (token_hash),
    KEY idx_subscription_tokens_lookup (token_type, token_hash, expires_at),
    CONSTRAINT fk_subscription_tokens_subscriber
        FOREIGN KEY (subscriber_id) REFERENCES subscribers(id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE email_deliveries (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    article_id BIGINT UNSIGNED NOT NULL,
    subscriber_id BIGINT UNSIGNED NOT NULL,
    status ENUM('pending', 'sent', 'failed') NOT NULL DEFAULT 'pending',
    provider_message_id VARCHAR(255) NULL,
    error_message VARCHAR(1000) NULL,
    sent_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_email_deliveries_article_subscriber (article_id, subscriber_id),
    KEY idx_email_deliveries_status_created (status, created_at),
    CONSTRAINT fk_email_deliveries_article
        FOREIGN KEY (article_id) REFERENCES innovation_news(id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_email_deliveries_subscriber
        FOREIGN KEY (subscriber_id) REFERENCES subscribers(id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE email_delivery_attempts (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    email_delivery_id BIGINT UNSIGNED NOT NULL,
    status ENUM('sent', 'failed') NOT NULL,
    error_message VARCHAR(1000) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_email_delivery_attempts_delivery (email_delivery_id, created_at),
    CONSTRAINT fk_email_delivery_attempts_delivery
        FOREIGN KEY (email_delivery_id) REFERENCES email_deliveries(id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE OR REPLACE VIEW v_source_stats AS
SELECT
    ns.id,
    ns.name,
    ns.slug,
    ns.is_active,
    ns.fetch_count,
    ns.success_count,
    ns.error_count,
    CASE WHEN ns.fetch_count = 0 THEN 0
         ELSE ROUND(ns.success_count * 100.0 / ns.fetch_count, 2) END AS success_rate,
    COUNT(n.id) AS total_articles,
    MAX(n.date_published) AS last_article_date,
    MAX(n.created_at) AS last_article_created,
    DATEDIFF(CURRENT_DATE, DATE(MAX(n.created_at))) AS days_since_last_article
FROM news_sources ns
LEFT JOIN innovation_news n ON n.source_id = ns.id
GROUP BY ns.id;

CREATE OR REPLACE VIEW v_recent_fetch_logs AS
SELECT
    fl.id,
    ns.name AS source,
    ns.slug AS source_slug,
    fl.status,
    fl.articles_found,
    fl.articles_sent,
    fl.new_articles,
    fl.duration_ms,
    fl.error_message,
    fl.created_at
FROM fetch_logs fl
LEFT JOIN news_sources ns ON ns.id = fl.source_id
WHERE fl.created_at >= DATE_SUB(NOW(), INTERVAL 1 DAY);

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
