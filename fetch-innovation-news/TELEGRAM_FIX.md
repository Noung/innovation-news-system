# Telegram Fix (retired)

เอกสารเดิมมีค่า configuration และแนวทาง deploy ที่ไม่ผ่าน Phase 0 safety baseline จึงไม่ควรนำกลับมาใช้

เก็บ Telegram credential ไว้เฉพาะ root `.env`, ไม่พิมพ์ token ลง log และใช้ขั้นตอนใน [Phase 0 rollout](../docs/phase0-rollout.md)
