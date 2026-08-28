# Innovation News — Project Handoff

อัปเดตล่าสุด: 28 สิงหาคม 2569 (2026-08-28), Asia/Bangkok

เอกสารนี้เป็นจุดเริ่มต้นสำหรับทำงานต่อในเครื่องหรือ workspace ใหม่ ห้ามบันทึกรหัสผ่าน token, Application Password, API key หรือค่าจาก `.env` ลงในไฟล์นี้

## 1. ภาพรวมระบบ

โครงการให้บริการอยู่สองเครื่องแยกกัน:

1. **Innovation News** — ระบบสกัด วิเคราะห์ จัดเก็บ และส่งข่าวอัตโนมัติ อยู่บนเครื่องที่ทันสมัย
2. **เว็บไซต์นวัตกรรม WordPress** — ช่องทางเผยแพร่หลัก อยู่บนระบบเดิม PHP 5.6 / WordPress 6.2.9

แนวทางที่ตกลงร่วมกันคือยังไม่เพิ่มระบบ subscription ลงใน WordPress รุ่นเดิม ระบบรับสมัครและส่งข่าวเฉพาะบุคคลจะพัฒนาที่ฝั่ง Innovation News โดย WordPress ยังเป็นช่องทางเผยแพร่หลัก

## 2. ตำแหน่งสำคัญ

- Local replica: `C:\Users\Kittisak\Downloads\innovation_news`
- PROD workspace: `/home/kittisak/.openclaw/workspace`
- PROD Admin URL เดิม: `http://192.168.160.19:3001/`
- PROD Phase 0 release: `/home/kittisak/.openclaw/workspace/releases/phase0-filezilla-20260828-064041`
- PROD pre-deploy backup: `/home/kittisak/.openclaw/workspace/releases/live-before-phase0-20260828-064857`
- PROD LAN bind patch: `/home/kittisak/.openclaw/workspace/releases/admin-lan-bind-20260828-070729`

## 3. งานที่เสร็จและตรวจยืนยันแล้ว

### WordPress taxonomy

- `innovation-tip` เชื่อมกับ taxonomy `organization_benefit`
- REST base คือ `organization-benefits`
- มี controlled vocabulary ครบ 20 terms
- ข่าวใหม่ส่ง taxonomy จำนวน 3 terms เข้า WordPress ได้สำเร็จ
- Backfill ข่าวเก่าเสร็จครบทั้งหมดแล้ว

### Local verification

- ชุดทดสอบ local ผ่านทั้งหมด `142` tests
- มีเอกสาร audit และเปรียบเทียบ PROD ที่:
  - `docs/file-hygiene-audit.md`
  - `docs/prod-backup-comparison-2026-08-28.md`
  - `docs/phase0-rollout.md`

### PROD deployment

- Phase 0 payload ตรวจ SHA256 ผ่านก่อนติดตั้ง
- สำรองไฟล์ live เดิม 29 ไฟล์ และตรวจ checksum ผ่าน
- Promote payload 38 ไฟล์แล้ว และ live checksum ตรงกับ release (`LIVE_CHECKSUM_EXIT=0`)
- Python/Phase 0 tests บน PROD ผ่าน 38 tests
- Admin dependency check จบด้วย `NPM_CHECK_EXIT=0`
- Admin config check ผ่าน
- PM2 มี process เดียวชื่อ `server`; ไม่มี fetch scheduler ซ้ำใน PM2
- Admin server, login และฐานข้อมูลทำงานปกติ
- `/api/health` ตอบ `status=ok`, `database=ok`

### Admin LAN compatibility

- server รุ่นใหม่เดิม bind ที่ `127.0.0.1` ทำให้ URL LAN เดิมเข้าไม่ได้
- เพิ่มการรองรับ `ADMIN_BIND_HOST=0.0.0.0` แบบ explicit
- PROD root `.env` กำหนด `ADMIN_BIND_HOST=0.0.0.0`
- นำ patch `admin-lan-bind-20260828-070729` ขึ้น live แล้ว
- หลัง `pm2 restart server --update-env` ตรวจ LAN HTTP ได้ `200`
- ผู้ใช้ยืนยันว่า login ผ่าน browser และฟังก์ชัน Admin ทำงานปกติ

### CSS/font

- `admin.css` มีขนาด 25,836 bytes ทั้งบน disk และผ่าน HTTP
- HTTP status `200`, content type `text/css`
- CSS โหลดครบ ความแตกต่างทางหน้าตาเกิดจากฟอนต์เดิมที่โหลดจาก CDN
- ยังไม่ต้องแก้ทันที; งานในอนาคตคือ self-host ฟอนต์ Noto Sans Thai หากต้องการหน้าตาเดิม

### Integration preflight

รันแบบ **ไม่มี `--send`** แล้ว ผลเป็น:

- Telegram configured; send skipped
- WordPress CPT + Benefit Taxonomy + 20 terms: `SUCCESS`
- LINE configured; send skipped

การทดสอบนี้ไม่ได้สร้างโพสต์และไม่ได้ส่งข้อความ Telegram/LINE

### Scheduler ปัจจุบันบน PROD

ใช้ OS cron เป็นเจ้าของ scheduler:

```cron
0 9 * * * /usr/bin/python3 /home/kittisak/.openclaw/workspace/scripts/fetch-innovation-news-mysql.py >> /home/kittisak/.openclaw/workspace/logs/cron-innovation-news-mysql.log 2>&1
0 9 * * * /usr/bin/python3 /home/kittisak/.openclaw/workspace/scripts/fetch-it24hrs-news.py >> /home/kittisak/.openclaw/workspace/logs/cron-it24hrs.log 2>&1
```

## 4. งานถัดไปที่ยังไม่ได้ทำ

ยังไม่ได้ตรวจ compatibility ของ `news_sources.source_url` หลัง Phase 0 ห้ามสรุปว่า scheduled fetch รอบใหม่ผ่านจนกว่าจะตรวจข้อนี้หรือเห็นผลรอบ 09:00 หลัง deployment

คำสั่งต่อไปเป็น read-only: อ่านเฉพาะ `id`, `slug` และ URL จากฐานข้อมูล แล้วแสดงเพียง `OK/BLOCKED`; ไม่แสดง URL หรือ API key ไม่ดึงข่าว ไม่เขียนฐานข้อมูล และไม่ส่งข้อความ

```bash
cd /home/kittisak/.openclaw/workspace
INNOVATION_NEWS_ENV_FILE=/home/kittisak/.openclaw/workspace/.env /usr/bin/python3 -c 'import os,runpy; n=runpy.run_path("scripts/fetch-innovation-news-mysql.py",run_name="source_preflight"); out=n["run_mysql_query"]("SELECT id,slug,source_url FROM news_sources WHERE is_active=1 ORDER BY id") or ""; rows=[x.split("\t",2) for x in out.splitlines() if x.strip()]; urls=lambda raw:[u.strip() for u in raw.split(",") if u.strip()]; state=lambda raw:"OK" if urls(raw) and all(n["source_url_is_allowed"](u) for u in urls(raw)) else "BLOCKED"; key=lambda slug:"READY" if slug!="newsapi" or os.getenv("INNOVATION_NEWS_SOURCE_API_KEY_NEWSAPI","").strip() else "MISSING"; print("ACTIVE_SOURCES=%d"%len(rows)); print("\n".join("%s\t%s\tURL=%s\tAPI_KEY=%s"%(i,s,state(raw),key(s)) for i,s,raw in rows))'
```

ผลที่ต้องการ:

- ทุกแหล่งเป็น `URL=OK`
- ถ้ามี slug `newsapi` ต้องเป็น `API_KEY=READY`

หากย้าย workspace หลังเวลา 09:00 ให้ตรวจผลรอบจริงก่อนด้วย:

```bash
tail -n 200 /home/kittisak/.openclaw/workspace/logs/cron-innovation-news-mysql.log
tail -n 200 /home/kittisak/.openclaw/workspace/logs/cron-it24hrs.log
```

อย่าคัดลอก log ที่มี credential หรือ URL ซึ่งมี query secret เข้า GitHub

## 5. สถานะ Git และ monorepo ใหม่

ได้สร้าง clean monorepo snapshot ใหม่ที่ `monorepo-staging/innovation-news-system` โดยใช้ fresh Git history และคง working tree/repository เดิมไว้โดยไม่ลบหรือเขียนทับ

snapshot ใหม่ครอบคลุม `scripts/`, `tests/`, `sql/migrations/`, `docs/`, `wordpress-plugin/`, Admin API/UI ใน `fetch-innovation-news/`, `.env.example`, README และเอกสาร handoff นี้

รายการที่ตั้งใจไม่รวม:

- `.env` และ `scripts/.env`
- SQL dumps ที่ `innovation_news.sql` ทั้งสองตำแหน่ง
- logs, cache, backups, release bundles และ `dist/`
- `node_modules`, `__pycache__`, `.pyc` และ nested Git metadata/history

เหตุผลที่ไม่ย้าย history ของ repository เดิมเข้ามาคือ history เดิมเคยมี source credential และ repository เดิมยัง diverge จาก remote การเริ่ม fresh private monorepo ลดความเสี่ยงที่จะพา secret/history ที่ไม่เกี่ยวข้องตามไปด้วย โดย repository เดิมยังอยู่ใน local replica สำหรับอ้างอิง

ก่อน commit ตรวจแล้ว:

- Secret sprawl audit: `PASS`
- Forbidden tracked artifacts: `PASS`
- Python tests: `142` tests, `OK`
- Node syntax: `PASS`

สร้าง private GitHub repository แล้วที่ `https://github.com/Noung/innovation-news-system` โดย `origin/main` เริ่มจาก clean snapshot commit `f200c00` และใช้ repository นี้เป็น canonical source สำหรับ workspace ใหม่

ห้าม commit ไฟล์ `.env`, logs, cache, backup, release bundle, database dump หรือ secret ทุกชนิด

### Local development status

clean monorepo สามารถรัน unit tests ใน local ได้ทันทีโดยใช้ `.env.example`:

```powershell
$env:INNOVATION_NEWS_ENV_FILE=(Resolve-Path .env.example)
python -m unittest discover -s tests -v
```

ระบบเต็มยังไม่ใช่ turnkey local runtime เพราะตั้งใจไม่รวม `.env`, database dump และ `node_modules` การเปิด Admin API/UI และทดสอบ fetch flow แบบ end-to-end ต้องใช้ MySQL local ที่แยกจาก PROD พร้อม schema และข้อมูลตัวอย่างที่ผ่านการ sanitize

milestone สำหรับพัฒนาต่อหลังตรวจ source preflight/ผล cron คือสร้าง Local Development Environment ด้วย Docker Compose ซึ่งประกอบด้วย MySQL, sanitized schema, sample data, Admin API/UI, `DRY_RUN=1` และ mock integrations สำหรับ WordPress, Telegram และ LINE ห้ามนำ PROD database หรือ PROD credentials มาใช้เป็น local test environment

## 6. วิธีเริ่มงานใน session ใหม่

1. เปิดและอ่าน `PROJECT_HANDOFF.md` ทั้งไฟล์
2. ตรวจ `docs/phase0-rollout.md` และ `docs/prod-backup-comparison-2026-08-28.md`
3. อย่า deploy หรือแก้ PROD ซ้ำก่อนตรวจสถานะจริง
4. ทำ source preflight ในหัวข้อ 4 หรืออ่าน log รอบ 09:00 หาก cron ทำงานไปแล้ว
5. ตรวจ `git remote -v` และยืนยันว่าเป็น private monorepo `innovation-news-system`
6. เมื่อสถานะ PROD หลัง deployment ผ่านแล้ว ให้เริ่มออกแบบ Local Development Environment ตามหัวข้อด้านบน

## 7. ข้อควรจำ

- Canonical environment บน PROD คือ `/home/kittisak/.openclaw/workspace/.env`
- `scripts/.env` เป็น legacy fallback ไม่ควรผสมค่ากับ root `.env`
- อย่าใช้ `--send` กับ integration test จนกว่าจะต้องการส่งข้อความทดสอบจริง
- อย่ารันตัว fetcher ด้วยมือหากไม่ต้องการสร้างและเผยแพร่ข่าว
- PM2 ใช้เฉพาะ Admin API; cron ใช้สำหรับ fetch jobs
