# Innovation News — Project Handoff

อัปเดตล่าสุด: 28 สิงหาคม 2569 (2026-08-28), Asia/Bangkok

เอกสารนี้เป็นจุดเริ่มต้นสำหรับทำงานต่อในเครื่องหรือ workspace ใหม่ ห้ามบันทึกรหัสผ่าน token, Application Password, API key หรือค่าจาก `.env` ลงในไฟล์นี้

## 0. สถานะก่อนย้าย workstation

บันทึกเมื่อ 2026-08-28 ก่อนออกจาก workstation `C:\laragon\www\innovation-news-system`:

- ผู้ใช้ยืนยันว่า PROD ทำงานถูกต้องแล้ว
- แนวทางต่อจากนี้คือพัฒนาและทดสอบใน Docker local, ทยอย commit/push เข้า private `origin/main` และ deploy PROD เป็นขั้นตอนแยกที่ต้องมี diff, tests, backup และ approval
- Git `main` push ถึง `origin/main` แล้ว โดยมี Docker local environment ที่ commits `828fa30` และ `0caade1`
- local services `mysql`, `mock-integrations`, `admin` และ `gateway` เป็น `healthy`
- local Admin ใช้งานได้ที่ `http://127.0.0.1:3001`
- local database มีข่าว `131`, sources `18` (active เฉพาะ `local-mock` 1), fetch logs `134`, local audit rows `2` และ procedures `2`
- regression tests ล่าสุดผ่าน `149/149`; Compose config, Node syntax และ diff checks ผ่าน
- ไม่มี PROD credentials หรือเส้นทางเขียนกลับ PROD ใน local stack

สิ่งที่ **ไม่เดินทางไปกับ Git** คือ Docker named volume และไฟล์ใต้ `local-data/` หากต้องการข้อมูลข่าว 131 รายการเหมือนเครื่องนี้ ต้องคัดลอกเฉพาะ sanitized dump ต่อไปนี้ผ่านสื่อ/พื้นที่ส่วนตัวแยกจาก Git:

```text
local-data/prod-snapshot/sanitized/innovation_news-local-sanitized-20260828.sql
SHA256 a0d8fa0743a5114f66c851507a57afdd927808f5da1b7d7f2053a7600a663302
```

อย่าคัดลอก raw dump หากไม่จำเป็น เพราะตรวจพบ query parameter ที่เข้าข่าย API key อยู่ 1 จุด หลังยืนยันว่า sanitized file สำรองสำเร็จควรลบ raw dump ออกจาก workstation เดิม

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

- ชุดทดสอบ local ผ่านทั้งหมด `149` tests (`142` tests เดิม + `7` local-development safety tests)
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

### Source URL compatibility preflight

ตรวจแบบ read-only หลัง Phase 0 แล้วเมื่อ 2026-08-28:

- active sources `16` แหล่ง
- ทุกแหล่งเป็น `URL=OK`
- ไม่มี active source ที่ใช้ slug `newsapi` จึงไม่มี NewsAPI key gate ในรอบนี้
- ไม่พบ `URL=BLOCKED` หรือ `API_KEY=MISSING`

ผลนี้ยืนยัน source configuration เท่านั้น ยังไม่ใช่หลักฐานว่า cron รอบ 09:00 ดึงและเผยแพร่ข่าวสำเร็จ

### Scheduler ปัจจุบันบน PROD

ใช้ OS cron เป็นเจ้าของ scheduler:

```cron
0 9 * * * /usr/bin/python3 /home/kittisak/.openclaw/workspace/scripts/fetch-innovation-news-mysql.py >> /home/kittisak/.openclaw/workspace/logs/cron-innovation-news-mysql.log 2>&1
0 9 * * * /usr/bin/python3 /home/kittisak/.openclaw/workspace/scripts/fetch-it24hrs-news.py >> /home/kittisak/.openclaw/workspace/logs/cron-it24hrs.log 2>&1
```

## 4. สถานะ PROD และการตรวจซ้ำในอนาคต

ตรวจ compatibility ของ `news_sources.source_url` หลัง Phase 0 ผ่านแล้ว และผู้ใช้ยืนยันเมื่อ 2026-08-28 ว่า PROD ทำงานถูกต้อง การอ่าน cron logs รอบ 09:00 ยังไม่ได้เก็บเป็นหลักฐานใน repository แต่ไม่เป็น blocker ของ local development หากจะ deploy PROD รอบถัดไปให้ตรวจสถานะ/log จริงแบบ read-only ใหม่ก่อนทุกครั้ง

คำสั่ง source preflight ต่อไปนี้เก็บไว้สำหรับตรวจซ้ำในอนาคต เป็น read-only: อ่านเฉพาะ `id`, `slug` และ URL จากฐานข้อมูล แล้วแสดงเพียง `OK/BLOCKED`; ไม่แสดง URL หรือ API key ไม่ดึงข่าว ไม่เขียนฐานข้อมูล และไม่ส่งข้อความ

```bash
cd /home/kittisak/.openclaw/workspace
INNOVATION_NEWS_ENV_FILE=/home/kittisak/.openclaw/workspace/.env /usr/bin/python3 -c 'import os,runpy; n=runpy.run_path("scripts/fetch-innovation-news-mysql.py",run_name="source_preflight"); out=n["run_mysql_query"]("SELECT id,slug,source_url FROM news_sources WHERE is_active=1 ORDER BY id") or ""; rows=[x.split("\t",2) for x in out.splitlines() if x.strip()]; urls=lambda raw:[u.strip() for u in raw.split(",") if u.strip()]; state=lambda raw:"OK" if urls(raw) and all(n["source_url_is_allowed"](u) for u in urls(raw)) else "BLOCKED"; key=lambda slug:"READY" if slug!="newsapi" or os.getenv("INNOVATION_NEWS_SOURCE_API_KEY_NEWSAPI","").strip() else "MISSING"; print("ACTIVE_SOURCES=%d"%len(rows)); print("\n".join("%s\t%s\tURL=%s\tAPI_KEY=%s"%(i,s,state(raw),key(s)) for i,s,raw in rows))'
```

ผลที่ต้องการ:

- ทุกแหล่งเป็น `URL=OK`
- ถ้ามี slug `newsapi` ต้องเป็น `API_KEY=READY`

หากต้อง re-audit scheduler หรือเตรียม deploy PROD รอบถัดไป ให้ตรวจผลรอบจริงก่อนด้วย:

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

ระบบเต็มตั้งใจไม่รวม `.env`, database dump และ `node_modules` แต่มี Docker Compose local runtime ที่แยกจาก PROD พร้อม MySQL, schema baseline และข้อมูลตัวอย่างที่ผ่านการ sanitize

สร้างและทดสอบ Local Development Environment แล้วที่ `compose.yaml` ประกอบด้วย MySQL, sanitized schema, synthetic sample data, Admin API/UI, `DRY_RUN=1` และ HTTPS mock integrations สำหรับ source, WordPress, Telegram และ LINE โดย MySQL, mock และ Admin อยู่ใน Docker internal network ส่วน gateway ที่ไม่มี credentials เป็น service เดียวที่ publish พอร์ต `127.0.0.1:3001`

รายละเอียดอยู่ที่ `docs/local-development.md` และ local baseline อยู่ที่ `docker/mysql/init/` ชุดนี้สร้างจาก application query contract ไม่ใช่ PROD dump และห้ามนำไปใช้เป็น production migration

ตรวจแล้ว:

- `docker compose config`: `PASS`
- Docker image build และ container smoke test บน Docker Desktop 29.6.2: `PASS`
- services `mysql`, `mock-integrations`, `admin` และ `gateway`: `healthy`
- Admin `/api/health`: `status=ok`, `database=ok`
- Admin login, protected APIs และ static UI assets: HTTP `200`
- integration preflight แบบไม่มี `--send`: WordPress CPT + taxonomy + 20 terms `SUCCESS`; Telegram/LINE configured และข้ามการส่ง
- dry-run fetch ก่อนสลับ snapshot: พบข่าวสังเคราะห์ 2 รายการ, เพิ่ม 1 รายการใน local MySQL และ delivery statuses เป็น `dry_run`; หลังสลับยังไม่รัน fetch เพื่อคงข่าวนำเข้าไว้ที่ `131`
- local-development safety tests: `7` tests, `OK`
- Python regression tests ทั้งหมด: `149` tests, `OK`
- Python/Node syntax และ `git diff --check`: `PASS`
- `npm audit` ทั้ง production dependencies และชุดเต็ม: `0 vulnerabilities`

local stack พร้อมใช้งานที่ `http://127.0.0.1:3001` โดยไม่ใช้ PROD credentials และไม่มีเส้นทางเขียนกลับ PROD

### Local sanitized PROD snapshot

หลังผู้ใช้เตรียม snapshot วันที่ 2026-08-28 ได้ตรวจและ restore ผ่านฐาน staging ที่แยกจากฐานหลัก แล้วสร้าง sanitized dump ซึ่งถูกเก็บใต้ `local-data/` ที่ ignore ทั้งจาก Git และ Docker build context

พบ query parameter ที่เข้าข่าย API key ใน raw `news_sources` 1 จุด จึงไม่ได้นำ raw dump เข้าใช้โดยตรง ขั้น sanitize ที่ทำแล้วคือแทน PROD source URLs ด้วย mock URLs, ปิด PROD sources ทั้งหมด, ล้าง PROD admin audit rows, ล้าง `fetch_logs.error_message` และเปลี่ยน views เป็น `SQL SECURITY INVOKER` พร้อม local-only definer จากนั้น restore ไฟล์ sanitized เข้า local `innovation_news` และลบฐาน staging/validation ชั่วคราวแล้ว

สถานะ local database หลังสลับและก่อนการ fetch ทดสอบรอบใหม่:

- ข่าวจาก snapshot `131` รายการ
- sources รวม `18`: PROD-derived inactive `17` + active `local-mock` `1`
- fetch logs `134` รายการ
- compatibility procedures `save_article` และ `log_fetch_operation` ครบ `2`
- login, `/api/sources`, `/api/articles`, `/api/logs`, dashboard และ integration preflight แบบไม่มี `--send`: `PASS`
- PROD ไม่ถูกเชื่อมต่อหรือเขียนข้อมูลจาก Docker local

เพิ่ม `docker/mysql/init/003_local_runtime_overlay.sql` เพื่อปิด imported sources, สร้าง/อัปเดต `local-mock` และคืน procedures ที่ fetcher ต้องใช้ ไฟล์ raw/sanitized snapshot ไม่อยู่ใน Git การสั่ง `docker compose down --volumes` จะลบ snapshot ใน volume และกลับไปใช้ synthetic baseline เมื่อเริ่ม stack ใหม่

## 6. วิธีเริ่มงานใน session ใหม่

1. เปิดและอ่าน `PROJECT_HANDOFF.md` ทั้งไฟล์
2. clone repository หรือรัน `git pull --ff-only origin main` แล้วตรวจ `git remote -v` ว่าเป็น private monorepo `innovation-news-system`
3. ตรวจ `docs/phase0-rollout.md` และ `docs/prod-backup-comparison-2026-08-28.md`
4. อย่า deploy หรือแก้ PROD ซ้ำก่อนตรวจสถานะจริง; ผู้ใช้ยืนยันว่า PROD ทำงานถูกต้อง ณ ตอนส่งมอบนี้
5. เปิด Docker Desktop, ใช้ context `desktop-linux` และเริ่ม local stack ตาม `docs/local-development.md`
6. หากไม่มี sanitized dump เครื่องใหม่จะเริ่มด้วย synthetic baseline ซึ่งยังพัฒนาและทดสอบได้ตามปกติ
7. หากต้องการข่าว 131 รายการเดิม ให้คัดลอก sanitized dump แยกจาก Git, ตรวจ SHA256 และทำขั้น restore ใน `docs/local-development.md`
8. ตรวจ `docker compose ps`, login, `/api/health` และรัน tests ก่อนเริ่มแก้โค้ด

## 7. ข้อควรจำ

- Canonical environment บน PROD คือ `/home/kittisak/.openclaw/workspace/.env`
- `scripts/.env` เป็น legacy fallback ไม่ควรผสมค่ากับ root `.env`
- อย่าใช้ `--send` กับ integration test จนกว่าจะต้องการส่งข้อความทดสอบจริง
- อย่ารันตัว fetcher ด้วยมือหากไม่ต้องการสร้างและเผยแพร่ข่าว
- PM2 ใช้เฉพาะ Admin API; cron ใช้สำหรับ fetch jobs
