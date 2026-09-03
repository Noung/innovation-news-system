# PROD Backup vs Local Comparison

วันที่ตรวจ: 2026-08-28 (Updated: 3 September 2026)

**หมายเหตุ:** เอกสารนี้เป็น point-in-time comparison เมื่อ 28 ส.ค. 2026 ปัจจุบัน local และ PROD อาจมีการเปลี่ยนแปลงเพิ่มเติม (Updated: 3 September 2026)

**หมายเหตุ:** เอกสารนี้เป็น point-in-time comparison เมื่อ 28 ส.ค. 2026 ปัจจุบัน local และ PROD อาจมีการเปลี่ยนแปลงเพิ่มเติมแล้ว

## ขอบเขต

- Local candidate: `C:\Users\Kittisak\Downloads\innovation_news`
- Current PROD backup: `D:\oar_innovation_system_PRODBACKUP\fetch-innovation-news`
- Git repository ที่พบในทั้งสองชุด: `fetch-innovation-news/.git`
- การตรวจเป็น read-only ต่อ PROD backup; ไม่มีการแก้ไข backup หรือ PROD
- `.env`, logs, cache, Git objects, `node_modules` และ `__pycache__` ถูกแยกออกจาก source hash comparison
- รายงานนี้ไม่บันทึก credential value

## Executive summary

Local ไม่ใช่สำเนาของ PROD แบบ byte-for-byte แต่เป็น candidate ที่นำฟังก์ชัน Admin จาก PROD มาต่อยอดด้วย Phase 0 security แล้ว จากการเปรียบเทียบชื่อ route และ function ยังไม่พบฟังก์ชัน Admin, fetcher, WordPress integration หรือ LINE integration ที่มีเฉพาะ PROD แต่หายจาก Local

อย่างไรก็ตาม ห้ามคัดลอก Local ทับ PROD ทั้งชุด เนื่องจาก:

1. PROD มี runtime configuration และ operational artifacts ที่ต้องรักษา
2. เอกสารและ SQL หลายไฟล์ต่างกันอย่างมีนัยสำคัญ
3. ทั้ง Local และ PROD มี uncommitted work จาก Git main เดิม
4. PROD ยังมี security debt ที่ต้องแก้ด้วย controlled rollout ไม่ใช่ file replacement
5. Git remote-tracking refs ในสองชุดไม่ตรงกันและอาจล้าสมัย

## Inventory comparison

หลังตัด generated/runtime/secret files ออกจาก source comparison:

| รายการ                         | จำนวน |
| ------------------------------ | ----: |
| Local safe files               |   103 |
| PROD safe files                |    72 |
| เหมือนกันทุก byte              |    16 |
| path เดียวกันแต่เนื้อหาต่างกัน |    50 |
| มีเฉพาะ Local                  |    37 |
| มีเฉพาะ PROD                   |     6 |

ไฟล์ที่มีเฉพาะ PROD ทั้ง 6 ไฟล์เป็น backup copies สามคู่ และแต่ละคู่เหมือนกันแบบ byte-for-byte:

- `scripts/bak/fetch-innovation-news-mysql.py` เท่ากับ `scripts/fetch-innovation-news-mysql.py.backup220769`
- `scripts/bak/line_integration.py` เท่ากับ `scripts/line_integration.py.backup220769`
- `scripts/bak/wordpress_integration.py` เท่ากับ `scripts/wordpress_integration.py.backup220769`

ไฟล์เหล่านี้ไม่ควรถูกนำมารวมกับ source หลัก ควร archive หนึ่งสำเนาต่อรุ่นพร้อม checksum หลังอนุมัติ

## Functional comparison

### Admin API/UI

- PROD และ Local มี API routes ชุดเดียวกัน รวม authentication, sources, source test, health, manual fetch, audit logs, fetch logs, articles และ dashboard
- ไม่พบ named JavaScript function ที่มีเฉพาะ PROD แล้วหายจาก Local
- Local เพิ่ม validation/redaction/security helpers โดยไม่ตัด route ของ PROD
- Local แยก Admin CSS ออกจาก external CDN และมี `tailwind.config.js`, source CSS และ generated `public/admin.css`
- Local เพิ่ม config check, loopback bind, trusted proxy policy, response sanitization, credential URL rejection, security headers และ rate limiting

ข้อสรุป: Local เป็น functional superset ของ Admin candidate จาก PROD ตาม static comparison แต่ยังต้องทำ regression test กับฐานข้อมูลจำลองก่อน promotion

### Fetcher และ integrations

- ไม่พบ Python function ที่มีเฉพาะ PROD ใน fetcher, WordPress integration หรือ LINE integration
- Local เพิ่ม global fetch cycle, local/MySQL locks, URL credential detection และ error redaction
- PROD active WordPress/LINE integration ยังมี `verify=False`; Local ถอด TLS bypass และรองรับ CA bundle
- Local fetcher มีการเปลี่ยนแปลงประมาณ +328/-27 บรรทัดจาก PROD จึงต้องทดสอบ canary ไม่ควรแทนไฟล์โดยตรง

### Scheduler

PROD backup `ecosystem.config.js` มีสาม PM2 apps:

1. `innovation-news-api`
2. `innovation-news-fetcher` พร้อม `cron_restart` เวลา 09:00
3. `it24hrs-news-fetcher` พร้อม `cron_restart` เวลา 09:00

Local Phase 0 เหลือ PM2 เฉพาะ Admin API และกำหนดให้ OS Cron เป็น scheduler เจ้าของเดียว หาก PROD ยังมี crontab เวลา 09:00 ตามการตรวจครั้งก่อน จะมีความเสี่ยง duplicate execution จาก Cron และ PM2 พร้อมกัน จึงต้องตรวจ runtime จริงก่อนเปลี่ยน scheduler

### Environment selection

- PROD PM2 config ชี้ Admin ไปที่ `scripts/.env`
- PROD backup มีทั้ง root `.env` และ `scripts/.env`
- Local Phase 0 ชี้ไปที่ root `.env` และกำหนด precedence ที่ชัดเจน
- PROD root `.env` ยังไม่มี Phase 0 keys ต่อไปนี้:
  - Admin bind/CORS/trusted proxy controls
  - subscription/email feature gates
  - local/MySQL fetch lock settings
  - NewsAPI header credential settings
  - WordPress/LINE TLS verification and CA bundle settings

ห้ามลบ `scripts/.env` จนกว่าจะยืนยันทุก entry point และผ่าน canary ด้วย root `.env`

## Security findings

### Critical: exposed WordPress credential

พบ WordPress Application Password ฝังเป็นข้อความตรงใน operational script/document อย่างน้อยสองไฟล์ใน PROD backup:

- `scripts/master-deploy-fix.sh`
- `fetch-innovation-news/QUICK_DEPLOY.md`

ต้องถือว่า credential นี้เปิดเผยแล้ว การลบข้อความออกจากไฟล์ไม่เพียงพอ ต้อง revoke Application Password เดิม ออกค่าใหม่ผ่านช่องทางจัดการ secret และตรวจ history/archive ที่อาจมีสำเนา

### High: TLS verification disabled

พบ `verify=False` ใน active PROD integration และ backup helpers รวมถึง:

- `scripts/wordpress_integration.py`
- `scripts/line_integration.py`
- `scripts/test-integrations.py`
- `scripts/bak/*`

Local แก้ประเด็นนี้แล้ว แต่การนำขึ้น PROD ต้องตรวจ certificate chain หรือ CA bundle ก่อนเพื่อไม่ให้ integration หยุดทำงาน

### High: unsafe operational helpers

PROD backup ยังมี helper ที่สามารถแก้ credential, ปิด TLS verification, เปลี่ยน crontab หรือหยุด/ลบ PM2 apps ทั้งหมด เช่น:

- `scripts/master-deploy-fix.sh`
- `scripts/update-wp-env.sh`
- `fetch-innovation-news/pm2-setup-prod.sh`

Local เปลี่ยน legacy helpers เป็น fail-closed stubs และจำกัด PM2 scope แล้ว จึงไม่ควรนำ helper จาก PROD กลับมาทับ Local

### Medium: runtime dependency installation

PROD `start.sh` รัน `npm install` อัตโนมัติเมื่อไม่พบ `node_modules`; Local เปลี่ยนเป็น fail closed และกำหนดให้ติดตั้ง dependency ผ่าน reviewed deployment step

## Git comparison

ทั้ง Local และ PROD working tree ใช้ HEAD เดียวกัน:

`8103484b5bb722ff44f2700ea86c4769529d9d0e`

แต่มีสถานะต่างกัน:

- PROD tracked changes: `api/server.js`, `public/index.html`
- PROD untracked operational files: PM2/deploy documents and scripts
- Local tracked changes: security/runtime changesเพิ่มใน `.gitignore`, package metadata, server, SQL, UI และ `start.sh`
- Local untracked files: PM2/deploy files และ self-hosted CSS/Tailwind files

remote-tracking `origin/main` ไม่ตรงกัน:

- Local cached `origin/main`: `7ee6267...`
- PROD cached `origin/main`: `aeaa28f...`

จึงห้ามใช้ cached `origin/main` ชุดใดเป็นคำตอบว่า remote main ปัจจุบันคืออะไร ต้องทำ authenticated `git fetch` ในขั้น Git reconciliation แล้วตรวจ graph ก่อน commit/push

โค้ด `scripts/`, `docs/`, `tests/`, `wordpress-plugin/` และ root files อยู่นอก nested Git repository ปัจจุบัน จึงยังไม่ถูกควบคุมเวอร์ชันโดย repository นี้

## Files requiring manual merge/review

### ต้องรักษาจาก Local

- Phase 0 runtime/security changes
- taxonomy, WordPress search และ backfill tools/tests
- self-hosted Admin CSS
- canonical env examples และ feature gates
- safe scheduler/deployment helpers

### ต้องใช้ PROD เป็น operational evidence

- runtime paths และ service names
- source/database schema state
- current environment key inventory
- current PM2/scheduler layout
- Admin/API behavior ที่ใช้อยู่จริง

### ห้ามเลือกข้างอัตโนมัติ

- root และ nested `innovation_news.sql`
- documentation ที่ path เดียวกันแต่เนื้อหาต่างกัน
- `ecosystem.config.js`
- `deploy-to-prod.sh`
- `.env` ทั้งสองตำแหน่ง
- backup/release artifacts

## Recommended reconciliation sequence

1. เก็บ PROD backup นี้เป็น immutable evidence และสร้าง manifest/checksum นอก working source
2. Rotate/revoke WordPress Application Password ที่พบใน plaintext; ทบทวน Telegram, LINE, DB และ NewsAPI credentials ด้วย
3. ตรวจ actual PROD scheduler แบบ read-only เพื่อยืนยัน Cron/PM2 duplication
4. ทำ semantic merge โดยใช้ Local เป็น Phase 0 candidate และ PROD เป็น operational reference; ห้าม copy directory ทับกัน
5. จัดทำ sanitized schema baseline จาก PROD โดยไม่รวมข้อมูลหรือ credential
6. รัน local tests และสร้าง staging bundle พร้อม checksum
7. ทำ canary โดยรักษา taxonomy 3 terms และ outbound behavior เดิม
8. หลังระบบนิ่ง จึง quarantine/delete generated files และ duplicate backups ตาม `file-hygiene-audit.md`
9. ตัดสินใจ repository topology แล้วจึง fetch remote main, สร้าง consolidation branch และ review ก่อน push

## Current decision

- Local ยังไม่พร้อมอัปโหลดหรือ deploy โดยตรง
- Local เป็นฐานที่เหมาะสมกว่าสำหรับการรวม Phase 0 เพราะรักษา PROD functions และเพิ่ม safety controls
- PROD backup มีข้อมูลใหม่ที่สำคัญด้าน runtime แต่มี security debt จึงต้องนำมาเป็น reference ไม่ใช่ source ที่คัดลอกกลับทั้งหมด
- ขั้นต่อไปควรเป็น credential containment และ semantic reconciliation ไม่ใช่ cleanup แบบลบไฟล์ทันที
