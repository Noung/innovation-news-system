# File Hygiene Audit

วันที่ตรวจ: 2026-08-28  
ขอบเขต: local replica ที่ `C:\Users\Kittisak\Downloads\innovation_news`  
โหมด: read-only audit — ยังไม่มีการลบ ย้าย หรือแก้ไขไฟล์ runtime

## สรุป

- พบไฟล์ทั้งหมด 2,812 ไฟล์ ขนาดรวมประมาณ 21.81 MiB
- `fetch-innovation-news/api/node_modules` มี 2,528 ไฟล์ ขนาด 17.48 MiB และสร้างใหม่จาก lockfile ได้
- Python `__pycache__` สองตำแหน่งรวมประมาณ 0.81 MiB
- log เก่ามี 6 ไฟล์ รวมประมาณ 1.03 MiB
- backup ของ fetcher มี 4 ไฟล์ รวมประมาณ 0.31 MiB และแบ่งเป็นไฟล์ซ้ำแบบ byte-for-byte สองคู่
- `dist` มี release artifact 14 ไฟล์ รวมประมาณ 0.22 MiB หลายเวอร์ชัน
- secret audit พบ credential copy เฉพาะใน `scripts/.env`; ไม่แสดงค่าความลับในรายงานนี้
- repository ที่ใช้งานได้จริงอยู่ใน `fetch-innovation-news/.git`; `.git` ที่ root ไม่สมบูรณ์และมีเพียง `info/exclude`
- ยังไม่มีการเปลี่ยน PROD และยังไม่มีการลบไฟล์ใด

## KEEP

เก็บไว้ใน working source และควรอยู่ใน repository หลังตรวจ secret:

- `scripts/fetch-innovation-news-mysql.py`
- `scripts/wordpress_integration.py`
- `scripts/line_integration.py`
- `scripts/run-fetch-innovation-news.sh` และ `.ps1`
- `scripts/install-innovation-news-cron.sh`
- `scripts/trigger-ksstat.sh`
- เครื่องมือ backfill และ benefit classifier ใน `scripts/`
- source code ใน `fetch-innovation-news/api`, `public`, `assets` และไฟล์ package lock
- `tests/`
- `docs/`
- `wordpress-plugin/` ในฐานะ source/reference โดยต้องระบุชัดว่ารุ่น 1.2.0 ต้องใช้ PHP 7.2 และห้ามลงบน PROD PHP 5.6
- `.env.example` และ `scripts/.env.example`
- `sql/migrations/README.md`

## QUARANTINE

จำเป็นต่อเครื่องบางเครื่อง แต่ห้าม commit หรือส่งต่อพร้อม source archive:

| รายการ | เหตุผล | ข้อเสนอ |
|---|---|---|
| `.env` | canonical runtime secrets | เก็บเฉพาะเครื่องที่ได้รับอนุญาต และใช้ secret manager สำหรับย้ายเครื่อง |
| `scripts/.env` | legacy credential copy; secret audit พบ 6 รายการ | ห้ามลบทันทีจนกว่ายืนยันว่า PROD ใช้ root `.env`; ถอนหลัง canary/rollback window |
| `innovation_news.sql` | database dump อาจมีข้อมูลหรือ credential ในอดีต | ห้าม push จนผ่าน content review; เก็บใน encrypted backup หากต้องใช้ |
| `fetch-innovation-news/innovation_news.sql` | tracked schema/dump และ Git history เคยมี source credential | ต้องแยก schema ออกจาก data และจัดการ Git history ตามกระบวนการอนุมัติ |
| `fetch-innovation-news/.git` | เป็น repository จริงและ history ต้องได้รับการตรวจ secret | เก็บเฉพาะ private repository; ห้ามเผยแพร่ก่อน rotate/revoke credential เดิม |

## ARCHIVE

ไม่ใช่ runtime dependency แต่มีคุณค่าด้าน rollback/หลักฐาน ควรย้ายออกจาก working tree ไปยัง archive ที่มี checksum:

- `logs/` ทั้งหมด: เก็บเฉพาะช่วง retention ที่องค์กรกำหนด แล้วลบหรือบีบอัดอย่างปลอดภัย
- backup fetcher 4 ไฟล์:
  - `scripts/fetch-innovation-news-mysql.py.backup.1774692955586`
  - `scripts/fetch-innovation-news-mysql.py.backup.1774692987982`
  - `scripts/fetch-innovation-news-mysql.py.bak.20260413_091322`
  - `scripts/fetch-innovation-news-mysql.py.bak.20260413_091357`
- `dist/` รุ่นเก่า: เก็บ release ที่เคยติดตั้งจริงพร้อม checksum และบันทึก compatibility; ย้ายรุ่นทดลองที่เหลือไป archive
- เอกสารวิเคราะห์ย้อนหลัง เช่น `docs/fetch-innovation-news-bak190369-analysis.md` ควรคงไว้ใน documentation archive ไม่ควรลบโดยไม่มีการทบทวน

## DELETE CANDIDATE

รายการต่อไปนี้สร้างใหม่ได้หรือเป็นสำเนาซ้ำ แต่ยังต้องขออนุมัติก่อนลบ:

| รายการ | ขนาดโดยประมาณ | เหตุผล |
|---|---:|---|
| `fetch-innovation-news/api/node_modules/` | 17.48 MiB | สร้างใหม่ด้วย reviewed `npm ci`; ถูก ignore โดย nested Git แล้ว |
| `scripts/__pycache__/` | 0.59 MiB | Python bytecode สร้างใหม่ได้ |
| `tests/__pycache__/` | 0.22 MiB | Python bytecode สร้างใหม่ได้ |
| log/cache ที่มีขนาด 0 byte | ต่ำมาก | ไม่มีข้อมูล |
| `dist/innovation-tip-benefit-taxonomy.zip` | 11 KB | ซ้ำ byte-for-byte กับรุ่น 1.1.4 |
| backup หนึ่งไฟล์จากแต่ละคู่ที่ซ้ำกัน | 0.15 MiB | ไม่เพิ่มข้อมูลสำหรับ rollback |

พื้นที่ที่คืนได้จาก generated files เพียงอย่างเดียวประมาณ 18.29 MiB โดยไม่รวม log, archive และ SQL dump

## REVIEW ก่อนตัดสินใจ

### 1. Repository topology

root มี `.git/info/exclude` แต่ไม่มี repository metadata ครบ จึงทำให้ `git status` ที่ root ล้มเหลว ขณะที่ `fetch-innovation-news/` เป็น Git repository จริง ต้องเลือกระหว่าง:

1. คง nested repository และเพิ่ม repository สำหรับส่วน `scripts/docs/tests/wordpress-plugin`; หรือ
2. ทำ repository เดียวที่ root หลังสร้าง backup และวางแผนรักษา history ของ repository เดิม

ห้ามลบ `.git` ใด ๆ ก่อนตัดสินใจและสำรอง history

### 2. SQL dumps สองตำแหน่ง

ไฟล์ SQL สองชุดไม่เหมือนกัน และมีความต่างจำนวนมาก จึงไม่ใช่ duplicate ที่ลบได้ทันที ต้องจำแนกว่าไฟล์ใดเป็น:

- schema baseline
- sanitized sample data
- PROD dump
- historical artifact

เป้าหมายระยะถัดไปควรเหลือ migration/schema ที่ตรวจสอบได้ และไม่นำข้อมูล PROD เข้า Git

### 3. Retired scripts

ยังไม่ควรลบไฟล์ต่อไปนี้ทันที:

- `master-deploy-fix.sh`
- `quick-deploy.sh`
- `fix-openclaw-path.sh`
- `fix-telegram-prod.sh`
- `test-telegram-prod.sh`
- `update-wp-env.sh`
- `thai_file_encrypt.py`

ไฟล์เหล่านี้ถูกเปลี่ยนให้ fail closed แล้ว และบางไฟล์ยังถูก `deploy-to-prod.sh` หรือ test อ้างอิงเพื่อแทนที่สำเนาอันตรายบน PROD การลบต้องทำพร้อมแก้ deployment manifest, tests และ retirement runbook

### 4. Admin documents ใน nested repository

ไฟล์ `PM2_SETUP.md`, `QUICK_DEPLOY.md` และ `TELEGRAM_FIX.md` ต้องตรวจว่าเป็นเอกสารเก่าหรือเอกสารปัจจุบัน ก่อนรวม/ย้ายไป `docs/archive/`; ปัจจุบันยังไม่ควรลบเพียงเพราะชื่อดูเก่า

### 5. Release artifacts

`dist/` มี WordPress plugin หลายรุ่นและ backfill tools หลายชุด ควรสร้าง release inventory ระบุ:

- เวอร์ชัน
- SHA-256
- PHP/WordPress compatibility
- เคยติดตั้ง PROD หรือไม่
- superseded by รุ่นใด

โดยเฉพาะ plugin 1.2.0 ใช้กับ PHP 5.6 ไม่ได้ จึงต้องไม่ตั้งชื่อหรือวางตำแหน่งให้ดูเหมือนเป็น PROD-ready package

## Exact duplicates ที่ยืนยันแล้ว

- `dist/innovation-tip-benefit-taxonomy.zip` เท่ากับ `dist/innovation-tip-benefit-taxonomy-1.1.4.zip`
- backup timestamp `1774692955586` เท่ากับ `1774692987982`
- backup timestamp `20260413_091322` เท่ากับ `20260413_091357`
- cache/log ว่าง 4 ไฟล์มี hash ของ empty file เหมือนกัน

## ลำดับ cleanup ที่เสนอ

1. สร้าง cleanup manifest พร้อม SHA-256 ของทุกไฟล์ที่จะย้ายหรือลบ
2. ลบเฉพาะ generated files (`node_modules`, `__pycache__`) หลังยืนยันว่ามี lockfile และทดสอบสร้างใหม่ได้
3. ย้าย log, backup และ release รุ่นเก่าไป quarantine/archive แทนการลบถาวร
4. ยืนยันการใช้ canonical root `.env` บน PROD แล้วจึงถอน `scripts/.env`
5. ตัดสินใจ repository topology
6. แยก schema ออกจาก SQL dump และตรวจ secret/data
7. refactor deployment/tests ก่อนลบ retired scripts
8. รัน syntax checks และ unit tests ทั้งหมดหลัง cleanup
9. จัดทำ `AGENTS.md` และ project handoff หลังโครงสร้างนิ่งแล้ว

## Acceptance criteria หลัง cleanup

- ไม่มี secret audit finding ในไฟล์ที่จะ commit
- ไม่มี `.env`, raw log, cache, `node_modules`, `__pycache__` หรือ PROD data ใน repository
- มี repository root ที่ชัดเจนเพียงแนวทางเดียว
- release artifacts ที่เก็บไว้มี checksum และ compatibility metadata
- Python, Node และ shell syntax ผ่าน
- unit tests ผ่านทั้งหมด
- PROD deployment และ scheduler ไม่ได้รับผลกระทบ

