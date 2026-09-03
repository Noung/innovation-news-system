# Documentation Index

เอกสารหลักของโปรเจกต์ถูกรวมไว้ในโฟลเดอร์นี้

## เอกสารที่มี

- [ADMIN_README.md](ADMIN_README.md)
  ภาพรวมของเว็บ admin, การรัน, env สำคัญ, และ API หลัก
- [ADMIN_GUIDE.md](ADMIN_GUIDE.md)
  คู่มือใช้งานหน้า admin และความหมายของแต่ละแท็บ
- [MIGRATIONS_AND_FLAGS.md](MIGRATIONS_AND_FLAGS.md)
  ลำดับ migration และ env flags ที่มีผลกับ runtime
- [SCHEDULING.md](SCHEDULING.md)
  วิธีตั้ง scheduler สำหรับ Windows และ Linux

## ไฟล์สำคัญของระบบ

- Python runtime: `scripts/fetch-innovation-news-mysql.py`
- Admin API: `fetch-innovation-news/api/server.js`
- Admin UI: `fetch-innovation-news/public/index.html`
- Schema snapshot: `sql/`
- Migrations: `sql/migrations/`
