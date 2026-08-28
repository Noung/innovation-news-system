# Innovation News Admin

เว็บ admin สำหรับดูและจัดการระบบ `fetch-innovation-news`

## สิ่งที่หน้า admin ทำได้ตอนนี้

- login ด้วย admin session
- ดูแหล่งข่าวทั้งหมดและสถานะ runtime warning
- เพิ่ม แก้ไข เปิดปิด และลบ source
- ดูบทความพร้อมสถานะการส่ง LINE
- ดู logs การดึงแบบแยก `MySQL / Telegram / WordPress / LINE`
- กด `รันตอนนี้` เพื่อสั่ง manual fetch
- ดู audit log ของการ login, แก้ source, และ manual fetch

## Stack

- Backend: Node.js + Express
- Frontend: HTML + Vanilla JavaScript
- Database: MySQL

## โครงสร้าง

```text
fetch-innovation-news/
├─ api/
│  ├─ package.json
│  └─ server.js
├─ assets/admin.css
├─ public/
│  ├─ index.html
│  └─ admin.css
├─ tailwind.config.js
└─ start.sh
```

## การติดตั้ง dependency ใน build environment

```bash
cd fetch-innovation-news/api
npm ci --omit=dev
```

ห้ามให้ startup script ติดตั้ง dependency เอง และต้องตรวจ advisory/lockfile ก่อนนำ artifact ขึ้น PROD

หากแก้ class ของหน้า Admin ให้ build CSS ด้วย dependency ที่ pin ใน lockfile:

```bash
cd fetch-innovation-news/api
npm ci --ignore-scripts
npm run build:css
```

runtime ใช้ `public/admin.css` ที่ self-host แล้ว ไม่เรียก Tailwind หรือ Google Fonts จาก CDN

## การรัน

จาก root ของ workspace:

```bash
node fetch-innovation-news/api/server.js
```

หรือใช้ startup script:

```bash
cd fetch-innovation-news
./start.sh
```

ค่าเริ่มต้นของ port คือ `3001` และ override ได้ด้วย `PORT`
ตัว server bind ที่ `127.0.0.1` และเชื่อถือ reverse proxy จาก loopback เท่านั้นโดยค่าเริ่มต้น (`ADMIN_BIND_HOST`, `ADMIN_TRUST_PROXY`) การเข้าจากเครือข่ายต้องผ่าน HTTPS reverse proxy

ตรวจ config โดยไม่เปิด port และไม่ต่อฐานข้อมูล:

```bash
node fetch-innovation-news/api/server.js --config-check
```

## Environment ที่สำคัญ

ค่าเหล่านี้ต้องอยู่ใน workspace-root `.env` ซึ่งเป็น canonical file

### Database

- `DB_HOST`
- `DB_USER`
- `DB_PASS`
- `DB_NAME`

### Admin Auth

- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `ADMIN_SESSION_SECRET`
- `ADMIN_SESSION_TTL_SECONDS`

password ต้องยาวอย่างน้อย 16 ตัวอักษรและไม่ใช่ placeholder ส่วน session secret ต้องยาวอย่างน้อย 32 ตัวอักษร

### Runtime Integration Flags

- `DRY_RUN`
- `ENABLE_TELEGRAM`
- `ENABLE_WORDPRESS`
- `ENABLE_LINE`

## URL ที่ใช้บ่อย

- Admin UI ภายในเครื่อง: `http://127.0.0.1:3001`
- Health check ภายในเครื่อง: `http://127.0.0.1:3001/api/health`

## API หลัก

- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `GET /api/sources`
- `POST /api/sources`
- `PUT /api/sources/:id`
- `PATCH /api/sources/:id/toggle`
- `DELETE /api/sources/:id`
- `GET /api/articles`
- `GET /api/logs`
- `GET /api/stats/dashboard`
- `POST /api/fetch/run-now`
- `GET /api/audit-logs`

## หมายเหตุ

- หน้า admin ปัจจุบันมี auth แล้ว ต่างจากเอกสารรุ่นเก่าที่เคยระบุว่ายังไม่มี
- สถานะ “ส่งแล้ว” ฝั่งบทความอิงจาก `line_status`
- ห้ามใช้ SQL dump ใน repository เป็นฐานใหม่จนกว่าจะตรวจ provenance, sanitize และสร้าง signed schema baseline แล้ว
