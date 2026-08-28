# PM2 Setup (Phase 0)

PM2 ดูแลเฉพาะ `innovation-news-api` เท่านั้น การดึงข่าวตามเวลาเป็นหน้าที่ของ OS cron

ตรวจแบบ read-only:

```bash
cd /home/kittisak/.openclaw/workspace/fetch-innovation-news
./pm2-test.sh
```

เมื่อผ่าน staged rollout แล้วจึงใช้:

```bash
./pm2-setup-prod.sh
```

สคริปต์จะลบเฉพาะ process เก่า `innovation-news-fetcher` และ `it24hrs-news-fetcher`, reload เฉพาะ API และบันทึก process list ใหม่ โดยไม่ใช้ `pm2 stop all` หรือ `pm2 delete all`

อย่าติดตั้ง PM2 รุ่นล่าสุดโดยอัตโนมัติในขั้น deploy ให้ติดตั้งเวอร์ชันที่องค์กรอนุมัติแยกจาก service rollout

ดูรายละเอียดที่ [Phase 0 rollout](../docs/phase0-rollout.md)
