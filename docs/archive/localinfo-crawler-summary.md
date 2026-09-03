# รายงานสรุปโปรเจกส์ localinfo-crawler
**วันที่:** 21 มีนาคม 2569
**สถานะ:** พบและวิเคราะห์โครงสร้างเสร็จสมบูรณ์

---

## 📊 ภาพรวมโปรเจกส์

### ชื่อโปรเจกส์
**localinfo-crawler** - ระบบดึงข้อมูลเนื้อหาและอาหารพื้นถิ่นจากหลายแหล่ง

### วัตถุประสงค์
- รวบรวมข้อมูลอาหารพื้นถิ่นจากหลายแหล่ง (WordPress, JSON, CSV, API)
- เก็บข้อมูลลง centralized database
- จัดหมวดหมู่อย่างเป็นระบบ (unified categories)
- ให้ admin review ก่อนนำไปใช้งานจริง

### สถานะปัจจุบัน
- ✅ โครงสร้างครบถ้วน
- ⚠️ Cron jobs มีปัญหา MODULE_NOT_FOUND
- ✅ มี logs แสดงว่าเคยทำงาน
- ❌ ไม่มี processes ทำงานอยู่ตอนนี้

---

## 🏗️ สถาปัตยกรรม

### Architecture v2.0: Centralized Database

```
┌─────────────────────────────────────────────────────┐
│              CENTRALIZED DATABASE                │
│              (pattani_food / localinfo)       │
└─────────────────────────────────────────────────────┘
         ↑               ↑               ↑               ↑
    WordPress      Local JSON       Local CSV          API
   (Pattani)     (Songkhla)      (Nakhon)        (Others)
```

### Core Tables

| Table | หน้าที่ |
|-------|----------|
| **food_items** | เก็บข้อมูลหลักทุกรายการ |
| **food_images** | เก็บรูปภาพหลายรูปต่อรายการ |
| **food_categories** | Mapping ระหว่างรายการและหมวดหมู่ |
| **unified_categories** | หมวดหมู่ร่วมทุก source |
| **data_sources** | ตั้งค่า sources (ตารางมาตร) |
| **sync_log** | Log การ sync แต่ละครั้ง |

### Key Concept: 2-Phase Categorization

#### 🔴 Phase 1: Sync (Crawler - Automatic)
- **เกิดขึ้น:** ทุกวันจันทร์ 02:00 น.
- **ทำอะไร:**
  1. ดึงข้อมูลจาก source
  2. บันทึก `wp_category` (หมวดหมู่เดิม)
  3. ตั้ง `main_category` = `wp_category`
  4. ตั้ง `review_status` = "Review"
  5. ส่งแจ้ง Telegram

```javascript
{
  source_type: 'wordpress',
  source_id: '879',
  source_name: 'Pattani Heritage City',
  title: 'ข้าวยำ',
  original_category: 'อาหารคาว',
  unified_category_id: NULL,        // ยังไม่กำหนด
  unified_category_name: NULL,     // ยังไม่กำหนด
  review_status: 'Review'
}
```

#### 🟢 Phase 2: Admin Review (Human - Manual)
- **เกิดขึ้น:** เมื่อ admin มีเวลา
- **ทำอะไร:**
  1. ดูรายการที่รอตรวจสอบ
  2. ✏️ แก้ไข `main_category` (ถ้าต้องการ)
  3. ✏️ ตั้ง `cuisine_type`, `difficulty_level`
  4. ✅ เปลี่ยน `review_status` เป็น "Approved" หรือ "Disabled"

```javascript
{
  source_type: 'wordpress',
  source_id: '879',
  source_name: 'Pattani Heritage City',
  title: 'ข้าวยำ',
  original_category: 'อาหารคาว',       // เก็บไว้ (audit trail)
  unified_category_id: 11,              // อาหารคาว (admin กำหนด)
  unified_category_name: 'อาหารคาว',   // Admin กำหนด
  review_status: 'Approved'
}
```

---

## 🗂️ โครงสร้าง Unified Categories

```
Unified Categories (Centralized, Cross-Source)
│
├─ 1. อาหารพื้นบ้าน
│  ├─ 11. อาหารคาว
│  ├─ 12. อาหารหวาน
│  └─ 13. อาหารแต่ที่ขาย
│
├─ 2. ร้านอาหาร
│  ├─ 21. ร้านอาหารแบบๆ
│  ├─ 22. ร้านอาหารตามสั่ง
│  └─ 23. ร้านก๋วยเตี๋ยว
│
├─ 3. ขนมของว่าง
│  ├─ 31. ขนมไทย
│  ├─ 32. ขนมต้นถิ่น
│  └─ 33. ขนมของว่างทั่วไป
│
├─ 4. เครื่องดื่ม
│  └─ ...
│
└─ 5. สินค้าพื้นเมือง
   └─ ...
```

---

## 🔧 Crawlers ที่มีทั้งหมด

| # | Crawler | Target | Size | วิธีดึง | สถานะ |
|---|---------|--------|------|----------|--------|
| 1 | **crawler_esanpedia.js** | Esanpedia (encyclopedia) | 35KB | Unknown | ⚠️ ไม่ทราบ |
| 2 | **crawler_walailak.js** | Walailak University | 27KB | Unknown | ⚠️ ไม่ทราบ |
| 3 | **crawler_pattani_heritage.js** | Pattani Heritage (Food) | 27KB | WordPress API | ⚠️ ไม่ทราบ |
| 4 | **crawler_westweb.js** | West Web | 28KB | Unknown | ⚠️ ไม่ทราบ |
| 5 | **crawler_sansai.js** | Sansai | 20KB | Unknown | ⚠️ ไม่ทราบ |

**รวม:** 5 crawlers ทั้งหมดเป็น JavaScript/Node.js based

---

## 📦 NPM Scripts

### สคริปต์ sync ทั้งหมด

```json
{
  "pattani:sync": "node crawler_pattani_heritage.js --full",
  "sansai:sync": "node crawler_sansai.js --full",
  "westweb:sync": "node crawler_westweb.js --full",
  "esanpedia:sync": "node crawler_esanpedia.js --full",
  "walailak:sync": "node crawler_walailak.js --full",
  "sync:all": "echo 'Syncing all sources...' && npm run pattani:sync && npm run sansai:sync && npm run westweb:sync && npm run esanpedia:sync && npm run walailak:sync"
}
```

### วิธีใช้

```bash
# Sync ทั้งหมด
npm run sync:all

# Sync แต่ละ source
npm run pattani:sync      # Pattani Heritage
npm run sansai:sync        # Sansai
npm run westweb:sync       # West Web
npm run esanpedia:sync     # Esanpedia
npm run walailak:sync      # Walailak University
```

---

## 🗄️ Database Schema

### food_items (Main Table)

| Column | Type | Purpose |
|--------|------|---------|
| `id` | BIGINT (PK) | Primary Key |
| `source_type` | VARCHAR | ประเภท source (wordpress, json, csv, api) |
| `source_id` | VARCHAR | ID จาก source เดิม |
| `source_name` | VARCHAR | ชื่อ source |
| `original_category` | VARCHAR | หมวดหมู่เดิม |
| `unified_category_id` | INT | หมวดหมู่ร่วม |
| `unified_category_name` | VARCHAR | ชื่อหมวดหมู่ร่วม |
| `review_status` | ENUM | Review/Approved/Disabled |
| `title` | VARCHAR(500) | ชื่อรายการ |
| `summary` | TEXT | สรุป |
| `content` | LONGTEXT | เนื้อหา |
| `link` | VARCHAR(1000) | URL ของรายการ |
| `date_published` | DATETIME | วันที่เผยแพร่ |
| `date_synced` | DATETIME | วันที่ sync |
| `created_at` | DATETIME | วันที่สร้าง |
| `updated_at` | DATETIME | วันที่อัปเดต |

### food_images

| Column | Type | Purpose |
|--------|------|---------|
| `id` | BIGINT (PK) | Primary Key |
| `food_item_id` | BIGINT (FK) | Reference to food_items |
| `image_url` | VARCHAR(1000) | URL ของรูป |
| `caption` | VARCHAR(500) | คำบรรยายรูป |

### unified_categories

| Column | Type | Purpose |
|--------|------|---------|
| `id` | INT (PK) | Primary Key |
| `name` | VARCHAR(100) | ชื่อหมวดหมู่ |
| `parent_id` | INT | Parent category |
| `description` | TEXT | คำอธิบาย |

---

## 🔄 Admin Review Workflow

```
┌─────────────────────────────────────────────────────────┐
│ รอบที่ 1: Sync (Automatic - ทุกวันจันทร์ 02:00)    │
└─────────────────────────────────────────────────────────┘
                            ↓
              ✅ ดึงข้อมูลจาก WordPress
              ✅ บันทึก wp_category (หมวดหมู่เดิม)
              ✅ ตั้ง main_category = wp_category
              ✅ ตั้ง review_status = "Review"
              ✅ ส่งแจ้ง Telegram
                            ↓
┌─────────────────────────────────────────────────────────┐
│ รอบที่ 2: Admin Review (Human - เมื่อมีเวลา)      │
└─────────────────────────────────────────────────────────┘
                            ↓
              👀 ดูรายการที่รอตรวจสอบ
              ✏️ แก้ไข main_category (ถ้าต้องการ)
              ✏️ ตั้ง cuisine_type, difficulty_level
              ✏️ เปลี่ยน review_status เป็น "Approved"
                    หรือ "Disabled"
                            ↓
              🎉 รายการพร้อมใช้งาน
```

### เครื่องมือ Admin Review

```bash
# ดูรายการที่รอตรวจสอบ
node admin-review.js --list-review

# ดูรายละเอียดรายการ
node admin-review.js --show 1

# อนุมัติรายการ
node admin-review.js --approve 1

# ปิดใช้งานรายการ (พร้อมเหตุผล)
node admin-review.js --disable 1 "Duplicate content"

# ตั้งค่าหมวดหมู่หลัก
node admin-review.js --set-cat 1 "อาหารคาว"
```

---

## 🐛 ปัญหาที่พบ

### 1. Cron Jobs MODULE_NOT_FOUND

**Error:**
```
Error: Cannot find module '/home/kittisak/.openclaw/workspace/localinfo_crawler/crawler-v4.js'
Error: Cannot find module '/home/kittisak/.openclaw/workspace/localinfo_crawler/crawler-westweb-v2.js'
```

**สาเหตุ:**
- Cron jobs อ้างถึงไฟล์ที่ไม่มีอยู่
- ไฟล์ถูกเปลี่ยนชื่อ/ลบแล้ว แต่ cron ยังไม่ได้อัปเดต

**สถานะปัจจุบัน:**
| ไฟล์ที่ cron อ้าง | ไฟล์จริง | สถานะ |
|-------------------|-----------|--------|
| `crawler-v4.js` | ❌ ไม่มี | Error |
| `crawler-westweb-v2.js` | ❌ ไม่มี | Error |
| `crawler_westweb.js` | ✅ มี | OK |

### 2. ไม่พบ Cron Jobs

**ผลการตรวจสอบ:**
- ❌ ไม่มีใน user crontab
- ❌ ไม่มีใน /etc/cron.d/
- ❌ ไม่มี systemd services
- ❌ ไม่มี processes ทำงานอยู่

**สรุป:** ไม่พบตำแหน่ง cron jobs ที่ตั้งไว้

### 3. Log Files แสดงว่าเคยทำงาน

**Log files:**
- `cron.log` - Main log
- `cron-pattani.log` - Pattani crawler log
- `cron-sansai.log` - Sansai crawler log
- `cron-westweb.log` - West web crawler log
- `cron-walailak.log` - Walailak crawler log

**สรุป:** ระบบเคยทำงานแต่ตอนนี้หยุดชะงั้น

---

## 📊 สถิติจาก Logs

### Log Entries (ตัวอย่างจากครั้งล่าสุด)

| เวลา | Source | สถานะ | รายละเอียด |
|--------|--------|--------|-------------|
| Mar 20 02:00 | Westweb | ❌ Error | Cannot find module crawler-westweb-v2.js |
| Mar 21 02:00 | Sansai | ❌ Error | Cannot find module crawler-v4.js |
| Mar 21 02:10 | Sansai | ❌ Error | Setup script failed |

**หมายเหตุ:**
- Cron พยายรันทุกวันจันทร์ 02:00 น.
- แต่ไฟล์ที่รันไม่ตรงกับชื่อจริง
- ทำให้ทุกครั้ง fail ด้วย MODULE_NOT_FOUND

---

## 💡 แนวทางแก้ไข

### 1. แก้ไข Cron Jobs

**วิธีที่ 1: ใช้ NPM Scripts**
```bash
# แก้ไข crontab
crontab -e

# เพิ่มบรรทัด (sync ทุก 6 ชั่วโมง)
0 */6 * * * cd /home/kittisak/.openclaw/workspace/localinfo_crawler && npm run sync:all >> /home/kittisak/.openclaw/workspace/localinfo_crawler/cron.log 2>&1
```

**วิธีที่ 2: รันแต่ละ crawler**
```bash
# Pattani - ทุกวันจันทร์ 02:00
0 2 * * 1 cd /home/kittisak/.openclaw/workspace/localinfo_crawler && npm run pattani:sync >> /home/kittisak/.openclaw/workspace/localinfo_crawler/cron-pattani.log 2>&1

# Sansai - ทุกวันจันทร์ 04:00
0 4 * * 1 cd /home/kittisak/.openclaw/workspace/localinfo_crawler && npm run sansai:sync >> /home/kittisak/.openclaw/workspace/localinfo_crawler/cron-sansai.log 2>&1

# Westweb - ทุกวันจันทร์ 06:00
0 6 * * 1 cd /home/kittisak/.openclaw/workspace/localinfo_crawler && npm run westweb:sync >> /home/kittisak/.openclaw/workspace/localinfo_crawler/cron-westweb.log 2>&1
```

### 2. ตรวจสอบไฟล์ที่มี

```bash
# ตรวจสอบไฟล์ทั้งหมด
ls -la /home/kittisak/.openclaw/workspace/localinfo_crawler/*.js

# ตรวจสอบว่าไฟล์ไหนเป็น active
find . -name "crawler*.js" -type f
```

### 3. ทดสอบรัน manual

```bash
# ทดสอบรันแต่ละ crawler
cd /home/kittisak/.openclaw/workspace/localinfo_crawler

node crawler_pattani_heritage.js --full
node crawler_sansai.js --full
node crawler_westweb.js --full
node crawler_esanpedia.js --full
node crawler_walailak.js --full
```

### 4. ตรวจสอบ Database Connection

```bash
# ตรวจสอบว่า MySQL ทำงานอยู่
systemctl status mysql

# เชื่อมต่อ database
mysql -u root -p

# ดู databases
SHOW DATABASES;

# ดู tables
USE pattani_food;
SHOW TABLES;

# ดู records
SELECT COUNT(*) FROM food_items;
```

---

## 📝 Dependencies

### package.json

```json
{
  "name": "localinfo-crawler",
  "version": "2.0.0",
  "dependencies": {
    "dotenv": "^17.3.1",
    "mysql2": "^3.6.5",
    "node_modules": "..."
  },
  "scripts": {
    "pattani:sync": "node crawler_pattani_heritage.js --full",
    "sansai:sync": "node crawler_sansai.js --full",
    "westweb:sync": "node crawler_westweb.js --full",
    "esanpedia:sync": "node crawler_esanpedia.js --full",
    "walailak:sync": "node crawler_walailak.js --full",
    "sync:all": "..."
  }
}
```

### ติดตั้ง Dependencies

```bash
cd /home/kittisak/.openclaw/workspace/localinfo_crawler
npm install
```

---

## 🔧 Configuration

### Environment Variables (.env)

```bash
DB_HOST=localhost
DB_USER=root
DB_PASS=your_password
DB_NAME=pattani_food
TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID}
```

### ค่าใน Crawler

```javascript
const CONFIG = {
  wpApi: {
    baseUrl: 'https://pattaniheritagecity.psu.ac.th/wp-json/wp/v2',
    postType: 'food',
    categories: [48, 49],  // 48=อาหารคาว, 49=อาหารหวาน
    defaultLat: 6.8683,    // Pattani PSU lat
    defaultLon: 101.2500    // Pattani PSU lon
  },
  db: {
    host: process.env.DB_HOST || 'localhost',
    user: process.env.DB_USER || 'root',
    password: process.env.DB_PASS || '',
    database: process.env.DB_NAME || 'pattani_food'
  }
};
```

---

## 🚀 การติดตั้ง

### วิธีแรก: ใช้ Install Script

```bash
cd /home/kittisak/.openclaw/workspace/localinfo_crawler
./install.sh
```

Script จะทำ:
- ✅ ติดตั้ง npm dependencies
- ✅ สร้าง database และ tables
- ✅ ตั้งค่า environment variables
- ✅ ตั้ง cron job (รันทุกวันจันทร์ 02:00)
- ✅ ทดสอบระบบ (dry-run)

### วิธีที่สอง: ติดตั้งแบบ manual

```bash
# 1. ติดตั้ง dependencies
cd /home/kittisak/.openclaw/workspace/localinfo_crawler
npm install

# 2. สร้างฐานข้อมูล
mysql -u root -p < schema.sql

# 3. ตั้งค่า Environment Variables
cp .env.example .env
# แก้ไข .env ด้วยค่าจริง

# 4. ทดสอบรัน
npm run sync:all
```

---

## 📊 การใช้งาน

### Query Examples

**1. ดูทุกรายการ**
```sql
SELECT id, title, original_category, unified_category_name, review_status
FROM food_items
ORDER BY created_at DESC;
```

**2. ดูรายการที่รอตรวจสอบ**
```sql
SELECT id, title, original_category, unified_category_name, sync_date
FROM food_items
WHERE review_status = 'Review'
ORDER BY created_at DESC;
```

**3. ดูรายการที่อนุมัติแล้ว**
```sql
SELECT id, title, unified_category_name, source_name
FROM food_items
WHERE review_status = 'Approved'
ORDER BY unified_category_name, title;
```

**4. สถิติตามหมวดหมู่**
```sql
SELECT unified_category_name, COUNT(*) as count
FROM food_items
WHERE review_status = 'Approved'
GROUP BY unified_category_name
ORDER BY count DESC;
```

---

## 📋 สรุปปัญหาและแนวทางแก้ไข

| ปัญหา | สาเหตุ | แนวทางแก้ไข |
|---------|--------|--------------|
| Cron MODULE_NOT_FOUND | ไฟล์ที่ cron อ้างไม่ตรงกับชื่อจริง | อัปเดต cron paths ให้ใช้ npm scripts |
| ไม่พบ cron jobs | Cron ถูกลบ/ย้าย | สร้าง cron jobs ใหม่ |
| Processes ไม่ทำงาน | Cron ไม่ทำงาน | แก้ cron และ test ใหม่ |
| Log files มี errors | MODULE_NOT_FOUND | แก้ชื่อไฟล์ใน cron |

---

## 🎯 ขั้นตอนถัดไป

### Short Term (ทันที)
1. ✅ แก้ cron jobs ให้ใช้ npm scripts
2. ✅ ทดสอบรันแต่ละ crawler
3. ✅ ตรวจสอบ database connection
4. ✅ ตรวจสอบว่าทุก source ทำงานได้

### Medium Term (1-2 สัปดาห์)
1. ปรับปรุง crawler ที่ทำงานไม่ได้
2. เพิ่ม error handling ที่ดีกว่า
3. พัฒนา monitoring system
4. เพิ่ม retry logic

### Long Term (1 เดือน+)
1. พัฒนา dashboard สำหรับ monitoring
2. เพิ่ม ML-based categorization
3. เพิ่ม features ใหม่ (sentiment analysis, etc.)
4. Integration กับ innovation-news-fetcher

---

## 📞 ข้อมูลติดต่อ

**ผู้พัฒนา:** น้องกุ้ง (OpenClaw Assistant)
**ผู้ดูแล:** คุณหนึ่ง
**องค์กร:** สำนักวิทยบริการ มหาวิทยาลัยสงขลานครินทร์
**Workspace:** `/home/kittisak/.openclaw/workspace/localinfo_crawler/`
**Database:** pattani_food / localinfo

---

## 📝 เอกสารประกอบ

| เอกสาร | ตำแหน่ง | หน้าที่ |
|---------|-----------|----------|
| README.md | localinfo_crawler/README.md | คำอธิบายการใช้งาน |
| ARCHITECTURE.md | localinfo_crawler/ARCHITECTURE.md | โครงสร้างระบบ |
| WORKFLOW.md | localinfo_crawler/WORKFLOW.md | ขั้นตอนการทำงาน |
| category-mapping.js | localinfo_crawler/category-mapping.js | Mapping หมวดหมู่ |

---

**รายงานสร้างเมื่อ:** 21 มีนาคม 2569
**สถานะ:** วิเคราะห์โครงสร้างเสร็จสมบูรณ์
