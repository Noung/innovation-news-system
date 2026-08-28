# SQL Migration Policy

ไดเรกทอรีนี้เป็นตำแหน่ง canonical สำหรับ migration ตั้งแต่ Phase 1 เป็นต้นไป ขณะนี้ยังไม่มี migration ที่อนุญาตให้ apply เพราะ historical artifacts ที่เอกสารเดิมอ้างถึงไม่ได้มากับ local replica

กติกา:

1. ใช้ชื่อ `NNNN_descriptive_name.sql` และเรียงลำดับแบบ append-only
2. แต่ละไฟล์ต้องมี SHA-256 sidecar และห้ามแก้ไฟล์หลัง apply
3. ต้องมี read-only plan แยกจาก explicit apply
4. apply ต้องถือ migration advisory lock และบันทึก version/checksum/time/operator ใน `schema_migrations`
5. ห้ามฝัง secret หรือ environment-specific URL ใน SQL
6. DDL ต้องมี preflight, backup, verification และ rollback/forward-fix ที่ระบุชัด
7. subscription migrations ห้ามถูกเรียกจนกว่า `ENABLE_SUBSCRIPTION_API` และ `ENABLE_EMAIL_WORKER` ยังเป็น `0` ใน rollout environment

ขั้นถัดไปก่อนเพิ่ม `0001`:

- กู้ migration ต้นฉบับที่หาย หรือ export schema-only จาก PROD แบบ read-only
- เปรียบเทียบกับ root `innovation_news.sql` โดยไม่เผยข้อมูลหรือ credential
- ให้ผู้ดูแลรับรอง baseline และ checksum
- จึงสร้าง migration runner และ migration สำหรับ subscription ใน Phase 1
