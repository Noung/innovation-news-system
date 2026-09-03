# Innovation News System - Kanban Roadmap

## 🎯 วิสัยทัศน์ (Vision)

ระบบจัดการและแจ้งเตือนข่าวนวัตกรรมและเทคโนโลยีอัตโนมัติสำหรับมหาวิทยาลัยสงขลานครินทร์ ที่ช่วยให้สามารถติดตามเทรนด์นวัตกรรมได้ง่ายและรวดเร็ว

---

## 📊 Kanban Board

### ✅ DONE (เสร็จแล้ว)

| หัวข้อ                                            | รายละเอียด                                                                                                                                                                                 | วันที่เสร็จ |
| ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------- |
| **ขั้นตอนที่ 1: วิจัยและวางแผน**                  | ศึกษาแหล่งข้อมูลข่าว, วิเคราะห์ความต้องการ                                                                                                                                                 | -           |
| **ขั้นตอนที่ 2: พัฒนา Core Engine**               | สร้าง Python script สำหรับดึงข่าวจากหลายแหล่ง                                                                                                                                              | -           |
| **ขั้นตอนที่ 3: ติดตั้ง MySQL Database**          | สร้าง Database และ Stored Procedures สำหรับบันทึกข่าว                                                                                                                                      | -           |
| **ขั้นตอนที่ 4: พัฒนา Filtering System**          | สร้าง Keyword filtering ทั้งภาษาไทยและอังกฤษ                                                                                                                                               | -           |
| **ขั้นตอนที่ 5: Duplicate Detection**             | ใช้ content hash เพื่อป้องกันบทความซ้ำ                                                                                                                                                     | -           |
| **ขั้นตอนที่ 6: Telegram Integration**            | เชื่อมต่อกับ Telegram Bot สำหรับการแจ้งเตือน                                                                                                                                               | -           |
| **ขั้นตอนที่ 7: Cron Job Setup**                  | ตั้งเวลาทำงานอัตโนมัติผ่าน cron                                                                                                                                                            | -           |
| **ขั้นตอนที่ 8: Multi-source Support**            | เชื่อมต่อ 16 แหล่งข้อมูล (NIA, ETDA, Techsauce, NSTDA, RYT9, iT24Hrs, TechTalkThai, NECTEC, Tech Movement, Innomatter, NRIIS, Innovation News Network, Tech Xplore, iMod, Blognone, OARKM) | -           |
| **ขั้นตอนที่ 9: WordPress Integration (Phase 1)** | สร้างโมดูล sync ไป WordPress REST API                                                                                                                                                      | -           |
| **ขั้นตอนที่ 10: PTB Custom Fields Support**      | ใช้ custom fields: `ptb_innovation_tip_content`, `ptb_innovation_tip_url`, `ptb_innovation_tip_video`                                                                                      | -           |
| **ขั้นตอนที่ 11: Environment Variables Setup**    | แยก credentials ออกจาก code (WordPress credentials)                                                                                                                                        | 2026-03-24  |
| **ขั้นตอนที่ 12: Benefits Generation System**     | พัฒนา AI-driven benefits analyzer สำหรับสร้าง "ประโยชน์ต่อองค์กร" อัตโนมัติ (15 หมวดหมู่)                                                                                                  | 2026-03-25  |
| **ขั้นตอนที่ 13: Message Format Update**          | อัปเดตรูปแบบข้อความ Telegram ใหม่ (สรุป 800 ตัวอักษร + ประโยชน์ต่อองค์กร + emojis)                                                                                                         | 2026-03-25  |
| **ขั้นตอนที่ 14: Documentation**                  | สร้างเอกสารสรุปภาพรวมระบบ (INNOVATION-NEWS-SYSTEM.md)                                                                                                                                      | 2026-03-25  |
| **ขั้นตอนที่ 15: LINE Integration**               | เชื่อมต่อกับ LINE Notify สำหรับการแจ้งเตือน                                                                                                                                                | 2026-04     |
| **ขั้นตอนที่ 16: Admin Dashboard**                | สร้าง Web Dashboard สำหรับจัดการแหล่งข้อมูล, ดูบทความ, logs                                                                                                                                | 2026-08     |
| **ขั้นตอนที่ 17: Phase 0 Deployment**             | Deploy ระบบสู่ PROD พร้อม security baseline, feature gates, audit logs                                                                                                                     | 2026-08-28  |
| **ขั้นตอนที่ 18: Docker Local Development**       | สร้าง Docker Compose environment สำหรับ local development                                                                                                                                  | 2026-08     |
| **ขั้นตอนที่ 19: WordPress Benefit Taxonomy**     | สร้าง controlled vocabulary 20 benefit terms สำหรับ WordPress                                                                                                                              | 2026-08     |
| **ขั้นตอนที่ 20: Database Security Hardening**    | ย้าย credentials ทั้งหมดไป .env, แยก PROD/Local                                                                                                                                            | 2026-08     |

---

### 🔄 IN PROGRESS (กำลังทำ)

| หัวข้อ                          | รายละเอียด                                                            | ความสำคัญ |
| ------------------------------- | --------------------------------------------------------------------- | --------- |
| **Subscription & Email System** | ระบบรับสมัคร subscriber พร้อม email notification ตาม benefit ที่เลือก | 🔴 สูง    |
| **WordPress URL to LINE**       | ส่ง WordPress URL ไป LINE แทน source URL                              | 🟡 กลาง   |
| **Error Handling Enhancement**  | ปรับปรุง error handling และ retry mechanism                           | 🟡 กลาง   |

---

### 📋 TO DO (จะทำ)

| หัวข้อ                     | รายละเอียด                                                           | ความสำคัญ | วันที่เริ่มที่คาดหวัง |
| -------------------------- | -------------------------------------------------------------------- | --------- | --------------------- |
| **Article Categorization** | จัดหมวดหมู่บทความอัตโนมัติ (AI/ML, EdTech, FinTech, HealthTech, ฯลฯ) | 🟡 กลาง   | Q4 2026               |
| **Advanced Analytics**     | ระบบวิเคราะห์: บทความยอดนิยม, แหล่งข้อมูลที่ดีที่สุด, เทรนด์การค้นหา | 🟢 ต่ำ    | Q4 2026               |
| **Sentiment Analysis**     | วิเคราะห์ความรู้สึกของบทความ (positive/negative/neutral)             | 🟢 ต่ำ    | Q1 2027               |
| **WhatsApp Integration**   | รองรับการแจ้งเตือนผ่าน WhatsApp                                      | 🟢 ต่ำ    | Q1 2027               |

---

### 📦 BACKLOG (เก็บไว้ก่อน)

| หัวข้อ                            | รายละเอียด                                                   | ความสำคัญ |
| --------------------------------- | ------------------------------------------------------------ | --------- |
| **AI-powered Summarization**      | ใช้ LLM (GPT/Claude) เพื่อสร้างสรุปภาษาไทยที่ดีขึ้น          | 🟡 กลาง   |
| **Article Recommendation Engine** | ระบบแนะนำบทความที่เกี่ยวข้องกับบทความที่ผู้ใช้อ่าน           | 🟢 ต่ำ    |
| **Full-text Search**              | ระบบค้นหาเต็มรูปแบบใน dashboard                              | 🟢 ต่ำ    |
| **Mobile App**                    | แอปมือถือสำหรับดูข่าวและการแจ้งเตือน                         | 🟢 ต่ำ    |
| **Social Media Auto-share**       | แชร์บทความที่น่าสนใจไป Facebook, LinkedIn, Twitter อัตโนมัติ | 🟢 ต่อ    |
| **Weekly/Monthly Digest**         | สรุปข่าวประจำสัปดาห์/เดือน                                   | 🟢 ต่อ    |

---

### 💡 FUTURE IDEAS (ไอเดียในอนาคต)

| หัวข้อ                              | รายละเอียด                                                   |
| ----------------------------------- | ------------------------------------------------------------ |
| **Collaborative Filtering**         | แชร์บทความที่น่าสนใจระหว่างผู้ใช้ในมหาวิทยาลัย               |
| **Integration with LMS**            | เชื่อมต่อกับ Learning Management System สำหรับ faculty/staff |
| **News Curation Gamification**      | ระบบจัดอันดับผู้ที่ค้นหา/แชร์ข่าวบ่อยที่สุด                  |
| **Multi-language Support**          | รองรับภาษาอื่นๆ (English, Chinese, Japanese)                 |
| **Real-time Trend Detection**       | ตรวจจับ trending topics จากบทความใหม่                        |
| **API Gateway**                     | เปิด API สำหรับ external services ที่ต้องการใช้ข้อมูล        |
| **Machine Learning Model Training** | Train custom model เพื่อคัดกรองและจัดหมวดหมู่ข่าว            |
| **Video Summarization**             | สร้างสรุปจาก video content ถ้าข่าวมี video                   |
| **Voice News Reader**               | อ่านข่าวด้วยเสียง (TTS) สำหรับผู้ใช้ที่ต้องการ               |

---

## 📈 Timeline ภาพรวม

```
Past (เสร็จแล้ว)          Present (กำลังทำ)      Future (จะทำ)
|------------------------------|---------------------|------------------------|
2024-2026                     Q2 2026               Q3-Q4 2026
  ✓ Core Engine                🔄 Security           📋 Admin Dashboard
  ✓ Database                   3 2026               Q4 2026 - 2027
  ✓ Core Engine                🔄 Subscription       📋 Categorization
  ✓ Database (MySQL)           🔄 Email Worker       📋 Analytics
  ✓ Filtering (16 sources)     🔄 WP URL → LINE      📋 AI Summarization
  ✓ Telegram                                        📋 Recommendation
  ✓ LINE Notify                                     💡 Mobile App
  ✓ WordPress + Benefits
  ✓ Admin Dashboard
  ✓ Phase 0 Deployment
  ✓ Docker Local Dev
---

## 🎯 ปีการศึกษา 2569 - เป้าหมาย (2026)
 ✅
- ✅ Benefits Generation System
- ✅ LINE Integration
- ✅ Admin Dashboard (พัฒนา)
- ✅ Database Security Hardening

### Q3 (กรกฎาคม - กันยายน 2026) 🔄
- ✅ Phase 0 Deployment (28 ส.ค.)
- ✅ Docker Local Development
- ✅ WordPress Benefit Taxonomy (20 terms)
- 🔄 Subscription & Email System
- 🔄 WordPress URL to LINE

### Q4 (ตุลาคม - ธันวาคม 2026)
- 📋 Article Categorization
- 📋 Advanced Analytics
- 📋 Weekly/Monthly Digest
- 💡 AI-powered Summarizare
- 💡 Real-time Trend Detection

---
0: Foundation (เสร็จแล้ว) ✅
```

16 News Sources → Fetcher → Filter → MySQL → Telegram
↓ ↓
WordPress LINE
↓
Admin Dashboard

```

### Phase 1: Subscription (กำลังทำ) 🔄
```

16 News Sources → Fetcher → Filter → MySQL → Telegram
↓ ↓
WordPress LINE
↓
Admin Dashboard
↓
Subscription API → Email Worker
↓
Subscriber Notifications

```

### Phase 2: Intelligence (อนาคต) 💡
```

16 News Sources → Fetcher → Filter → MySQL → Telegram
↓ ↓
Category Benefits

### Phase 3: Intelligence (อนาคต) 💡

```
News Sources → Fetcher → Filter → MySQL → Telegram
                          ↓        ↓
                    Sentiment  Summarization (AI)
                          ↓        ↓
                    Admin Dashboard → WordPress
                          ↓
                    Recommendation Engine
                          ↓
                    Multi-channel + Mobile App
```

---

## 🔍 เส้นทางการพัฒนาจากเริ่มต้นจนถึงปัจจุบัน

### 1. Discovery Phase (Q3-Q4 2024)

- วิจัยแหล่งข้อมูลข่าวด้านนวัตกรรม
- วิเคราะห์ความต้องการของมหาวิทยาลัย
- กำหนด requirement พื้นฐาน

### 2. MVP Development (Q1 2025)

- พัฒนา Python script สำหรับดึงข่าว
- ติดตั้ง MySQL และสร้าง Stored Procedures
- เชื่อมต่อกับ Telegram Bot
- พัฒนา Filtering System

### 3. Multi-source Integration (Q2 2025)

- เชื่อมต่อกับ 10 แหล่งข้อมูลหลัก
- พัฒนา Round-robin scheduler
- ปรับปรุง duplicate detection

### 4. WordPress Integration (Q3 2025)

- พัฒนา WordPress REST API module
- สนับสนุน PTB Custom Fields
- ทดสอบและ deploy

### 5. Enhanced Intelligence (Q4 2025 - Q1 2026)

- พัฒนา Benefits Generation System (15 หมวดหมู่)
- อัปเดตรูปแบบข้อความ
- ปรับปรุงความปลอดภัย (Environment Variables)

### 6. Documentation9-03)

| Metric                  | ค่า    | เป้าหมาย Q4 |
| ----------------------- | ------ | ----------- |
| แหล่งข้อมูลที่เชื่อมต่อ | 16     | 20+         |
| บทความที่บันทึก/วัน     | ~1-3   | ~5-10       |
| Telegram Subscribers    | 1      | 10-50       |
| LINE Subscribers        | 1      | 20-100      |
| WordPress Posts         | 6,400+ | 10,000+     |
| Admin Dashboard Users   | 1      | 3-5         |
| Email Subscribers       | 0      | 50-10       |

## 📊 Metrics และ KPI

### ปัจจุบัน (2026-03-25)

| Metric                  | ค่า          | เป้าหมาย Q2 |
| ----------------------- | ------------ | ----------- |
| แหล่งข้อมูลที่เชื่อมต่อ | 10           | 10+         |
| บทความที่บันทึก/วัน     | ~1-3         | ~5-10       |
| Telegram Subscribers    | 1 (คุณหนึ่ง) | 10-50       |
| WordPress Sync Rate     | 100%         | 100%        |
| Uptime                  | >95%         | >99%        |

---

## 🚀 Next Actions (อย่างน้อย 1 อย่างจะเริ่มทำใน 7 วัน)

1. **Database Security Hardening** (ความสำคัญ: 🔴 สูง)
   - ย้าย DB credentials ไป .env
   - เข้ารหัส passwords ใน .env
   - ป้องกันการ expose credentials

2. **Admin Dashboard - POC** (ความสำคัญ: 🔴 สูง)
   - วาง wireframe
   - เลือก framework (Flask/Django/FastAPI)
   - เริ่ม develop MVP version

---

## 📞 การติดต่อ

- **ผู้ดูแล**: คุณหนึ่ง
- **ทีม**: สำนักวิทยบริการ มหาวิทยาลัยสงขลานครินทร์
- **วันที่สร้างเอกสาร**: 2026-03-25
- **อัปเดตล่าสุด**: 2026-03-25

---

_เอกสารนี้จะถูกอัปเดตอย่างสม่ำเสมอเพื่อติดตามความคืบหน้าของโครงการ 🦐_
