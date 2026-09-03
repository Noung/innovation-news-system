# รายงานการศึกษาไฟล์ fetch-innovation-news_bak190369.py
**วันที่:** 20 มีนาคม 2569
**ไฟล์:** `/home/kittisak/.openclaw/workspace/scripts/fetch-innovation-news_bak190369.py`
**ขนาด:** 837 บรรทัด (33KB)

---

## 📊 ภาพรวม

ไฟล์ backup นี้เป็น **version ที่สมบูรณ์** มี fetch functions และ main function ครบถ้วน ซึ่งต่างจากไฟล์ปัจจุบันที่มีแค่ helper functions

### ความแตกต่างระหว่าง 2 versions

| ประเด็น | ไฟล์ปัจจุบัน (fetch-innovation-news.py) | ไฟล์ backup (fetch-innovation-news_bak190369.py) |
|---------|----------------------------------------|---------------------------------------------------|
| บรรทัด | 326 บรรทัด (19KB) | 837 บรรทัด (33KB) |
| Fetch Functions | ❌ ไม่มี | ✅ มี 9 ฟังก์ชัน |
| Main Function | ❌ ไม่มี | ✅ มี |
| Sources List | ❌ ไม่มี | ✅ มี 9 แหล่งข้อมูล |
| Helper Functions | ✅ 11 ฟังก์ชัน | ✅ 17 ฟังก์ชัน |

---

## 🌐 แหล่งข้อมูล 9 แหล่ง (ใน backup)

| # | แหล่ง | วิธีดึง | URL | Function |
|---|--------|---------|-----|----------|
| 1 | **NIA** | HTML Scraping | https://www.nia.or.th/article/blog.html | `fetch_nia()` |
| 2 | **ETDA** | HTML Scraping | https://www.etda.or.th/th/Useful-Resource/knowledge-sharing/articles.aspx | `fetch_etda()` |
| 3 | **Techsauce** | RSS Feed | https://techsauce.co/feed | `fetch_techsauce_rss()` |
| 4 | **NSTDA** | HTML Scraping | https://www.nstda.or.th/home/knowledgebase/knowledge | `fetch_nstda()` |
| 5 | **RYT9** | RSS Feed | https://www.ryt9.com/tag/%E0%B8%99%E0%B8%A7%E0%B8%B1%E0%B8%95%E0%B8%81%E0%B8%A3%E0%B8%A3%E0%B8%A1/feed | `fetch_ryt9_rss()` |
| 6 | **iT24Hrs** | RSS Feed | https://it24hrs.com/feed | `fetch_it24hrs_rss()` |
| 7 | **TechTalkThai** | RSS Feed | https://www.techtalkthai.com/feed | `fetch_techtalkthai_rss()` |
| 8 | **NECTEC** | RSS Feed | https://www.nectec.or.th/news/feed | `fetch_nectec_rss()` |
| 9 | **TechMovement** | API | https://techmovement.co.th/news/api | `fetch_techmovement_api()` |

**หมายเหตุ:** ไม่มี Innomatter (ซึ่งมีใน version ล่าสุด)

---

## 🔧 รายละเอียด Fetch Functions

### 1. `fetch_nia()` - HTML Scraping
```python
url: https://www.nia.or.th/article/blog.html
method: regex pattern matching
max_articles: 20
```

**Pattern ที่ใช้:**
```python
# Extract article cards
pattern = r'<a[^>]*href="([^"]+)"[^>]*>.*?<h[2-4][^>]*>([^<]+)</h[2-4]>'

# Extract date
date_pattern = r'<span[^>]*class="[^"]*date[^"]*"[^>]*>([^<]+)</span>'

# Extract summary
summary_pattern = r'<p[^>]*>([^<]{100,400})</p>'
```

**สิ่งที่ดึง:**
- title (h2-h4 tags)
- link (href attribute)
- date (span with date class)
- summary (p tag, 100-400 chars)

---

### 2. `fetch_etda()` - HTML Scraping
```python
url: https://www.etda.or.th/th/Useful-Resource/knowledge-sharing/articles.aspx
method: regex pattern matching
max_articles: 20
```

**เหมือนกับ NIA:**
- ใช้ pattern เดียวกัน
- ดึง title, link, date, summary

---

### 3. `fetch_techsauce_rss()` - RSS Feed
```python
url: https://techsauce.co/feed
method: XML parsing (RSS 2.0)
max_articles: unlimited (all items)
```

**XML Elements:**
```xml
<item>
  <title>...</title>
  <link>...</link>
  <pubDate>...</pubDate>
  <description>...</description>
</item>
```

---

### 4. `fetch_nstda()` - HTML Scraping
```python
url: https://www.nstda.or.th/home/knowledgebase/knowledge
method: regex pattern matching
max_articles: 20
```

**เหมือนกับ NIA/ETDA:**
- ใช้ pattern เดียวกัน
- ดึง title, link, date, summary

---

### 5. `fetch_ryt9_rss()` - RSS Feed
```python
url: https://www.ryt9.com/tag/นวัตกรรม/feed
method: XML parsing (RSS 2.0)
max_articles: unlimited (all items)
```

**URL Encoding:**
- Tag "นวัตกรรม" ถูก URL-encoded

---

### 6. `fetch_it24hrs_rss()` - RSS Feed
```python
url: https://it24hrs.com/feed
method: XML parsing (RSS 2.0)
max_articles: unlimited (all items)
```

---

### 7. `fetch_techtalkthai_rss()` - RSS Feed
```python
url: https://www.techtalkthai.com/feed
method: XML parsing (RSS 2.0)
max_articles: unlimited (all items)
```

**หมายเหตุ:**
- ไม่มี trailing slash (ต่างจาก version ล่าสุด)

---

### 8. `fetch_nectec_rss()` - RSS Feed
```python
url: https://www.nectec.or.th/news/feed
method: XML parsing (RSS 2.0)
max_articles: unlimited (all items)
```

**หมายเหตุ:**
- version นี้ใช้ RSS Feed (version ล่าสุดใช้ HTML scraping 2 URLs)

---

### 9. `fetch_techmovement_api()` - API
```python
url: https://techmovement.co.th/news/api
method: JSON API
max_articles: 20
```

**API Response Structure:**
```python
# Support 2 formats:
# 1. Array directly
[data1, data2, ...]

# 2. Object with 'data' field
{'data': [data1, data2, ...]}
```

**JSON Fields:**
```python
{
  'title': str,
  'url' or 'link': str,
  'date' or 'published_at': str,
  'summary' or 'description': str
}
```

---

## 📝 Helper Functions (17 ฟังก์ชัน)

### Core Functions
| # | Function | หน้าที่ |
|---|----------|---------|
| 1 | `log_message(message)` | Log ข้อความไฟล์ |
| 2 | `get_content_hash(content)` | สร้าง MD5 hash สำหรับ deduplication |
| 3 | `load_cache()` | โหลด cache จาก JSON |
| 4 | `save_cache(cache)` | บันทึก cache ไป JSON |
| 5 | `get_current_source_index()` | อ่าน index ปัจจุบัน |
| 6 | `update_source_index(index, total_sources)` | อัปเดต index ถัดไป (rotation) |
| 7 | `is_article_sent(hash_value, cache)` | เช็คว่าบทความถูกส่งแล้วหรือไม่ |
| 8 | `mark_article_sent(hash_value, cache)` | ทำเครื่องหมายบทความว่าส่งแล้ว |
| 9 | `clean_text(text)` | ลบ HTML tags และ whitespace |
| 10 | `is_innovation_article(title, summary)` | กรองด้วย keywords |
| 11 | `parse_date(date_str)` | แปลง string เป็น datetime |
| 12 | `is_within_last_1_year(date_obj)` | เช็คว่าภายใน 1 ปีหรือไม่ |
| 13 | `format_thai_date(date_obj)` | แปลงเป็นวันที่ไทย |
| 14 | `send_telegram_message(message)` | ส่งข้อความ Telegram |
| 15 | `generate_benefits(article)` | สร้าง bullet points ประโยชน์ |
| 16 | `format_message(article)` | จัด format ข้อความ Telegram |
| 17 | `main()` | ฟังก์ชันหลัก |

---

## 🔑 Keywords (การกรองข่าว)

### English Keywords (23 คำ)
```python
INNOVATION_KEYWORDS = [
    # AI & Automation
    'ai', 'artificial intelligence', 'machine learning', 'ml', 'deep learning',
    'automation', 'chatbot', 'copilot', 'gpt', 'llm', 'generative ai',

    # Digital Transformation
    'digital transformation', 'digitalization', 'digital economy', 'digital innovation',
    'digital workplace', 'digital workplace', 'remote work', 'hybrid work',

    # Innovation in Organization
    'innovation', 'innovation strategy', 'business innovation', 'innovation management',
    'startup', 'startup ecosystem', 'entrepreneur', 'entrepreneurship',

    # Technology for Learning
    'learning technology', 'edtech', 'e-learning', 'online learning',
    'digital learning', 'training technology', 'skills development',

    # Other relevant
    'technology adoption', 'tech adoption', 'future of work', 'future skills',
    'digital skills', 'tech trends', 'emerging technology', 'disruption'
]
```

### Thai Keywords (12 คำ)
```python
INNOVATION_KEYWORDS_TH = [
    'ปัญญาประดิษฐ์', 'ปัญญาประดิษฐฐ์', 'ai', 'เอไอ',
    'นวัตกรรม', 'นวัตกรรมไทย', 'นวัตกรรมองค์กร',
    'ดิจิทัลทรานส์ฟอร์เมชัน', 'การเปลี่ยนผ่านดิจิทัล',
    'ดิจิทัล', 'เทคโนโลยีดิจิทัล',
    'สตาร์ทอัพ', 'สตาร์ทอัพไทย',
    'อัตโนมาติก', 'ระบบอัตโนมัติ', 'หุ่นยนต์',
    'การเรียนรู้ดิจิทัล', 'เอ็ดเทค', 'อีเลิร์นนิง',
    'ทักษะดิจิทัล', 'พัฒนาทักษะ', 'การฝึกอบรม',
    'เทคโนโลยี', 'นวัตกรรม', 'เทรนด์เทคโนโลยี'
]
```

**รวม:** 35 คีย์เวิร์ด (น้อยกว่า version ล่าสุดที่มี 45+ คำ)

---

## 🎨 Format ข้อความ Telegram

### Format เมื่อมีบทความใหม่
```
📌 Innovation Daily Update

เรื่อง: {title}
แหล่ง: {source}
วันที่: {thai_date}

รายละเอียดโดยสรุป:
{summary[:300]}...

ประโยชน์ต่อองค์กร:
{bullet 1}
{bullet 2}
{bullet 3}

อ่านต่อ: {link}
```

### Format เมื่อไม่มีบทความใหม่
```
📌 Innovation Daily Update

แหล่งข้อมูล: {source_name}
สถานะ: ขณะนี้ยังไม่มีบทความด้าน innovation/learning technology ใหม่

🔄 จะตรวจสอบแหล่งถัดไปในชั่วโมงหน้า
```

---

## 🔄 Workflow การทำงาน (ใน backup)

### Flow หลัก
```python
main()
  ↓
load_cache()
  ↓
get_current_source_index() → ถ้าไม่มีเริ่มที่ 0
  ↓
SOURCES[index] → ดึง (source_name, fetcher)
  ↓
articles = fetcher() → เรียก fetch function
  ↓
update_source_index(index, total_sources) → index + 1, modulo total
  ↓
for each article:
  ├─ content_hash = hash(title + link)
  ├─ if not is_article_sent(hash):
  │    new_articles.append((article, hash))
  ↓
if new_articles:
  ├─ article, hash = new_articles[0] → ส่งแค่ 1 บทความแรก
  ├─ message = format_message(article)
  ├─ send_telegram_message(message)
  └─ mark_article_sent(hash, cache)
else:
  ├─ send no_new_msg → แจ้งว่าไม่มีข่าวใหม่
  ↓
save_cache(cache)
```

### Rotation System
```python
sources = [('NIA', fetch_nia), ('ETDA', fetch_etda), ..., ('TechMovement', fetch_techmovement_api)]
total = 9

# Index เดินทาง: 0 → 1 → 2 → ... → 8 → 0 → 1 → ...
update_source_index(current_idx, total)  # (0, 9) → 1
```

---

## 📂 โครงสร้าง Cache

### Cache Format
```python
{
    "sent_hashes": [
        "md5_hash_1",
        "md5_hash_2",
        ...
    ]
}
```

### Hash Generation
```python
hash = md5(title + link)  # รวม title + link แล้ว hash
```

---

## ⚙️ Configuration

### Files & Paths
```python
TELEGRAM_USER_ID = "${TELEGRAM_CHAT_ID}"
OPENCLAW_BIN = "/home/kittisak/.npm-global/bin/openclaw"

CACHE_FILE = "/home/kittisak/.openclaw/workspace/cache/innovation-news-cache.json"
LOG_FILE = "/home/kittisak/.openclaw/workspace/logs/innovation-news-fetch.log"
SOURCES_INDEX_FILE = "/home/kittisak/.openclaw/workspace/cache/innovation-sources-index.txt"
```

### Thai Months
```python
THAI_MONTHS = {
    1: "ม.ค.", 2: "ก.พ.", 3: "มี.ค.", 4: "เม.ย.",
    5: "พ.ค.", 6: "มิ.ย.", 7: "ก.ค.", 8: "ส.ค.",
    9: "ก.ย.", 10: "ต.ค.", 11: "พ.ย.", 12: "ธ.ค."
}
```

---

## 🐛 ประเด็นที่สังเกตได้

### สิ่งที่ดีกว่าใน version นี้
1. ✅ **โครงสร้างครบถ้วน** - มีทุกอย่างที่ต้องการ
2. ✅ **SOURCES list ชัดเจน** - ง่ายต่อการแก้ไข/เพิ่มแหล่งใหม่
3. ✅ **Main function ง่าย** - logic ชัดเจน
4. ✅ **Helper functions ครบ** - ทุกฟังก์ชันที่จำเป็น
5. ✅ **TechMovement API** - ใช้ API แทน HTML scraping (เสถียรกว่า)

### สิ่งที่ด้อยกว่า version ล่าสุด
1. ❌ **Keywords น้อยกว่า** - 35 vs 45+ คำ
2. ❌ **ไม่มี Innomatter** - version ล่าสุดมี 10 แหล่งข้อมูล
3. ❌ **NECTEC เป็น RSS** - version ล่าสุดใช้ HTML scraping (ดีกว่าถ้า RSS ไม่ update)
4. ❌ **TechTalkThai URL** - ไม่มี trailing slash
5. ❌ **เพิ่งส่ง 1 บทความ/รอบ** - version ล่าสุดอาจส่งได้หลายบทความ

---

## 🚀 การฟื้นฟูจาก Backup

### ขั้นตอนที่แนะนำ

1. **Restore ไฟล์:**
   ```bash
   cp fetch-innovation-news_bak190369.py fetch-innovation-news.py
   ```

2. **อัปเกรด:**
   - เพิ่ม keywords จาก version ล่าสุด
   - เพิ่ม Innomatter (fetch_innomatter_rss())
   - แก้ TechTalkThai URL (เพิ่ม trailing slash)
   - แก้ NECTEC เป็น HTML scraping (ถ้าจำเป็น)
   - อัปเด TechMovement ใช้ HTML scraping (ถ้า API ไม่เสถียร)

3. **ทดสอบ:**
   ```bash
   python3 fetch-innovation-news.py
   ```

---

## 📊 สรุปการเปรียบเทียบ

| คุณลักษณะ | ไฟล์ปัจจุบัน | ไฟล์ backup | ควรใช้ |
|----------|--------------|-------------|----------|
| ความสมบูรณ์ | ❌ 326 บรรทัด (เฉพาะ helper) | ✅ 837 บรรทัด (ครบ) | Backup |
| แหล่งข้อมูล | ไม่ชัดเจน | 9 แหล่ง (ชัดเจน) | Backup |
| Fetch functions | ❌ ไม่มี | ✅ 9 ฟังก์ชัน | Backup |
| Main function | ❌ ไม่มี | ✅ มี | Backup |
| Keywords | ✅ 45+ คำ | ⚠️ 35 คำ | ผสม |
| แหล่งข้อมูลทั้งหมด | 10 แหล่ง (จาก log) | 9 แหล่ง | ผสม |
| ทำงานจริง | ❓ ไม่แน่ใจ | ✅ เคยทำงานได้ | Backup |

---

## 💡 ข้อเสนอแนะ

### แนวทางการแก้ไข
1. **ใช้ backup เป็นฐาน** เพราะสมบูรณ์กว่า
2. **Copy features ดีๆ จาก version ล่าสุด** (keywords, Innomatter)
3. **อัปเด TechMovement** ใช้ HTML scraping ถ้า API ไม่เสถียร
4. **อัปเด NECTEC** ใช้ HTML scraping ถ้า RSS ไม่ update
5. **ทดสอบทีละแหล่ง** ก่อน deploy จริง

### การ merge 2 versions
```
Backup (ฐาน):
  ├─ Fetch functions (9 sources)
  ├─ Main function
  ├─ Helper functions
  └─ Workflow

Latest (features):
  ├─ Keywords (45+ คำ)
  ├─ Innomatter source
  ├─ NECTEC HTML scraping
  ├─ TechMovement HTML scraping
  └─ Other improvements

Result:
  ├─ 10 sources (NIA, ETDA, Techsauce, NSTDA, RYT9, iT24Hrs, TechTalkThai, NECTEC, TechMovement, Innomatter)
  ├─ 45+ keywords
  ├─ Complete functions
  └─ Tested & stable
```

---

*รายงานสร้างเมื่อ: 20 มีนาคม 2569*
*เอกสารนี้เป็นผลการวิเคราะห์ไฟล์ backup fetch-innovation-news_bak190369.py*
