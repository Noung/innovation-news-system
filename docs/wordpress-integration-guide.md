# WordPress Integration Guide

## ภาพรวม

Integration นี้จะ sync บทความจากระบบ fetch-innovation-news ไปยัง WordPress Custom Post Type `innovation-tip` โดยใช้ WordPress REST API

## สถาปัตยกรรม

```
fetch-innovation-news-mysql.py
    ↓
1. Fetch articles from 16 sources
2. Filter by keywords + date
3. Check duplicate in MySQL
4. Save to MySQL
5. Save to WordPress (innovation-tip CPT + benefit taxonomy)
6. Send Telegram notification
7. Send LINE notification
```

**หมายเหตุ:** ปัจจุบันระบบรองรับ 16 แหล่งข้อมูล และส่ง notification ผ่านทั้ง Telegram และ LINE

## ไฟล์ที่ใช้

| ไฟล์                                                | หน้าที่                                                 |
| --------------------------------------------------- | ------------------------------------------------------- |
| `scripts/wordpress_integration.py`                  | Module สำหรับ WordPress API                             |
| `scripts/fetch-innovation-news-mysql.py`            | Script หลัก (updated แล้ว)                              |
| `scripts/test-integrations.py`                      | Script ทดสอบ integrations และ WordPress taxonomy schema |
| `wordpress-plugin/innovation-tip-benefit-taxonomy/` | Plugin สำหรับ taxonomy ประโยชน์ต่อองค์กร                |
| `.env`                                              | Environment variables                                   |

รายละเอียดการติดตั้ง taxonomy, การเลือก 3 terms และการทำหน้า archive/filter อยู่ใน [wordpress-benefit-taxonomy.md](wordpress-benefit-taxonomy.md)

## ขั้นตอนการติดตั้ง

### 1. เตรียม WordPress

#### 1.1 ตรวจสอบ Custom Post Type

ตรวจสอบว่า CPT `innovation-tip` มีอยู่แล้วและ enabled REST API:

1. Login WordPress Admin
2. เลือก **Innovation Tips** → **Add New**
3. ถ้าเห็นหน้าสร้าง post แล้ว แปลว่า CPT พร้อมใช้
4. ตรวจสอบ REST API endpoint:
   ```bash
   curl -I https://your-site.com/wp-json/wp/v2/innovation-tip
   ```
   ต้องได้ `200 OK`

#### 1.2 สร้าง Application Password

1. Login WordPress Admin
2. เลือก **Users** → **Your Profile**
3. Scroll ลงไปที่ **Application Passwords**
4. ตั้งชื่อ: `Innovation News Bot`
5. กด **Add New Application Password**
6. Copy password (แสดงครั้งเดียวเท่านั้น)

**หมายเหตุ:** ใช้ Application Password ไม่ใช้ Password ปกติ!

#### 1.3 เพิ่ม Custom Fields (ถ้ายังไม่มี)

เพิ่ม fields ใหม่สำหรับเก็บ metadata:

```php
// ใน functions.php หรือ custom plugin

add_filter('ptb/innovation-tip/metaboxes', function($metaboxes) {
    $metaboxes['innovation_tip_metadata'] = [
        'id' => 'innovation_tip_metadata',
        'title' => 'ข้อมูลเพิ่มเติม (Auto-sync)',
        'fields' => [
            [
                'id' => 'innovation_tip_source',
                'type' => 'text',
                'name' => 'แหล่งข้อมูล',
                'description' => 'แหล่งที่ดึงข่าวมา'
            ],
            [
                'id' => 'innovation_tip_source_url',
                'type' => 'text',
                'name' => 'URL แหล่งข้อมูล'
            ],
            [
                'id' => 'innovation_tip_content_hash',
                'type' => 'text',
                'name' => 'Content Hash',
                'description' => 'MD5 hash สำหรับตรวจซ้ำ'
            ],
            [
                'id' => 'innovation_tip_sync_date',
                'type' => 'text',
                'name' => 'วันที่ Sync'
            ]
        ]
    ];

    return $metaboxes;
});
```

### 2. ตั้งค่า Environment Variables

แก้ไฟล์ `.env`:

```bash
# WordPress Integration (optional)
# Leave empty to disable WordPress sync

# URL root ของ WordPress REST API (ต้องมี /wp-json แต่ไม่ต้องต่อ /wp/v2)
WP_API_URL=https://your-wordpress-site.com/wp-json

# Username สำหรับ login WordPress (not email)
WP_USERNAME=admin

# Application Password ที่ generate จาก WP Admin
WP_APP_PASSWORD=abcd 1234 efgh 5678
```

**หมายเหตุ:**

- `WP_API_URL`: ใช้ URL เต็มรวม `/wp-json`
- `WP_USERNAME`: Username ของ WordPress (admin หรือ user ที่มีสิทธิ์ create posts)
- `WP_APP_PASSWORD`: Application Password ที่ generate จาก Profile

### 3. Test Integration

รัน script test:

```bash
cd /home/kittisak/.openclaw/workspace/scripts
python3 test-integrations.py
```

ผลลัพธ์ที่คาดหวัง:

```
[WORDPRESS]
  ✅ WordPress CPT + Benefit Taxonomy + 20 terms: SUCCESS
```

คำสั่งนี้ไม่สร้าง WordPress post แต่จะส่งข้อความทดสอบไป Telegram/LINE หากตั้งค่า channel ไว้ จึงควรทดสอบในสภาพแวดล้อมที่เหมาะสม

### 4. Verify Taxonomy Assignment on Staging

ทดสอบ fetch ข่าวหนึ่งรายการบน staging แล้วตรวจว่า post มี taxonomy “ประโยชน์ต่อองค์กร” จำนวน 3 terms ที่ไม่ซ้ำกัน ดูขั้นตอนและ REST URLs ใน [wordpress-benefit-taxonomy.md](wordpress-benefit-taxonomy.md)

### 5. Run Full Integration

เมื่อ test ผ่านแล้ว ให้รัน script หลัก:

```bash
# รัน manual
/usr/bin/python3 /home/kittisak/.openclaw/workspace/scripts/fetch-innovation-news-mysql.py

# หรือใช้ wrapper script
/home/kittisak/.openclaw/workspace/scripts/run-fetch-innovation-news.sh
```

Script จะทำงานตามปกติ และ sync ไป WordPress อัตโนมัติ

## Field Mapping

| Field จาก Article | Field ใน WordPress CPT        | Type        |
| ----------------- | ----------------------------- | ----------- |
| `title`           | `post_title`                  | Post title  |
| `summary`         | `innovation_tip_content`      | Textarea    |
| `link`            | `innovation_tip_url`          | Link button |
| `source`          | `innovation_tip_source`       | Text        |
| `source_url`      | `innovation_tip_source_url`   | Text        |
| `content_hash`    | `innovation_tip_content_hash` | Text        |
| `sync_date`       | `innovation_tip_sync_date`    | Text        |

## Source Mapping

| Source Name                      | WordPress Value |
| -------------------------------- | --------------- |
| NIA (สำนักงานนวัตกรรมแห่งชาติ)   | NIA             |
| ETDA (สพธอ.)                     | ETDA            |
| Techsauce                        | Techsauce       |
| NSTDA (สวทช.)                    | NSTDA           |
| RYT9                             | RYT9            |
| iT24Hrs                          | iT24Hrs         |
| TechTalkThai                     | TechTalkThai    |
| NECTEC (สวทช.)                   | NECTEC          |
| NRIIS (สำนักงานการวิจัยแห่งชาติ) | NRIIS           |
| Innomatter                       | Innomatter      |

## Troubleshooting

### ❌ WordPress connection failed

**สาเหตุ:**

- URL ผิด
- WordPress site down
- REST API disabled

**วิธีแก้:**

1. ตรวจสอบ URL ถูกต้องไหม
2. Test REST API: `curl https://your-site.com/wp-json/wp/v2`
3. ตรวจสอบ WordPress permalinks: Settings → Permalinks → Post name

### ❌ Authentication failed (401)

**สาเหตุ:**

- Username ผิด
- Application Password ผิด/หมดอายุ

**วิธีแก้:**

1. ตรวจสอบ username ใน WordPress Admin
2. Generate Application Password ใหม่
3. Update `.env` และรัน test ใหม่

### ❌ Cannot save post (404/405)

**สาเหตุ:**

- CPT ไม่มี REST API enabled
- Custom fields ไม่ถูก register

**วิธีแก้:**

1. ตรวจสอบ CPT registration: `show_in_rest => true`
2. ตรวจสอบ custom fields ถูก register แล้ว

### ❌ Timeout errors

**สาเหตุ:**

- WordPress server ช้า
- Network latency

**วิธีแก้:**

1. เพิ่ม timeout ใน `wordpress_integration.py`
2. Check WordPress server performance

### ⚠️ Duplicate posts

**สาเหตุ:**

- Hash collision
- WordPress database ไม่ sync

**วิธีแก้:**

1. ตรวจสอบ `innovation_tip_content_hash` field
2. Delete duplicates จาก WordPress Admin

## Disable WordPress Sync

ถ้าต้องการปิด WordPress sync ชั่วคราว:

**Option 1: ปล่อย .env ว่าง**

```bash
# ใน .env
WP_API_URL=
WP_USERNAME=
WP_APP_PASSWORD=
```

**Option 2: ลบ module import**

แก้ `fetch-innovation-news-mysql.py`:

```python
# Comment out or remove these lines:
try:
    from wordpress_integration import save_to_wordpress
    WORDPRESS_ENABLED = True
except ImportError:
    WORDPRESS_ENABLED = False
```

## Monitoring

ตรวจสอบ logs:

```bash
# Main script log
tail -f /home/kittisak/.openclaw/workspace/logs/innovation-news-fetch.log

# Cron log
tail -f /home/kittisak/.openclaw/workspace/logs/cron-innovation-news-mysql.log
```

หาก integration ทำงานถูกต้องจะเห็น:

```
✅ Saved to WordPress: Article Title (ID: 123)
📄 Synced to WordPress (Post ID: 123)
```

หากล้มเหลวจะเห็น:

```
⚠️  Failed to sync to WordPress (non-fatal)
❌ Failed to save to WordPress: ...
```

## Cron Job (ถ้ายังไม่มี)

เพิ่ม cron job:

```bash
crontab -e
```

เพิ่มบรรทัด:

```cron
# Fetch innovation news every 30 minutes
*/30 * * * * /home/kittisak/.openclaw/workspace/scripts/run-fetch-innovation-news.sh
```

---

**Last Updated:** 2026-03-24
**Version:** 1.0
