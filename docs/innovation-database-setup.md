# Innovation News Database - Setup Complete

**Date:** 22 March 2026 (Updated: 3 September 2026)
**Database:** `innovation_news`
**User:** `kittisak`

## ✅ Setup Status: Complete (Schema Evolved)

**หมายเหตุ:** เอกสารนี้แสดงสถานะเริ่มต้นของ database เมื่อ 22 มี.ค. 2026 ปัจจุบัน schema มีวิวัฒนาการเพิ่มเติม:

- เพิ่มตาราง `admin_audit_logs` สำหรับบันทึกการใช้งาน Admin
- เพิ่มตาราง `article_benefits` สำหรับเก็บ benefit ของแต่ละบทความ
- เพิ่มตาราง `subscribers`, `subscriber_benefits`, `subscription_tokens`, `email_deliveries` สำหรับระบบ subscription (กำลังพัฒนา)
- เพิ่ม stored procedures สำหรับ subscription management
- เพิ่ม views สำหรับ admin dashboard
- จำนวน sources เพิ่มจาก 10 เป็น 16 sources

### Database Created

```sql
Database: innovation_news
Character Set: utf8mb4
Collation: utf8mb4_unicode_ci
```

### Tables Created (3 tables)

#### 1. news_sources

**Purpose:** Store news source configurations

**Columns:**
| Column | Type | Description |
|--------|------|-------------|
| id | INT UNSIGNED PK | Primary Key |
| name | VARCHAR(100) UNIQUE | Source name (NIA, ETDA, etc.) |
| slug | VARCHAR(100) UNIQUE | Source slug (nia, etda, etc.) |
| source_url | VARCHAR(500) | Source URL |
| fetch_method | ENUM(rss, html, api) | Fetch method |
| is_active | TINYINT(1) | Active status |
| last_fetched_at | DATETIME | Last fetch timestamp |
| fetch_count | INT UNSIGNED | Total fetch attempts |
| success_count | INT UNSIGNED | Successful fetches |
| error_count | INT UNSIGNED | Failed fetches |
| created_at | DATETIME | Creation time |
| updated_at | DATETIME | Update time |

**Indexes:**

- PRIMARY (id)
- UNIQUE (name)
- UNIQUE (slug)
- KEY (is_active)
- KEY (last_fetched_at)

**Seed Data:** 16 sources inserted (ปัจจุบัน)

1. NIA (html)
2. ETDA (rss)
3. Techsauce (rss)
4. NSTDA (api/wordpress)
5. RYT9 (rss)
6. iT24Hrs (rss)
7. TechTalkThai (rss)
8. NECTEC (html)
9. Tech Movement (html)
10. Innomatter (rss)
11. NRIIS (rss)
12. Innovation News Network (api/wordpress)
13. Tech Xplore (rss)
14. iMod (api/wordpress)
15. Blognone (rss)
16. OARKM (rss)

---

#### 2. innovation_news

**Purpose:** Store innovation news articles

**Columns:**
| Column | Type | Description |
|--------|------|-------------|
| id | INT UNSIGNED PK | Primary Key |
| source_id | INT UNSIGNED FK | Reference to news_sources |
| title | VARCHAR(500) | Article title |
| summary | TEXT | Article summary (800 chars) |
| link | VARCHAR(1000) UNIQUE | Article URL |
| date_published | VARCHAR(100) | Original publish date |
| date_sent | DATETIME | Sent to Telegram time |
| content_hash | VARCHAR(32) | MD5 hash for deduplication |
| is_sent | TINYINT(1) | Sent status |
| created_at | DATETIME | Creation time |
| updated_at | DATETIME | Update time |

**Foreign Keys:**

- `source_id` → `news_sources(id)` (RESTRICT on delete, CASCADE on update)

**Indexes:**

- PRIMARY (id)
- UNIQUE (link)
- KEY (source_id)
- KEY (content_hash)
- KEY (date_sent)
- KEY (is_sent)
- KEY (source_id, date_sent)

---

#### 3. fetch_logs

**Purpose:** Log fetch operations

**Columns:**
| Column | Type | Description |
|--------|------|-------------|
| id | BIGINT UNSIGNED PK | Primary Key |
| source_id | INT UNSIGNED FK | Reference to news_sources |
| articles_found | INT UNSIGNED | Articles found |
| articles_sent | INT UNSIGNED | Articles sent |
| new_articles | INT UNSIGNED | New articles |
| status | ENUM(...) | Fetch status |
| error_message | TEXT | Error details |
| duration_ms | INT UNSIGNED | Fetch duration |
| created_at | DATETIME | Log timestamp |

**Foreign Keys:**

- `source_id` → `news_sources(id)` (SET NULL on delete, CASCADE on update)

**Indexes:**

- PRIMARY (id)
- KEY (source_id)
- KEY (status)
- KEY (created_at)
- KEY (source_id, status)
- KEY (status, created_at)

---

### Views Created (4 views)

#### 1. v_source_stats

**Purpose:** Source statistics overview

**Columns:**

- id, name, slug, is_active
- fetch_count, success_count, error_count
- success_rate (percentage)
- total_articles
- last_article_date
- last_article_created
- days_since_last_article

**Usage:**

```sql
SELECT * FROM v_source_stats ORDER BY total_articles DESC;
```

---

#### 2. v_latest_articles

**Purpose:** Latest articles (last 7 days)

**Columns:**

- id, title, link, source, source_slug
- date_published, date_sent, is_sent
- summary_preview (first 200 chars)

**Usage:**

```sql
SELECT * FROM v_latest_articles ORDER BY date_sent DESC LIMIT 20;
```

---

#### 3. v_today_articles

**Purpose:** Today's articles only

**Columns:**

- id, title, link, source, date_sent
- is_sent, summary_preview (first 150 chars)

**Usage:**

```sql
SELECT * FROM v_today_articles;
```

---

#### 4. v_recent_fetch_logs

**Purpose:** Recent fetch logs (last 24 hours)

**Columns:**

- id, source, source_slug
- status, articles_found, articles_sent, new_articles
- duration_ms, error_message, created_at

**Usage:**

```sql
SELECT * FROM v_recent_fetch_logs;
```

---

## 🔗 Relationships

```
news_sources (1) ────────────── (N) innovation_news
     id (PK)                        source_id (FK)

news_sources (1) ────────────── (N) fetch_logs
     id (PK)                        source_id (FK)
```

---

## 📊 Quick Queries

### Check all sources

```sql
SELECT * FROM news_sources ORDER BY id;
```

### Check source stats

```sql
SELECT * FROM v_source_stats;
```

### Check latest articles

```sql
SELECT * FROM v_latest_articles LIMIT 10;
```

### Check recent fetch logs

```sql
SELECT * FROM v_recent_fetch_logs;
```

### Articles by source

```sql
SELECT s.name, COUNT(n.id) AS total
FROM news_sources s
LEFT JOIN innovation_news n ON s.id = n.source_id
GROUP BY s.id;
```

---

## 🔧 Database Connection

**Connection String:**

```
mysql -u kittisak -p*${DB_PASS}* innovation_news
```

**Python Connection:**

```python
import mysql.connector

connection = mysql.connector.connect(
    host='localhost',
    user='kittisak',
    password='*${DB_PASS}*',
    database='innovation_news'
)
```

---

## ✅ Verification Results

**Tables:** ✅ 3 tables created

- news_sources
- innovation_news
- fetch_logs

**Foreign Keys:** ✅ 2 FKs created

- innovation_news.source_id → news_sources.id
- fetch_logs.source_id → news_sources.id

**Views:** ✅ 4 views created

- v_source_stats
- v_latest_articles
- v_today_articles
- v_recent_fetch_logs

**Seed Data:** ✅ 10 sources inserted

- NIA, ETDA, Techsauce, NSTDA, RYT9
- iT24Hrs, TechTalkThai, NECTEC, TechMovement, Innomatter

---

## 📝 Next Steps

1. **Update Python script** - Add MySQL connection to fetch-innovation-news.py
2. **Test integration** - Run fetch script and verify data insertion
3. **Create monitoring** - Use views to track performance
4. **Backup database** - Set up regular backups

---

**Status:** ✅ Database setup complete and ready for use!
