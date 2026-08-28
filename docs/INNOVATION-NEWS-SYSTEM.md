# Innovation News System - ภาพรวมระบบ

## 📋 รายละเอียด

ระบบจัดการและแจ้งเตือนข่าวนวัตกรรมและเทคโนโลยีสำหรับมหาวิทยาลัยสงขลานครินทร์ ทำงานอัตโนมัติโดยดึงข่าวจากแหล่งข้อมูลหลายแห่ง และส่งการแจ้งเตือนผ่าน Telegram พร้อมทั้ง sync ไปยัง WordPress

---

## 🏗️ โครงสร้างระบบ

```
innovation-news-system/
├── scripts/
│   ├── fetch-innovation-news-mysql.py    # สคริปต์หลัก (ดึงข่าว, บันทึก DB, ส่ง Telegram)
│   ├── wordpress_integration.py           # โมดูล Sync ไป WordPress
│   ├── run-fetch-innovation-news.sh       # Wrapper สำหรับ cron job
│   ├── manage-wordpress-posts.sh          # จัดการโพสต์ WordPress
│   └── update-wp-env.sh                   # retired: ห้ามใช้แก้ credentials
├── logs/
│   ├── innovation-news-fetch.log          # Log หลัก
│   └── cron-innovation-news-mysql.log     # Log จาก cron
├── cache/
│   ├── innovation-news-cache.json         # Cache ข่าว
│   └── innovation-sources-index.txt       # Index แหล่งข้อมูลปัจจุบัน
├── .env                                   # Environment Variables
└── docs/
    └── INNOVATION-NEWS-SYSTEM.md          # เอกสารนี้
```

---

## 🔄 ขั้นตอนการทำงาน (Workflow)

### 1. ดึงข่าว (Fetching)
- ระบบดึงข่าวจาก 10 แหล่งข้อมูล (Round-robin):
  - NIA (สำนักงานนวัตกรรมแห่งชาติ)
  - ETDA (สำนักงานพัฒนาธุรกรรมทางอิเล็กทรอนิกส์)
  - Techsauce
  - NSTDA (สำนักงานวิจัยและนวัตกรรมทางวิทยาศาสตร์และเทคโนโลยี)
  - RYT9
  - iT24Hrs
  - TechTalkThai
  - NECTEC (ศูนย์เทคโนโลยีอิเล็กทรอนิกส์และคอมพิวเตอร์แห่งชาติ)
  - NRIIS (สำนักงานการวิจัยแห่งชาติ)
  - Innomatter

### 2. กรองข่าว (Filtering)
- ตรวจสอบด้วยคำสำคัญ (Keywords) ทั้งภาษาไทยและอังกฤษ:
  - AI, Machine Learning, Digital Transformation, Innovation, EdTech
  - ปัญญาประดิษฐ์, นวัตกรรม, สตาร์ทอัพ, ดิจิทัล, เอ็ดเทค ฯลฯ
- ตรวจสอบวันที่ (ไม่เกิน 1 ปี)
- ตรวจสอบความซ้ำ (Duplicate detection) ด้วย content hash

### 3. บันทึกข่าว (Storage)
- บันทึกลง MySQL Database (`innovation_news`) ผ่าน Stored Procedures
- สร้าง **ประโยชน์ต่อองค์กร** อัตโนมัติจากการวิเคราะห์คำสำคัญ (15 หมวดหมู่)

### 4. ส่งการแจ้งเตือน (Notification)
- ส่งข้อความไปยัง Telegram
- รูปแบบข้อความ:
  ```
  📌 Innovation Daily Update

  หัวข้อ: [title]
  เผยแพร่เมื่อ: [วันที่ไทย]
  แหล่งข้อมูล: [source]

  รายละเอียดโดยสรุป: [ไม่เกิน 800 ตัวอักษร]...

  ประโยชน์ต่อองค์กร:
  💡 [ประโยชน์ที่ 1]
  🚀 [ประโยชน์ที่ 2]
  📊 [ประโยชน์ที่ 3]

  อ่านต่อ: [link]
  ```

### 5. Sync ไป WordPress (Optional)
- สร้างโพสต์ประเภท `innovation-tip` ใน WordPress
- ใช้ PTB Custom Fields:
  - `ptb_innovation_tip_content`: เนื้อหารวม (สรุป + ประโยชน์ + ที่มา)
  - `ptb_innovation_tip_url`: ลิงก์ต้นฉบับ
  - `ptb_innovation_tip_video`: วิดีโอ (ว่างเปล่า)
- ตรวจสอบความซ้ำก่อนบันทึก

---

## 🗄️ โครงสร้าง Database

### Database: `innovation_news`

#### Stored Procedures

**1. `save_article`** - บันทึกหรืออัปเดตบทความ
```sql
CALL save_article(
    source_slug,      -- VARCHAR(50)
    title,            -- TEXT
    summary,          -- TEXT
    link,             -- TEXT
    date,             -- DATE
    content_hash,     -- VARCHAR(32)
    @article_id,      -- OUT: INT
    @is_new           -- OUT: BOOLEAN
);
```

**2. `log_fetch_operation`** - บันทึกประวัติการดึงข่าว
```sql
CALL log_fetch_operation(
    source_slug,      -- VARCHAR(50)
    status,           -- VARCHAR(20)
    articles_found,   -- INT
    articles_sent,    -- INT
    new_articles,     -- INT
    error_message,    -- TEXT (NULL ได้)
    duration_ms       -- INT
);
```

#### Tables (推测จาก Stored Procedures)

**`innovation_news`** - เก็บบทความ
- `id` (INT, PK)
- `source_slug` (VARCHAR(50))
- `title` (TEXT)
- `summary` (TEXT)
- `link` (TEXT)
- `date` (DATE)
- `content_hash` (VARCHAR(32), UNIQUE)
- `created_at` (DATETIME)
- `updated_at` (DATETIME)

**`fetch_logs`** - ประวัติการดึงข่าว
- `id` (INT, PK)
- `source_slug` (VARCHAR(50))
- `status` (VARCHAR(20))
- `articles_found` (INT)
- `articles_sent` (INT)
- `new_articles` (INT)
- `error_message` (TEXT)
- `duration_ms` (INT)
- `created_at` (DATETIME)

---

## 🔧 Environment Variables (`.env`)

```bash
# Telegram
TELEGRAM_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID}

# WordPress Integration
WP_API_URL=https://innovation.oas.psu.ac.th/wp-json
WP_USERNAME=openclawbot
WP_APP_PASSWORD=your_app_password
```

---

## 🤖 คุณสมบัติการวิเคราะห์ประโยชน์ต่อองค์กร

ระบบจะวิเคราะห์หัวข้อและสรุปข่าว เพื่อสร้าง "ประโยชน์ต่อองค์กร" อัตโนมัติ จาก 15 หมวดหมู่:

| หมวดหมู่ | คำสำคัญตัวอย่าง |
|------------|-------------------|
| ความสามารถในการแข่งขัน | competitiv, competitive, แข่งขัน, ได้เปรียบ |
| การลดต้นทุนและเพิ่มประสิทธิภาพ | cost, saving, ลดต้นทุน, ประหยัด, ประสิทธิภาพ |
| ดิจิทัลทรานส์ฟอร์เมชัน | digital transformation, ดิจิทัล, ดิจิทัลทรานส์ฟอร์เมชัน |
| การพัฒนาทักษะและการเรียนรู้ | skill, training, education, ทักษะ, ฝึกอบรม, edtech |
| การใช้งาน AI และเทคโนโลยีขั้นสูง | ai, ml, automation, chatbot, ปัญญาประดิษฐ์, เอไอ |
| ความปลอดภัยและความเป็นส่วนตัว | security, privacy, cyber, ความปลอดภัย, ไซเบอร์ |
| การสร้างนวัตกรรมและการเปลี่ยนแปลง | innovation, disruption, นวัตกรรม, เปลี่ยนแปลง |
| การปรับตัวต่อเทรนด์และการเปลี่ยนแปลงตลาด | trend, market, future, เทรนด์, ตลาด |
| การจัดการข้อมูลและวิเคราะห์ | data, analytics, big data, ข้อมูล, วิเคราะห์ |
| การสร้างประสบการณ์ลูกค้าและบริการ | customer, service, experience, ลูกค้า, บริการ |
| การเชื่อมต่อและการทำงานร่วมกัน | collaboration, connect, เชื่อมต่อ, ทำงานร่วมกัน |
| การประยุกต์ใช้ในภาคอุตสาหกรรม | industry, health, finance, อุตสาหกรรม, สุขภาพ |
| ความยั่งยืนและผลกระทบสิ่งแวดล้อม | sustainability, esg, ยั่งยืน, สิ่งแวดล้อม |
| การสนับสนุนนโยบายและกฎระเบียบ | regulation, policy, นโยบาย, กฎระเบียบ |
| การขยายตลาดและโอกาสทางธุรกิจ | business, opportunity, ธุรกิจ, โอกาส |

---

## ⏰ การตั้งเวลา (Scheduling)

ระบบทำงานผ่าน cron job:
- **Script**: `/home/kittisak/.openclaw/workspace/scripts/run-fetch-innovation-news.sh`
- **Cron Schedule**: (ต้องตรวจสอบจาก crontab)
- **Log**: `/home/kittisak/.openclaw/workspace/logs/cron-innovation-news-mysql.log`

---

## 📊 การตรวจสอบและดู Logs

### Log Files

```
logs/
├── innovation-news-fetch.log          # Log หลักจาก Python script
└── cron-innovation-news-mysql.log     # Log จาก cron job
```

### ดู Log ล่าสุด
```bash
tail -f /home/kittisak/.openclaw/workspace/logs/innovation-news-fetch.log
```

---

## 🔍 การจัดการ WordPress Posts

### ตรวจสอบโพสต์
```bash
/home/kittisak/.openclaw/workspace/scripts/manage-wordpress-posts.sh check
```

### ลบโพสต์
```bash
/home/kittisak/.openclaw/workspace/scripts/manage-wordpress-posts.sh delete
```

### ค้นหาโพสต์ทดสอบ
```bash
/home/kittisak/.openclaw/workspace/scripts/manage-wordpress-posts.sh search
```

### อัปเดต WordPress Credentials

สคริปต์เดิมถูก retire เพราะสร้างสำเนา credential แบบ plaintext และแทนค่าด้วย `sed` อย่างไม่ปลอดภัย ให้แก้ canonical root `.env` ผ่านขั้นตอนจัดการ secret ที่องค์กรอนุมัติ โดยตั้ง permission เป็น `600` หรือ `400` และห้ามพิมพ์ค่าลับลง log

---

## 🚀 การใช้งาน

### รันแบบ Manual (ทดสอบ)
```bash
cd /home/kittisak/.openclaw/workspace/scripts
python3 fetch-innovation-news-mysql.py
```

### รันผ่าน Cron
```bash
/home/kittisak/.openclaw/workspace/scripts/run-fetch-innovation-news.sh
```

---

## 📦 แหล่งข้อมูลข่าว (News Sources)

| # | แหล่งข้อมูล | URL | วิธีการดึง |
|---|---------------|-----|---------------|
| 1 | NIA | https://www.nia.or.th/article/blog.html | Web Scraping (Regex) |
| 2 | ETDA | RSS Feed | XML Parser |
| 3 | Techsauce | RSS Feed | XML Parser |
| 4 | NSTDA | REST API | JSON |
| 5 | RYT9 | RSS Feed | XML Parser |
| 6 | iT24Hrs | Web Scraping (Regex) | HTML Parser |
| 7 | TechTalkThai | RSS Feed | XML Parser |
| 8 | NECTEC | Web Scraping (Regex) | HTML Parser |
| 9 | NRIIS | RSS Feed | XML Parser |
| 10 | Innomatter | RSS Feed | XML Parser |

---

## 🔒 ความปลอดภัย

- ✅ Database credentials ถูก hardcode ใน script (ควรย้ายไป .env)
- ✅ WordPress credentials เก็บใน .env
- ✅ Telegram token เก็บใน .env
- ⚠️ ควรพิจารณาใช้ environment variables สำหรับ database credentials

---

## 🛠️ การบำรุงรักษา

### อัปเดต Keywords
แก้ไข `INNOVATION_KEYWORDS` และ `INNOVATION_KEYWORDS_TH` ใน `fetch-innovation-news-mysql.py`

### เพิ่มแหล่งข้อมูลใหม่
1. เพิ่ม function fetch_* ใหม่
2. เพิ่ม tuple ใหม่ใน `SOURCES`
3. เพิ่ม mapping ใน `SOURCE_SLUGS`

### อัปเดต WordPress Integration
แก้ไข `wordpress_integration.py` หากต้องการเปลี่ยน Custom Fields

---

## 📝 ประวัติการอัปเดต

| วันที่ | การเปลี่ยนแปลง |
|---------|-------------------|
| 2026-03-25 | เพิ่มระบบสร้าง "ประโยชน์ต่อองค์กร" อัตโนมัติ (15 หมวดหมู่) |
| 2026-03-25 | แก้ไขฟอร์แมตข้อความ Telegram ใหม่ (สรุป 800 ตัวอักษร + ประโยชน์ต่อองค์กร) |
| 2026-03-24 | แก้ไข .env loading สำหรับ WordPress Sync |
| - | ระบบ sync ไป WordPress ด้วย PTB Custom Fields |

---

## 📞 การติดต่อ

- **ผู้ดูแล**: คุณหนึ่ง
- **ทีม**: สำนักวิทยบริการ มหาวิทยาลัยสงขลานครินทร์
- **วันที่สร้างเอกสาร**: 2026-03-25

---

_เอกสารนี้สร้างขึ้นเมื่อ: 2026-03-25 โดย น้องกุ้ง 🦐_
