# WordPress Benefit Manual Backfill Worklist

เอกสารนี้ใช้สำหรับสร้างรายการตรวจสอบงาน Backfill แบบ Manual จาก PLAN JSON
ที่สร้างและตรวจ checksum แล้ว เหมาะสำหรับ Production ที่ยังใช้ PHP 5.6 และ
ปลั๊กอิน `Innovation Tip Benefit Taxonomy` เวอร์ชัน 1.1.4

## ขอบเขตความปลอดภัย

สคริปต์ `scripts/create-wordpress-benefit-manual-worklist.py`:

- อ่านเฉพาะ PLAN JSON และไฟล์ `.sha256` ในเครื่อง
- ไม่อ่าน `.env` หรือ Application Password
- ไม่มี HTTP request และไม่แก้ไข WordPress
- รับเฉพาะ full plan, schema 2, strict classifier และ controlled terms 20 รายการ
- ปฏิเสธ PLAN ที่เก่ากว่า 24 ชั่วโมงโดยค่าเริ่มต้น
- ส่งออกเฉพาะ `auto_ready`
- ตรวจว่าทุกรายการยังมี taxonomy ว่างและมีหมวดเดิมครบ 3 รายการใน PLAN
- ปฏิเสธ plan ที่ถูกตัดทอน, checksum ผิด, site ผิด หรือจำนวนไม่ตรง
- สร้าง CSV แบบ UTF-8 BOM และป้องกัน CSV formula injection
- ไม่เขียนทับไฟล์เดิมและสร้าง checksum ให้ CSV เริ่มต้น

CSV นี้เป็น **checklist สำหรับเจ้าหน้าที่เท่านั้น** ห้ามนำไป import เข้า
WordPress หรือใช้เป็น input ของเครื่องมือ APPLY

## สร้าง PLAN ใหม่แบบอ่านอย่างเดียว

ห้ามใช้ PLAN เก่าข้ามวันกับงาน Manual ให้สร้าง full plan ใหม่ก่อน โดยคำสั่งนี้
เรียก WordPress ด้วย GET เท่านั้น:

```bash
cd /home/kittisak/.openclaw/workspace

python3 scripts/plan-wordpress-benefit-backfill.py \
  --env-file /home/kittisak/.openclaw/workspace/.env \
  --output /home/kittisak/.openclaw/workspace/backfill-plans/benefits-full-manual-20260727.json
```

ตรวจ checksum:

```bash
cd /home/kittisak/.openclaw/workspace/backfill-plans
sha256sum -c benefits-full-manual-20260727.sha256
```

ตรวจ `Plan summary` ก่อน หากจำนวน `auto_ready` ไม่ใช่ 23 ให้หยุดและตรวจ
ความเปลี่ยนแปลงก่อน ไม่แก้ `--expected-count` ให้ผ่านโดยไม่ได้ตรวจสอบ

## สร้างรายการ 23 auto-ready

รันจาก root ของ workspace บน PROD:

```bash
cd /home/kittisak/.openclaw/workspace

python3 scripts/create-wordpress-benefit-manual-worklist.py \
  --plan /home/kittisak/.openclaw/workspace/backfill-plans/benefits-full-manual-20260727.json \
  --output /home/kittisak/.openclaw/workspace/manual-backfill/benefits-auto-ready-manual-20260727.csv \
  --expected-api-url https://innovation.oas.psu.ac.th/wp-json/wp/v2 \
  --expected-count 23 \
  --batch-size 5 \
  --max-plan-age-hours 24
```

คำสั่งนี้ต้องแสดง:

```text
Mode: MANUAL WORKLIST (offline; no WordPress requests)
Auto-ready rows: 23
Batches: 5 (up to 5 rows each)
```

ตรวจ checksum ของ CSV เริ่มต้น:

```bash
cd /home/kittisak/.openclaw/workspace/manual-backfill
sha256sum -c benefits-auto-ready-manual-20260727.sha256
```

ผลที่ถูกต้อง:

```text
benefits-auto-ready-manual-20260727.csv: OK
```

หลังตรวจ checksum ให้เก็บ CSV ต้นฉบับไว้ และทำสำเนาสำหรับบันทึกความคืบหน้า
เพราะ checksum จะไม่ตรงตามปกติเมื่อมีการกรอกข้อมูลเพิ่ม:

```bash
cp -p \
  benefits-auto-ready-manual-20260727.csv \
  benefits-auto-ready-manual-20260727-working.csv
```

## วิธีทำงานทีละชุด

เริ่มเฉพาะ `batch=1` จำนวน 5 รายการ:

1. เปลี่ยน `workflow_status` จาก `pending` เป็น `in_review`
2. เปิด `rest_verification_url` ก่อนหน้าแก้ไข และตรวจว่า:
   - `organization-benefits` ยังเป็น `[]`
   - `modified_gmt` ตรงกับ `observed_modified_gmt` ใน CSV
   - หากค่าใดไม่ตรง ให้ใช้สถานะ `blocked` และไม่แก้โพสต์นั้น
3. เปิด `wp_admin_edit_url`
4. ตรวจว่าช่อง **ประโยชน์ต่อองค์กร** ยังไม่มี taxonomy
   - หากมี taxonomy อยู่แล้ว ให้หยุดรายการนั้น ใช้สถานะ `blocked`
   - ห้ามลบหรือเขียนทับหมวดที่บุคคลอื่นเพิ่มภายหลัง PLAN
5. เปรียบเทียบข้อความ “ประโยชน์ต่อองค์กร” เดิมกับ `benefit_1` ถึง
   `benefit_3`
6. เลือก taxonomy ทั้ง 3 รายการตามชื่อที่ระบุ
7. กด **Update** โดยไม่เปลี่ยนชื่อเรื่อง เนื้อหา ผู้เขียน หรือสถานะโพสต์
8. เปลี่ยน `workflow_status` เป็น `updated_in_wp` และกรอก `wp_updated_at`
9. เปิด `rest_verification_url` อีกครั้ง
10. ยืนยันว่า `organization-benefits` มี term ID ตรงกับ
   `benefit_1_term_id` ถึง `benefit_3_term_id` ครบ 3 ค่า
11. กรอก `rest_verified=yes`, `verified_at`, `reviewer` และเปลี่ยน
    `workflow_status` เป็น `verified`

ค่าที่ใช้ใน `workflow_status`:

```text
pending
in_review
updated_in_wp
verified
blocked
```

ให้ตรวจผลหน้าเว็บและหน้าค้นหาหลังจบ batch แรก ก่อนเริ่ม batch ถัดไป

ระหว่างดำเนินงาน Manual ห้ามรันเครื่องมือ APPLY หรือกระบวนการ Backfill อื่น
กับ Post IDs ชุดเดียวกัน

## เมื่อสคริปต์หยุดด้วย ERROR

สคริปต์ถูกออกแบบให้หยุดโดยไม่สร้าง CSV บางส่วน หาก checksum, site, จำนวน
โพสต์ หรือ controlled terms ไม่ตรง ห้ามแก้ JSON หรือ `.sha256` ด้วยมือ
ให้ตรวจสาเหตุหรือสร้าง PLAN แบบ read-only ใหม่แทน
