# Innovation News Fetcher (MySQL Version)

**Version:** 2.0.0 (Updated: 3 September 2026)
**Database:** `innovation_news`
**Python:** 3.6+
**Created:** 2026-03-22

**หมายเหตุ:** เอกสารนี้แสดงสถานะเดิมของ fetcher ปัจจุบันระบบรองรับ 16 แหล่งข้อมูล และมี Admin Dashboard สำหรับจัดการ sources แบบ dynamic

---

## 📋 รายละเอียด

### แหล่งข่าวที่รองรับ (16 sources - ปัจจุบัน)

| #   | Source                                                      | ประเภท | URL                                   |
| --- | ----------------------------------------------------------- | ------ | ------------------------------------- |
| 1   | NIA (สำนักงานนวัตกรรมแห่งชาติ)                              | HTML   | https://www.nia.or.th                 |
| 2   | ETDA (สำนักงานพัฒนาธุรกรรมทางอิเล็กทรอนิกส์)                | RSS    | https://www.etda.or.th                |
| 3   | Techsauce                                                   | RSS    | https://techsauce.com                 |
| 4   | NSTDA (สำนักงานพัฒนาวิทยาศาสตร์และเทคโนโลยีแห่งชาติ)        | API    | https://www.nstda.or.th               |
| 5   | RYT9                                                        | RSS    | https://www.ryt9.com                  |
| 6   | iT24Hrs                                                     | RSS    | https://www.it24hrs.com               |
| 7   | TechTalkThai                                                | RSS    | https://www.techtalkthai.com          |
| 8   | NECTEC (ศูนย์เทคโนโลยีอิเล็กทรอนิกส์และคอมพิวเตอร์แห่งชาติ) | HTML   | https://www.nectec.or.th              |
| 9   | Tech Movement                                               | HTML   | https://techmovement.co.th            |
| 10  | Innomatter                                                  | RSS    | https://www.innomatter.com            |
| 11  | NRIIS (ระบบข้อมูลสารสนเทศวิจัยและนวัตกรรมแห่งชาติ)          | RSS    | https://nriis.go.th                   |
| 12  | Innovation News Network                                     | API    | https://www.innovationnewsnetwork.com |
| 13  | Tech Xplore                                                 | RSS    | https://techxplore.com                |
| 14  | iMod                                                        | API    | https://www.iphonemod.net             |
| 15  | Blognone                                                    | RSS    | https://www.blognone.com              |
| 16  | OARKM (การจัดการความรู้ สำนักวิทยบริการ ม.อ.ปัตตานี)        | RSS    | https://oarkm.oas.psu.ac.th           |

---

## 🎯 คุณสมบัติ

### ✅ บันทึกลง Database

- บันทึกบทความลง table `innovation_news`
- ใช้ stored procedures `save_article` และ `log_fetch_operation`
- Check duplicate ด้วย MD5 hash
- บันทึกบันทึกบทความเดิม

### ✅ Tracking และ Statistics

- บันทึก logs ทุกการ fetch ลง table `fetch_logs`
- Update stats ของแต่ละ source (fetch_count, success_count, error_count)
- Track เวลา last_fetched_at ของแต่ละ source

### ✅ ส่ง Telegram

- ส่งบทความใหม่ผ่าน Telegram
- ใช้ OpenClaw CLI สำหรับการส่ง
- หมุนเวียน source ทุก 30 นาที

### ✅ Deduplication

- ใช้ MD5 hash ของ title + link
- Check duplicate ใน database
- บันทึกบทความเดิม (update) ถ้ามีอยู่

---

## 📦 Requirements

### System

- **Python:** 3.6+ (แนะนำ 3.8+)
- **MySQL:** 5.7+ (แนะนำ 8.0+)
- **OS:** Linux (Ubuntu/Debian recommended)
- **RAM:** 512MB minimum
- **Disk:** 500MB free space

### Python Packages

```bash
# Core requirements
requests
mysql-connector-python
```

**ติดตั้ง:**

```bash
pip3 install requests mysql-connector-python
```

### Database

**ต้องมี database:** `innovation_news`

**ต้องมี tables:**

- `news_sources` (10 sources seeded)
- `innovation_news` (บทความ)
- `fetch_logs` (logs)

**ต้องมี stored procedures:**

- `save_article` - บันทึกบทความ
- `log_fetch_operation` - บันทึก logs และ update stats

---

## 📂 File Structure

```
/home/kittisak/.openclaw/workspace/scripts/
├── fetch-innovation-news-mysql.py  # Main script
├── fetch-innovation-news.py           # Old version (cache-based)
└── setup-innovation-db.sql           # Database setup script

/home/kittisak/.openclaw/workspace/cache/
├── innovation-news-cache.json          # Cache file (legacy)
└── innovation-sources-index.txt       # Source rotation index

/home/kittisak/.openclaw/workspace/logs/
└── innovation-news-fetch.log            # Log file

/home/kittisak/.openclaw/workspace/docs/
├── innovation-database-setup.md        # Database documentation
└── fetch-innovation-news-mysql.md     # This README
```

---

## 🚀 การติดตั้ง

### 1. ติดตั้ง Database

```bash
# เข้าไป folder scripts
cd /home/kittisak/.openclaw/workspace/scripts

# รัน database setup script
mysql -u kittisak -p*${DB_PASS}* < setup-innovation-db.sql
```

**ผลลัพธ์:**

```
✅ Database setup complete!
Database: innovation_news
Tables: news_sources, innovation_news, fetch_logs
Views: v_source_stats, v_latest_articles, v_today_articles, v_recent_fetch_logs
Sources seeded: 10
```

### 2. ติดตั้ง Python Packages

```bash
# ติดตั้ง Python packages
pip3 install requests mysql-connector-python
```

### 3. ตั้งค่า Environment Variables (ถ้าต้องการ)

```bash
# แก้ไฟล์ script หรือ set environment variables
export TELEGRAM_TOKEN="your-telegram-token"
export TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID}"
```

**หมายเหตุ:**

- Script มี default values อยู่แล้ว
- ปกติใช้ `TELEGRAM_CHAT_ID` เพียง
- ระมัวเปลี่ยน token

---

## 💻 การใช้งาน

### รัน Manual (ทดสอบ)

```bash
# รัน script ด้วย manual
cd /home/kittisak/.openclaw/workspace/scripts
python3 fetch-innovation-news-mysql.py
```

**ผลลัพธ์:**

```
=== Starting innovation news fetch ===
🔄 Fetching from source 1/10: NIA
✅ NIA: Found 8 innovation articles
✅ Found 3 new innovation articles
✅ Sent: C-A-S-E Mobility 4 เทคโนโลยียานต์สมัยใหม่
=== Innovation news fetch completed ===
```

### ตั้ง Cron Job

```bash
# เปิด crontab
crontab -e
```

**เพิ่ม:**

```cron
# Innovation News Fetcher
# รันทุก 30 นาที (ทุกชั่วโมงที่ 00 และ 30)
0,30 * * * * cd /home/kittisak/.openclaw/workspace/scripts && /usr/bin/python3 fetch-innovation-news-mysql.py >> /home/kittisak/.openclaw/workspace/logs/innovation-news-fetch.log 2>&1
```

**บันทึก:**

```bash
# บันทึก crontab
crontab -l > /tmp/crontab-backup
```

---

## 📊 Database Schema

### Table: news_sources

| Column          | Type                | Description           |
| --------------- | ------------------- | --------------------- |
| id              | INT UNSIGNED PK     | Primary Key           |
| name            | VARCHAR(100) UNIQUE | Source name           |
| slug            | VARCHAR(100) UNIQUE | Source slug           |
| source_url      | VARCHAR(500)        | Source URL            |
| fetch_method    | ENUM                | 'rss', 'html', 'api'  |
| is_active       | TINYINT(1)          | Active status (0/1)   |
| last_fetched_at | DATETIME            | Last successful fetch |
| fetch_count     | INT UNSIGNED        | Total fetch attempts  |
| success_count   | INT UNSIGNED        | Successful fetches    |
| error_count     | INT UNSIGNED        | Failed fetches        |

### Table: innovation_news

| Column         | Type                 | Description                 |
| -------------- | -------------------- | --------------------------- |
| id             | INT UNSIGNED PK      | Primary Key                 |
| source_id      | INT UNSIGNED FK      | Reference to news_sources   |
| title          | VARCHAR(500)         | Article title               |
| summary        | TEXT                 | Article summary (800 chars) |
| link           | VARCHAR(1000) UNIQUE | Article URL                 |
| date_published | VARCHAR(100)         | Original publish date       |
| date_sent      | DATETIME             | Sent to Telegram time       |
| content_hash   | VARCHAR(32)          | MD5 hash for deduplication  |
| is_sent        | TINYINT(1)           | Was article sent?           |
| created_at     | DATETIME             | Creation time               |
| updated_at     | DATETIME             | Update time                 |

### Table: fetch_logs

| Column         | Type               | Description                             |
| -------------- | ------------------ | --------------------------------------- |
| id             | BIGINT UNSIGNED PK | Primary Key                             |
| source_id      | INT UNSIGNED FK    | Reference to news_sources               |
| articles_found | INT UNSIGNED       | Total articles found                    |
| articles_sent  | INT UNSIGNED       | Articles sent to Telegram               |
| new_articles   | INT UNSIGNED       | New articles (not in DB)                |
| status         | ENUM               | 'success', 'partial', 'failed', 'error' |
| error_message  | TEXT               | Error details                           |
| duration_ms    | INT UNSIGNED       | Fetch duration in ms                    |
| created_at     | DATETIME           | Log timestamp                           |

---

## 🔄 Stored Procedures

### save_article

บันทึกบทความลง database พร้อม check duplicate

**Parameters:**

- `p_source_slug` (VARCHAR 100) - Source slug (e.g., 'nstda')
- `p_title` (VARCHAR 500) - Article title
- `p_summary` (TEXT) - Article summary
- `p_link` (VARCHAR 1000) - Article URL
- `p_date_published` (VARCHAR 100) - Original publish date
- `p_content_hash` (VARCHAR 32) - MD5 hash

**Returns:**

- `p_article_id` (INT) - Article ID
- `p_is_new` (BOOLEAN) - True if new, False if updated

**วิธีใช้:**

```sql
CALL save_article(
  'nstda',
  'Test Article Title',
  'Test article summary...',
  'https://www.nstda.or.th/test',
  '2025-03-22',
  'abc123',
  @article_id,
  @is_new
);
```

---

### log_fetch_operation

บันทึก logs การ fetch และ update stats

**Parameters:**

- `p_source_slug` (VARCHAR 100) - Source slug
- `p_status` (ENUM) - 'success', 'partial', 'failed', 'error'
- `p_articles_found` (INT) - Total articles found
- `p_articles_sent` (INT) - Articles sent to Telegram
- `p_new_articles` (INT) - New articles
- `p_error_message` (TEXT) - Error details
- `p_duration_ms` (INT) - Fetch duration in ms

**วิธีใช้:**

```sql
CALL log_fetch_operation(
  'nstda',
  'success',
  10,
  1,
  1,
  NULL,
  2500
);
```

---

## 📈 Monitoring และ Debugging

### ดู Logs

```bash
# ดู logs ล่าสุด
tail -f /home/kittisak/.openclaw/workspace/logs/innovation-news-fetch.log
```

### ดู Database

```bash
# ดูบทความล่าสุด
mysql -u kittisak -p*${DB_PASS}* -D innovation_news -e "
SELECT id, title, source_id, date_sent
FROM innovation_news
ORDER BY date_sent DESC
LIMIT 10;
"

# ดู logs การ fetch ล่าสุด
mysql -u kittisak -p*${DB_PASS}* -D innovation_news -e "
SELECT * FROM fetch_logs
ORDER BY created_at DESC
LIMIT 10;
"

# ดูสถิติ sources
mysql -u kittisak -p*${DB_PASS}* -D innovation_news -e "
CALL get_source_statistics();
"
```

### ดู Views

```bash
# ดูบทความล่าสุด 7 วัน
mysql -u kittisak -p*${DB_PASS}* -D innovation_news -e "
SELECT * FROM v_latest_articles LIMIT 10;
"

# ดูบทความวันนี้
mysql -u kittisak -p*${DB_PASS}* -D innovation_news -e "
SELECT * FROM v_today_articles;
"

# ดู dashboard stats
mysql -u kittisak -p*${DB_PASS}* -D innovation_news -e "
CALL get_dashboard_stats();
"
```

---

## 🔧 Configuration

### แก้ไฟล์ Script (หากต้องการ)

แก้ configuration ที่ด้านบนของ script:

```python
# Database
DB_HOST = 'localhost'
DB_USER = 'kittisak'
DB_PASS = '*${DB_PASS}*'
DB_NAME = 'innovation_news'

# Telegram
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '${TELEGRAM_CHAT_ID}')

# Files
CACHE_FILE = "/home/kittisak/.openclaw/workspace/cache/innovation-news-cache.json"
LOG_FILE = "/home/kittisak/.openclaw/workspace/logs/innovation-news-fetch.log"
SOURCES_INDEX_FILE = "/home/kittisak/.openclaw/workspace/cache/innovation-sources-index.txt"
```

---

## 🐛 Troubleshooting

### ปัญหา: ModuleNotFoundError: No module named 'mysql'

**สาเหตุ:** ไม่ได้ติดตั้ง mysql-connector-python

**วิธีแก้:**

```bash
pip3 install mysql-connector-python
```

---

### ปัญหา: Access denied for user 'kittisak'@'localhost'

**สาเหตุ:** Password ผิด หรือ user ไม่มี permission

**วิธีแก้:**

```bash
# Grant permissions
mysql -u root -p
GRANT ALL PRIVILEGES ON innovation_news.* TO 'kittisak'@'localhost';
FLUSH PRIVILEGES;
```

---

### ปัญหา: Stored procedure not found

**สาเหตุ:** ไม่ได้รัน database setup script

**วิธีแก้:**

```bash
cd /home/kittisak/.openclaw/workspace/scripts
mysql -u kittisak -p*${DB_PASS}* < setup-innovation-db.sql
```

---

### ปัญหา: No articles found

**สาเหตุ:** Keywords ไม่ match หรือ source เปลี่ยน pattern

**วิธีแก้:**

```bash
# ดู logs
tail -50 /home/kittisak/.openclaw/workspace/logs/innovation-news-fetch.log

# รัน script manual เพื่อ debug
python3 fetch-innovation-news-mysql.py
```

---

### ปัญหา: Telegram not sending

**สาเหตุ:** TELEGRAM_TOKEN ผิด หรือ OpenClaw CLI error

**วิธีแก้:**

```bash
# ทดสอบ OpenClaw CLI
openclaw message send --channel telegram --target ${TELEGRAM_CHAT_ID} --message "Test message"

# ตรวจสอบ TELEGRAM_TOKEN
# (ถ้าเปลี่ยน token ใหม่ ต้อง update ใน crontab)
```

---

## 📝 การต่อยอดและบำรุง

### Weekly Maintenance

```bash
# Cleanup old articles (เก่ากว่า 6 เดือน)
mysql -u kittisak -p*${DB_PASS}* -D innovation_news -e "
CALL cleanup_old_articles(180);
"

# ดู stats
mysql -u kittisak -p*${DB_PASS}* -D innovation_news -e "
SELECT
  'Total Articles' AS metric,
  COUNT(*) AS value
FROM innovation_news;
"
```

---

### Monthly Maintenance

```bash
# Backup database
mysqldump -u kittisak -p*${DB_PASS}* innovation_news > innovation_news_backup_$(date +%Y%m%d).sql

# Optimize tables
mysql -u kittisak -p*${DB_PASS}* -D innovation_news -e "
OPTIMIZE TABLE innovation_news;
OPTIMIZE TABLE news_sources;
OPTIMIZE TABLE fetch_logs;
"
```

---

## 🎯 การใช้งานกับหน้าเว็บ / Application

### Query Examples

**ดูบทความล่าสุด:**

```sql
SELECT
  n.title,
  n.link,
  s.name AS source,
  n.date_published,
  n.date_sent,
  LEFT(n.summary, 200) AS summary_preview
FROM innovation_news n
INNER JOIN news_sources s ON n.source_id = s.id
ORDER BY n.date_sent DESC
LIMIT 10;
```

**ดูตาม source:**

```sql
SELECT
  n.title,
  n.link,
  n.date_published,
  n.date_sent
FROM innovation_news n
INNER JOIN news_sources s ON n.source_id = s.id
WHERE s.slug = 'nstda'
ORDER BY n.date_sent DESC
LIMIT 10;
```

**ค้นหา:**

```sql
SELECT
  n.title,
  n.link,
  n.date_published,
  MATCH(n.title, n.summary) AGAINST ('AI' IN BOOLEAN MODE) AS score
FROM innovation_news n
WHERE MATCH(n.title, n.summary) AGAINST ('AI' IN BOOLEAN MODE)
ORDER BY score DESC
LIMIT 10;
```

---

## 📚 References

- **Database Documentation:** `/home/kittisak/.openclaw/workspace/docs/innovation-database-setup.md`
- **Stored Procedures:** `/home/kittisak/.openclaw/workspace/docs/stored-procedures.md`
- **Old Version:** `fetch-innovation-news.py` (cache-based, no database)

---

## 🔄 Version History

### v2.0.0 (2026-03-22)

- ✅ Add MySQL database integration
- ✅ Use stored procedures for CRUD operations
- ✅ Replace cache file with database deduplication
- ✅ Add fetch logs and source statistics
- ✅ Fix NSTDA pattern (HTML scraping)

### v1.0.0 (2026-03-20)

- ✅ Initial version with 10 sources
- ✅ Cache file-based deduplication
- ✅ Telegram notifications
- ✅ Source rotation

---

## 💡 Tips และ Best Practices

1. **Monitoring:** ตรวจสอบ logs ประจำ วัน
2. **Maintenance:** รัน cleanup_old_articles ทุกสัปดาห์
3. **Backup:** Backup database ทุกเดือน
4. **Performance:** ใช้ views แทน queries ที่ซับซ้อน
5. **Security:** อย่า hardcode passwords ใน scripts

---

## 🆘 Support

หากพบปัญหาหรือมีข้อสงสัย:

1. ดู logs ก่อน
2. ตรวจสอบ connection database
3. ตรวจสอบ stored procedures
4. ติดต่อผู้ดูแลระบบ (คุณหนึ่ง)

---

**Status:** ✅ Production Ready
