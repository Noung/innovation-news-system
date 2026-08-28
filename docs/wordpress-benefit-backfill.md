# WordPress benefit taxonomy backfill

เอกสารนี้ใช้สำหรับวางแผนเติม taxonomy `organization_benefit`
ให้โพสต์ `innovation-tip` เดิมที่ยังไม่มี term โดยแบ่งงานเป็นขั้นแยกกัน
เพื่อลดความเสี่ยงต่อระบบ PROD

## ขอบเขตขั้นที่ 1: PLAN เท่านั้น

ไฟล์ `scripts/plan-wordpress-benefit-backfill.py`:

- ส่งเฉพาะ HTTP `GET` ไปยัง WordPress
- ไม่สร้างหรือแก้ post/term
- ไม่เรียก LINE, Telegram หรือ cron ดึงข่าว
- ไม่เขียนฐานข้อมูล MySQL
- ตรวจว่า CPT, taxonomy, REST base และ controlled terms ทั้ง 20 รายการตรงกัน
- อ่านโพสต์ `innovation-tip` ที่เผยแพร่แล้วทุกหน้า
- ข้ามโพสต์ที่มี taxonomy อยู่แล้ว
- สกัดหมวดเดิมจากส่วน “ประโยชน์ต่อองค์กร”
- ตัดส่วนหมวดเดิมออกก่อนส่ง title/summary เข้า classifier
- แยกผลเป็น `auto_ready`, `review` และ `skip_existing`
- สร้าง JSON, CSV และ SHA256 สำหรับตรวจสอบก่อนใช้ APPLY แยก

PLAN ไม่ส่งคำสั่งแก้ไข WordPress แม้จะติดตั้งเครื่องมือ APPLY อยู่แล้ว

## ไฟล์ที่ต้องนำขึ้น PROD

```text
scripts/benefit_classifier.py
scripts/plan-wordpress-benefit-backfill.py
scripts/apply-wordpress-benefit-backfill.py
tests/test_wordpress_benefit_backfill.py
tests/test_wordpress_benefit_backfill_apply.py
tests/test_wordpress_benefit_backfill_endpoint.py
```

การเพิ่มไฟล์ backfill เหล่านี้ไม่เปลี่ยนการทำงานของ
`fetch-innovation-news-mysql.py` และ cron เดิม

แพ็กเกจ release แยกเป็นสองไฟล์เพื่อให้อัปเดตทีละส่วน:

```text
dist/innovation-tip-benefit-taxonomy-1.2.0.zip
dist/wordpress-benefit-backfill-tools-1.1.0.zip
```

ให้ใช้ชื่อไฟล์ที่มีเลขเวอร์ชันเท่านั้น ไม่ใช้
`dist/innovation-tip-benefit-taxonomy.zip` ซึ่งอาจเป็น artifact รุ่นเก่าจาก
การพัฒนาก่อนหน้า ตรวจ SHA256 จาก release manifest ทุกครั้งก่อนแตกไฟล์
แพ็กเกจ tools มีสำเนา source ของปลั๊กอินใน `wordpress-plugin/` สำหรับ
PHP lint และ contract tests เท่านั้น ส่วนปลั๊กอินที่ WordPress ใช้งานจริง
ต้องอัปเดตจาก ZIP แรกใน `wp-content/plugins/`

## ตรวจสอบก่อนรัน

ทำงานจาก workspace:

```bash
cd /home/kittisak/.openclaw/workspace

python3 -m py_compile \
  scripts/benefit_classifier.py \
  scripts/plan-wordpress-benefit-backfill.py \
  scripts/apply-wordpress-benefit-backfill.py

python3 -m unittest discover -s tests -v
```

ผลที่คาดหวังคือ `OK` และไม่มี syntax error

## สร้างแผนแบบอ่านอย่างเดียว

ระบุ `.env` ให้ชัดเจนเพื่อไม่ให้สคริปต์เดาว่าจะใช้ไฟล์ใด:

```bash
python3 scripts/plan-wordpress-benefit-backfill.py \
  --env-file /home/kittisak/.openclaw/workspace/.env \
  --output /home/kittisak/.openclaw/workspace/backfill-plans/benefits-plan-20260724.json
```

จาก crontab ปัจจุบัน cron เรียก Python โดยตรง และ fetcher ตรวจ
workspace-root `.env` ก่อน `scripts/.env` จึงใช้ workspace-root ในตัวอย่างนี้
หากสภาพแวดล้อม cron กำหนด `INNOVATION_NEWS_ENV_FILE` ไว้ต่างหาก
ให้ใช้ path เดียวกับค่านั้นแทน ทั้งสองกรณีควรตรวจบรรทัด `WordPress API:`
ที่ planner แสดงว่าชี้ไปยังเว็บไซต์ที่ถูกต้องก่อนใช้รายงาน

สคริปต์สร้างโฟลเดอร์ปลายทางให้เอง หากชื่อไฟล์มีอยู่แล้วจะหยุดและไม่เขียนทับ

ผลลัพธ์มีสามไฟล์:

```text
backfill-plans/benefits-plan-20260724.json
backfill-plans/benefits-plan-20260724.csv
backfill-plans/benefits-plan-20260724.sha256
```

ข้อความสรุปที่ปลอดภัยสำหรับส่งกลับมาตรวจร่วมกัน:

```text
Plan summary: wp_total=..., included=..., auto_ready=..., review=..., skip_existing=...
```

ไม่ควรส่ง `.env`, Application Password หรือคัดลอก manifest ทั้งไฟล์ลงช่องสนทนา
ให้ส่งเฉพาะบรรทัดสรุปก่อน หากต้องตรวจรายละเอียดให้ใช้ CSV เฉพาะแถว
`review` โดยปิดข้อมูลที่ไม่ต้องการเปิดเผย

## ความหมายของสถานะ

- `auto_ready`: พบหมวดเดิมครบ 3 รายการเท่านั้น
- `review`: หมวดเดิมมากกว่า/น้อยกว่า 3 รายการ, ใช้ fallback,
  มีเพียงชื่อเรื่อง, คะแนนลำดับตัดสินเสมอกัน หรือเป็นข้อเสนอจาก
  classifier โดยไม่มีหมวดเดิม รวมถึงกรณีหมวดเดิมใน `ptb_meta`
  และ `content` ขัดแย้งกัน
- `skip_existing`: โพสต์มี taxonomy อยู่แล้วและ planner จะไม่เสนอให้แก้

## ขั้นที่ 2: APPLY แบบ fail-closed

ไฟล์ `scripts/apply-wordpress-benefit-backfill.py` มีค่าเริ่มต้นเป็น
PREFLIGHT แบบอ่านอย่างเดียว ต้องระบุ `--execute` จึงจะส่ง WordPress POST

ข้อกำหนดสำคัญ:

- รับเฉพาะ JSON จาก PLAN schema 2 พร้อม `.sha256` ที่ตรงกัน
- PLAN ต้องครบ ไม่ใช่ preview และมีอายุไม่เกิน 24 ชั่วโมง
- รับเฉพาะ `auto_ready`; ปฏิเสธ `review` และ `skip_existing`
- ตรวจ env/site/schema/controlled terms และ term IDs ซ้ำ
- ตรวจ taxonomy ยังว่าง, `modified_gmt`, content hash และหมวดเดิม
- ต้องใช้ปลั๊กอิน `Innovation Tip Benefit Taxonomy` เวอร์ชัน 1.2.0
  และ guarded contract 2
- ตรวจ capability และ server-owned state fingerprint ผ่าน endpoint
  แบบอ่านอย่างเดียวก่อนประกาศว่าโพสต์ `READY`
- POST เฉพาะ custom endpoint
  `/wp-json/oar-innovation/v1/benefit-backfill/{id}` ไม่ใช้ Core post update
- WordPress ตรวจ `modified_gmt`, taxonomy เดิม และ fingerprint ของ
  title/content/excerpt/PTB meta ซ้ำภายใน transaction ก่อนกำหนด 3 terms
- ใช้ InnoDB, SERIALIZABLE transaction, row/range locks และตรวจ controlled
  vocabulary ครบ 20 terms ซ้ำก่อนเขียน
- ไม่สร้าง post หรือ term และไม่ retry POST ที่ผลลัพธ์อาจกำกวม
- GET ตรวจผลผ่านทั้ง Core REST และ guarded DB state หลัง POST
- แยก `guard_rejected` (เช่น HTTP 409) ออกจากผลเครือข่ายกำกวม
  และหยุด batch ทันทีทั้งสองกรณี
- เขียน audit JSON พร้อม SHA256 โดยไม่บันทึกรหัสผ่าน

PREFLIGHT canary หนึ่งรายการ:

```bash
python3 scripts/apply-wordpress-benefit-backfill.py \
  --env-file /home/kittisak/.openclaw/workspace/.env \
  --plan /home/kittisak/.openclaw/workspace/backfill-plans/benefits-full.json \
  --post-id 123
```

ผลต้องลงท้ายด้วย:

```text
Result: PREFLIGHT PASS (no WordPress changes)
```

การเขียนจริงต้องเพิ่ม `--execute`, `--confirm-run-id` ที่ตรงกับ PLAN
และ `--audit-output` เป็นชื่อไฟล์ใหม่ ห้ามเริ่มด้วย `--all-auto-ready`
จนกว่า canary 1 รายการจะผ่านและตรวจใน WordPress แล้ว

เครื่องมือไม่ใช้ Core post update เนื่องจากไม่มี compare-and-set สำหรับกรณีนี้
ปลั๊กอิน 1.2.0 จึงเพิ่ม guarded endpoint ที่เปลี่ยนเฉพาะ term relationships
หลัง expected state ตรงกันเท่านั้น อย่างไรก็ตาม WordPress term hooks ของ
ปลั๊กอินอื่นอาจมีผลภายนอกฐานข้อมูล เช่น ส่งอีเมลหรือเรียก API ซึ่ง transaction
ย้อนกลับไม่ได้ จึงยังต้องเริ่มด้วย canary หนึ่งรายการในช่วงที่ไม่มีผู้ดูแล
กำลังแก้โพสต์เก่า และตรวจ log/ผลกระทบอื่นร่วมด้วย

หาก APPLY ล้มเหลวหรือผลเครือข่ายกำกวม จะคงไฟล์ `.apply.lock` ไว้เพื่อ
บังคับให้ตรวจ audit ก่อนดำเนินการต่อ ห้ามลบ lock หรือรันซ้ำอัตโนมัติ
เครื่องมือนี้ไม่ทำ rollback อัตโนมัติ เพราะอาจทับการแก้ไขที่เกิดภายหลัง
หาก canary ต้องย้อนกลับ ให้ตรวจ audit และนำ 3 terms ออกจากโพสต์นั้น
ผ่าน WordPress Admin อย่างมีผู้ตรวจสอบ
