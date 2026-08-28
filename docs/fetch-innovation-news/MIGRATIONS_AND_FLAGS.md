# Migrations and Runtime Flags

## สถานะ provenance ปัจจุบัน

เอกสารรุ่นเดิมอ้างถึง migration วันที่ 2026-04-08 และ 2026-04-09 ใต้ `sql/migrations/` แต่ไฟล์เหล่านั้นไม่อยู่ใน local replica ชุดนี้ จึงยังยืนยันลำดับและ checksum ไม่ได้

Phase 0 จะไม่สร้าง migration ย้อนหลังจากการคาดเดา และไม่แก้ schema PROD งานก่อนเริ่ม Phase 1 คือกู้ artifact ต้นฉบับ หรือทำ schema baseline ที่ตรวจสอบกับ PROD และลงนาม checksum แล้ว

นโยบายสำหรับ migration ใหม่อยู่ที่ [sql/migrations/README.md](../../sql/migrations/README.md)

## Runtime safety flags

### Integration

- `DRY_RUN=1`: ยังอ่านแหล่งข่าว/บันทึก DB ตามพฤติกรรมเดิม แต่ไม่ส่ง integration ภายนอก
- `ENABLE_TELEGRAM=0`: ปิด Telegram
- `ENABLE_WORDPRESS=0`: ปิด WordPress และ LINE ที่ขึ้นกับ WordPress
- `ENABLE_LINE=0`: ปิด LINE

### TLS

- `WP_VERIFY_TLS=1` และ `LINE_VERIFY_TLS=1`: ค่าใช้งานปกติ
- `WP_CA_BUNDLE`, `LINE_CA_BUNDLE`: path ของ PEM bundle เมื่อใช้ private CA
- runtime ไม่อนุญาตให้ตั้ง verification เป็น false และปฏิเสธ endpoint ที่ไม่ใช่ HTTPS

### Concurrency

- `INNOVATION_NEWS_FETCH_LOCK_NAME`: ชื่อ MySQL advisory lock ที่ทุก trigger ต้องใช้ร่วมกัน
- `INNOVATION_NEWS_FETCH_LOCK_TIMEOUT_SECONDS=0`: เมื่อมีรอบอื่นอยู่ให้ข้ามทันที
- `INNOVATION_NEWS_FETCH_FILE_LOCK`: local lock file สำหรับป้องกัน process ซ้ำบนเครื่องเดียวกัน

### Source credentials

- ห้ามเก็บ API key, token, userinfo หรือ password ใน `news_sources.source_url`
- URL ของ source ต้องเป็น HTTPS
- News API ใช้ `INNOVATION_NEWS_SOURCE_API_KEY_NEWSAPI` และส่งด้วย header ที่ระบุใน `INNOVATION_NEWS_SOURCE_API_KEY_HEADER_NEWSAPI`
- redirect ของ generic API ถูกปิดเพื่อไม่ให้ custom credential header ไหลไป host อื่น

### Subscription gates

ค่าต่อไปนี้ต้องคงสถานะปิดจนกว่า schema, consent flow และ email delivery จะผ่านการทดสอบ:

```dotenv
ENABLE_SUBSCRIPTION_API=0
ENABLE_EMAIL_WORKER=0
EMAIL_SEND_MODE=disabled
```

ไม่มี endpoint หรือ worker ใดควรตีความ “ไม่มี key” ว่าเปิดใช้งาน
