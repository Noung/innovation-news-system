CREATE DEFINER=`kittisak`@`%` PROCEDURE `log_fetch_operation`(
  IN p_source_slug VARCHAR(100),
  IN p_status ENUM('success', 'partial', 'failed', 'error'),
  IN p_articles_found INT,
  IN p_articles_sent INT,
  IN p_new_articles INT,
  IN p_error_message TEXT,
  IN p_duration_ms INT
)
BEGIN
  DECLARE v_source_id INT;

  -- ค้นหา source_id จาก slug
  SELECT id INTO v_source_id
  FROM news_sources
  WHERE slug = p_source_slug
  LIMIT 1;

  -- ถ้าไม่พบ source → log error และ return
  IF v_source_id IS NULL THEN
    -- บันทึก log ว่า source_slug ไม่พบ พร้อม error_message
    INSERT INTO fetch_logs (
      source_id,
      status,
      articles_found,
      articles_sent,
      new_articles,
      error_message,
      duration_ms
    ) VALUES (
      NULL,
      'error',
      0,
      0,
      0,
      CONCAT('Source slug not found: ', IFNULL(p_source_slug, '(NULL)')),
      IFNULL(p_duration_ms, 0)
    );

    -- ไม่อัปเดต news_sources stats เพราะไม่รู้ว่าเป็น source ไหน
    LEAVE sp_label;
  END IF;

  -- ถ้าพบ source → บันทึก log ปกติ
  INSERT INTO fetch_logs (
    source_id,
    status,
    articles_found,
    articles_sent,
    new_articles,
    error_message,
    duration_ms
  ) VALUES (
    v_source_id,
    p_status,
    p_articles_found,
    p_articles_sent,
    p_new_articles,
    p_error_message,
    p_duration_ms
  );

  -- อัปเดต stats ของ source
  UPDATE news_sources
  SET fetch_count = fetch_count + 1,
      success_count = success_count + IF(p_status = 'success', 1, 0),
      error_count = error_count + IF(p_status IN ('failed', 'error'), 1, 0),
      last_fetched_at = NOW(),
      updated_at = NOW()
  WHERE id = v_source_id;

  sp_label: END;
