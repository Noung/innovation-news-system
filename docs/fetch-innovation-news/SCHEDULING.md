# Scheduling

ระบบ PROD ใช้ OS cron เป็นเจ้าของการเรียกตัวดึงข่าวตามเวลาเพียงระบบเดียว ส่วน PM2 ดูแลเฉพาะ `innovation-news-api` เท่านั้น

## กติกาหลัก

- cron เรียก `scripts/run-fetch-innovation-news.sh`
- ห้ามกำหนด `cron_restart` ให้ fetcher ใน PM2
- root `.env` คือ configuration หลัก
- `scripts/.env` เป็น fallback ชั่วคราวเพื่อ rollback เท่านั้น
- ทุก trigger รวมถึงปุ่ม Run Now ใช้ local file lock และ MySQL advisory lock ชุดเดียวกัน

## ติดตั้งอย่างปลอดภัย

ตัวติดตั้งเป็น dry-run โดยค่าเริ่มต้นและแก้เฉพาะ managed block ของ Innovation News:

```bash
cd /home/kittisak/.openclaw/workspace
scripts/install-innovation-news-cron.sh --dry-run
```

dry-run จะแสดงเฉพาะจำนวน entry, schedule และ checksum โดยไม่พิมพ์ command เดิมซึ่งอาจมี credential ตรวจ summary แล้วจึงติดตั้ง:

```bash
scripts/install-innovation-news-cron.sh --apply
```

managed block ที่ได้จะมีรูปแบบนี้:

```cron
# BEGIN INNOVATION-NEWS MANAGED
0 9 * * * /home/kittisak/.openclaw/workspace/scripts/run-fetch-innovation-news.sh
# END INNOVATION-NEWS MANAGED
```

ตัวติดตั้งจะสำรอง crontab เดิมด้วย permission จำกัดไว้ใต้ `backups/crontab/` และจะนำ legacy entry ที่เรียก fetcherหลักโดยตรงออก โดยไม่แตะ iT24Hrs, KS State หรืองานอื่น หาก crontab เดิมมี credential ต้องย้าย backup ไปพื้นที่เข้ารหัสที่อนุมัติและกำหนดวันลบ

## Global run lock

ตัว fetcherถือ local `flock` ป้องกัน process บน host เดียวกันและ MySQL named lock ป้องกันทุก client ตลอดรอบ ตั้งแต่ก่อนอ่าน source จนส่ง integration และอัปเดต source index เสร็จ:

- exit `0`: จบรอบตามปกติ
- exit `75`: มีอีกรอบกำลังทำงาน จึงข้ามรอบนี้โดยไม่ดึงหรือเผยแพร่ข่าว
- exit `70`: ยืนยัน lock ไม่ได้ ระบบหยุดแบบ fail closed
- exit `1`: runtime error ที่ไม่คาดหมาย

ปุ่ม Run Now แปลง exit `75` เป็น HTTP `409 FETCH_ALREADY_RUNNING`

## การเลือก environment

ลำดับคือ explicit `INNOVATION_NEWS_ENV_FILE` → root `.env` → legacy `scripts/.env` การโหลดจะหยุดเมื่อพบไฟล์แรก ไม่ค้น `.env` จาก current working directory และค่าจากไฟล์ที่เลือกจะแทน inherited environment (ยกเว้น path ที่ใช้เลือกไฟล์เอง)

ดูขั้นตอนนำขึ้นจริงและย้อนกลับใน [phase0-rollout.md](../phase0-rollout.md)
