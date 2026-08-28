# Local Development with Docker Compose

เอกสารนี้อธิบาย local stack ที่แยกจาก PROD โดยตั้งใจ ทั้ง credentials, database, URLs, network และ runtime data เป็นของ local เท่านั้น

## ขอบเขตที่รองรับ

Compose stack มีสี่ services:

| Service | หน้าที่ | Host access |
|---|---|---|
| `mysql` | MySQL พร้อม sanitized schema และ synthetic seed | ไม่ publish |
| `mock-integrations` | HTTPS mock สำหรับ generic source, WordPress REST และ LINE | ไม่ publish |
| `admin` | Node Admin API/UI พร้อม Python fetcher ใน image เดียวกัน | ไม่ publish |
| `gateway` | TCP forwarder ที่ไม่มี credentials สำหรับเข้า Admin จาก host | `127.0.0.1:3001` |

MySQL, mock และ Admin อยู่ใน Docker network ที่กำหนด `internal: true` จึงไม่มีเส้นทางออกอินเทอร์เน็ตระหว่าง runtime ส่วน gateway เชื่อม internal network กับ network สำหรับ host access และไม่มี application credentials หรือ mounted files พอร์ตเดียวที่ publish bind เฉพาะ loopback ของเครื่องพัฒนา

`admin` ต้อง bind `0.0.0.0` ภายใน container เพื่อรับ port forwarding แต่ host publish จำกัดไว้ที่ `127.0.0.1` ไม่ใช่การเปิด Admin ออก LAN แบบ PROD

## Safety contract

- ใช้ `docker/local.env.example` และ `docker/mysql.env.example` ซึ่งมีเฉพาะ dummy values ที่ตั้งใจให้ track ได้
- ค่าเริ่มต้นเป็น `DRY_RUN=1`
- subscription และ email worker ปิดอยู่
- source ที่ active มีเพียง `local-mock` และชี้ไป `mock-integrations` ภายใน Compose
- WordPress และ LINE ชี้ไป mock HTTPS ภายในเท่านั้น
- Telegram command ใช้ `docker/mock/openclaw-mock` ไม่เรียก OpenClaw จริง
- mock TLS ใช้ CA และ server certificate ที่สร้างใหม่ใน named volume ตอน container เริ่มทำงาน
- ไม่ mount root `.env`, PROD dump, user home หรือ Docker socket เข้า container
- runtime filesystem ของ `admin` เป็น read-only ยกเว้น tmpfs สำหรับ `cache/` และ `logs/`

ห้ามแก้ไฟล์ตัวอย่างให้มี PROD credential หากต้อง override ค่าสำหรับ local ให้คัดลอก `docker/local.env.example` เป็น `docker/local.env` ซึ่ง `.gitignore` ป้องกันไว้ แล้วเพิ่มไฟล์ override ของ Compose ในเครื่องโดยไม่ commit

## Sanitized database baseline

ไฟล์ต่อไปนี้จะถูกรันโดย MySQL เฉพาะตอนสร้าง volume ใหม่:

1. `docker/mysql/init/001_local_baseline.sql`
2. `docker/mysql/init/002_local_seed.sql`
3. `docker/mysql/init/003_local_runtime_overlay.sql`

baseline สร้างจาก query contract ที่โค้ดปัจจุบันใช้ ไม่ได้ export หรือคัดลอกจาก PROD ประกอบด้วย:

- `news_sources`
- `innovation_news`
- `fetch_logs`
- `admin_audit_logs`
- views สำหรับ source stats และ recent fetch logs
- compatibility procedures `save_article` และ `log_fetch_operation`

seed มี source, article และ fetch log สังเคราะห์เท่านั้น ไม่มี URL, identifier, article หรือ credential จาก PROD

runtime overlay ปิด source ที่ไม่ใช่ `local-mock`, บังคับ endpoint ทดสอบให้ชี้เข้า mock และสร้าง compatibility procedures `save_article` กับ `log_fetch_operation` ใหม่ จึงใช้ซ้ำได้ทั้งหลัง synthetic baseline และหลัง restore sanitized snapshot

baseline นี้เป็น **local fixture** ไม่ใช่ migration และห้ามนำไป apply บน PROD การทำ production schema baseline ยังต้องใช้ schema-only inspection, review และ checksum ตาม `sql/migrations/README.md`

## Sanitized PROD snapshot บนเครื่องนี้

โฟลเดอร์ `local-data/` ถูกตัดออกทั้งจาก Git และ Docker build context ไฟล์ raw และ sanitized dump จึงเป็น local artifacts และไม่อยู่ใน repository

snapshot วันที่ 2026-08-28 ผ่านการ restore/sanitize/restore validation แล้ว สถานะฐาน `innovation_news` ที่ Admin ใช้อยู่คือ:

- ข่าวจาก snapshot 131 รายการ
- PROD sources 17 รายการ โดยปิดทั้งหมดและแทน `source_url` ด้วย mock URLs
- `local-mock` active 1 รายการ ทำให้มี sources รวม 18 รายการ
- fetch logs 134 รายการ โดยล้าง `error_message`
- ล้าง PROD admin audit rows; การ login/ใช้งาน local จะสร้าง audit rows ใหม่เฉพาะใน Docker
- views 4 รายการใช้ `SQL SECURITY INVOKER` และ local-only definer
- compatibility procedures 2 รายการมาจาก local runtime overlay

การรัน `docker compose down --volumes` จะลบ snapshot ที่ restore อยู่ใน named volume และกลับไปสร้าง synthetic baseline จาก init SQL เมื่อ `docker compose up -d` ครั้งถัดไป

## เริ่มใช้งาน

ต้องเปิด Docker Desktop/daemon ก่อน จาก repository root รัน:

```powershell
docker compose build
docker compose up -d
docker compose ps
```

เมื่อ services healthy เปิด:

- Admin: `http://127.0.0.1:3001`
- Mock health ตรวจผ่าน Docker healthcheck และไม่เปิด port สู่ host

Admin username/password เป็น dummy values ใน `docker/local.env.example` และใช้ได้เฉพาะ local stack นี้

ตรวจ health และ integration preflight แบบไม่ส่งข้อมูล:

```powershell
docker compose exec admin node fetch-innovation-news/api/server.js --config-check
docker compose exec admin python scripts/test-integrations.py
```

ทดสอบ fetch flow ได้จากปุ่ม Run now ใน Admin หรือคำสั่งต่อไปนี้ การรันจะอ่าน mock source และเขียนเฉพาะ local MySQL แต่ `DRY_RUN=1` จะข้าม Telegram, WordPress และ LINE writes:

```powershell
docker compose exec admin python scripts/fetch-innovation-news-mysql.py
```

## Reset local data

หยุด containers โดยเก็บ database volume:

```powershell
docker compose down
```

หากต้องการล้างข้อมูล local และให้ init SQL ทำงานใหม่ทั้งหมด:

```powershell
docker compose down --volumes
docker compose up -d
```

คำสั่ง `down --volumes` ลบเฉพาะ named volumes ของ project `innovation-news-local` และกู้ข้อมูลใน volumes เหล่านั้นกลับไม่ได้

## Verification และข้อจำกัดปัจจุบัน

- ทดสอบ build และ container smoke test แล้วบน Docker Desktop 29.6.2
- services ทั้งสี่ (`mysql`, `mock-integrations`, `admin`, `gateway`) เป็น `healthy`
- Admin health, login, protected APIs และ static UI assets ตอบสำเร็จผ่าน `127.0.0.1:3001`
- integration preflight แบบไม่มี `--send` ผ่าน โดย WordPress mock ยืนยัน CPT, taxonomy และ controlled vocabulary ครบ 20 terms
- dry-run fetch ที่ทดสอบก่อนสลับ snapshot อ่านข่าวสังเคราะห์ 2 รายการจาก mock, เพิ่มบทความใหม่ 1 รายการใน local MySQL และไม่ส่ง Telegram, WordPress หรือ LINE; หลังสลับ snapshot ยังไม่ได้รัน fetch เพื่อคงข่าวนำเข้าไว้ที่ 131 รายการ
- `docker compose config`, Python safety/regression tests, Python/Node syntax และ `git diff --check` ผ่าน
- `npm audit` ทั้ง production dependencies และชุดเต็มรายงาน `0 vulnerabilities`
- MySQL image ใช้สาย `8.4`; ก่อนใช้ baseline นี้เป็นข้อมูลอ้างอิงของ PROD ต้องตรวจ server version จริงบน PROD แยกต่างหาก
- network isolation มีผลตอน runtime ส่วนขั้น build ยังต้องดาวน์โหลด base images และ dependencies จาก registry
