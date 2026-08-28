# Stored Procedures - Setup Complete

**Date:** 22 March 2026
**Database:** `innovation_news`
**User:** `kittisak`

## ✅ Setup Status: Complete

**Procedures Created:** 10/10 ✅

---

## 📋 Stored Procedures

### 1. 📝 `save_article`
**Purpose:** Save article to database (check duplicate first)

**Parameters:**
- `p_source_slug` (VARCHAR 100) - Source slug (e.g., 'nstda')
- `p_title` (VARCHAR 500) - Article title
- `p_summary` (TEXT) - Article summary
- `p_link` (VARCHAR 1000) - Article URL
- `p_date_published` (VARCHAR 100) - Original publish date
- `p_content_hash` (VARCHAR 32) - MD5 hash for deduplication
- `OUT p_article_id` (INT) - Returns article ID
- `OUT p_is_new` (BOOLEAN) - Returns true if new, false if updated

**Usage:**
```sql
CALL save_article(
  'nstda',
  'Article Title',
  'Summary...',
  'https://...',
  '2025-03-22',
  'abc123',
  @article_id,
  @is_new
);

SELECT @article_id, @is_new;
```

**Test Result:** ✅ Passed
- Article ID: 1
- Is New: 1

---

### 2. 📊 `log_fetch_operation`
**Purpose:** Log fetch operation and update source stats

**Parameters:**
- `p_source_slug` (VARCHAR 100) - Source slug
- `p_status` (ENUM) - 'success', 'partial', 'failed', 'error'
- `p_articles_found` (INT) - Total articles found
- `p_articles_sent` (INT) - Articles sent to Telegram
- `p_new_articles` (INT) - New articles (not in cache)
- `p_error_message` (TEXT) - Error details if failed
- `p_duration_ms` (INT) - Fetch duration in milliseconds

**Usage:**
```sql
CALL log_fetch_operation(
  'nstda',
  'success',
  10,
  5,
  2,
  NULL,
  1500
);
```

**Test Result:** ✅ Passed
- Fetch log created
- Source stats updated (fetch_count++, success_count++)

---

### 3. 📈 `get_source_statistics`
**Purpose:** Get statistics for all sources (for dashboard)

**Parameters:** None

**Returns:**
- Source info (id, name, slug, is_active)
- Stats (fetch_count, success_count, error_count, success_rate)
- Article count (total_articles)
- Last article (last_article, days_since_last_article)

**Usage:**
```sql
CALL get_source_statistics();
```

**Test Result:** ✅ Passed
- Returns stats for all 10 sources
- Success rate calculated correctly

---

### 4. 📅 `get_today_articles`
**Purpose:** Get today's articles (for homepage/dashboard)

**Parameters:**
- `p_limit` (INT, optional) - Max articles to return (default: 20)

**Returns:**
- Article info (id, title, link, source, date_sent)
- Summary preview (first 150 chars)

**Usage:**
```sql
CALL get_today_articles(10);
```

**Test Result:** ✅ Passed
- Returns today's articles
- Limit works correctly

---

### 5. 🧹 `cleanup_old_articles`
**Purpose:** Delete old articles and logs (maintenance task)

**Parameters:**
- `p_days_to_keep` (INT, optional) - Days to keep (default: 365)

**Usage:**
```sql
CALL cleanup_old_articles(180);
```

**Test Result:** ✅ Passed
- Deletes articles older than X days
- Deletes logs older than 30 days
- Returns count of deleted articles

---

### 6. 🔄 `update_source_status`
**Purpose:** Enable or disable a source

**Parameters:**
- `p_slug` (VARCHAR 100) - Source slug
- `p_is_active` (TINYINT) - 1 = enable, 0 = disable

**Usage:**
```sql
-- Disable NSTDA
CALL update_source_status('nstda', 0);

-- Enable NSTDA
CALL update_source_status('nstda', 1);
```

**Test Result:** ✅ Passed
- Disable: Works (is_active = 0)
- Enable: Works (is_active = 1)

---

### 7. 📋 `get_articles_by_source`
**Purpose:** Get articles from a specific source

**Parameters:**
- `p_slug` (VARCHAR 100) - Source slug
- `p_days` (INT, optional) - Filter by days (default: all)
- `p_limit` (INT, optional) - Max articles (default: 20)

**Returns:**
- Article info (id, title, link, date_published, date_sent)
- Summary preview (first 200 chars)

**Usage:**
```sql
-- Get NSTDA articles from last 7 days
CALL get_articles_by_source('nstda', 7, 10);
```

**Test Result:** ✅ Passed
- Returns articles from specific source
- Date filter works
- Limit works

---

### 8. 📊 `get_dashboard_stats`
**Purpose:** Get dashboard statistics (for admin panel)

**Parameters:** None

**Returns:**
- Total articles
- Today's articles
- Active sources
- Total fetches (24h)
- Success rate (24h)

**Usage:**
```sql
CALL get_dashboard_stats();
```

**Test Result:** ✅ Passed
- Returns all 5 metrics
- Aggregations correct

---

### 9. 🔍 `search_articles`
**Purpose:** Search articles by keyword

**Parameters:**
- `p_keyword` (VARCHAR 500) - Search keyword
- `p_limit` (INT, optional) - Max results (default: 20)

**Returns:**
- Article info (id, title, link, source, date_sent)
- Summary preview (first 200 chars)

**Usage:**
```sql
-- Search for 'AI'
CALL search_articles('AI', 10);
```

**Test Result:** ✅ Passed
- Returns matching articles
- Searches both title and summary

---

### 10. 📰 `get_recent_articles`
**Purpose:** Get recent articles (within X days)

**Parameters:**
- `p_days` (INT, optional) - Days to look back (default: 7)
- `p_limit` (INT, optional) - Max results (default: 20)

**Returns:**
- Article info (id, title, link, source, date_published, date_sent)
- Summary preview (first 200 chars)

**Usage:**
```sql
-- Get articles from last 7 days
CALL get_recent_articles(7, 10);
```

**Test Result:** ✅ Passed
- Returns recent articles
- Date filter works
- Limit works

---

## 🧪 Test Results Summary

| Procedure | Status | Notes |
|-----------|--------|-------|
| `save_article` | ✅ Passed | Insert & update logic working |
| `log_fetch_operation` | ✅ Passed | Log + stats update working |
| `get_source_statistics` | ✅ Passed | All sources stats correct |
| `get_today_articles` | ✅ Passed | Returns today's articles |
| `cleanup_old_articles` | ✅ Passed | Deletes old data correctly |
| `update_source_status` | ✅ Passed | Enable/disable working |
| `get_articles_by_source` | ✅ Passed | Source filter working |
| `get_dashboard_stats` | ✅ Passed | All metrics correct |
| `search_articles` | ✅ Passed | Search logic working |
| `get_recent_articles` | ✅ Passed | Date filter working |

---

## 📁 Files Created

1. **SQL Script:** `/home/kittisak/.openclaw/workspace/scripts/setup-procedures.sql`
2. **Documentation:** `/home/kittisak/.openclaw/workspace/docs/stored-procedures.md` (this file)

---

## 🔗 Integration with Python

### Example: Save article and log fetch

```python
import mysql.connector

connection = mysql.connector.connect(
    host='localhost',
    user='kittisak',
    password='*${DB_PASS}*',
    database='innovation_news'
)

cursor = connection.cursor()

# Save article
cursor.callproc('save_article', [
    'nstda',
    article['title'],
    article['summary'],
    article['link'],
    article['date'],
    article['hash']
])

# Get result
for result in cursor.stored_results():
    article_id, is_new = result[0]
    print(f"Article ID: {article_id}, Is New: {is_new}")

# Log fetch operation
cursor.callproc('log_fetch_operation', [
    'nstda',
    'success',
    articles_found,
    articles_sent,
    new_articles,
    None,
    duration_ms
])

connection.commit()
cursor.close()
```

---

## 🎯 Next Steps

1. **Update Python script** - Modify fetch-innovation-news.py to use stored procedures
2. **Test integration** - Run fetch script and verify data insertion
3. **Create monitoring** - Use get_source_statistics for dashboard
4. **Set up cron for cleanup** - Run cleanup_old_articles weekly

---

**Status:** ✅ All 10 stored procedures created and tested successfully!
