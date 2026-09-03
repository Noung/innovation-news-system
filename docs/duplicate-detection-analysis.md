# รายงานตรวจสอบระบบ Duplicate Detection

**Date:** March 2026 (Updated: 3 September 2026)

**หมายเหตุ:** เอกสารนี้วิเคราะห์ระบบ duplicate detection เดิม ปัจจุบันระบบใช้ multi-layer duplicate detection:

1. Content hash (title + link)
2. Legacy title-only hash (backward compatibility)
3. Title + link exact match

## วิธีการทำงาน

### 1. Content Hash Generation

**ตำแหน่ง:** `generate_content_hash()` ใน `scripts/fetch-innovation-news-mysql.py`

```python
hash_input = f"{normalized_title(article.get('title', ''))}|{normalized_link(article.get('link', ''))}"
content_hash = hashlib.md5(hash_input.encode('utf-8')).hexdigest()
```

**รายละเอียด:**

- ใช้ **MD5** algorithm
- สร้าง hash จาก **title + link** (คั่นด้วย `|`)
- ใช้ **UTF-8** encoding สำหรับภาษาไทย
- มี legacy title-only hash สำหรับ backward compatibility

---

### 2. Duplicate Check (ก่อนบันทึก)

**ตำแหน่ง:** Line 174-176

```python
def is_article_duplicate(content_hash: str) -> bool:
    out = run_mysql_query(f"SELECT COUNT(*) FROM innovation_news WHERE content_hash = '{content_hash}';")
    return int(out) > 0 if out else False
```

**รายละเอียด:**

- ค้นหาจาก table `innovation_news`
- ใช้ `content_hash` เป็นคีย์หลัก
- ถ้า `COUNT(*) > 0` แปลว่าเป็น duplicate

---

### 3. Save to Database

**ตำแหน่ง:** Line 150-168

```python
def save_article_to_db(article: Dict, source_slug: str, content_hash: str) -> Optional[int]:
    # ตรวจสอบ duplicate ก่อนบันทึก
    if is_article_duplicate(content_hash):
        log_message(f"  ℹ️ Article already exists in DB (skipped): {article['title'][:50]}")
        return None

    # บันทึกลง DB โดยใช้ stored procedure
    query = f"SET @aid=NULL; SET @isnew=NULL; CALL save_article({esc(source_slug)}, {esc(article['title'])}, {esc(article['summary'][:800])}, {esc(article['link'])}, {esc(article['date'])}, {esc(content_hash)}, @aid, @isnew); SELECT @aid, @isnew;"

    out = run_mysql_query(query)
    if out:
        res = out.strip().split('\n')[-1].split('\t')
        if len(res) >= 2:
            article_id = int(res[0])
            if article_id:
                log_message(f"  💾 Saved new article to DB: {article['title'][:50]}")
                return article_id
```

**รายละเอียด:**

- เรียก `save_article()` stored procedure
- ส่ง parameters: `source_slug`, `title`, `summary`, `link`, `date`, `content_hash`
- รับ output: `@aid` (article ID) และ `@isnew` (เป็นข่าวใหม่)
- ถ้า `@aid` ไม่เป็น NULL แปลว่าบันทึกสำเร็จ

---

### 4. Main Loop Logic

**ตำแหน่ง:** Line 689-730

```python
for article in articles:
    # 1. แปลงวันที่
    date_obj = parse_date(article['date'])
    if not is_within_last_1_year(date_obj):
        continue

    # 2. สร้าง content hash จาก title
    content_hash = hashlib.md5(article['title'].encode('utf-8')).hexdigest()

    # 3. ตรวจสอบ duplicate จาก DB
    if is_article_duplicate(content_hash):
        continue

    # 4. Log และบันทึกลง DB
    log_message(f"  ✓ Selected new article: {article['title'][:50]}")
    article_id = save_article_to_db(article, source_slug, content_hash)

    if article_id:
        new_article = article
        new_count = 1
        sent_count = 1

        # 5. เตรียมข้อมูลประโยชน์
        article['benefits'] = generate_benefits(article['title'], article['summary'])

        # 6. ส่ง Telegram
        log_message("  📨 Sending to Telegram...")
        send_telegram_message(format_message(article))

        # 7. Sync to WordPress
        if WORDPRESS_ENABLED:
            wp_id = save_to_wordpress(article, content_hash)
            if wp_id:
                log_message(f"  📄 Saved to WP (ID: {wp_id})")

            # 8. ส่ง LINE (ถ้า WP บันทึกสำเร็จ)
            if LINE_ENABLED and wp_id:
                log_message("  🟢 WordPress Success. Sending to LINE...")
                if send_to_line(article):
                    log_message("  ✅ Sent to LINE successfully")

        break  # หยุดหลังจากบันทึกข่าวแรกครั้งแล้ว
```

---

## ข้อได้เปรียบและข้อจำกัด

### ✅ ข้อได้เปรียบ

1. **สองชั้นการตรวจสอบ duplicate:**
   - ตรวจสอบ 2 ครั้ง:
     - ในฟังก์ชัน `is_article_duplicate()` (SQL query)
     - อีกครั้งใน `save_article_to_db()` ก่อนบันทึก
   - ช่วยป้องกันไม่บันทึกข้อมูลซ้ำ

2. **ใช้ MD5 hash:**
   - รวดเร็ว ในการค้นหา
   - แทบเที่ยบกับ table index

3. **ใช้ UTF-8 encoding:**
   - รองรับภาษาไทย

4. **หยุด loop หลังบันทึกข่าวแรก:**
   - ป้องกันบันทึกข่าวเดียวหลายครั้งในรอบเดียว

### ⚠️ ข้อจำกัด

1. **Content hash ใช้ title เท่านั้น:**
   - ไม่รวม summary หรือ link
   - อาจเกิด false positive ถ้า title ซ้ำแต่เนื้อหาต่าง
   - ตัวอย่าง: "OpenAI launches Sora" จากแหล่ง A และ "OpenAI launches Sora" จากแหล่ง B จะถูกมองว่าซ้ำ

2. **MD5 collision:**
   - แม้จะพบได้ยาก แต่เป็นไปได้ในทางทฤษฎาค์

3. **ไม่มีการ update ข้อมูลเดิม:**
   - ถ้าบทความเดิมมีแต่ title ต่าง summary/link จะไม่ถูก update

---

## Table Schema (จาก stored procedure)

### innovation_news table

โดยสันนิษฐานจาก stored procedure `save_article()`:

```sql
-- Columns (โดยประมาณจาก usage):
- id (PRIMARY KEY, AUTO_INCREMENT)
- source_slug
- title
- summary
- link
- date
- content_hash (INDEXED)
- created_at
- updated_at
```

---

## แหล่งตรวจสอบ Duplicate

### MySQL Query

```sql
-- ค้นหา duplicates จาก title
SELECT title, COUNT(*) as count
FROM innovation_news
GROUP BY title
HAVING count > 1;

-- ค้นหา duplicates จาก content_hash
SELECT content_hash, title, COUNT(*) as count
FROM innovation_news
GROUP BY content_hash
HAVING count > 1;

-- ตรวจสอบ duplicates ล่าสุด
SELECT source_slug, title, link, created_at
FROM innovation_news
WHERE content_hash IN (
    SELECT content_hash
    FROM innovation_news
    GROUP BY content_hash
    HAVING COUNT(*) > 1
)
ORDER BY created_at DESC
LIMIT 20;
```

---

## แนวทางปรับปรุง (ถ้าต้องการ)

### 1. เพิ่ม summary เข้าไปใน content hash

```python
# ก่อน (เฉพาะ title):
content_hash = hashlib.md5(article['title'].encode('utf-8')).hexdigest()

# หลัง (title + summary):
content_hash = hashlib.md5((article['title'] + article['summary'][:500]).encode('utf-8')).hexdigest()
```

### 2. ใช้ SHA-256 แทน MD5

```python
content_hash = hashlib.sha256(article['title'].encode('utf-8')).hexdigest()
```

### 3. เพิ่ม link เข้าไปใน hash

```python
content_hash = hashlib.md5(article['link'].encode('utf-8')).hexdigest()
```

---

## สรุป

**วิธีการปัจจุบัน:**

- ตรวจสอบ duplicate จาก **title** (MD5 hash)
- ค้นหาจาก table `innovation_news`
- ใช้ UTF-8 encoding สำหรับภาษาไทย
- หยุด loop หลังบันทึกข่าวแรก

**แหล่งตรวจสอบ:**

- ฟังก์ชัน `is_article_duplicate()` (Line 174-176)
- ฟังก์ชัน `save_article_to_db()` (Line 150-168)
- Main loop (Line 689-730)

**โต๊ะ:** MySQL table `innovation_news` ใน database `innovation_news`

---

**อัปเดตล่าสุด:** 27 มีนาคม 2569 (11:55 น.)
**ผู้วิเคราะห์:** น้องกุ้ง 🦐
