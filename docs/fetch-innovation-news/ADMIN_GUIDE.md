# Admin Guide

คู่มือนี้อธิบายการใช้งานหน้า admin ตามพฤติกรรมปัจจุบันของระบบ

## การเข้าใช้งาน

1. รัน backend:

```bash
node fetch-innovation-news/api/server.js
```

2. เปิด:

```text
http://localhost:3001
```

3. login ด้วย `ADMIN_USERNAME` และ `ADMIN_PASSWORD` จาก [`.env`](/d:/Downloads/Fetch-Innovation-News/Dev/.env)

## แท็บหลัก

### 1. Sources

ใช้สำหรับจัดการแหล่งข่าว

- เพิ่ม source ใหม่
- แก้ไข source เดิม
- เปิด/ปิด source
- ลบ source ที่ยังไม่มีบทความหรือ fetch log ผูกอยู่
- ดู runtime warning ว่า slug นั้นมี fetcher รองรับหรือไม่
- ทดสอบการดึงแบบ read-only ราย source ก่อนเปิดใช้งานจริง

ข้อสำคัญ:

- `slug` ต้องตรงกับ runtime fetcher ที่ระบบรองรับ
- `fetch_method` ต้องสอดคล้องกับ slug นั้น
- source ที่เป็น `rss` จะถูกดึงด้วย generic RSS fetcher ตาม `source_url` จริงในฐานข้อมูล
- source ที่เป็น `api` จะถูกดึงแบบ generic ได้ ถ้า `source_url` เป็น WordPress REST endpoint เช่น `/wp-json/wp/v2/posts`
- ใน dropdown ของหน้า admin จะแสดงรูปแบบยอดนิยมอื่นด้วย แต่จะเลือกได้เฉพาะรูปแบบที่ระบบรองรับจริงตอนนี้
- source ใหม่จะถูกสร้างเป็น `Inactive` เสมอ และควรทดสอบให้ผ่านก่อนค่อยเปิดใช้งาน
- source จะเปิดใช้งานได้ก็ต่อเมื่อผลทดสอบล่าสุดเป็น `passed` และพบข่าวอย่างน้อย 1 รายการ
- ถ้าแก้ `slug`, `source_url` หรือ `fetch_method` ผลทดสอบเดิมจะถูกรีเซ็ต และ source จะกลับเป็น `Inactive`
- ในฟอร์มเพิ่ม/แก้ไข source มีปุ่ม `Info` ข้างช่อง `วิธีดึงข้อมูล` สำหรับดูรูปแบบข้อมูลที่ระบบรองรับ พร้อมตัวอย่าง URL ของแต่ละแบบ

ชนิดการรองรับที่แสดงบนการ์ด source:

- badge นี้อิง “วิธีที่ runtime จะลองใช้ก่อน” ไม่ใช่แค่การมี fallback อยู่ในโค้ด

- `Generic RSS`
  ระบบใช้ตัวดึง RSS กลางของโปรเจกต์อ่านจาก `source_url` โดยตรง จึงเพิ่ม source ใหม่ได้โดยไม่ต้องเขียน fetcher รายเว็บ ถ้า feed เป็นมาตรฐานและ URL ถูกต้อง
- `Generic WP API`
  ระบบใช้ตัวดึง WordPress REST API กลางของโปรเจกต์ เช่น `/wp-json/wp/v2/posts` จึงเพิ่ม source ใหม่ได้โดยไม่ต้องเขียน fetcher รายเว็บ
- `Custom HTML Fetcher`
  แหล่งนี้ต้องใช้โค้ด Python เฉพาะเว็บเพื่อ parse HTML เพราะโครงสร้างหน้าเว็บไม่ใช่มาตรฐานกลาง แอดมินต้องมี fetcher รองรับก่อนจึงจะใช้งานจริงได้
- `Custom API Fetcher`
  แหล่งนี้ใช้ API เฉพาะทางที่โครงสร้างไม่ตรงกับ generic WordPress API จึงต้องมี fetcher เฉพาะใน Python เพื่อ map field และจัดการ logic ของแหล่งนั้น
- `Custom RSS Fetcher`
  แหล่งนี้ใช้ RSS แต่ยังมีเหตุผลให้ต้องใช้ fetcher เฉพาะ เช่น feed หลายชุดรวมกัน, ต้องจัดลำดับ/คัดกรองแบบพิเศษ, หรือมี parsing เพิ่มเติมที่ generic RSS ทำแทนไม่ได้

สถานะการทดสอบบนการ์ด source:

- `Pending`
  ยังไม่เคยทดสอบ หรือเพิ่งแก้ config จนต้องทดสอบใหม่
- `Passed`
  ทดสอบล่าสุดผ่าน และพบข่าวอย่างน้อย 1 รายการ สามารถเปิดใช้งานได้
- `Failed`
  ทดสอบล่าสุดไม่ผ่าน หรือไม่พบบทความที่เข้าเกณฑ์ จึงยังไม่ควรเปิดใช้งาน

### 2. Articles

ใช้สำหรับดูบทความที่ถูกบันทึกใน MySQL

ข้อมูลสำคัญที่แสดง:

- แหล่งข่าว
- หัวข้อ
- วันที่ต้นทาง
- วันที่เข้าระบบ
- สถานะการส่ง LINE

ตัวกรองสถานะมี 3 ค่า:

- `ทุกสถานะ`
- `ส่งแล้ว`
- `ยังไม่ส่ง`

โดยหน้าเว็บอิงจาก `line_status` เป็นหลัก

### 3. Logs

ใช้สำหรับดูผลการดึงต่อรอบ

คอลัมน์หลัก:

- `พบ`
- `ใหม่`
- `บันทึก MySQL`
- `ส่ง Telegram`
- `ส่ง WP`
- `ส่ง LINE`
- `สถานะ`
- `ใช้เวลา`

ความหมายของ `ใช้เวลา` คือเวลารวมของรอบนั้น ตั้งแต่เริ่ม fetch จนจบ flow ของรอบ

### 4. Audit Log

ใช้สำหรับตรวจสอบย้อนหลังว่า admin ทำอะไรไปบ้าง

ตัวอย่าง action ที่ถูกบันทึก:

- login
- logout
- create source
- update source
- delete source
- toggle source
- run now
- run now failed

## ปุ่ม `รันตอนนี้`

ปุ่มนี้จะสั่งให้ backend เรียก [fetch-innovation-news-mysql.py](/d:/Downloads/Fetch-Innovation-News/Dev/fetch-innovation-news-mysql.py) ทันทีหนึ่งรอบ

พฤติกรรม:

- กันการรันซ้อน ถ้ามีรอบที่กำลังทำงานอยู่แล้ว
- เขียน audit log ทุกครั้ง
- อ่านค่า `DRY_RUN` และ `ENABLE_*` จาก env ตามปกติ

## สถานะที่ควรรู้

### บทความ

- บทความในหน้า `Articles` อิง `line_status`
- dashboard ที่นับข่าวส่งแล้ว ก็อิง `line_status='sent'`

### Logs

- `mysql_status` บอกว่าบันทึกลงฐานสำเร็จหรือไม่
- `telegram_status` บอกผลการส่ง Telegram
- `wordpress_status` บอกผลการ sync WordPress
- `line_status` บอกผลการส่ง LINE

ถ้า WordPress ไม่ได้ `created` ระบบจะไม่ส่ง LINE

## การทดสอบบน local

ถ้าต้องการทดสอบโดยไม่ยิง integration ออกจริง ให้ตั้ง:

```env
DRY_RUN=1
```

## Generic JSON API

ตอนนี้ระบบรองรับ `Generic JSON API` แล้ว โดยใช้ได้กับ public JSON endpoint ที่มี URL เดียว และต้องกรอก mapping แบบ dot-path ให้ครบ

ฟิลด์ที่ต้องกรอก:

- `items_path`
  path ไปยัง array ของรายการข่าว เช่น `data.items`
- `title_field`
  path ของหัวข้อข่าวในแต่ละ item เช่น `title`
- `link_field`
  path ของลิงก์ข่าว เช่น `url`
- `date_field`
  path ของวันที่เผยแพร่ เช่น `published_at`
- `summary_field`
  ไม่บังคับ ถ้าเว้นว่างระบบจะใช้ title แทน

ตัวอย่าง:

```text
URL: https://example.com/api/news
items_path: data.items
title_field: title
link_field: url
date_field: published_at
summary_field: summary
```

ข้อจำกัดรอบแรก:

- รองรับเฉพาะ endpoint เดียวต่อ source
- ต้องเป็น public JSON API ที่ไม่ต้อง auth
- `items_path` ต้องชี้ไปยัง array จริง
- ถ้าแก้ `source_url`, `fetch_method`, `api_variant` หรือ mapping ระบบจะรีเซ็ตผลทดสอบและบังคับให้ทดสอบใหม่ก่อนเปิดใช้งาน

หรือปิดเฉพาะตัวด้วย:

```env
ENABLE_TELEGRAM=0
ENABLE_WORDPRESS=0
ENABLE_LINE=0
```

## Dashboard

Dashboard เป็นหน้าอ่านสถิติสำหรับผู้ดูแลระบบเท่านั้น ไม่สั่ง fetch ข่าว ไม่เขียนข้อมูลลง MySQL และไม่เปลี่ยน flow การส่ง Telegram, WordPress หรือ LINE

หน้า Dashboard อ่านข้อมูลจาก endpoint:

```text
GET /api/dashboard/overview
```

ข้อมูลที่แสดง:

- ข่าวทั้งหมด ข่าววันนี้ และข่าวใน 7 วันล่าสุด
- จำนวนข่าวที่ส่ง LINE สำเร็จ และจำนวนที่ส่ง Telegram/WordPress สำเร็จสะสม
- จำนวน fetch ใน 24 ชั่วโมงล่าสุด พร้อม success rate
- จำนวน source ทั้งหมด active/inactive และ source ที่ควรตรวจสอบ
- แนวโน้ม 7 วันของจำนวนข่าวที่บันทึกและ fetch ที่สำเร็จ
- ข้อควรตรวจสอบสำหรับ admin เช่น source ที่ health ไม่ปกติหรือ fetch/delivery มี issue ล่าสุด โดยยุบข้อมูล issue ล่าสุดไว้ในกล่องนี้ และเรียงจากเวลาใหม่ไปเก่า
- ตาราง Source Health จากสถานะ active, ผลทดสอบ source ล่าสุด, fetch log ล่าสุด และ success rate 7 วัน โดยเรียงตาม source id จากน้อยไปมาก และแสดง pagination ครั้งละ 20 รายการเสมอเมื่อมีข้อมูล

ความหมาย Health:

- `ปกติ`: source active และไม่พบสัญญาณผิดปกติล่าสุด
- `ควรตรวจ`: fetch ล่าสุดเป็น partial
- `ผิดพลาด`: fetch ล่าสุดเป็น failed/error
- `รอทดสอบ`: ผลทดสอบ source ล่าสุดยังไม่ passed
- `ยังไม่ fetch`: source active แต่ยังไม่มีประวัติ fetch
- `Inactive`: source ถูกปิดไว้และไม่ถูกวน fetch

Dashboard ใช้ schema เดิมทั้งหมด จึงไม่ต้องรัน migration เพิ่ม

## หมายเหตุด้านความปลอดภัย

- เปลี่ยน `ADMIN_PASSWORD` และ `ADMIN_SESSION_SECRET` ก่อนใช้จริง
- ถ้าเป็น staging หรือ production ควรวาง reverse proxy และจำกัดการเข้าถึงเครือข่ายเพิ่มเติม
