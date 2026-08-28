# แหล่งข้อมูล 11 แหล่ง - สถานะการกรองข้อมูล

## 📊 สรุปการกรองข้อมูล

### ✅ แหล่งที่มีการกรองในฟังก์ชัน fetcher()

| แหล่ง | วิธีกรอง | คำอธิบาย |
|-------|-----------|-----------|
| **iT24Hrs** | ✅ กรองใน fetcher | ใช้ `is_innovation_article(t)` ใน list comprehension |

### ⚠️ แหล่งที่ไม่มีการกรองในฟังก์ชัน fetcher() (พึ่ง main() loop)

| แหล่ง | วิธีกรอง | หมายเหตุ |
|-------|-----------|-----------|
| **NIA** | ❌ ไม่กรอง (ข้าม) | ทุกข่าวที่ NIA ส่งถือว่า innovation อยู่แล้ว |
| **ETDA** | ⚠️ กรองใน main() | รับจาก RSS ทั้งหมด, กรองใน main() loop |
| **Techsauce** | ⚠️ กรองใน main() | รับจาก RSS ทั้งหมด, กรองใน main() loop |
| **NSTDA** | ⚠️ กรองใน main() | รับจาก API 50+ เรื่อง, กรองใน main() loop |
| **RYT9** | ⚠️ กรองใน main() | รับจาก RSS ทั้งหมด, กรองใน main() loop |
| **TechTalkThai** | ⚠️ กรองใน main() | รับจาก RSS ทั้งหมด, กรองใน main() loop |
| **NECTEC** | ⚠️ กรองใน main() | รับจาก regex matches ทั้งหมด, กรองใน main() loop |
| **NRIIS** | ⚠️ กรองใน main() | รับจาก RSS ทั้งหมด, กรองใน main() loop |
| **Innomatter** | ⚠️ กรองใน main() | รับจาก RSS ทั้งหมด, กรองใน main() loop |
| **TechMovement** | ✅ กรองใน fetcher | ใช้ `is_innovation_article(title, excerpt)` ใน loop |

---

## 🔍 รายละเอียดการกรองของแต่ละแหล่ง

### 1. NIA (สำนักงานนวัตกรรมแห่งชาติ)
**สถานะ:** ❌ ไม่มีการกรอง (ข้าม)

**Code:**
```python
# Line 430-467
for item in items[:15]:
    # ... extract title, link, etc ...
    
    # NIA sends all articles without filtering (all are relevant)
    # No need to check is_innovation_article()
    
    articles.append({...})
```

**หมายเหตุ:**
- NIA ส่งเฉพาะบทความด้าน innovation เท่านั้น
- ไม่ต้องกรองเพราะทุกข่าวถือเป็น innovation อยู่แล้ว

---

### 2. ETDA (สพธอ.)
**สถานะ:** ⚠️ กรองใน main() loop

**Code:**
```python
# Line 470-482
root = ET.fromstring(requests.get(url, timeout=30, headers=headers).content)
items = root.findall('.//item')
articles = [{'title': clean_text(i.find('title').text), ...} for i in items[-10:]]
```

**หมายเหตุ:**
- RSS feeds จาก ETDA มีหลายประเภท (knowledge-sharing, PR news)
- บางเรื่องอาจไม่ใช่ innovation
- กรองใน main() loop ด้วย `is_innovation_article()`

---

### 3. Techsauce
**สถานะ:** ⚠️ กรองใน main() loop

**Code:**
```python
# Line 484-486
root = ET.fromstring(requests.get("https://techsauce.co/feed/", timeout=30, headers=headers).content)
return [{'title': clean_text(i.find('title').text), ...} for i in root.findall('.//item')[:10]]
```

**หมายเหตุ:**
- Techsauce RSS มีข่าวหลายหมวดหมู่
- กรองใน main() loop ด้วย `is_innovation_article()`

---

### 4. NSTDA (สวทช.)
**สถานะ:** ⚠️ กรองใน main() loop

**Code:**
```python
# Line 488-490 (หลังแก้ไข)
posts = requests.get("https://www.nstda.or.th/home/wp-json/wp/v2/news_post?per_page=50", timeout=30, headers=headers).json()
return [{'title': clean_text(p['title']['rendered']), ...} for p in posts]
```

**หมายเหตุ:**
- NSTDA API มีข่าว 26/50 = 52% เป็น innovation
- กรองใน main() loop ด้วย `is_innovation_article()`
- เพิ่ม per_page จาก 10 → 50 เพื่อครอบความ

---

### 5. RYT9
**สถานะ:** ⚠️ กรองใน main() loop

**Code:**
```python
# Line 492-494
root = ET.fromstring(requests.get("https://www.ryt9.com/tag/%E0%B8%99%E0%B8%A7%E0%B8%B1%E0%B8%95%E0%B8%81%E0%B8%A3%E0%B8%A1/rss.xml", timeout=30, headers=headers).content)
return [{'title': clean_text(i.find('title').text), ...} for i in root.findall('.//item')[:10]]
```

**หมายเหตุ:**
- RSS feed มี tag นวัตกรรม
- แต่บางเรื่องอาจไม่ใช่ innovation เท่ากับที่ต้องการ
- กรองใน main() loop ด้วย `is_innovation_article()`

---

### 6. iT24Hrs
**สถานะ:** ✅ กรองใน fetcher

**Code:**
```python
# Line 496-498
matches = re.findall(r'<h[2-4][^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', res, re.DOTALL)
return [{'title': clean_text(t), ...} for l, t in matches[:10] if is_innovation_article(t)]
```

**หมายเหตุ:**
- กรองตั้งแต่ใน fetcher ด้วย `is_innovation_article(t)`
- ไม่ต้องกรองอีกครั้งใน main() loop

---

### 7. TechTalkThai
**สถานะ:** ⚠️ กรองใน main() loop

**Code:**
```python
# Line 500-502
root = ET.fromstring(requests.get("https://www.techtalkthai.com/feed/", timeout=30, headers=headers).content)
return [{'title': clean_text(i.find('title').text), ...} for i in root.findall('.//item')[:10]]
```

**หมายเหตุ:**
- RSS feed มีข่าวด้านเทคโนโลยีหลายหมวดหมู่
- กรองใน main() loop ด้วย `is_innovation_article()`

---

### 8. NECTEC (สวทช.)
**สถานะ:** ⚠️ กรองใน main() loop

**Code:**
```python
# Line 504-508
res = requests.get("https://www.nectec.or.th/news/pr-news.html", timeout=30, headers=headers).text
matches = re.findall(r'<h3[^>]*elementor-post__title[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', res, re.DOTALL)
return [{'title': clean_text(t), ...} for l, t in matches[:10]]
```

**หมายเหตุ:**
- Web scraping จากหน้า PR news
- กรองใน main() loop ด้วย `is_innovation_article()`

---

### 9. NRIIS (สำนักงานการวิจัยแห่งชาติ)
**สถานะ:** ⚠️ กรองใน main() loop

**Code:**
```python
# Line 510-525
root = ET.fromstring(requests.get("https://nriis.go.th/rss.aspx", timeout=30, headers=headers).content)
items = root.findall('.//item')
return [{
    'title': clean_text(i.find('title').text),
    'link': i.find('link').text,
    ...
} for i in items[:10]]
```

**หมายเหตุ:**
- RSS feed มีบทความหลายประเภท
- กรองใน main() loop ด้วย `is_innovation_article()`

---

### 10. Innomatter
**สถานะ:** ⚠️ กรองใน main() loop

**Code:**
```python
# Line 527-529
root = ET.fromstring(requests.get("https://www.innomatter.com/feed/", timeout=30, headers=headers).content)
return [{'title': clean_text(i.find('title').text), ...} for i in root.findall('.//item')[:10]]
```

**หมายเหตุ:**
- RSS feed มีข่าวด้านนวัตกรรม/technology
- กรองใน main() loop ด้วย `is_innovation_article()`

---

### 11. TechMovement
**สถานะ:** ✅ กรองใน fetcher

**Code:**
```python
# Line 570-636
for card in cards:
    # ... extract data ...
    
    # ตรวจสอบว่าเป็น innovation article หรือไม่
    if not is_innovation_article(title, excerpt):
        continue
    
    articles.append({...})
```

**หมายเหตุ:**
- กรองตั้งแต่ใน fetcher ด้วย `is_innovation_article(title, excerpt)`
- ใช้ทั้ง title และ excerpt ในการกรอง
- ไม่ต้องกรองอีกครั้งใน main() loop

---

## 🎯 การกรองใน main() loop

**Code ที่เพิ่ม (Line 695-702):**
```python
for article in articles:
    date_obj = parse_date(article['date'])
    if not is_within_last_1_year(date_obj): continue
    content_hash = hashlib.md5(article['title'].encode('utf-8')).hexdigest()

    if is_article_duplicate(content_hash): continue

    # กรองเฉพาะ innovation/learning technology articles
    # (บาง source เช่น NIA ไม่ต้องกรองเพราะทุกข่าวเป็น innovation อยู่แล้ว)
    if source_name not in ['NIA'] and not is_innovation_article(article['title'], article['summary']):
        continue

    log_message(f"  ✓ Selected new article: {article['title'][:50]}")
```

---

## 📊 สรุปการกรอง

| แหล่ง | กรองใน fetcher | กรองใน main() loop | กรองรวม |
|-------|------------------|----------------------|-----------|
| NIA | ❌ ไม่กรอง | ❌ ข้าม | ❌ ไม่กรอง (ทุกข่าว innovation) |
| ETDA | ❌ | ✅ | ✅ |
| Techsauce | ❌ | ✅ | ✅ |
| NSTDA | ❌ | ✅ | ✅ |
| RYT9 | ❌ | ✅ | ✅ |
| **iT24Hrs** | ✅ | ✅ | ✅ (กรองซ้ำ 2 ครั้ง) |
| TechTalkThai | ❌ | ✅ | ✅ |
| NECTEC | ❌ | ✅ | ✅ |
| NRIIS | ❌ | ✅ | ✅ |
| Innomatter | ❌ | ✅ | ✅ |
| **TechMovement** | ✅ | ❌ ข้าม | ✅ (กรองใน fetcher) |

---

## 💡 ข้อสังเกต

1. **NIA** เป็นกรณีพิเศษ - ส่งเฉพาะ innovation articles เท่านั้น
2. **iT24Hrs** กรองซ้ำ 2 ครั้ง (fetcher + main()) - อาจ optimize ได้
3. **TechMovement** กรองใน fetcher - มีประสิทธิญายใช้ทั้ง title และ excerpt
4. **Source อื่นๆ** กรองใน main() loop - ช่วยลดความซับซ้อนใน code

---

## 📈 ผลลัพธ์

- ✅ ทุกแหล่งที่ไม่ใช่ NIA มีการกรอง innovation keywords
- ✅ ทุกแหล่งตรวจสอบ duplicates (content_hash)
- ✅ ทุกแหล่งตรวจสอบ อายุไม่เกิน 1 ปี
- ✅ ทุกแหล่งส่งไป DB → Telegram → WordPress → LINE

---

**อัปเดตล่าสุด:** 27 มีนาคม 2569 (11:50 น.)
**ผู้วิเคราะห์:** น้องกุ้ง 🦐
